#!/usr/bin/env python3
"""Compile Quartz Quadrant (R5) background data into src/background_r5_tables.inc
and src/background_r5_palette.inc.

    python3 tools/background_r5_assets.py            write both includes
    python3 tools/background_r5_assets.py --check    fail if either is stale

Scroll: the checked scroll IR (tools/scroll/R5/ir, scroll-ir/1+r5; proved by
tools/scroll/R5/check_r5.py) gives each program's table rows and background Y
per enkeino variant.  The source files give what the IR leaves to the port:
layer rates (scroll(): scrollb/c/z_h(scra_hz * C)), scrbinit()'s layer reset,
enkeichg()'s player X thresholds, the render kind (zonescrsetsub0 only, or
SCR51D/53D's tail ramp) and z81awrttbl/z81awrttbl2 (plane row layers).
Program ids are act*4+era (0-3 SCR51A-D, 4-7 SCR52A-D, 10-11 SCR53C-D).

Palette: COL5A-D.C clchgctr() scripts (color_change_data {adr, tate, yoko,
time, colortbl}) and zone5color0/1 (colorset2(4)/(5), entries 16-63).  Every
script and table must appear byte-identical in a retail MMD that links it.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
IR = ROOT/'tools/scroll/R5/ir'
SOURCE = ROOT/'build/audit/source/src/R5'
TABLES = ROOT/'src/background_r5_tables.inc'
PALETTE = ROOT/'src/background_r5_palette.inc'
PROGRAMS = {0: 'SCR51A', 1: 'SCR51B', 2: 'SCR51C', 3: 'SCR51D', 4: 'SCR52A', 5: 'SCR52B', 6: 'SCR52C',
            7: 'SCR52D', 10: 'SCR53C', 11: 'SCR53D'}
LAYERS = ['camera', 'scrb_h_posit', 'scrc_h_posit', 'scrz_h_posit']
# Retail MMD per COL5 letter (each era links its own COL5x.C).
COL_MMD = {'A': 'R51A__.MMD', 'B': 'R51B__.MMD', 'C': 'R51C__.MMD', 'D': 'R51D__.MMD'}


def function(src, name):
    m = re.search(r'\n(?:static )?[\w*]+ ' + name + r'\([^;{]*\)\s*\{', src)
    assert m, name
    depth, end = 1, m.end()
    while depth:
        depth += (src[end] == '{')-(src[end] == '}')
        end += 1
    return re.sub(r'/\*.*?\*/', '', src[m.start():end], flags=re.S)


class Lin:
    """sum m*(u16(x) >> s): enough for scrbinit's shifts, adds and small products."""
    def __init__(self, terms):
        self.t = dict(terms)

    def __rshift__(self, n):
        assert len(self.t) == 1 and list(self.t.values()) == [1], self.t
        (s, _), = self.t.items()
        return Lin({s+n: 1})

    def __add__(self, o):
        t = dict(self.t)
        for s, m in o.t.items():
            t[s] = t.get(s, 0)+m
        return Lin(t)

    def __mul__(self, k):
        return Lin({s: m*k for s, m in self.t.items()})


def scrbinit(src):
    body = function(src, 'scrbinit')
    env = {'sXpos': Lin({0: 1})}
    out = {}
    for stmt in re.findall(r'(?<![\w.])(\w+(?:\.\w+)*)\s*(=|>>=)\s*([^;]*);', body):
        lhs, op, rhs = stmt
        if lhs.startswith('lYwk') or '_v_' in lhs:
            continue
        rhs = re.sub(r'\((?:unsigned short|short)\)', '', rhs)
        val = eval(rhs, {}, env) if op == '=' else env[lhs] >> int(rhs)
        if lhs.endswith('.w.h'):
            out[lhs.split('_')[0]] = val
        else:
            env[lhs] = val
    assert set(out) == {'scrb', 'scrc', 'scrz'}, out
    return [sorted(out[k].t.items()) for k in ('scrb', 'scrc', 'scrz')]


def rates(src):
    body = function(src, 'scroll')
    found = {}
    for m in re.finditer(r'lXwk = scra_hz((?: \* \d+)+);\s*(?:lXwk \+= lXwk \* (\d+);\s*)?scroll([bcz])_h\(lXwk', body):
        v = 1
        for f in re.findall(r'\d+', m[1]):
            v *= int(f)
        if m[2]:
            v *= 1+int(m[2])
        found[m[3]] = v
    assert set(found) == set('bcz'), found
    return [found[k] for k in 'bcz']


