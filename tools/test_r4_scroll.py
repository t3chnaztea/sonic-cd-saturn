#!/usr/bin/env python3
"""Compare native Tidal Tempest line scroll (src/background_r4.c) with the
compiled original SCR41A-D, SCR42A/C and SCR43C/D.C scroll() and with retail
CPU captures of all ten R4 programs (tools/capture_r4_scroll.py).

Source gate: each program's own scroll(), z41aline() and zonescrsetsub0() are
compiled unchanged; only camera-move and plane-write calls are removed, and
scrollb_v() keeps its assignment.  Native and original must agree on the
background Y and on every background word of all 224 visible lines, and on
the foreground word of every line below the water surface (above it the
decompiled C copies a half word it never sets; the retail gate covers it).
Retail gate: both words of all 224 lines of 68 captures per program.
"""
import argparse
import ctypes as C
import random
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from test_cc_palette import function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src'
PROGRAMS = {0: 'SCR41A', 1: 'SCR41B', 2: 'SCR41C', 3: 'SCR41D', 4: 'SCR42A', 6: 'SCR42C', 10: 'SCR43C', 11: 'SCR43D'}
RETAIL = {0: 'R41A', 1: 'R41B', 2: 'R41C', 3: 'R41D', 4: 'R42A', 5: 'R42B', 6: 'R42C', 7: 'R42D', 10: 'R43C', 11: 'R43D'}
OUT = ROOT/'build/tt/scroll-native'

HARNESS = r'''
#include <stdint.h>
typedef struct { unsigned char l, h; } short_chars;
typedef union { short w; short_chars b; } short_union;
typedef struct { short l, h; } int_shorts;
typedef struct { unsigned char l0, l, h0, h; } int_chars;
typedef union { int l; int_shorts w; int_chars b; } int_union;
typedef struct { unsigned char l, h; } ushort_uchars;
typedef union { unsigned short w; ushort_uchars b; } ushort_union;
typedef struct { unsigned short l, h; } uint_ushorts;
typedef struct { unsigned char l0, l, h0, h; } uint_uchars;
typedef union { unsigned int l; uint_ushorts w; uint_uchars b; } uint_union;
short_union scroll_start, waterdirec;
ushort_union scrflaga, scrflagb, scrflagc, scrflagz;
int_union vscroll, scra_h_posit, scra_v_posit, scrb_h_posit, scrb_v_posit,
          scrc_h_posit, scrc_v_posit, scrz_h_posit, scrz_v_posit;
short scra_hz, scra_vz, waterposi, hscrollwork[256];
int_union hbuf[240], *lphscrollbuff = hbuf;
%(awasintbl)s
static void scrollb_v(unsigned short wD0) { scrb_v_posit.w.h = wD0; }
static void zonescrsetsub0(short HPosi, short VPosi, unsigned short offs);
static int z41aline(int hsCount);
%(body)s
int run(int x, int y, int bgy, const int *layers, int phase, int surface, int32_t *out) {
    for (int i = 0; i < 256; i++) hscrollwork[i] = 0;
    for (int i = 0; i < 240; i++) hbuf[i].l = 0x7fff7fff;
    scra_h_posit.l = x * 65536; scra_v_posit.l = y * 65536;
    scrb_h_posit.l = layers[0]; scrc_h_posit.l = layers[1]; scrz_h_posit.l = layers[2];
    scrb_v_posit.l = bgy * 65536;
    waterdirec.w = (short)phase; waterposi = (short)surface;
    scroll();
    for (int i = 0; i < 232; i++) out[i] = hbuf[i].l;
    return scrb_v_posit.w.h;
}
'''


