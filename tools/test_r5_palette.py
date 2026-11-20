#!/usr/bin/env python3
"""Compiled-original COL5A-D palette oracle for Quartz Quadrant (all ten programs).

Each COL5x.C's own clchgctr(), colchgsub(), colorset/colorset2/colorset00 and
tables, and the program's own enkeichg() (SCR5*.C; tile, map and scrbinit
calls stubbed) are compiled unchanged and run in GAME5.C order: game_init's
enkeichg(), then per update clchgctr() and enkeichg() unless the previous
enkeichg set mapwrt_cnt, with scrflaga.b.h set when the camera crossed a
16-pixel line.  Native runs through its own API (scd_r5_reset/step/
background_y/set_colrev/set_boss/palette).  The route crosses every
enkeichg band both ways at several speeds (so crossings delay the switch),
toggles colrevflag and bossflag, and pauses; every entry of every frame must
match, including the frame a switch writes zone5color0/1.
"""
import ctypes as C
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from background_r5_assets import PROGRAMS, function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src'
OUT = ROOT/'build/qq/palette'
HARNESS = r'''
#include <stdint.h>
%(types)s
typedef struct { unsigned char peRed, peGreen, peBlue, peFlags; } PALETTEENTRY;
typedef struct { PALETTEENTRY *PeSrc; short offset; short cnt; } palette_part;
typedef struct { int_union xposi; } sprite_status;
sprite_status actwk[1];
ushort_union scrflaga; int_union scra_h_posit, scra_v_posit;
unsigned char enkeino, colrevflag, bossflag, mapwrt_cnt, mapwkb[8][64];
PALETTEENTRY work[4][64], *lpcolorwk = work[0], *lpcolorwk2 = work[1], *lpcolorwk3 = work[2], *lpcolorwk4 = work[3];
unsigned char clchgtim[16], clchgcnt[16];
static void ChangeTileBmp(int a, int b) { (void)a; (void)b; }
static void mapset2(unsigned char *p, int i) { (void)p; (void)i; }
static void scrbinit(short x, short y) { (void)x; (void)y; }
void colorset(int); void colorset2(int);
%(body)s
void init(int px, int base) {
    for (int i = 0; i < 16; i++) clchgtim[i] = clchgcnt[i] = 0;
    for (int b = 0; b < 4; b++) for (int i = 0; i < 64; i++)
        work[b][i] = (PALETTEENTRY){((i+base)%%8)*32, (((i+base)/8)%%8)*32, (((i+base)*3)%%8)*32, 1};
    enkeino = 0; mapwrt_cnt = 0; colrevflag = bossflag = 0; scrflaga.w = 0;
    actwk[0].xposi.l = px * 65536; enkeichg();
}
void step(int px, int crossed, int colrev, int boss) {
    colrevflag = (unsigned char)colrev; bossflag = (unsigned char)boss;
    clchgctr();
    scrflaga.b.h = (char)(crossed ? 4 : 0);
    actwk[0].xposi.l = px * 65536;
    if (mapwrt_cnt & 1) mapwrt_cnt &= 254; else enkeichg();
}
int enkei(void) { return enkeino; }
void read_colors(uint16_t *out) { for (int i = 0; i < 64; i++) { PALETTEENTRY c = lpcolorwk[i];
    out[i] = 0x8000 | ((c.peRed/32)*31/7) | (((c.peGreen/32)*31/7) << 5) | (((c.peBlue/32)*31/7) << 10); } }
'''


def original(pid):
    letter = 'ABCD'[pid & 3]
    col = (SOURCE/'R5'/f'COL5{letter}.C').read_text()
    scr = (SOURCE/'R5'/f'{PROGRAMS[pid]}.C').read_text()
    typedef = re.search(r'typedef struct \{\s*unsigned char adr;.*?color_change_data;', col, re.S)[0]
    arrays = '\n'.join(m[0] for m in re.finditer(r'(?:PALETTEENTRY|palette_part) \w+\[\d+\] = \{.*?\};', col, re.S))
    body = typedef+'\n'+arrays+'\nstatic void colorset00(int, int);\n'
    body += 'static void colchgsub(unsigned char**, unsigned char**, color_change_data*);\n'
    body += '\n'.join(function(col, n) for n in ('colchgsub', 'clchgctr', 'colorset', 'colorset2', 'colorset00'))
    body += '\n'+(function(scr, 'enkeichg') if 'void enkeichg' in scr else 'void enkeichg(void) {}')
    text = (SOURCE/'TYPES.H').read_text()
    path = OUT/f'original-{PROGRAMS[pid]}.c'
    path.write_text(HARNESS % dict(types=text[:text.index('uint_union;')+len('uint_union;')], body=body))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.step.argtypes = [C.c_int, C.c_int, C.c_int, C.c_int]
    return dll


