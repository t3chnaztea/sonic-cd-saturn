#!/usr/bin/env python3
"""Stardust Speedway (R7) and Metallic Madness (R8) scroll programs from the retail MMDs -> src/background_r7_tables.inc.

    python3 tools/background_r7_assets.py            parse, write the include
    python3 tools/background_r7_assets.py --check    fail if the include is stale

Retail scroll() builds hscrollwork ($FFA800) between `lea $a800.w,a1` and
`lea $cc00.w,a1` from two statement shapes, matched byte for byte:

  fill   move.w layer.w,d0 : neg.w d0 : moveq #n-1,d6 : move.w d0,(a1)+ : dbra
  chain  bsr.w to  move.w A.w,d0 : move.w B.w,d2 : sub.w d0,d2 : ext.l d2 :
         moveq #s1,d1 : asl.l d1,d2 : divu.w #D,d2 : ext.l d2 : moveq #s2,d1 :
         asl.l d1,d2 : move.w A.w,d3 : [swap d3 : add.l d2,d3 : swap d3] :
         moveq #n-1,d6 : [adda.w #span,a1] : loop { write -d3.w counts[d6]+1
         times ((a1)+ or -(a1)) ; swap d3 : add.l d2,d3 : swap d3 } : [adda.w #span,a1] : rts

A/B are $F700 camera, $F708 scrb, $F710 scrc, $F718 scrz.  d3's high word
(radwk's fraction) is never initialised: the first chain inherits the high word
of scroll()'s hz*32 (the scrb step), each later chain the fraction the one
before it left.  divu.w leaves the dividend when the quotient overflows.  The
line writer copies one hscrollwork word per 8 lines with -camera X in the high
word; R71B/R72B switch rows whose first line is at or past the parsed
threshold to a per-line wave: -(scrz + (u16)sin((waterdirec>>8) + 2k) >> 5).
The decompiled SCR7*.C differs (hsw high word 0, scrc - camera in z71aline1,
signed divides, zeroed fractions); retail captures are the authority
(tools/test_r7_scroll.py).
"""
import argparse
import json
import re
import struct
from fractions import Fraction
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from extract_mmd import disc_files  # noqa: E402
from retail_span import disc_span  # noqa: E402

OUT = ROOT/'src/background_r7_tables.inc'
IR = ROOT/'tools/scroll/R7/ir'
PROGRAMS = {0: '1A', 1: '1B', 2: '1C', 3: '1D', 4: '2A', 5: '2B', 6: '2C', 7: '2D', 10: '3C', 11: '3D'}
LAYER = {0xf700: 0, 0xf708: 1, 0xf710: 2, 0xf718: 3}
START = disc_span('R71B__.MMD',0x2956,8,'6ca0271cb21718db3971c1cb151a1969726671de88bba5a40b909e8ddab9291b')          # clr.b $f758.w ; lea $a800.w,a1
END = bytes.fromhex('43f8cc00')                    # lea $cc00.w,a1
CAMERA_HIGH = disc_span('R71B__.MMD',0x295e,8,'6c10c7e7f87384364e228b9d22d79f758d0624a090558863b25ba8bdaa550cce')
FILL = re.compile(rb'\x30\x38(..)\x44\x40\x7c(.)\x32\xc0\x51\xce\xff\xfc', re.S)
BSR = re.compile(rb'\x61\x00(..)', re.S)
CHAIN = re.compile(rb'\x30\x38(?P<A>..)\x34\x38(?P<B>..)(?P<dbl>\xd4\x42)?\x94\x40\x48\xc2\x72(?P<s1>.)\xe3\xa2'
                   rb'\x84\xfc(?P<D>..)\x48\xc2\x72(?P<s2>.)\xe3\xa2'
                   rb'\x36\x38(?P<A2>..)(?P<pre>\x48\x43\xd6\x82\x48\x43)?\x7c(?P<n>.)(?:\xd2\xfc(?P<span>..))?'
                   rb'\x30\x03\x44\x40\x7a\x00\x1a\x3b\x60(?P<disp>.)(?P<dir>\x33\x00|\x32\xc0)\x51\xcd\xff\xfc'
                   rb'\x48\x43\xd6\x82\x48\x43\x51\xce..(?:\xd2\xfc(?P<span2>..))?\x4e\x75', re.S)
