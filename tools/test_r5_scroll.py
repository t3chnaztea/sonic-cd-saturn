#!/usr/bin/env python3
"""Compare native Quartz Quadrant line scroll (src/background_r5.c) with the
compiled original SCR51A-D, SCR52A-D and SCR53C/D.C scroll() and with retail
CPU captures of all ten R5 programs (tools/capture_r5_scroll.py).

Source gate: each program's own scroll(), line builders (z5*line*),
scrollb/c/z_h, scrollb_v and zonescrsetsub0 are compiled; the camera-move
calls (scrchk, scroll_h, scroll_v) are removed and scra_hz is 0, so the layers
stay where the fixture puts them.  Where the retail 68k differs from the
decompiled C, the C is patched to the 68k and each patch is counted:
  - builders: to.w - from.w is 16-bit (sub.w); divu.w keeps the signed low
    word of the quotient, or the dividend's low word when it overflows;
  - builders: the 16.16 accumulator starts from d3's high word (the seed, or
    the fraction the previous builder left) instead of 0;
  - SCR51A/52A enkeino-even edge fills read scrb (move.w $F708), not scrz;
  - SCR53D draws (sYnumsv << 3) tail lines, as SCR51D/52D, not >> 3.
Seeds come from scra_hz (scd_r5_set_hz) or, in SCR51D/52D/53D, the camera Y
delta (scd_r5_set_vy).  A sequence check keeps hscrollwork across an enkeino
switch: rows the new variant does not write show the old variant's values.  Native and original must
agree on the background Y and on every background word the original writes
for all 224 visible lines, at every enkeino (0-2) and at scrbinit's and
random layer positions; scrbinit() itself is compiled and compared for every
camera X 0..32767.  (The C writes 0 for the foreground half of table lines;
the retail gate covers that half.)
Retail gate: both words of all 224 lines of every self-consistent capture.
Skipped and counted: captures whose foreground words do not all hold the
recorded camera (a frame split mid main loop) or whose enkeino changed in
the captured frame, and lines showing rows the variant does not write (stale
from earlier play), and captures whose camera Y moved after scroll() (background Y disagrees) or whose player or camera did not follow the fixture.  SCR51D/52D/53D captures whose camera did not move
vertically seed their builders from a register left by earlier code; their
builder lines may differ by 1 and are counted.
"""
import argparse
import ctypes as C
import json
import random
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from background_r5_assets import PROGRAMS, function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src'
RETAIL = {0: 'R51A', 1: 'R51B', 2: 'R51C', 3: 'R51D', 4: 'R52A', 5: 'R52B', 6: 'R52C', 7: 'R52D', 10: 'R53C', 11: 'R53D'}
OUT = ROOT/'build/qq/scroll-native'
SENTINEL = 0x7fff7fff
PATCHES = {}
SEED = {}

HARNESS = r'''
#include <stdint.h>
%(types)s
short_union scroll_start;
ushort_union scrflaga, scrflagb, scrflagc, scrflagz;
int_union vscroll, scra_h_posit, scra_v_posit, scrb_h_posit, scrb_v_posit,
          scrc_h_posit, scrc_v_posit, scrz_h_posit, scrz_v_posit;
short scra_hz, scra_vz, hscrollwork[256];
unsigned d3frac;
static int r5_divu(int n, unsigned d) { unsigned q = (unsigned)n / d; return (short)(q > 0xffff ? (unsigned)n : q); }
unsigned char enkeino, scra_h_count, scra_v_count, scrb_h_count, scrb_v_count, scrc_h_count,
              scrc_v_count, scrz_h_count, scrz_v_count;
int_union hbuf[240], *lphscrollbuff = hbuf;
%(protos)s
%(body)s
static void init(short sXpos, short sYpos) { scrbinit(sXpos, sYpos); }
int run(int x, int y, const int *layers, int enkei, int32_t *out, int keep, unsigned seed) {
    if (!keep) for (int i = 0; i < 256; i++) hscrollwork[i] = 0;
    d3frac = seed;
    for (int i = 0; i < 240; i++) hbuf[i].l = 0x7fff7fff;
    scra_h_posit.l = x * 65536; scra_v_posit.l = y * 65536; scra_hz = scra_vz = 0;
    scrb_h_posit.l = layers[0]; scrc_h_posit.l = layers[1]; scrz_h_posit.l = layers[2];
    enkeino = (unsigned char)enkei;
    scroll();
    for (int i = 0; i < 232; i++) out[i] = hbuf[i].l;
    return scrb_v_posit.w.h;
}
void layers_at(int x, int enkei, int *out) {
    enkeino = (unsigned char)enkei;
    scrb_h_posit.l = scrc_h_posit.l = scrz_h_posit.l = 0;
    init((short)x, 0);
    out[0] = scrb_h_posit.l; out[1] = scrc_h_posit.l; out[2] = scrz_h_posit.l;
}
'''