def enkei(src):
    if 'void enkeichg' not in src:
        return (0, 0)
    body = function(src, 'enkeichg')
    tbl = [int(v) for v in re.findall(r'-?\d+', re.search(r'short tbl\[\d+\] = \{(.*?)\}', body, re.S)[1])]
    first = tbl[:tbl.index(-1)]
    assert len(first) == 2 and 'if (actwk[0].xposi.w.h <= poswk) break;' in body
    assert re.search(r'colorset2\(\(tbl0\[EnkeiNo\] >> 2\) \+ 4\)', body)
    assert re.search(r'char tbl0\[3\] = \{\s*2, 4, 2\s*\}', body)
    return tuple(first)


def wrttbl(src, name):
    m = re.search(r'unsigned char ' + name + r'\[(\d+)\](\s*=\s*\{(.*?)\})?;', src, re.S)
    if not m:
        return None
    n = int(m[1])
    values = [int(v) for v in re.findall(r'\d+', m[3])] if m[2] else [0]*n
    assert len(values) == n
    # scrollwrtb reads index (y/16)&127 + 1; past the table it reads the next
    # BSS object, which is zero-filled (z81awrttbl2 / nothing written).
    return values+[0]*(129-n)


def render_kind(src, name):
    body = function(src, 'scroll')
    tail = bool(re.search(r'for \(sYnumsv = (?:sYnumsv \* 8|\(sYnumsv << 3\)) - 1; sYnumsv >= 0; --sYnumsv\)', body))
    tail53 = 'for (sYnumsv = (sYnumsv >> 3) - 1; sYnumsv >= 0; --sYnumsv)' in body
    if not (tail or tail53):
        assert 'zonescrsetsub0(scrb_v_posit.w.h, 28, &pHscrbuf, psHscr);' in body, name
        return 0
    assert 'sYline = 39;' in body and 'sYnumsv = 29;' in body, name
    return 1 if tail else 2


ADDR = {0xf700: 'camera', 0xf708: 'scrb_h_posit', 0xf710: 'scrc_h_posit', 0xf718: 'scrz_h_posit'}
BUILDER = re.compile(rb'\x30\x38\xf7([\x00-\xff])\x34\x38\xf7([\x00-\xff])\x94\x40\x48\xc2\x72([\x00-\x0f])\xe3\xa2'
                     rb'\x84\xfc([\x00-\xff]{2})\x48\xc2\x72([\x00-\x0f])\xe3\xa2\x36\x38\xf7([\x00-\xff])\x7c([\x00-\x7f])', re.S)


def builders(mmd):
    """68k line builders in a retail program, in call (bsr) order.  Each is
    d2 = ext.l(to.w - from.w) << a; divu.w #div,d2; ext.l d2; asl.l #b,d2;
    d3.w = from.w; then G groups hi(d3 swapped + k*d2): the quotient is the
    signed low word (the dividend's when divu overflows) and the accumulator's
    fraction is d3's high word on entry, carried from builder to builder."""
    found = {}
    for m in BUILDER.finditer(mmd):
        f, t, a, div, b, f2, g = m.groups()
        f, t, f2 = 0xf700 | f[0], 0xf700 | t[0], 0xf700 | f2[0]
        assert f == f2
        found[0x200000+m.start()] = dict(frm=ADDR[f], to=ADDR[t], mul=1 << a[0],
                                         div=struct.unpack('>H', div)[0], scale=1 << b[0], G=g[0]+1)
    calls = []
    for m in re.finditer(rb'\x61\x00([\x00-\xff]{2})', mmd):
        target = 0x200000+m.start()+2+struct.unpack('>h', m[1])[0]
        if target in found:
            calls.append((m.start(), found[target]))
    return [b for _, b in sorted(calls)]


def row_code(expr):
    if expr['op'] == 'layer':
        return (1, LAYERS.index(expr['layer']), 0, 0, 1, 0)
    assert expr['op'] == 'interp', expr
    return (2, LAYERS.index(expr['from']), LAYERS.index(expr['to']), expr['mul'], expr['div'], expr['k'])


