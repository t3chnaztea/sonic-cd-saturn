#!/usr/bin/env python3
"""Compiled-original COL6A-D palette oracle for Wacky Workbench (all ten programs).

Each COL6x.C's own clchgctr(), colchg6a/6b(), clchg_sub0() and tables are
compiled unchanged and stepped once per update alongside native
scd_background_palette (src/background_r6.c via background.c).  Act 3 runs
toggle bossflag bit 5 (col6a3col_stop).  Every entry of every frame must
match, and a repeated display call must not advance the scripts.  The native
clchgcnt[3] (flashing floor step) must equal the original's every update.
"""
import ctypes as C
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from test_cc_palette import function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src/R6'
OUT = ROOT/'build/ww/palette'
IDS = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11]
HARNESS = r'''
#include <stdint.h>
typedef struct { unsigned char peRed, peGreen, peBlue, peFlags; } PALETTEENTRY;
typedef struct { PALETTEENTRY *PeSrc; short offset; short cnt; } palette_part;
typedef struct { unsigned char l, h; } short_chars;
typedef union { short w; short_chars b; } short_union;
typedef struct { short l, h; } int_shorts;
typedef union { int l; int_shorts w; } int_union;
unsigned char bossflag;
PALETTEENTRY work[4][64], *lpcolorwk = work[0], *lpcolorwk2 = work[1], *lpcolorwk3 = work[2], *lpcolorwk4 = work[3];
unsigned char clchgtim[7], clchgcnt[7];
void clchg_sub0(unsigned char*, unsigned char*, unsigned char*, PALETTEENTRY*);
%(body)s
void init(void) {
    for (int i = 0; i < 7; i++) clchgtim[i] = clchgcnt[i] = 0;
    for (int b = 0; b < 4; b++) for (int i = 0; i < 64; i++) work[b][i] = (PALETTEENTRY){(i%%8)*32, ((i/8)%%8)*32, ((i*3)%%8)*32, 1};
}
void step(int boss) { bossflag = (unsigned char)boss; clchgctr(); }
void read_colors(uint16_t *out) { for (int i = 0; i < 64; i++) { PALETTEENTRY c = lpcolorwk[i];
    out[i] = 0x8000 | ((c.peRed/32)*31/7) | (((c.peGreen/32)*31/7) << 5) | (((c.peBlue/32)*31/7) << 10); } }
'''


def original(letter):
    src = (SOURCE/f'COL6{letter}.C').read_text()
    arrays = '\n'.join(m[0] for m in re.finditer(r'(?:unsigned char|PALETTEENTRY) \w+\[\d+\] = \{.*?\};', src, re.S))
    chg = 'colchg6b' if letter == 'B' else 'colchg6a'
    body = arrays+'\nvoid '+chg+'(void);\n'+function(src, 'clchg_sub0')+'\n'+function(src, 'clchgctr')+'\n'+function(src, chg)
    path = OUT/f'original-{letter}.c'
    path.write_text(HARNESS % dict(body=body))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.step.argtypes = [C.c_int]
    return dll


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc', '-Iassets/generated',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    native.scd_background_palette.argtypes = [C.c_uint, C.c_uint, C.c_void_p, C.c_void_p]
    native.scd_r6_set_bossflag.argtypes = [C.c_uint]
    native.scd_r6_palette_count.restype = C.c_uint
    frames = 6000
    cases = changed = 0
    for pid in IDS:
        letter = 'ABCD'[pid & 3]
        orig = original(letter)
        orig.init()
        ocnt = (C.c_ubyte*7).in_dll(orig, 'clchgcnt')
        expected = (C.c_uint16*64)()
        actual = (C.c_uint16*64)()
        orig.read_colors(expected)
        base = C.create_string_buffer(b''.join(int(v).to_bytes(2, 'big') for v in expected))
        previous = bytes(expected)
        for frame in range(frames+1):
            boss = 32 if pid >= 8 and (frame//700) % 2 else 0
            if frame:
                orig.step(boss)
            native.scd_r6_set_bossflag(boss)
            orig.read_colors(expected)
            for _ in range(2):
                native.scd_background_palette(48+pid, frame, base, actual)
                if list(actual) != list(expected):
                    bad = [(i, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
                    raise AssertionError((pid, frame, bad[:4]))
            assert native.scd_r6_palette_count(3) == ocnt[3], (pid, frame)
            values = bytes(expected)
            changed += values != previous
            previous = values
            cases += 1
    print(f'PASS: WW palette: {cases} compiled-original/native COL6A-D frames ({cases*64} entries, {changed} changes) across 10 programs')


if __name__ == '__main__':
    main()
