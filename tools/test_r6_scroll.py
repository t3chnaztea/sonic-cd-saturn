#!/usr/bin/env python3
"""Compare native Wacky Workbench scroll (src/background_r6.c) with the compiled
original SCR61A-D, SCR62A-D and SCR63C/D.C scroll() and with retail CPU captures
(tools/capture_r6_scroll.py).

Source gate: each program's scroll() and everything it reaches (z6?aline /
z81aline, zonescrsetsub0, scrollb/c/z_h, scrollb_v, ETC.C sinset) are compiled
unchanged by tools/scroll/R6/oracle.generate, plus scrbinit(); only scrchk,
scroll_h and scroll_v are empty (the camera is the input).  Camera walks move
X by up to 16 px per update in both directions and sweep camera Y 0..2047.
Every update, the native layer accumulators (scd_r6_layers_reset/step) must
equal scrb/scrc/scrz_h_posit, native background Y must equal scrb_v_posit, and
both words of all 224 hscroll lines must match.  Uninitialised locals (the
radwk fraction in SCR61B/SCR62B) are zero here; the retail gate covers them.
Retail gate: both words of all 224 lines of every capture.
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
sys.path.insert(0, str(ROOT/'tools/scroll'))
sys.path.insert(0, str(ROOT/'tools/scroll/R6'))
from test_cc_palette import function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src'
PROGRAMS = {0: 'SCR61A', 1: 'SCR61B', 2: 'SCR61C', 3: 'SCR61D', 4: 'SCR62A', 5: 'SCR62B', 6: 'SCR62C',
            7: 'SCR62D', 10: 'SCR63C', 11: 'SCR63D'}
OUT = ROOT/'build/ww/scroll-native'
HARNESS = r'''
static int_union buf[240];
unsigned short retail_frac;
void init(int x, int y) {
    memset(hscrollwork, 0, sizeof hscrollwork);
    scra_h_posit.l = x << 16; scra_v_posit.l = y << 16;
    scrb_h_posit.l = scrc_h_posit.l = scrz_h_posit.l = 0;
    scrb_h_count = scrc_h_count = scrz_h_count = scrb_v_count = 0;
    scrbinit((short)x, (short)y);
}
void step(int x, int y, int set, const int *layers, int *out, int *state) {
    scra_hz = set ? (short)(set >> 1) : (short)((x - scra_h_posit.w.h) * 256);
    retail_frac = (unsigned short)((unsigned)((int)scra_hz * 32) >> 16);
    scra_h_posit.w.h = (short)x; scra_v_posit.w.h = (short)y;
    if (set) { scrb_h_posit.l = layers[0]; scrc_h_posit.l = layers[1]; scrz_h_posit.l = layers[2]; }
    /* set: the layers are this update's result; undo the step scroll() adds */
    if (set) { scrb_h_posit.l -= scra_hz * 48; scrc_h_posit.l -= scra_hz << 7; scrz_h_posit.l -= scra_hz << 6; }
    for (int i = 0; i < 240; i++) buf[i].l = 0x7fff7fff;
    scroll_start.w = 0; lphscrollbuff = buf;
    scroll();
    for (int i = 0; i < 224; i++) out[i] = buf[i].l;
    state[0] = scrb_h_posit.l; state[1] = scrc_h_posit.l; state[2] = scrz_h_posit.l; state[3] = scrb_v_posit.w.h;
}
'''


def original(name):
    import oracle
    path = SOURCE/'R6'/f'{name}.C'
    src, _ = oracle.generate(path, name.lower())
    src = src[:src.index('#define ORACLE_IR')].replace('#include "evaluate_ext.h"\n', '')
    if 'z81aline' in src:
        # Retail 68000 z81aline (R61B 0x2a98, R62B the same): the difference is
        # a word, divu.w #17 is unsigned and leaves the dividend on overflow,
        # and radwk's fraction is the high word of scroll()'s hz*32.  The C has
        # a signed divide and reads radwk.w.h uninitialised; retail captures
        # prove the retail rules.
        for old, new in [('  lXwk <<= 7;', '  lXwk = (short)lXwk; lXwk <<= 7;'),
                         ('  lXwk /= 17;', '  { unsigned int u = (unsigned int)lXwk / 17u; lXwk = (short)(u > 65535u ? (unsigned short)lXwk : (unsigned short)u); }'),
                         ('  radwk.w.l = scrb_h_posit.w.h;', '  radwk.w.l = scrb_h_posit.w.h; radwk.w.h = retail_frac;')]:
            assert src.count(old) == 1, (name, old)
            src = src.replace(old, new)
        src = src.replace('short hscrollwork[256];', 'short hscrollwork[256];\nextern unsigned short retail_frac;', 1)
    # Retail z6?aline (R61C 0x2ab4, all lerp programs): sub.w word difference,
    # muls.w, lsr.l #8, add.w.  Five decompiled files narrow the product to an
    # unsigned short instead; retail captures prove the retail rule.
    src = src.replace('  lXwk = scra_h_posit.w.h - scrb_h_posit.w.h;', '  lXwk = (short)(scra_h_posit.w.h - scrb_h_posit.w.h);')
    src = src.replace('(short)((unsigned short)((256 - coswk) * lXwk) >> 8)', '(short)((unsigned int)((256 - coswk) * lXwk) >> 8)')
    text = path.read_text()
    init = function(text, 'scrbinit')
    src += '\nstatic void scrbinit(short, short);\n'+init+'\n'+HARNESS
    OUT.mkdir(parents=True, exist_ok=True)
    c = OUT/f'original-{name}.c'
    c.write_text(src)
    lib = c.with_suffix('.dylib')
    subprocess.run(['clang', '-std=gnu99', '-O1', '-fwrapv', '-fno-strict-aliasing', '-w', '-ftrivial-auto-var-init=zero',
                    '-shared', '-fPIC', f'-I{path.parent}', f'-I{SOURCE}', f'-I{ROOT}/tools/scroll/R6', str(c), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.init.argtypes = [C.c_int, C.c_int]
    dll.step.argtypes = [C.c_int, C.c_int, C.c_int, C.POINTER(C.c_int), C.POINTER(C.c_int32), C.POINTER(C.c_int32)]
    return dll


def native_lib():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-Isrc', '-dynamiclib',
                    'src/background_r6.c', '-o', str(lib)], cwd=ROOT, check=True)
    n = C.CDLL(str(lib))
    n.scd_r6_layers_reset.argtypes = [C.c_int, C.POINTER(C.c_int32)]
    n.scd_r6_layers_step.argtypes = [C.c_int, C.POINTER(C.c_int32)]
    n.scd_r6_lines_layers.argtypes = [C.c_uint, C.c_int, C.POINTER(C.c_int32), C.c_int,
                                      C.POINTER(C.c_int32), C.POINTER(C.c_int32), C.c_uint]
    n.scd_r6_background_y.argtypes = [C.c_uint, C.c_int]
    return n


def compare(tag, pid, x, top, lay, out, native, bg, fg):
    native.scd_r6_lines_layers(pid, x, lay, top, bg, fg, 224)
    for i in range(224):
        want = ((-C.c_int16(out[i] & 0xffff).value) & 511, (-(out[i] >> 16)) & 511)
        got = ((bg[i] >> 16) & 511, (fg[i] >> 16) & 511)
        if got != want:
            raise AssertionError((tag, x, top, i, got, want, [lay[j] >> 16 for j in range(3)]))
    return 448


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--full', action='store_true', help='longer walks')
    args = ap.parse_args()
    native = native_lib()
    bg, fg = (C.c_int32*232)(), (C.c_int32*232)()
    out, state = (C.c_int32*224)(), (C.c_int32*4)()
    zero = (C.c_int*3)()
    rng = random.Random(6)
    words = updates = 0
    for pid, name in PROGRAMS.items():
        orig = original(name)
        walks = 12 if args.full else 3
        for walk in range(walks):
            x, y = rng.randrange(0, 12000), rng.randrange(0, 2048)
            orig.init(x, y)
            lay = (C.c_int32*4)()
            native.scd_r6_layers_reset(x, lay)
            dx = rng.choice((-16, -5, -1, 1, 3, 16))
            for n in range(4000 if args.full else 1200):
                if rng.random() < 0.05:
                    dx = rng.randrange(-16, 17)
                nx = max(-4096, min(16383, x+dx))
                y = (y+rng.choice((-8, -1, 0, 1, 8))) & 2047
                orig.step(nx, y, 0, zero, out, state)
                native.scd_r6_layers_step(nx-x, lay)
                x = nx
                if tuple(lay[:3]) != tuple(state[:3]):
                    raise AssertionError((name, 'layers', walk, n, x, list(lay), list(state[:3])))
                top = native.scd_r6_background_y(pid, y)
                assert top == state[3], (name, 'background Y', y, top, state[3])
                words += compare(name, pid, x, top, lay, out, native, bg, fg)
                updates += 1
        # scrbinit, compared exactly from a fresh start (no camera move)
        for x in (0, 1, 15, 16, 255, 4095, 12345, 16383, -1, -4096):
            orig.init(x, 400)
            lay = (C.c_int32*4)()
            native.scd_r6_layers_reset(x, lay)
            orig.step(x, 400, 0, zero, out, state)
            assert tuple(lay[:3]) == tuple(state[:3]), (name, 'scrbinit', x, list(lay), list(state[:3]))
        # arbitrary layer words
        for _ in range(300 if args.full else 100):
            x, y = rng.randrange(-4096, 16384), rng.randrange(0, 2048)
            layers = (C.c_int*3)(*(rng.randrange(-1 << 31, 1 << 31) for _ in range(3)))
            hz = rng.randrange(-16, 17)*256
            orig.init(x, y)
            orig.step(x, y, (hz << 1) | 1, layers, out, state)
            lay = (C.c_int32*4)(*layers, ((hz*32) >> 16) & 0xffff)
            words += compare(name, pid, x, state[3], lay, out, native, bg, fg)
    captures = 0
    for pid, name in PROGRAMS.items():
        prog = 'R6'+name[4:]
        base = ROOT/'build/ww/scroll-retail'/prog
        report = json.loads((base/'report.json').read_text())
        for s in report['samples']:
            a, pin = s['actual_16_16'], s['inputs']
            raw = (base/f'{s["index"]:03}-hscroll.bin').read_bytes()
            # A libretro frame can end inside the next update's scroll(), so the
            # layer words read afterwards may be half-stepped.  The scroll() that
            # wrote this table started from the pinned words and moved the camera
            # by hz (its hscroll high word is -camera X): rebuild what it used.
            x = -struct.unpack_from('>h', raw, 0)[0]
            dx = C.c_int16(x - (pin['cameraX'] >> 16)).value
            lay = (C.c_int32*4)(pin['cameraBgX'], pin['cameraBg2X'], pin['cameraBg3X'], 0)
            native.scd_r6_layers_step(dx, lay)
            y, top = a['cameraY'] >> 16, a['cameraBgY'] >> 16
            assert native.scd_r6_background_y(pid, y) == top, (prog, 'capture background Y', s['index'], y, top)
            for i in range(224):
                f, b = struct.unpack_from('>hh', raw, i*4)
                out[i] = (f << 16) | (b & 0xffff)
            words += compare(prog+f'#{s["index"]}', pid, x, top, lay, out, native, bg, fg)
            captures += 1
    n = C.CDLL(str(OUT/'native.dylib'))
    assert [i for i in range(32) if n.scd_r6_valid(i)] == sorted(PROGRAMS), 'scd_r6_valid'
    print(f'PASS: WW scroll: {words} original/native line words over {updates} compiled-original updates of 10 programs '
          f'and {captures} retail captures')


if __name__ == '__main__':
    main()