def body(doc, v, kind, rate):
    assert not v.get('ramp_gate') and v['beyond_table'] == 'unwritten'
    for name, L in v['layers'].items():
        assert L['U'] == 0 and L['C'] == rate[LAYERS.index(name)-1], (doc['program'], name, L, rate)
    rows = []
    for run in v['runs']:
        rows += [row_code(run['expr'])]*run['entries']
    assert len(rows)*8 == v['table_end'], doc['program']
    for c in v.get('corrections') or []:
        if c['rule'] == 'PASTBUF':
            assert c['first_row'] == len(rows)
            for run in c['runs_past_buffer']:
                rows += [row_code(run['expr'])]*run['entries']
        else:
            assert c['rule'] == 'TAILFIT' and kind == 2, c
    tail = 0
    if v['bands']:
        (b,) = v['bands']
        assert b['tail'] and b['start'] == v['table_end'] == 320 and b['expr']['op'] == 'ramp' and kind, b
        e = b['expr']
        assert (e['to'], e['D'], e['diff_bits'], e['step_bits']) == ('camera', 256, 16, 16), e
        tail = LAYERS.index(e['from'])
    g = v['bg_y']
    assert g['op'] == 'shift' and len(g['terms']) <= 3, g
    terms = (g['terms']+[[0, 0]]*3)[:3]
    return rows, tail, (g['src'], g['post'], terms), v['buffer_lines']//8-1


def hz_seed(mmd, name):
    """d3's high word when scroll() calls its first builder, as a shift of
    scra_hz: d3 = ext.l(scra_hz) << n (asl.l #n,d4; move.l d4,d3; [add.l d3,d3]),
    with scrollb_h/scrollb_v writing only its low byte/word afterwards.  0: the
    program leaves d3 to earlier code (SCR51D/52D/53D; taken as 0)."""
    ms = list(re.finditer(rb'\x38\x38\xf7\x3a\x48\xc4([\xe1-\xef])\x84\x26\x04(\xd6\x83)?', mmd))
    m = ms[-1] if ms else None  # the last full write of d3 in scroll()
    assert len(ms) <= 2 and (len(ms) < 2 or ms[1].start()-ms[0].start() < 64), name
    if not m:
        assert name[-1] == 'D', name
        return 0
    return ((m[1][0] >> 1) & 7) + (1 if m[2] else 0)


MMDS = None


