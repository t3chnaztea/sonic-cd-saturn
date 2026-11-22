#!/usr/bin/env python3
"""Wacky Workbench animated tiles from the retail R61A-R63D MMDs -> assets/generated/ww_terrain.inc.

    python3 tools/ww_terrain_assets.py           parse the routines, write the include
    python3 tools/ww_terrain_assets.py --check   re-parse and fail if the include differs

Each retail UpdateAnimTiles routine (found through extract_zone_auto.ANIM_INIT_CALL)
starts `jsr helper; lea timers.w,a2; lea frames.w,a4` and then runs two or three
calls of the shape

    lea record.l,a1 : move.w #longs-1,d6 : bsr.w routine : bne.b skip : LVLDMA buffer -> cell

where routine is one of two helpers (both advance a2/a4 by one slot):
  const   subq.b #1,(a2) : bpl.w : move.b (a1),(a2)          record = tim, frames, ptr[frames]
  script  subq.b #1,(a2) : bpl.b : ... move.b 2(a1,d0),(a2)  record = count, 0, (tim,no)[count], ptr[]
Two programs add a gate and two a boss hook, matched byte for byte:
  toggle  (R61C/R62C) before call 1: subq.b #1,tim2 : bmi : bra ; eori.b #1,frame2 ;
          move.b table(pc,frame2),tim2 ; tst.b frame2 : beq off   (table 90,30); off
          (past the rts) DMAs a zeroed buffer over call 1's block every update
  boss    (R63C/R63D) call 0 fired: bclr #6,bossflag : bne -> bset #7 and DMA-fill the
          block with 0 ; else btst #7 : beq -> normal DMA ; else DMA to an unused cell.
The art pointers address the MMD itself (loaded at 0x200000).  The PC DEV6x.C
differs (tbl_sp timer 2 against retail 3, tbl_null writes where retail skips);
retail is the authority and tools/test_ww_terrain.py checks it against the
retail VRAM.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from extract_mmd import disc_files  # noqa: E402
from retail_span import disc_span  # noqa: E402
from extract_zone_auto import ANIM_INIT_CALL  # noqa: E402

ORIGIN = 0x200000
OUT = ROOT/'assets/generated/ww_terrain.inc'
BUILD = ROOT/'build/ww/terrain'
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']
HEAD = re.compile(rb'\x4e\xb9....\x45\xf8(..)\x49\xf8(..)', re.S)
CALL = re.compile(rb'\x43\xf9(....)\x3c\x3c(..)\x61\x00(..)\x66(.)', re.S)
DMA = re.compile(rb'\x4b\xf9\x00\xc0\x00\x04\x2a\xbc\x94.\x93.\x2a\xbc\x96\x8c\x95\xc0\x3a\xbc\x97\x7f'
                 rb'\x3a\xbc(..)\x31\xfc\x00(.)\xf6\x40\x3a\xb8\xf6\x40', re.S)
CONST = bytes.fromhex('53126a00')        # subq.b #1,(a2) ; bpl.w
SCRIPT = bytes.fromhex('53126a42')       # subq.b #1,(a2) ; bpl.b
TOGGLE = re.compile(rb'\x53\x38\xf6\x6e\x6b\x02\x60\x12\x0a\x38\x00\x01\xf6\x68\x10\x38\xf6\x68\x48\x80'
                    rb'\x11\xfb\x00\x0c\xf6\x6e\x4a\x38\xf6\x68\x67(.)\x60\x02(.)(.)', re.S)
BOSS = bytes.fromhex('08b80006f7a7')      # bclr.b #6,bossflag.w


def cell(word, high):
    return (struct.unpack('>H', word)[0] & 0x3fff | (high & 3) << 14)//32


def parse(prog):
    ents = {struct.unpack('>I', m[1])[0] for m in ANIM_INIT_CALL.finditer(prog)}
    assert len(ents) == 1, ents
    at = ents.pop()-ORIGIN
    if prog[at:at+2] == b'\x4e\xf9':   # bare jmp: the program animates no tiles
        return [], None
    head = HEAD.match(prog, at)
    assert head and head[1] == b'\xf6\x6c' and head[2] == b'\xf6\x66', prog[at:at+16].hex()
    end = prog.index(b'\x4e\x75', head.end())   # the routine's rts
    code = prog[head.end():end]
    calls, gate = [], None
    for m in CALL.finditer(code):
        rec = struct.unpack('>I', m[1])[0]-ORIGIN
        longs = struct.unpack('>H', m[2])[0]+1
        target = head.end()+m.start()+12+struct.unpack('>h', m[3])[0]  # bsr.w: PC = its address + 2
        kind = {CONST: 'const', SCRIPT: 'script'}[prog[target:target+4]]
        after = code[m.end()+(2 if m[4] == b'\x00' else 0):m.end()+200]   # bne.w carries a word
        if after.startswith(BOSS):
            # bit 7 set: DMA to an unused cell (first); bit 6 event: fill; else
            # the block's own cell (last before the next call).
            gate = 'boss'
            window = after[:CALL.search(after).start()] if CALL.search(after) else after
            dmas = list(DMA.finditer(window))
            dma = dmas[-1]
            # the DMA fill (autoinc 1, 0x100 bytes of 0) targets the same cell
            fill = disc_span('R63C__.MMD',0xe43c,16,'fb9e4a871f44cb270148689bb81bedcdb56d10b9248566223255ea2365649a11')+dma[1]+b'\x00'+dma[2]
            assert len(dmas) == 2 and fill in window, window.hex()
        else:
            dma = DMA.match(after)
        assert dma, after[:40].hex()
        if kind == 'const':
            tim, frames = prog[rec], prog[rec+1]
            ptrs = struct.unpack(f'>{frames}I', prog[rec+2:rec+2+4*frames])
            pairs = []
        else:
            count = prog[rec]
            assert prog[rec+1] == 0
            pairs = list(prog[rec+2:rec+2+2*count])
            frames = max(pairs[1::2])+1
            ptrs = struct.unpack(f'>{frames}I', prog[rec+2+2*count:rec+2+2*count+4*frames])
            tim = 0
        art = [prog[p-ORIGIN:p-ORIGIN+longs*4] for p in ptrs]
        calls.append(dict(kind=kind, tim=tim, pairs=pairs, frames=len(ptrs), longs=longs,
                          cell=cell(dma[1], dma[2][0]), art=art, at=head.end()+m.start()))
    tog = TOGGLE.search(code)
    if tog:
        gate = 'toggle'
        assert (tog[2][0], tog[3][0]) == (90, 30), tog.groups()
        assert calls[0]['at']-head.end() < tog.start() < calls[1]['at']-head.end(), 'toggle gates call 1'
        # frame2 == 0 branches past the rts: zero the buffer and DMA it over call 1's block
        off = head.end()+tog.end()-6+2+tog[1][0]   # beq.b at end-6; PC = its address + 2
        clear = disc_span('R61C__.MMD',0xfd04,20,'6d24ae07359f2ff2f90af7b94acb6ee63adf4be7bc7ce44f5f8f3a83f3275aac')
        assert prog[off:off+len(clear)] == clear, prog[off:off+24].hex()
        dma = DMA.match(prog, off+len(clear))
        assert dma and cell(dma[1], dma[2][0]) == calls[1]['cell'] and calls[1]['longs'] == 64, 'gate-off clear'
    return calls, gate


def build(rnd=6, pre='ww', maxcalls=3):
    files = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    text = [f'/* Generated by tools/ww_terrain_assets.py from the retail R{rnd}1A-R{rnd}3D UpdateAnimTiles routines;',
            '   art is retail data (assets/generated, never under src/).  Do not edit. */']
    progs, report = [], {}
    for p in PROGRAMS:
        name = f'R{rnd}{p}'
        calls, gate = parse(files[name+'__.MMD'])
        assert len(calls) <= maxcalls, (name, len(calls))
        pid = (int(p[0])-1)*4+'ABCD'.index(p[1])
        body = []
        for n, c in enumerate(calls):
            tag = f'{pre}{pid}_{n}'
            text.append(f'static const uint8_t {tag}_art[{c["frames"]}][{c["longs"]*4}] = {{' +
                        ','.join('{'+','.join(map(str, a))+'}' for a in c['art'])+'};')
            pairs = c['pairs'] or [0, 0]
            text.append(f'static const uint8_t {tag}_pairs[{len(pairs)}] = {{{",".join(map(str, pairs))}}};')
            body.append(f'{{{int(c["kind"] == "script")},{c["tim"]},{len(c["pairs"])//2},{c["frames"]},'
                        f'{c["longs"]//8},{c["cell"]},{tag}_pairs,&{tag}_art[0][0]}}')
        g = {'toggle': 1, 'boss': 2}.get(gate, 0)
        progs.append((pid, f'{{{len(calls)},{g},{{{",".join(body)}}}}}'))
        report[name] = dict(gate=gate, calls=[{k: v for k, v in c.items() if k not in ('art', 'at')} |
                                             dict(art=[hashlib.sha256(a).hexdigest()[:16] for a in c['art']]) for c in calls])
    table = ['{0}']*12
    for pid, s in progs:
        table[pid] = s
    text.insert(2, f'typedef struct {{ uint8_t script, tim, count, frames, tiles; uint16_t cell; const uint8_t *pairs, *art; }} {pre}_anim_call;')
    text.insert(3, f'typedef struct {{ uint8_t calls, gate; {pre}_anim_call call[{maxcalls}]; }} {pre}_anim_program;  /* gate 1 toggle, 2 boss */')
    text.append(f'static const {pre}_anim_program {pre}_anim[12] = {{'+','.join(table)+'};')
    return '\n'.join(text)+'\n', report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    text, report = build()
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD/'assets.json').write_text(json.dumps(report, indent=1)+'\n')
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            sys.exit(f'FAIL: {OUT.relative_to(ROOT)} differs from the retail routines')
        print(f'PASS: WW animated tiles: {len(report)} retail UpdateAnimTiles routines parsed, include current')
        return
    OUT.write_text(text)
    print('wrote', OUT.relative_to(ROOT))
    for k, v in report.items():
        print(k, v['gate'], [(c['kind'], c['tim'], c['pairs'], c['frames'], c['longs'], c['cell']) for c in v['calls']])


if __name__ == '__main__':
    main()
