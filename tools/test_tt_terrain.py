#!/usr/bin/env python3
"""Native Tidal Tempest fire tiles vs the compiled original DEV41A.C cg_change.

Drives both with one camera path that leaves and re-enters the X < 640 / Y < 352
fire area, and checks every tick: the frame each slot shows, the cell it
writes, and that the art is the retail frame assets/generated/tt_terrain.inc holds.
Every other R4 program (DEV41B-D, DEV42x, DEV43x are stubs) must report no slots.
"""
import ctypes as C
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import tt_terrain_assets as T  # noqa: E402

OUT = ROOT/'build/tt/terrain'


class Write(C.Structure):
    _fields_ = [('cell', C.c_uint16), ('cells', C.c_uint16), ('art', C.c_void_p), ('frame', C.c_uint)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc', '-Iassets/generated',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    native.scd_background_tile_cycle.argtypes = [C.c_uint, C.c_uint, C.POINTER(Write)]
    native.scd_background_tile_cycle.restype = C.c_uint
    native.scd_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    native.scd_background_reset.argtypes = [C.c_void_p, C.c_int]
    inc = (ROOT/'assets/generated/tt_terrain.inc').read_text()
    cells = [int(v) for v in re.search(r'r4_fire_cell\[3\] = \{([^}]*)\}', inc)[1].split(',')]
    orig = T.oracle()
    orig.init()
    scroll = C.create_string_buffer(64)
    out = (Write*3)()
    legs = [(0, 12), (300, 200), (700, 100), (100, 400), (639, 351), (640, 0), (200, 100)]
    ticks = 0
    for tick in range(4000):
        x, y = legs[(tick//293) % len(legs)]
        native.scd_background_reset(scroll, x)
        native.scd_background_y(24, y, 0)
        orig.step(x, y)
        n = native.scd_background_tile_cycle(24, tick, out)
        assert n == 3, n
        for s in range(3):
            first = orig.tile(T.SLOTS[s])
            want = first//16 if first >= 0 else 0
            got = out[s].frame >> (3*s) & 7
            assert out[s].cell == cells[s] and out[s].cells == 16, (tick, s, out[s].cell)
            assert got == want, (tick, x, y, s, got, want)
            if s:
                assert out[s].art - out[0].art == (s*8+got)*512 - (out[0].frame & 7)*512, (tick, s)
        ticks += 1
    for pid in (1, 2, 3, 4, 5, 6, 7, 10, 11):
        assert native.scd_background_tile_cycle(24+pid, 0, out) == 0, pid
    print(f'PASS: TT fire tiles: {ticks} native/compiled-original DEV41A ticks x 3 slots match; 9 stub programs have no slots')


if __name__ == '__main__':
    main()