def build_tables():
    global MMDS
    from extract_mmd import disc_files
    MMDS = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    out = ['/* Generated by tools/background_r5_assets.py from tools/scroll/R5/ir and SCR51A-53D.C.  Do not edit. */']
    meta = []
    for pid in range(12):
        name = PROGRAMS.get(pid)
        if not name:
            meta.append('{0}')
            continue
        doc = json.loads((IR/f'{name}.json').read_text())
        assert doc['ir'] == 'scroll-ir/1+r5' and doc['program'] == f'R5/{name}.C'
        src = (SOURCE/f'{name}.C').read_text()
        kind = render_kind(src, name)
        rate = rates(src)
        init = scrbinit(src)
        thresholds = enkei(src)
        flag = doc['flag']
        if thresholds[0]:
            assert flag['name'] == 'enkeino' and flag['mask'] == 1 and flag['values'] == [0, 1, 2]
            assert flag['set_for_player_x'] == [[thresholds[0]+1, thresholds[1]]], (flag, thresholds)
        else:
            assert flag is None or flag.get('constant') == 0, flag
        variants = {v['when'] if v['when'] is not None else 0: v for v in doc['variants']}
        tables = [wrttbl(src, 'z81awrttbl'), wrttbl(src, 'z81awrttbl2')]
        assert tables[0]
        if name in ('SCR51A', 'SCR52A'):
            # Retail plane B (tools/capture_r5_plane.py) holds the rows this
            # table gives scrz (6) drawn around scrb, the layer the retail
            # edge fills scroll them by (see below).
            assert tables[0][:5] == [6]*5
            tables[0] = [2 if v == 6 else v for v in tables[0]]
        bodies = []
        mmd = MMDS[f'R{name[3:]}__.MMD']
        calls = builders(mmd)
        seed = hz_seed(mmd, name)
        for when in (0, 1):
            v = variants.get(when, variants[0])
            rows, tail, bgy, mask = body(doc, v, kind if when == 0 or v is variants[0] else 0, rate)
            vk = kind if tail else 0
            if name in ('SCR51A', 'SCR52A') and when == 0:
                # The retail even branch fills rows 0-7 and 88-95 from scrb
                # (move.w $F708,d0; neg.w d0; move.w #7,d6; move.w d0,(a1)+; dbf),
                # where SCR51A/52A.C and the IR read scrz.
                fill = rb'\x30\x38\xf7\x08\x44\x40\x3c\x3c\x00\x07\x32\xc0\x51\xce\xff\xfc'
                assert len(re.findall(fill, mmd)) == 2, name
                edge = list(range(8))+list(range(88, 96))
                assert len(rows) == 96 and all(rows[i] == (1, 3, 0, 0, 1, 0) for i in edge), name
                for i in edge:
                    rows[i] = (1, 1, 0, 0, 1, 0)
            # The variant's builders, in call order: one per interp parameter set,
            # with G = its highest group + 1 (each group writes >= 1 entry).
            keys = {}
            for r in rows:
                if r[0] == 2:
                    k = (LAYERS[r[1]], LAYERS[r[2]], r[3], r[4])
                    keys[k] = max(keys.get(k, 0), r[5]+1)
            chosen = []
            for c in calls:
                k = (c['frm'], c['to'], c['mul'], c['div'])
                if k in keys and c['G'] == keys[k] and k not in [x[0] for x in chosen]:
                    chosen.append((k, c))
            assert len(chosen) == len(keys) <= 2, (name, when, keys, calls)
            index = {k: i for i, (k, _) in enumerate(chosen)}
            rows = [(1, r[1], 0, 0) if r[0] == 1 else (2, 0, index[(LAYERS[r[1]], LAYERS[r[2]], r[3], r[4])], r[5]) for r in rows]
            out.append(f'static const r5_row r5_rows_{pid}_{when}[{len(rows)}] = {{{",".join("{%d,%d,%d,%d}" % r for r in rows)}}};')
            bl = [f'{{{LAYERS.index(c["frm"])},{LAYERS.index(c["to"])},{c["mul"]},{c["div"]},{c["scale"]},{c["G"]}}}' for _, c in chosen]
            builders_text = '{' + ','.join((bl+['{0}', '{0}'])[:2]) + '}'
            src_bits, post, terms = bgy
            t = ','.join('{%d,%d}' % tuple(x) for x in terms)
            # enkeino & 1 selects z81awrttbl2 only where scrollwrtb reads it.
            wt = 1 if when and tables[1] is not None else 0
            bodies.append(f'{{{len(rows)},{mask},{vk},{tail},{src_bits},{post},{{{t}}},{len(chosen)},{builders_text},r5_rows_{pid}_{when},r5_wrttbl_{pid}_{wt}}}')
        for i, t in enumerate(tables):
            if t is not None:
                out.append(f'static const uint8_t r5_wrttbl_{pid}_{i}[129] = {{{",".join(map(str, t))}}};')
        init_text = ','.join('{' + ','.join('{%d,%d}' % tm for tm in (terms+[(0, 0)]*2)[:2]) + '}' for terms in init)
        assert all(len(t) <= 2 for t in init)
        meta.append(f'{{"{name}",{seed},{{{",".join(map(str, rate))}}},{{{init_text}}},{{{thresholds[0]},{thresholds[1]}}},'
                    f'{{{",".join(bodies)}}}}}')
    # wrttbl declarations must precede the bodies that point at them.
    decl = [l for l in out[1:] if 'r5_wrttbl_' in l and l.startswith('static const uint8_t')]
    rows = [l for l in out[1:] if l not in decl]
    lines = [out[0]]+decl+rows
    lines.append(f'static const r5_program r5_programs[12] = {{{",".join(meta)}}};')
    return '\n'.join(lines)+'\n'


def entries(src, name):
    body = re.search(r'PALETTEENTRY '+name+r'\[\d+\] = \{(.*?)\};', src, re.S)[1]
    v = list(map(int, re.findall(r'\d+', body)))
    return pack(v)


def in_mmd(colors, mmd):
    """colors appears in mmd, comparing the CRAM bits (0x0EEE) of each word:
    COL5A colchg52's last word is 0xA000 in retail, black like the C's 0."""
    if colors in mmd:
        return True
    n = len(colors)//2
    want = [w & 0x0eee for w in struct.unpack(f'>{n}H', colors)]
    at = mmd.find(colors[:4])
    while at >= 0:
        if at+2*n <= len(mmd) and [w & 0x0eee for w in struct.unpack_from(f'>{n}H', mmd, at)] == want:
            return True
        at = mmd.find(colors[:4], at+1)
    return False