WAVE_RE = re.compile(rb'\x0c\x44(..)\x64.', re.S)
# R82x: the difference/divide moved to a helper that divides by d6
CHAIN2 = re.compile(rb'\x30\x38(?P<A>..)\x34\x38(?P<B>..)\x7c(?P<D>.)\x61\x00(?P<div>..)'
                    rb'\x36\x38(?P<A2>..)(?P<pre>\x48\x43\xd6\x82\x48\x43)?\x7c(?P<n>.)(?:\xd2\xfc(?P<span>..))?'
                    rb'\x30\x03\x44\x40\x7a\x00\x1a\x3b\x60(?P<disp>.)(?P<dir>\x33\x00|\x32\xc0)\x51\xcd\xff\xfc'
                    rb'\x48\x43\xd6\x82\x48\x43\x51\xce..(?:\xd2\xfc(?P<span2>..))?\x4e\x75', re.S)
DIVIDE = re.compile(rb'\x94\x40\x48\xc2\x72(?P<s1>.)\xe3\xa2\x84\xc6\x48\xc2\x72(?P<s2>.)\xe3\xa2\x4e\x75', re.S)
# R82A/D: the whole difference/divide (with A/B/D) is a helper; the chain
# routine calls it, then loads A into d3 (span before n here)
CHAIN4 = re.compile(rb'\x61\x00(?P<div>..)\x36\x38(?P<A2>..)(?:\xd2\xfc(?P<span>..))?\x7c(?P<n>.)'
                    rb'\x30\x03\x44\x40\x7a\x00\x1a\x3b\x60(?P<disp>.)(?P<dir>\x33\x00|\x32\xc0)\x51\xcd\xff\xfc'
                    rb'\x48\x43\xd6\x82\x48\x43\x51\xce..(?:\xd2\xfc(?P<span2>..))?\x4e\x75', re.S)
DIVIDE4 = re.compile(rb'\x30\x38(?P<A>..)\x34\x38(?P<B>..)\x94\x40\x48\xc2\x72(?P<s1>.)\xe3\xa2'
                     rb'\x84\xfc(?P<D>..)\x48\xc2\x72(?P<s2>.)\xe3\xa2\x4e\x75', re.S)
# R81x: the caller passes counts (lea table.l,a2), the span (moveq,d4) and n-1 (moveq,d6)
CALL3 = re.compile(rb'\x45\xf9(?P<table>....)\x78(?P<span>.)\x7c(?P<n>.)\x61\x00(?P<disp>..)', re.S)
CHAIN3 = re.compile(rb'\x30\x38(?P<A>..)\x34\x38(?P<B>..)\x94\x40\x48\xc2\x72(?P<s1>.)\xe3\xa2'
                    rb'\x84\xfc(?P<D>..)\x48\xc2\x72(?P<s2>.)\xe3\xa2\x36\x38(?P<A2>..)\xd2\xc4'
                    rb'\x30\x03\x44\x40\x7a\x00\x1a\x32\x60\x00\x33\x00\x51\xcd\xff\xfc'
                    rb'\x48\x43\xd6\x82\x48\x43\x51\xce..\xd2\xc4\x4e\x75', re.S)


def word(b):
    return struct.unpack('>H', b)[0]