def route(act):
    """(camera x, camera y, colrev, boss) per update after the start."""
    hi = 10903 if act < 2 else 3735
    legs = [(3000, 0, 60), (3500, 2, 0), (3600, 1, 30), (3380, 3, 0), (5000, 7, 0), (5000, 0, 120),
            (7100, 16, 0), (7000, 5, 0), (8900, 4, 0), (8700, 6, 0), (10000, 9, 0), (8000, 12, 0), (hi, 3, 0),
            (3000, 20, 0), (2000, 1, 0), (3424, 40, 3)]+[(3425-i % 2, 1, 0) for i in range(12)]+[(3424, 1, 4)]
    x, y, f = 2800, 300, 0
    for tx, speed, hold in legs:
        tx = min(tx, hi)
        while x != tx:
            x += max(-speed, min(speed, tx-x)) if speed else 0
            if not speed:
                break
            y = 300+((f//50) % 3)*(-1 if f % 7 else 1)*6
            f += 1
            yield x, y, (f//400) % 2, (f//333) % 2
        for _ in range(hold):
            f += 1
            yield x, y, (f//400) % 2, (f//333) % 2


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O1', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc',
                    'src/background_r5.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    for f in ('scd_r5_step', 'scd_r5_set_enkei'):
        getattr(native, f).argtypes = [C.c_uint, C.c_int] + ([C.c_int] if f == 'scd_r5_set_enkei' else [])
    native.scd_r5_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    native.scd_r5_palette.argtypes = [C.c_uint, C.c_uint, C.c_void_p]
    frames = entries_changed = switches = 0
    for pid in PROGRAMS:
        orig = original(pid)
        expected = (C.c_uint16*64)()
        actual = (C.c_uint16*64)()
        native.scd_r5_set_colrev(0)
        native.scd_r5_set_boss(0)
        x, y = 2800, 300
        orig.init(x+160, pid)
        native.scd_r5_reset(x)
        native.scd_r5_background_y(pid, y, x+160)
        orig.read_colors(expected)
        base = bytes(expected)
        prev = bytes(expected)
        last = (x, y)
        enkei = orig.enkei()
        for f, (x, y, colrev, boss) in enumerate([(x, y, 0, 0)]+list(route(pid//4))):
            if f:
                crossed = bool(((last[0] ^ x) | (last[1] ^ y)) & 16)
                orig.step(x+160, crossed, colrev, boss)
                native.scd_r5_set_colrev(colrev)
                native.scd_r5_set_boss(boss)
                native.scd_r5_step(pid, x)
                native.scd_r5_background_y(pid, y, x+160)
                last = (x, y)
            orig.read_colors(expected)
            if orig.enkei() != native.scd_r5_enkei() and orig.enkei() != enkei:
                pass  # native reports the enkeino this frame's scroll used
            switches += orig.enkei() != enkei
            enkei = orig.enkei()
            for _ in range(2):  # a repeated (paused) display call must not advance
                src = C.create_string_buffer(base, 128)
                C.memmove(actual, src, 128)
                native.scd_r5_palette(pid, f, actual)
                if list(actual) != list(expected):
                    bad = [(i, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
                    raise AssertionError((PROGRAMS[pid], f, x, y, colrev, boss, orig.enkei(), bad[:4]))
            entries_changed += bytes(expected) != prev
            prev = bytes(expected)
            frames += 1
    print(f'PASS: QQ palette: {frames} compiled-original/native COL5A-D frames ({frames*64} entries, '
          f'{entries_changed} changes, {switches} enkeichg switches) across 10 programs')


if __name__ == '__main__':
    main()
