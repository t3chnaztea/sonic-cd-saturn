#!/usr/bin/env python3
"""Native Stardust Speedway COL7A-D palette scripts vs the retail CPU.

Boots each retail R7<act><era> program and records CRAM for 900 vblanks.  For
the entries the scripts write (src/background_r7_palette.inc), native
scd_background_palette(60+id, frame) must show the same colors at every
update for one frame offset (boot leaves the timers at an arbitrary phase; the
offset is searched).  COL7B/COL7C have no scripts: native must leave the base
palette untouched.  The PC COL7x.C tables are cross-checked byte for byte in
the MMDs by tools/ss_palette_assets.py.
"""
import ctypes as C
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from capture_cc_scroll import boot  # noqa: E402

OUT = ROOT/'build/ss/palette'
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']


def saturn(md):
    b, g, r = md >> 9 & 7, md >> 5 & 7, md >> 1 & 7
    return 0x8000 | (r*31//7) | (g*31//7) << 5 | (b*31//7) << 10


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc', '-Iassets/generated',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    native.scd_background_palette.argtypes = [C.c_uint, C.c_uint, C.c_void_p, C.c_void_p]
    inc = (ROOT/'src/background_r7_palette.inc').read_text()
    frames, checked = 900, 0
    for p in PROGRAMS:
        pid = (int(p[0])-1)*4+'ABCD'.index(p[1])
        indices = sorted({int(m[1]) for m in re.finditer(r'r7_%s\d_script\[\d+\] = \{(\d+),' % p[1], inc)} ^
                         ({58, 62} if p[1] == 'D' and p[0] != '1' else set()))  # Acts 2/3 run 62, not 58
        core, e, _, _ = boot(p[1], int(p[0]), 7)
        cram = []
        for _ in range(frames):
            core.pad = 0
            core.run()
            core.host.chunks.clear()
            v = struct.unpack('<64H', C.string_at(core.cram, 128))
            cram.append([saturn((x >> 6 & 7) << 9 | (x >> 3 & 7) << 5 | (x & 7) << 1) for x in v])
        base = C.create_string_buffer(bytes(128))
        out = (C.c_uint16*64)()
        if not indices:
            native.scd_background_palette(60+pid, 500, base, out)
            assert list(out) == [0]*64, p
            continue
        found = None
        for lag in range(0, 3000):
            ok = True
            for f in range(0, frames):
                native.scd_background_palette(60+pid, f+lag, base, out)
                if any(out[i] != cram[f][i] for i in indices):
                    ok = False
                    break
            if ok:
                found = lag
                break
            native.scd_background_palette(60+pid, 0, base, out)
        if found is None:
            raise SystemExit(f'FAIL: SS palette: R7{p} matches no frame offset (entries {indices})')
        checked += frames*len(indices)
    print(f'PASS: SS palette: {checked} retail CRAM entry-frames of the COL7A/COL7D scripts match native; COL7B/C leave the base')


if __name__ == '__main__':
    main()