def original(pid):
    name = PROGRAMS[pid]
    src = (SOURCE/'R4'/f'{name}.C').read_text()
    table = re.search(r'unsigned char awasintbl\[256\] = \{.*?\};', (SOURCE/'TBL0.C').read_text(), re.S).group(0)
    scroll = function(src, 'scroll')
    for call in ('scrchk', 'scroll_h', 'scroll_v', 'scrollz_h', 'scrollc_h', 'scrollb_h', 'scrollb_hv'):
        scroll = re.sub(r'\n\s*' + call + r'\(.*?\);[^\n]*', '\n', scroll)
    body = scroll + '\n' + function(src, 'zonescrsetsub0').replace('void zonescrsetsub0', 'static void zonescrsetsub0', 1)
    if 'z41aline' in src:
        m = re.search(r'static int z41aline\(int hsCount\)\s*\{', src)
        depth, end = 1, m.end()
        while depth:
            depth += (src[end] == '{')-(src[end] == '}')
            end += 1
        body += '\n' + src[m.start():end]
    else:
        body += '\nstatic int z41aline(int h) { return h; }'
    path = OUT/f'original-{name}.c'
    path.write_text(HARNESS % dict(awasintbl=table, body=body))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-O1', '-fwrapv', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.run.argtypes = [C.c_int, C.c_int, C.c_int, C.POINTER(C.c_int), C.c_int, C.c_int, C.POINTER(C.c_int32)]
    return dll


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--full', action='store_true', help='every background Y the buffer holds')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-Isrc', '-dynamiclib',
                    'src/background_r4.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    native.scd_r4_lines_layers.argtypes = [C.c_uint, C.c_int, C.POINTER(C.c_int32), C.c_int, C.c_int, C.c_uint,
                                           C.POINTER(C.c_int32), C.POINTER(C.c_int32), C.c_uint]
    native.scd_r4_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    bg = (C.c_int32*232)()
    fg = (C.c_int32*232)()
    out = (C.c_int32*232)()
    rng = random.Random(4)
    words = windows = 0
    for pid, name in PROGRAMS.items():
        orig = original(pid)
        xs = [0, 1, 31, 255, 639, 640, 1001, 4093, 8191, 11800]
        layer_sets = [(x, (x*12//256*65536, x*24//256*65536, x*16//256*65536)) for x in xs]
        layer_sets += [(x, tuple(rng.randrange(0, 1 << 26) for _ in range(3))) for x in (700, 5000)]
        # Camera Y limits (src/scroll_limits.h): act 1 0-1296, acts 2/3 0-2048.
        ys = list(range(0, (1296 if pid < 4 else 2048)+1, 1 if args.full else 37))+[1296 if pid < 4 else 2048]
        frames = (1, 2, 777) if args.full else (1, 777)
        for x, layers in layer_sets:
            lay = (C.c_int32*3)(*layers)
            for y in ys:
                top = native.scd_r4_background_y(pid, x, y)
                for frame in frames:
                    for surface in (y-1000, y, y+100, y+223, 32767):
                        native.scd_r4_set_water(surface)
                        # Retail authority: the CPU starts the wobble at avp >= waterposi,
                        # where the C says avp > waterposi; feed the C surface-1.
                        got_top = orig.run(x, y, top, (C.c_int*3)(*layers), ((frame-1)*128) & 0xffff, surface-1, out)
                        if got_top != top:
                            raise AssertionError((name, 'background Y', x, y, got_top, top))
                        native.scd_r4_lines_layers(pid, x, lay, y, top, frame, bg, fg, 224)
                        first = 0 if y >= surface else surface-y
                        for i in range(224):
                            ob = (-C.c_int16(out[i] & 0xffff).value) & 511
                            if (bg[i] >> 16) & 511 != ob:
                                raise AssertionError((name, 'bg', x, y, top, frame, surface, i, (bg[i] >> 16) & 511, ob))
                            words += 1
                            if i >= first:
                                of = (-(out[i] >> 16)) & 511
                                if (fg[i] >> 16) & 511 != of:
                                    raise AssertionError((name, 'fg', x, y, frame, surface, i, (fg[i] >> 16) & 511, of))
                                words += 1
                        windows += 1
    captures = 0
    import json
    for pid, prog in RETAIL.items():
        base = ROOT/'build/tt/scroll-retail'/prog
        report = json.loads((base/'report.json').read_text())
        for s in report['samples']:
            a = s['actual_16_16']
            x, y, top = a['cameraX'] >> 16, a['cameraY'] >> 16, a['cameraBgY'] >> 16
            moved = (x, y) != (s['inputs']['cameraX'], s['inputs']['cameraY'])
            if not moved and native.scd_r4_background_y(pid, x, y) != top:
                raise AssertionError((prog, 'capture background Y', s['index'], x, y, top))
            assert s['water_phase_before'] % 128 == 0
            frame = s['water_phase_before']//128+1
            lay = (C.c_int32*3)(a['cameraBgX'], a['cameraBg2X'], a['cameraBg3X'])
            native.scd_r4_set_water(s['water_surface'])
            native.scd_r4_lines_layers(pid, x, lay, y, top, frame, bg, fg, 224)
            raw = (base/f'{s["index"]:03}-hscroll.bin').read_bytes()
            for i in range(224):
                f, b = struct.unpack_from('>hh', raw, i*4)
                got = ((bg[i] >> 16) & 511, (fg[i] >> 16) & 511)
                if got != ((-b) & 511, (-f) & 511):
                    raise AssertionError((prog, 'capture', s['index'], x, y, top, s['water_surface'], i, got, ((-b) & 511, (-f) & 511)))
                words += 2
            captures += 1
    # the table-free validity mask must name exactly the programs the tables hold
    assert [i for i in range(32) if native.scd_r4_valid(i)] == sorted(RETAIL), 'scd_r4_valid'
    native.scd_r4_set_water(32767)
    scope = 'all' if args.full else 'probe'
    print(f'PASS: TT scroll: {words} original/native line words across {windows} {scope} windows of 8 compiled programs and {captures} retail captures of 10 programs')


if __name__ == '__main__':
    main()
