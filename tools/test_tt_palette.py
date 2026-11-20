#!/usr/bin/env python3
"""Compiled-original COL4A-D palette oracle for Tidal Tempest (all ten programs).

Each COL4x.C's own clchgctr(), clchg_sub0(), colorset2()/colorset00() and
tables are compiled unchanged and driven with the same camera path as native
scd_background_palette (src/background_r4.c via background.c).  The path
crosses COL4A's camera X 640 / Y 352 switches (including the one-shot
colorset2(4) and the timer-4 flag it shares) in every act.  Every entry of
every frame must match.
"""
import ctypes as C
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from test_cc_palette import function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src/R4'
OUT = ROOT/'build/tt/palette'
IDS = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11]
HARNESS = r'''
#include <stdint.h>
typedef struct { unsigned char peRed, peGreen, peBlue, peFlags; } PALETTEENTRY;
typedef struct { PALETTEENTRY *PeSrc; short offset; short cnt; } palette_part;
typedef struct { unsigned char l, h; } short_chars;
typedef union { short w; short_chars b; } short_union;
typedef struct { short l, h; } int_shorts;
typedef union { int l; int_shorts w; } int_union;
short_union stageno; int_union scra_h_posit, scra_v_posit;
PALETTEENTRY work[4][64], *lpcolorwk = work[0], *lpcolorwk2 = work[1], *lpcolorwk3 = work[2], *lpcolorwk4 = work[3];
unsigned char clchgtim[7], clchgcnt[7];
void clchg_sub0(unsigned char*, unsigned char*, unsigned char*, PALETTEENTRY*);
void colorset2(int);
static void colorset00(int, int);
%(body)s
void init(int act) {
    for (int i = 0; i < 7; i++) clchgtim[i] = clchgcnt[i] = 0;
    for (int b = 0; b < 4; b++) for (int i = 0; i < 64; i++) work[b][i] = (PALETTEENTRY){(i%%8)*32, ((i/8)%%8)*32, ((i*3)%%8)*32, 1};
    stageno.w = 0; stageno.b.l = (unsigned char)act;
}
void step(int x, int y) { scra_h_posit.l = x * 65536; scra_v_posit.l = y * 65536; clchgctr(); }
void read_colors(uint16_t *out) { for (int i = 0; i < 64; i++) { PALETTEENTRY c = lpcolorwk[i];
    out[i] = 0x8000 | ((c.peRed/32)*31/7) | (((c.peGreen/32)*31/7) << 5) | (((c.peBlue/32)*31/7) << 10); } }
'''


def original(letter):
    src = (SOURCE/f'COL4{letter}.C').read_text()
    arrays = '\n'.join(m[0] for m in re.finditer(r'(?:unsigned char|PALETTEENTRY|palette_part) \w+\[\d+\] = \{.*?\};', src, re.S))
    body = arrays+'\n'+function(src, 'clchg_sub0')+'\n'+function(src, 'clchgctr')
    body += '\n'+function(src, 'colorset2')+'\nstatic '+function(src, 'colorset00')
    path = OUT/f'original-{letter}.c'
    path.write_text(HARNESS % dict(body=body))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.step.argtypes = [C.c_int, C.c_int]
    return dll


def path(frames):
    """Camera (x, y) per update: start area, cave (Y >= 352), back, X >= 640, and back."""
    legs = [(100, 100), (100, 400), (100, 100), (700, 100), (300, 200), (600, 360), (900, 900)]
    for f in range(frames):
        yield legs[(f//211) % len(legs)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc', '-Iassets/generated',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    native.scd_background_palette.argtypes = [C.c_uint, C.c_uint, C.c_void_p, C.c_void_p]
    native.scd_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    native.scd_background_reset.argtypes = [C.c_void_p, C.c_int]
    scroll = C.create_string_buffer(64)
    frames = 6000
    cases = changed = 0
    traces = {}
    for pid in IDS:
        letter = 'ABCD'[pid & 3]
        orig = original(letter)
        orig.init(pid//4)
        expected = (C.c_uint16*64)()
        actual = (C.c_uint16*64)()
        orig.read_colors(expected)
        base = C.create_string_buffer(b''.join(int(v).to_bytes(2, 'big') for v in expected))
        trace = hashlib.sha256()
        previous = bytes(expected)
        for frame, (x, y) in enumerate([(0, 0)]+list(path(frames))):
            if frame:
                orig.step(x, y)
            native.scd_background_reset(scroll, x)
            native.scd_background_y(24+pid, y, 0)
            orig.read_colors(expected)
            for _ in range(2):  # a repeated (paused) display call must not advance
                native.scd_background_palette(24+pid, frame, base, actual)
                if list(actual) != list(expected):
                    bad = [(i, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
                    raise AssertionError((pid, frame, x, y, bad[:4]))
            values = bytes(expected)
            changed += values != previous
            previous = values
            trace.update(values)
            cases += 1
        traces[pid] = trace.hexdigest()[:12]
    print(f'PASS: TT palette: {cases} compiled-original/native COL4A-D frames ({cases*64} entries, {changed} changes) across 10 programs')


if __name__ == '__main__':
    main()
