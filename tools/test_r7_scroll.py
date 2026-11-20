#!/usr/bin/env python3
"""Native Stardust Speedway scroll (src/background_r7.c) vs retail CPU captures.

Every capture of tools/capture_r7_scroll.py (68 per program: camera sweeps and
random layer words, SCR71B/72B with their waterdirec phase) must match native
in both words of all 224 hscroll lines and in background Y.  A libretro frame
can end inside the next update's scroll(), so the words that scroll() used are
rebuilt from the pinned inputs: the camera X from the table's high word,
the layers stepped by that update's hz (scd_r7_layers_step), which also sets
the d3 fraction the first chain inherits.  The decompiled SCR7*.C is not the
oracle (see tools/background_r7_assets.py); --c-report counts its differences.
"""
import argparse
import ctypes as C
import json
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = {0: '1A', 1: '1B', 2: '1C', 3: '1D', 4: '2A', 5: '2B', 6: '2C', 7: '2D', 10: '3C', 11: '3D'}
OUT = ROOT/'build/ss/scroll-native'


def native_lib():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-Isrc', '-dynamiclib',
                    'src/background_r7.c', '-o', str(lib)], cwd=ROOT, check=True)
    n = C.CDLL(str(lib))
    n.scd_r7_layers_step.argtypes = [C.c_uint, C.c_int, C.POINTER(C.c_int32)]
    n.scd_r7_lines_layers.argtypes = [C.c_uint, C.c_int, C.POINTER(C.c_int32), C.c_int, C.c_uint,
                                      C.POINTER(C.c_int32), C.POINTER(C.c_int32), C.c_uint]
    n.scd_r7_background_y.argtypes = [C.c_uint, C.c_int]
    n.scd_r7_force_hz.argtypes = [C.c_int32]
    return n


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    native = native_lib()
    bg, fg = (C.c_int32*232)(), (C.c_int32*232)()
    words = captures = 0
    for pid, p in PROGRAMS.items():
        base = ROOT/'build/ss/scroll-retail'/f'R7{p}'
        report = json.loads((base/'report.json').read_text())
        for s in report['samples']:
            a, pin = s['actual_16_16'], s['inputs']
            raw = (base/f'{s["index"]:03}-hscroll.bin').read_bytes()
            x = -struct.unpack_from('>h', raw, 0)[0]
            hz = s['scroll_x_diff_8_8']
            lay = (C.c_int32*4)(pin['cameraBgX'], pin['cameraBg2X'], pin['cameraBg3X'], 0)
            native.scd_r7_force_hz(hz)
            native.scd_r7_layers_step(pid, 0, lay)
            native.scd_r7_force_hz(0x7fffffff)
            y, top = a['cameraY'] >> 16, a['cameraBgY'] >> 16
            got_top = native.scd_r7_background_y(pid, y)
            assert got_top == top, (p, 'background Y', s['index'], y, got_top, top)
            water = s.get('water_phase_before') or 0
            native.scd_r7_lines_layers(pid, x, lay, top, water, bg, fg, 224)
            for i in range(224):
                f, b = struct.unpack_from('>hh', raw, i*4)
                got = ((bg[i] >> 16) & 511, (fg[i] >> 16) & 511)
                if got != ((-b) & 511, (-f) & 511):
                    raise AssertionError((f'R7{p}', s['index'], x, hz, top, water, i, got, ((-b) & 511, (-f) & 511),
                                          [v >> 16 for v in lay[:3]]))
                words += 2
            captures += 1
    assert [i for i in range(40) if native.scd_r7_valid(i)] == sorted(PROGRAMS)+[12+i for i in sorted(PROGRAMS)], 'scd_r7_valid'
    print(f'PASS: SS scroll: {words} retail/native line words across {captures} retail captures of 10 programs')


if __name__ == '__main__':
    main()
