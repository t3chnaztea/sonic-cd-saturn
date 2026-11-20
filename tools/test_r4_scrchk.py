#!/usr/bin/env python3
"""Retail proof of SCRCHK4.C zone42chk for R42A-D.

The reconstructed C compares (camera X << 16) with 512; the retail CPU
switches Tidal Tempest Act 2's bottom bound from 2048 to 1808 exactly when
camera X reaches 512, and back below it, with no 4-line easing.  src/main.c
implements the retail rule; this test re-derives it from the original program.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from capture_cc_scroll import boot  # noqa: E402


def main():
    checks = 0
    for era in 'ABCD':
        core, e, _, _ = boot(era, 2, 4)

        def word(key):
            return struct.unpack('>h', core.work_read(e[key], 2))[0]
        for player_x in (671, 672, 1000, 671, 300, 673):
            for _ in range(60):
                p = bytearray(core.work_read(e['objPlayerSlot'], 64))
                struct.pack_into('>I', p, e['oX'], player_x*65536)
                core.work_write(e['objPlayerSlot'], p)
                core.pad = 0
                core.run()
                core.host.chunks.clear()
            cam = word('cameraX')
            want = 2048 if cam < 512 else 1808
            got = (word('destBottomBound'), word('bottomBound'))
            assert got == (want, want), (f'R42{era}', player_x, cam, got, want)
            checks += 1
    print(f'PASS: TT2 zone42chk: {checks} retail R42A-D bottom-bound probes switch at camera X 512')


if __name__ == '__main__':
    main()