def types():
    text = (SOURCE/'TYPES.H').read_text()
    return text[:text.index('uint_union;')+len('uint_union;')]


def original(pid):
    name = PROGRAMS[pid]
    src = (SOURCE/'R5'/f'{name}.C').read_text()
    scroll = function(src, 'scroll')
    for call in ('scrchk', 'scroll_h', 'scroll_v'):
        scroll = re.sub(r'\n\s*' + call + r'\(\);[^\n]*', '\n', scroll)
    names = ['zonescrsetsub0', 'scrollb_v', 'scrollb_h', 'scrollc_h', 'scrollz_h', 'scrbinit']
    lines = sorted(set(re.findall(r'\b(z5\w*line\w*)\(', scroll)))
    names += lines
    protos = '\n'.join(re.search(r'static void ' + n + r'\([^)]*\);', src)[0] for n in names)
    patches = 0
    if name in ('SCR51A', 'SCR52A'):
        assert scroll.count('ldwk.w.l = -scrz_h_posit.w.h;') == 2
        scroll = scroll.replace('ldwk.w.l = -scrz_h_posit.w.h;', 'ldwk.w.l = -scrb_h_posit.w.h;')
        patches += 2
    if name == 'SCR53D':
        assert scroll.count('(sYnumsv >> 3) - 1') == 1
        scroll = scroll.replace('(sYnumsv >> 3) - 1', '(sYnumsv << 3) - 1')
        patches += 1
    funcs = []
    for n in names:
        f = function(src, n)
        if n in lines:
            f, a = re.subn(r'lHwk = (scr\w_h_posit\.w\.h - scr\w_h_posit\.w\.h);', r'lHwk = (short)(\1);', f)
            f, b = re.subn(r'lHwk = \(unsigned int\)lHwk \* (\d+) / (\d+);', r'lHwk = r5_divu(lHwk * \1, \2);', f)
            f, c = re.subn(r'ldHposwk\.l = 0;', 'ldHposwk.l = (int)(d3frac << 16);', f)
            assert a == b == c == 1, (name, n, a, b, c)
            f = f.rstrip()[:-1]+'  d3frac = (unsigned short)ldHposwk.w.h;\n}'
            patches += 4
        funcs.append(f)
    body = scroll+'\n'+'\n'.join(funcs)
    PATCHES[name] = patches
    path = OUT/f'original-{name}.c'
    path.write_text(HARNESS % dict(types=types(), protos=protos, body=body))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-O1', '-fwrapv', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.run.argtypes = [C.c_int, C.c_int, C.POINTER(C.c_int), C.c_int, C.POINTER(C.c_int32), C.c_int, C.c_uint]
    dll.layers_at.argtypes = [C.c_int, C.c_int, C.POINTER(C.c_int)]
    return dll


def native_lib():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-Isrc', '-dynamiclib',
                    'src/background_r5.c', '-o', str(lib)], cwd=ROOT, check=True)
    n = C.CDLL(str(lib))
    n.scd_r5_lines_layers.argtypes = [C.c_uint, C.c_int, C.POINTER(C.c_int32), C.c_int,
                                      C.POINTER(C.c_int32), C.POINTER(C.c_int32), C.c_uint]
    n.scd_r5_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    n.scd_r5_set_enkei.argtypes = [C.c_uint, C.c_int, C.c_int]
    n.scd_r5_layers.restype = C.POINTER(C.c_int32)
    n.scd_r5_reset.argtypes = [C.c_int]
    n.scd_r5_set_hz.argtypes = [C.c_int]
    n.scd_r5_set_vy.argtypes = [C.c_int]
    return n