def parse(prog):
    a = prog.index(START)+4
    b = prog.index(END, a)
    body = prog[a+4:b]
    assert body.startswith(CAMERA_HIGH), body[:8].hex()
    at, ops = len(CAMERA_HIGH), []
    while at < len(body):
        f = FILL.match(body, at)
        if f:
            ops.append(('fill', LAYER[word(f[1])], f[2][0]+1))
            at = f.end()
            continue
        k = CALL3.match(body, at)
        if k:
            target = a+4+k.start('disp')+struct.unpack('>h', k['disp'])[0]  # bsr.w: PC = the displacement's address
            c = CHAIN3.match(prog, target)
            assert c, prog[target:target+48].hex()
            n = k['n'][0]+1
            table = struct.unpack('>I', k['table'])[0]-0x200000
            assert word(c['A2']) == word(c['A'])
            ops.append(('chain', LAYER[word(c['A'])], LAYER[word(c['B'])], c['s1'][0], word(c['D']), c['s2'][0], 0, n,
                        k['span'][0]//2, list(prog[table:table+n]), 0))
            at = k.end()
            continue
        m = BSR.match(body, at)
        assert m, body[at:at+8].hex()
        target = a+4+at+2+struct.unpack('>h', m[1])[0]
        c = CHAIN.match(prog, target)
        c4 = None if c else CHAIN4.match(prog, target)
        if c4:
            d = DIVIDE4.match(prog, c4.start('div')+struct.unpack('>h', c4['div'])[0])
            assert d, 'divide helper (R82A/D)'
            c = dict(c4.groupdict(), A=d['A'], B=d['B'], s1=d['s1'], s2=d['s2'], D=d['D'], dbl=None, pre=None,
                     _disp_at=c4.start('disp'))
        elif not c:
            c = CHAIN2.match(prog, target)
            assert c, prog[target:target+48].hex()
            d = DIVIDE.match(prog, c.start('div')+struct.unpack('>h', c['div'])[0])
            assert d, 'divide helper'
            c = dict(c.groupdict(), s1=d['s1'], s2=d['s2'], D=b'\x00'+c['D'], dbl=None,
                     _disp_at=c.start('disp'))
        else:
            c = dict(c.groupdict(), _disp_at=c.start('disp'))
        A, B = LAYER[word(c['A'])], LAYER[word(c['B'])]
        assert word(c['A2']) == word(c['A'])
        n = c['n'][0]+1
        span = word(c['span']) if c['span'] else 0
        assert (c['span2'] is None) == (c['span'] is None) and (not span or word(c['span2']) == span)
        backward = c['dir'] == b'\x33\x00'
        assert backward == bool(span)
        # move.b d8(pc,d6.w),d5: the extension word sits at the move's address + 2
        table = c['_disp_at']-1+struct.unpack('>b', c['disp'])[0]
        counts = list(prog[table:table+n])
        # dbl: add.w d2,d2 before the subtract (difference 2*B - A)
        ops.append(('chain', A, B, c['s1'][0], word(c['D']), c['s2'][0], int(bool(c['pre'])), n, span//2, counts, int(bool(c['dbl']))))
        at = m.end()
    # R71B/R72B: addi.w #$80,waterdirec.w then a line writer with cmpi.w #threshold,d4
    if prog[b:b+0x40].find(bytes.fromhex('06780080f7d8')) < 0:
        return ops, 0
    wave = WAVE_RE.search(prog, b, b+0x200)
    assert wave, 'wave line writer'
    return ops, word(wave[1])


# scroll()'s layer steps: move.w scra_hz,d4 : ext.l d4 : asl.l #k,d4 :
# [move.l d4,d3 : add.l d3,d3 (m times) : add.l d3,d4] : moveq #flag,d6 : bsr
# (flag 2 scrb, 4 scrc, 6 scrz).  d3 ends as hz*M for the last step that uses it;
# its high word is the first chain's fraction.
STEP = re.compile(rb'\x38\x38\xf7\x3a\x48\xc4(?P<asl>[\xe1-\xef]\x84)(?P<m3>\x26\x04(?:\xd6\x83|\xd6\x84|[\xe0-\xef]\x83)+\xd8\x83)?\x7c(?P<f>[\x02\x04\x06])\x61\x00', re.S)


def steps(prog):
    a = prog.index(START)
    rates, frac = [0, 0, 0], None
    for m in STEP.finditer(prog, a-0x100, a):
        k = (m['asl'][0] >> 1 & 7) or 8
        rate = 1 << k
        if m['m3']:
            # move.l d4,d3 : {add.l d3,d3 | add.l d4,d3 | asl.l/asr.l #n,d3} : add.l d3,d4
            c = Fraction(1)
            for i in range(2, len(m['m3'])-2, 2):
                w = m['m3'][i:i+2]
                n = (w[0] >> 1 & 7) or 8
                c = c*2 if w == b'\xd6\x83' else c+1 if w == b'\xd6\x84' else c*(1 << n) if w[0] & 1 else c/(1 << n)
            mul = (1 << k)*c
            assert mul.denominator == 1
            rate += int(mul)
            frac = int(mul)   # d3 = hz * frac
        rates[m['f'][0]//2-1] = rate
    assert frac is not None
    return rates, frac


R8_INIT = {  # PC SCR8*.C scrbinit(x, y) horizontal words as (mul, shift mask, K) per scrb/scrc/scrz
    'sXpos = (unsigned short)sXpos >> 1; scrc_h_posit.w.h = sXpos; sXpos = (unsigned short)sXpos >> 1; '
    'scrz_h_posit.w.h = sXpos; sXpos = (unsigned short)sXpos >> 2; scrb_h_posit.w.h = sXpos * 3;': [(3, 16, 0), (1, 2, 0), (1, 4, 0)],
    'sXpos = (unsigned short)sXpos >> 1; scrc_h_posit.w.h = sXpos; scrz_h_posit.w.h = sXpos + 112; '
    'sXpos = (unsigned short)sXpos >> 2; scrb_h_posit.w.h = sXpos * 3;': [(3, 8, 0), (1, 2, 0), (1, 2, 112)],
    'scrc_h_posit.w.h = sXpos + 112; sXpos = (unsigned short)sXpos >> 2; scrz_h_posit.w.h = sXpos * 3 + 112; '
    'sXpos = (unsigned short)sXpos * 2; scrb_h_posit.w.h = sXpos + 112;': [(2, 4, 112), (1, 1, 112), (3, 4, 112)],
}


def program(files, rnd, p, pid, text):
    name = f'R{rnd}{p}'
    prog = files[name+'__.MMD']
    ops, wave = parse(prog)
    doc = json.loads((ROOT/f'tools/scroll/R{rnd}/ir/SCR{rnd}{p}.json').read_text())
    rates, frac = steps(prog)
    ir_rates = [doc['layers'].get(k, {'C': 0})['C'] for k in ('scrb_h_posit', 'scrc_h_posit', 'scrz_h_posit')]
    assert all(r == i or not i for r, i in zip(rates, ir_rates)), (name, rates, ir_rates)
    g = doc['bg_y']
    src = (ROOT/f'build/audit/source/src/R{rnd}/SCR{rnd}{p}.C').read_text()
    if rnd == 7:
        # DEV7x are stubs: every R7 UpdateAnimTiles is a bare jmp (no animated tiles)
        from extract_zone_auto import ANIM_INIT_CALL
        ents = {struct.unpack('>I', m[1])[0] for m in ANIM_INIT_CALL.finditer(prog)}
        assert len(ents) == 1 and prog[ents.pop()-0x200000:][:2] == b'\x4e\xf9', f'{name} animates tiles'
        # scrbinit (PC SCR7*.C): each layer word = mul * sum(x >> k)
        init = []
        body = re.search(r'void scrbinit\(short yWk, short xWk\) \{(.*?)\n\}', src, re.S)[1]
        for layer in ('scrb', 'scrc', 'scrz'):
            e = re.search(layer+r'_h_posit\.w\.h = \(unsigned short\)\((.*?)\);', body)[1]
            shifts = [int(k) for k in re.findall(r'xWk >> (\d)', e)]
            mul = 3 if e.replace(' ', '').endswith('*3') else 1
            assert re.fullmatch(r'\(?xWk>>\d\)?(\+\(xWk>>\d\))*(\*3)?', e.replace(' ', '')), e
            init.append((mul, sum(1 << k for k in shifts), 0))
        bgy = (g['shifts'][0], g['shifts'][1]) if g['op'] == 'shifts' else (0, 0)
    else:
        body = re.search(r'void scrbinit\(short sXpos, short sYpos\) \{(.*?)\n\}', src, re.S)[1]
        lines = ' '.join(l.strip() for l in re.sub(r'/\*.*?\*/', '', body).splitlines() if 'sXpos' in l or 'h_posit' in l)
        init = R8_INIT[lines]
        assert g['op'] == 'shift' and len(g['k']) == 1, g
        bgy = (g['k'][0], 16)   # (y >> k) + (y >> 16): one shift
    wm = re.search(r'z81awrttbl\[(\d+)\]\s*=\s*\{(.*?)\}', src, re.S)
    # SCR71C/72C/73C declare the table without an initialiser: all rows static
    wrt = [int(v) for v in re.findall(r'\d+', re.sub(r'/\*.*?\*/', '', wm[2]))] if wm else [0]*65
    assert wm or re.search(r'static unsigned char z81awrttbl\[\d+\];', src), name
    assert len(wrt) == (int(wm[1]) if wm else 65) and set(wrt) <= {0, 2, 4, 6}, name
    wrt = (wrt+[wrt[-1]]*65)[:65]   # rows past the table repeat its last entry (never on screen)
    text.append(f'static const uint8_t r78_wrttbl_{pid}[65] = {{{",".join(map(str, wrt))}}};')
    rows = []
    for op in ops:
        if op[0] == 'fill':
            rows.append('{0,%d,0,0,0,0,0,%d,0,0}' % (op[1], op[2]))
        else:
            _, A, B, s1, D, s2, pre, n, span, counts, dbl = op
            text.append(f'static const uint8_t r78_counts_{pid}_{len(rows)}[{n}] = {{{",".join(map(str, counts))}}};')
            rows.append('{%d,%d,%d,%d,%d,%d,%d,%d,%d,r78_counts_%d_%d}' % (1+dbl, A, B, s1, D, s2, pre, n, span, pid, len(rows)))
    text.append(f'static const r7_op r78_ops_{pid}[{len(rows)}] = {{{",".join(rows)}}};')
    meta = (f'{{"{name}",{len(rows)},r78_ops_{pid},{{{",".join(map(str, rates))}}},'
            f'{{{",".join("{%d,%d,%d}" % i for i in init)}}},{bgy[0]},{bgy[1]},{wave},r78_wrttbl_{pid},{frac}}}')
    return meta, dict(ops=[list(o) for o in ops], wave=wave, rates=rates, bg_y=g)


def build():
    files = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    text = ['/* Generated by tools/background_r7_assets.py from the retail R71A-R73D and R81A-R83D scroll().  Do not edit. */']
    meta, report = [], {}
    for rnd in (7, 8):
        for pid in range(12):
            p = PROGRAMS.get(pid)
            if not p:
                meta.append('{0}')
                continue
            m, report[f'R{rnd}{p}'] = program(files, rnd, p, pid+12*(rnd-7), text)
            meta.append(m)
    # CalcSine ($200710): 256*sin truncated toward zero, with two entries retail stores 2 lower
    import math
    sine = [int(256*math.sin(2*math.pi*i/256)) for i in range(256)]
    sine[147] = sine[237] = -117
    retail = struct.unpack('>256h', files['R71B__.MMD'][0x728:0x728+512])
    assert list(retail) == sine and files['R71B__.MMD'][0x710:0x728] == disc_span('R71B__.MMD',0x710,24,'b4e3dfd37237376d2b0c2ce6eea6898bfceefeb62e094a1f84401e1a655abc5e')
    text.append(f'static const int16_t r78_sine[256] = {{{",".join(map(str, sine))}}};')
    text.append(f'/* ids 0-11 Stardust Speedway, 12-23 Metallic Madness (act*4+era) */')
    text.append(f'static const r7_program r78_programs[24] = {{{",".join(meta)}}};')
    return '\n'.join(text)+'\n', report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--show', action='store_true')
    args = ap.parse_args()
    text, report = build()
    if args.show:
        for k, v in report.items():
            print(k, v)
    if args.check:
        if OUT.read_text() != text:
            sys.exit(f'FAIL: {OUT.relative_to(ROOT)} is stale; run tools/background_r7_assets.py')
        print(f'PASS: {OUT.relative_to(ROOT)} matches the retail R7/R8 scroll() code')
        return
    OUT.write_text(text)
    print('wrote', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