def pack(v):
    # PALETTEENTRY holds 3 bits per channel as c/32 (COL5D zone5color1[42]
    # has 240, which the colour conversion also reads as 7).
    assert len(v) % 4 == 0 and all(x % 16 == 0 and x < 256 for i, x in enumerate(v) if i % 4 != 3)
    return b''.join(struct.pack('>H', v[i]//32*2 | v[i+1]//32*2 << 4 | v[i+2]//32*2 << 8) for i in range(0, len(v), 4))


def build_palette(check_retail=True):
    from convert_assets import palette
    from extract_mmd import disc_files
    files = disc_files((ROOT/'build/retail/sonic.iso').read_bytes()) if check_retail else None
    out = ['/* Generated by tools/background_r5_assets.py from COL5A-D.C, cross-checked in the retail MMDs.  Do not edit. */']
    proofs = 0
    names = {}
    for letter in 'ABCD':
        src = (SOURCE/f'COL5{letter}.C').read_text()
        mmd = files[COL_MMD[letter]] if files else None
        fn = function(src, 'clchgctr')
        for m in re.finditer(r'color_change_data (colchg\d+) = \{\s*(\d+), (\d+), (\d+), (\d+),\s*\{(.*?)\}\s*\};', fn, re.S):
            adr, tate, yoko, time = map(int, m.group(2, 3, 4, 5))
            colors = pack(list(map(int, re.findall(r'\d+', m[6]))))
            assert len(colors) == tate*yoko*2 and adr+yoko <= 64, (letter, m[1])
            if mmd is not None:
                assert in_mmd(colors, mmd), (letter, m[1])
                proofs += 1
            words = struct.unpack(f'>{tate*yoko}H', palette(colors))
            key = f'r5_{letter}_{m[1]}'
            names[letter, m[1]] = key
            out.append(f'static const uint16_t {key}_c[{len(words)}] = {{{",".join(map(str, words))}}};')
            out.append(f'static const r5_script {key} = {{{adr},{tate},{yoko},{time},{key}_c}};')
        for i in (0, 1):
            z = entries(src, f'zone5color{i}')
            if mmd is not None:
                assert in_mmd(z, mmd), (letter, i)
                proofs += 1
            assert re.search(r'\{ zone5color%d, 16, 48 \}' % i, src)
            words = struct.unpack('>48H', palette(z))
            out.append(f'static const uint16_t r5_{letter}_zone{i}[48] = {{{",".join(map(str, words))}}};')
    # The control flow of each clchgctr is written out in src/background_r5.c;
    # pin the shapes it assumes.
    shapes = {
        'A': [r'if \(!colrevflag\) \{\s*colchgsub\([^;]*&colchg50\);\s*\} else \{\s*colchgsub\([^;]*&colchg53\);\s*\}\s*'
              r'if \(enkeino & 1\) \{\s*colchgsub\([^;]*&colchg52\);\s*\}\s*else \{\s*colchgsub\([^;]*&colchg51\);\s*\}\s*\}$'],
        'B': [r'if \(!colrevflag\) \{\s*colchgsub\([^;]*&colchg50\);\s*\} else \{\s*colchgsub\([^;]*&colchg52\);\s*\}\s*'
              r'if \(!\(enkeino & 1\)\) \{\s*colchgsub\([^;]*&colchg51\);\s*\}\s*\}$'],
        'C': [r'if \(!bossflag\) \{\s*pChgTime = clchgtim;\s*pChgCnt = clchgcnt;\s*if \(!colrevflag\) \{\s*colchgsub\([^;]*&colchg50\);\s*'
              r'\} else \{\s*colchgsub\([^;]*&colchg51\);\s*\}\s*\}\s*\}$'],
        'D': [r'if \(bossflag\) \{\s*\+\+pChgTime;\s*\+\+pChgCnt;\s*\}\s*else \{\s*if \(!colrevflag\) \{\s*colchgsub\([^;]*&colchg50\);\s*'
              r'\} else \{\s*colchgsub\([^;]*&colchg53\);\s*\}\s*\}\s*if \(enkeino & 1\) \{\s*colchgsub\([^;]*&colchg51\);\s*'
              r'colchgsub\([^;]*&colchg52\);\s*\}\s*\}$'],
    }
    for letter, pats in shapes.items():
        fn = function((SOURCE/f'COL5{letter}.C').read_text(), 'clchgctr')
        for p in pats:
            assert re.search(p, fn.strip(), re.S), letter
    return '\n'.join(out)+'\n', proofs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    tables = build_tables()
    pal, proofs = build_palette()
    if args.check:
        stale = [p.relative_to(ROOT).as_posix() for p, t in ((TABLES, tables), (PALETTE, pal)) if not p.exists() or p.read_text() != t]
        if stale:
            sys.exit(f'FAIL: {", ".join(stale)} stale; run tools/background_r5_assets.py')
        print(f'PASS: QQ background tables match tools/scroll/R5/ir and SCR5*.C; {proofs} COL5A-D script/color tables found in retail MMDs')
        return
    TABLES.write_text(tables)
    PALETTE.write_text(pal)
    print('wrote', TABLES.relative_to(ROOT), PALETTE.relative_to(ROOT), f'({proofs} retail table matches)')


if __name__ == '__main__':
    main()
