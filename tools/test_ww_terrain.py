#!/usr/bin/env python3
"""Native Wacky Workbench animated tiles vs the retail CPU, all ten programs.

Boots each retail R6<act><era> (tools/capture_cc_scroll.boot) and records the
VRAM blocks every UpdateAnimTiles call writes (assets/generated/ww_terrain.inc,
from tools/ww_terrain_assets.py) for 900 vblanks.  Native
scd_background_tile_cycle(48+id, tick) must show the same art in every block
at every vblank for one tick offset (boot leaves the timers at an arbitrary
phase; the offset is searched).  R63C/R63D then get bossflag bit 6 poked into
retail RAM: the thunder block must clear, bit 7 must be set, and the block
must stay clear, as the native routine does with scd_r6_set_bossflag.

The PC DEV6x.C is not the oracle here: its tbl_sp timer is 2 where retail
reloads 3, its R61C/R62C gate decrements and xors the timer itself where
retail toggles frame2 and reloads 90/30, and its R63C/R63D clear bossflag
bit 6 on every call; the retail CPU is the authority.
"""
import ctypes as C
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from capture_cc_scroll import boot  # noqa: E402

OUT = ROOT/'build/ww/terrain'
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']
BOSSFLAG = 0xfff7a7


class Write(C.Structure):
    _fields_ = [('cell', C.c_uint16), ('cells', C.c_uint16), ('art', C.c_void_p), ('frame', C.c_uint)]


def native_lib():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    import subprocess
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc', '-Iassets/generated',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib)], cwd=ROOT, check=True)
    n = C.CDLL(str(lib))
    n.scd_background_tile_cycle.argtypes = [C.c_uint, C.c_uint, C.POINTER(Write)]
    n.scd_background_tile_cycle.restype = C.c_uint
    n.scd_r6_set_bossflag.argtypes = [C.c_uint]
    n.scd_r6_bossflag.restype = C.c_uint
    return n


def native_blocks(native, era, tick, out):
    n = native.scd_background_tile_cycle(era, tick, out)
    return [(out[i].cell, C.string_at(out[i].art, out[i].cells*32)) for i in range(n)]


def main():
    native = native_lib()
    out = (Write*3)()
    frames = 900
    total = 0
    offsets = {}
    for p in PROGRAMS:
        pid = (int(p[0])-1)*4+'ABCD'.index(p[1])
        era = 48+pid
        native.scd_r6_set_bossflag(0)
        cells = [(w[0], len(w[1])) for w in native_blocks(native, era, 0, out)]
        assert cells, p
        core, e, _, _ = boot(p[1], int(p[0]), 6)
        boss = p[0] == '3'
        retail = []
        for f in range(frames+(300 if boss else 0)):
            if boss and f == frames:
                w = bytearray(core.work_read(BOSSFLAG-1, 2))   # word-aligned access
                w[1] |= 64
                core.work_write(BOSSFLAG-1, bytes(w))
            core.pad = 0
            core.run()
            core.host.chunks.clear()
            retail.append([core.swapped(core.vram, c*32, size) for c, size in cells])
        found = None
        for lag in range(0, 4000):
            native.scd_r6_set_bossflag(0)
            ok = True
            for f in range(frames):
                got = [w[1] for w in native_blocks(native, era, f+lag, out)]
                if got != retail[f]:
                    ok = False
                    break
            if ok:
                found = lag
                break
        if found is None:
            raise SystemExit(f'FAIL: WW animated tiles: R6{p} matches no tick offset')
        offsets[p] = found
        total += frames*len(cells)
        if boss:
            # the poke lands before update `frames`; replay with the flag set there
            native.scd_r6_set_bossflag(0)
            native_blocks(native, era, found+frames-1, out)
            native.scd_r6_set_bossflag(64)
            for f in range(frames, frames+300):
                got = [w[1] for w in native_blocks(native, era, f+found, out)]
                assert got == retail[f], (p, 'boss', f)
            flag = core.work_read(BOSSFLAG-1, 2)[1]
            assert flag & 0xc0 == 0x80 and native.scd_r6_bossflag() & 0xc0 == 0x80, (p, hex(flag))
            assert retail[-1][0] == bytes(len(retail[-1][0])), (p, 'thunder block not cleared')
            total += 300*len(cells)
    (OUT/'offsets.json').write_text(json.dumps(offsets)+'\n')
    print(f'PASS: WW animated tiles: {total} retail VRAM block frames of 10 programs match native '
          f'(R63C/R63D bossflag bit 6 clear and bit 7 hold included)')


if __name__ == '__main__':
    main()
