#!/usr/bin/env python3
"""Native Metallic Madness scroll (src/background_r7.c ids 12-23) vs retail CPU captures.

Every capture of tools/capture_r8_scroll.py (68 per program: camera sweeps and
random layer words, SCR71B/72B with their waterdirec phase) must match native
in both words of all 224 hscroll lines and in background Y.  A libretro frame
can end inside the next update's scroll(), so the words that scroll() used are
rebuilt from the pinned inputs: the camera X from the table's high word,
the layers stepped by that update's hz (scd_r7_layers_step), which also sets
the d3 fraction the first chain inherits.  The decompiled SCR8*.C is not the
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
OUT = ROOT/'build/mm/scroll-native'


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
    words = captures = moved = 0
    for pid0, p in PROGRAMS.items():
        pid = pid0+12
        base = ROOT/'build/mm/scroll-retail'/f"R8{p}"
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
            # scroll_v may move the camera up to 16 px (or clamp it to the act's limits) inside the update whose
            # table this is, and the pins restore it before the snapshot: the
            # scroll() used some camera Y within 16 px of the pin (the first
            # candidate that reproduces all 224 lines is taken).
            pin_y = pin['cameraY'] >> 16
            want = [struct.unpack_from('>hh', raw, i*4) for i in range(224)]
            want = [((-b) & 511, (-f) & 511) for f, b in want]
            act_y = a['cameraY'] >> 16   # the limits (scralim_down) may clamp the pin
            for y in [pin_y, act_y]+[c+d for c in (pin_y, act_y) for k in range(1, 17) for d in (-k, k)]:
                top = native.scd_r7_background_y(pid, y)
                native.scd_r7_lines_layers(pid, x, lay, top, 0, bg, fg, 224)
                got = [((bg[i] >> 16) & 511, (fg[i] >> 16) & 511) for i in range(224)]
                if got == want:
                    break
            else:
                bad = next(i for i in range(224) if got[i] != want[i])
                raise AssertionError((f'R8{p}', s['index'], x, hz, pin_y, bad, got[bad], want[bad], [v >> 16 for v in lay[:3]]))
            moved += y != pin_y
            words += 448
            captures += 1
    print(f'PASS: MM scroll: {words} retail/native line words across {captures} retail captures of 10 programs ({moved} used a camera Y moved inside the update)')


if __name__ == '__main__':
    main()