def seed_frac(shift, hz, vy):
    """d3's high word at the first builder: ext.l(scra_hz) << shift, or
    ror.l #8 of scroll_v's camera Y delta (shift 0: SCR51D/52D/53D)."""
    if shift:
        return ((hz << shift) >> 16) & 0xffff
    v = (vy << 16) & 0xffffffff
    return ((v >> 8) | (v << 24) & 0xffffffff) >> 16


def compare(native, orig, pid, name, x, layers, y, e, hz, vy, bg, fg, out, keep=False):
    """One window; returns (words compared, lines the C leaves unwritten)."""
    top = native.scd_r5_background_y(pid, y, x+160)
    got_top = orig.run(x, y, (C.c_int*3)(*layers), e, out, keep, seed_frac(SEED[pid], hz, vy))
    if got_top != top:
        raise AssertionError((name, 'background Y', e, x, y, got_top, top))
    native.scd_r5_lines_layers(pid, x, (C.c_int32*3)(*layers), top, bg, fg, 224)
    words = unwritten = 0
    for i in range(224):
        if out[i] == SENTINEL:
            unwritten += 1
            continue
        ob = (-C.c_int16(out[i] & 0xffff).value) & 511
        if (bg[i] >> 16) & 511 != ob:
            raise AssertionError((name, 'bg', e, x, y, hz, vy, top, i, (bg[i] >> 16) & 511, ob))
        words += 1
    return words, unwritten


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--full', action='store_true', help='every camera Y 0..800')
    ap.add_argument('--source-only', action='store_true')
    args = ap.parse_args()
    from background_r5_assets import hz_seed
    from extract_mmd import disc_files
    mmds = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    native = native_lib()
    bg = (C.c_int32*232)()
    fg = (C.c_int32*232)()
    out = (C.c_int32*232)()
    got = (C.c_int*3)()
    rng = random.Random(5)
    words = windows = inits = unwritten = kept = 0
    for pid, name in PROGRAMS.items():
        SEED[pid] = hz_seed(mmds[f'R{name[3:]}__.MMD'], name)
        orig = original(pid)
        enkeis = (0, 1, 2) if pid < 8 else (0,)
        for e in enkeis:
            for x in range(0, 32768, 1 if args.full else 7):
                native.scd_r5_set_enkei(pid, e, x)
                orig.layers_at(x, e, got)
                have = native.scd_r5_layers()
                if [have[i] for i in range(3)] != list(got):
                    raise AssertionError((name, 'scrbinit', e, x, [have[i] for i in range(3)], list(got)))
                inits += 1
        xs = [0, 1, 31, 255, 639, 1001, 3424, 3425, 4093, 7008, 8191, 8801, 10903]
        ys = list(range(0, 801, 1 if args.full else 13))+[800]
        motion = [(0, 0), (-768, 0), (3072, 0), (4096, 5), (-256, -3), (1280, 16)]
        for e in enkeis:
            layer_sets = []
            for x in xs:
                orig.layers_at(x, e, got)
                layer_sets.append((x, tuple(got)))
            layer_sets += [(x, tuple(rng.randrange(-1 << 27, 1 << 27) for _ in range(3))) for x in (700, 5000, 9000)]
            for n, (x, layers) in enumerate(layer_sets):
                hz, vy = motion[n % len(motion)]
                native.scd_r5_reset(x)
                native.scd_r5_set_enkei(pid, e, x)
                native.scd_r5_set_hz(hz)
                native.scd_r5_set_vy(vy)
                for y in ys:
                    w, u = compare(native, orig, pid, name, x, layers, y, e, hz, vy, bg, fg, out)
                    words += w
                    unwritten += u
                    windows += 1
        # hscrollwork persists across an enkeino switch: rows the new variant
        # does not write keep the old variant's last values.
        if pid < 8:
            for a, b in ((0, 1), (1, 0), (1, 2), (2, 1)):
                for xa, xb in ((1001, 3000), (5003, 4093), (9000, 700)):
                    orig.layers_at(xa, a, got)
                    la = tuple(got)
                    orig.layers_at(xb, b, got)
                    lb = tuple(got)
                    for y in range(0, 4096, 61 if not args.full else 13):
                        native.scd_r5_reset(xa)
                        native.scd_r5_set_enkei(pid, a, xa)
                        native.scd_r5_set_hz(0)
                        native.scd_r5_set_vy(0)
                        orig.run(xa, 0, (C.c_int*3)(*la), a, out, 0, 0)
                        native.scd_r5_set_enkei(pid, b, xb)
                        w, u = compare(native, orig, pid, name, xb, lb, y, b, 0, 0, bg, fg, out, keep=True)
                        words += w
                        unwritten += u
                        kept += 1
    scope = 'all' if args.full else 'probe'
    patches = sum(PATCHES.values())
    source = (f'{words} original/native line words across {windows} {scope} windows and {kept} enkeino-switch windows '
              f'of 10 compiled programs ({patches} retail-authority patches, {unwritten} unwritten lines), {inits} scrbinit layer sets')
    if unwritten:
        raise AssertionError(('lines the patched C leaves unwritten', unwritten))
    if args.source_only:
        print(f'PASS: QQ scroll: {source}')
        return
    captures = retail_words = split = switched = stale = tolerated = unsettled = lost = 0
    for pid, prog in RETAIL.items():
        base = ROOT/'build/qq/scroll-retail'/prog
        report = json.loads((base/'report.json').read_text())
        for s in report['samples']:
            a = s['actual_16_16']
            x, y, top = a['cameraX'] >> 16, a['cameraY'] >> 16, a['cameraBgY'] >> 16
            e = s['enkeino']
            raw = (base/f'{s["index"]:03}-hscroll.bin').read_bytes()
            if any((-struct.unpack_from('>h', raw, i*4)[0]) & 511 != x & 511 for i in range(224)):
                split += 1
                continue
            if s['enkeino_before'] != e:
                switched += 1
                continue
            if abs(s['player_x']-(s['inputs']['cameraX']+160)) > 16 or s['scra_hz'] != s['inputs']['move'][0]*256:
                lost += 1  # the player or camera does not follow the fixture (scra_hz != its move)
                continue
            native.scd_r5_reset(x)
            native.scd_r5_set_enkei(pid, e, x)
            native.scd_r5_set_hz(s['scra_hz'])
            native.scd_r5_set_vy(s['scra_vz'] // 256)
            if native.scd_r5_background_y(pid, y, s['player_x']) != top:
                if y != s['inputs']['cameraY']:
                    unsettled += 1  # camera Y moved again after scroll() in the captured frame
                    continue
                raise AssertionError((prog, 'capture background Y', s['index'], e, x, y, top))
            lay = (C.c_int32*3)(a['cameraBgX'], a['cameraBg2X'], a['cameraBg3X'])
            native.scd_r5_lines_layers(pid, x, lay, top, bg, fg, 224)
            body = json.loads((ROOT/'tools/scroll/R5/ir'/f'{PROGRAMS[pid]}.json').read_text())['variants']
            v = next((b for b in body if b['when'] in (e & 1, None)), body[0])
            table = v['table_end']//8+sum(c.get('rows', 0) for c in v.get('corrections') or [] if c['rule'] == 'PASTBUF')
            loose = PROGRAMS[pid][-1] == 'D' and not s['scra_vz']
            for i in range(224):
                f, b = struct.unpack_from('>hh', raw, i*4)
                row = ((top+i) & 0xffff) >> 3 & (v['buffer_lines']//8-1)
                if row >= table and not (v['bands'] and row >= 40):
                    stale += 1
                    continue
                have = ((bg[i] >> 16) & 511, (fg[i] >> 16) & 511)
                want = ((-b) & 511, (-f) & 511)
                if have != want:
                    if loose and have[1] == want[1] and (have[0]-want[0]) % 512 in (1, 511):
                        tolerated += 1
                        continue
                    raise AssertionError((prog, 'capture', s['index'], e, x, y, top, i, have, want))
                retail_words += 2
            captures += 1
    print(f'PASS: QQ scroll: {source}; {retail_words} words of {captures} retail captures of 10 programs '
          f'(skipped: {split} split, {switched} enkeino-switch, {unsettled} camera-Y split, {lost} unfollowed, {stale} stale-row lines; '
          f'{tolerated} SCR5xD lines off by 1 from an unseeded builder)')


if __name__ == '__main__':
    main()
