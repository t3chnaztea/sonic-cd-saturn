#!/usr/bin/env python3
"""Capture original Sega CD Wacky Workbench (R6) scroll output for camera fixtures.

Boots the original R6<act><era> program (tools/capture_cc_scroll.boot), pins
the camera, the three background layers and Sonic (at the camera's follow
point, so scroll_h/scroll_v leave the camera still) for 8 updates, then
records the CPU-produced hscroll table and the camera/layer words the last
scroll() used.  R6 scroll() has no frame-dependent term.

    python3 tools/capture_r6_scroll.py 1 A      one program
    python3 tools/capture_r6_scroll.py --all    all ten
"""
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot
from zone_object_source import dependencies

KEYS = ['cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg2Y', 'cameraBg3X', 'cameraBg3Y']
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']


def capture(act, era, out):
    core, e, frame, program = boot(era, act, 6)
    name = f'R6{act}{era}'
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f'{act}{era}')
    ys = [0, 96, 240, 600, 1000, 1500, 1808]
    fixtures = [(x, y, None) for x in [0, 1, 31, 255, 1001, 4093, 8191, 11800] for y in ys]
    fixtures += [(rng.randrange(0, 12000), rng.choice(ys), [rng.randrange(0, 1 << 26) for _ in range(3)]) for _ in range(12)]
    samples = []
    for index, (x, y, layers) in enumerate(fixtures):
        u = x & 0xffff
        bg = layers or [((u >> 4)*3) << 16, (u >> 1) << 16, (u >> 2) << 16]
        by = (y & 0xffff) >> 2
        inputs = dict(cameraX=x << 16, cameraY=y << 16, cameraBgX=bg[0], cameraBgY=by << 16,
                      cameraBg2X=bg[1], cameraBg2Y=by << 16, cameraBg3X=bg[2], cameraBg3Y=by << 16)
        player = bytearray(core.work_read(e['objPlayerSlot'], 64))
        struct.pack_into('>I', player, e['oX'], (x+160)*65536)
        struct.pack_into('>I', player, e['oY'], (y+96)*65536)
        player[e['oXVel']:e['oXVel']+6] = bytes(6)
        player[e['oFlags']] = 2
        player[e['oRoutine']] = 2
        player[0x2c] = 0
        player[0x30:0x32] = struct.pack('>H', 120)
        for _ in range(8):
            core.work_write(e['objPlayerSlot'], player)
            for key, value in inputs.items():
                core.work_write(e[key], struct.pack('>I', value & 0xffffffff))
            core.pad = 0
            core.run()
            frame += 1
            core.host.chunks.clear()
        scroll = core.work_read(e['hscroll'], 1024)
        deform = core.work_read(e['deformBuffer'], 512)
        actual = {key: struct.unpack('>i', core.work_read(e[key], 4))[0] for key in KEYS}
        # scra_hz of that update: R61B/R62B z81aline reads a fraction left from hz*32.
        scroll_dx = struct.unpack('>h', core.work_read(e['scrollXDiff'], 2))[0]
        (out/f'{index:03}-hscroll.bin').write_bytes(scroll)
        (out/f'{index:03}-deform-after.bin').write_bytes(deform)
        samples.append(dict(index=index, frame=frame, inputs=inputs, actual_16_16=actual, scroll_x_diff_8_8=scroll_dx,
                            scroll_sha256=hashlib.sha256(scroll).hexdigest()))
    report = dict(program=name, program_sha256=hashlib.sha256(program).hexdigest(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), dependencies=dependencies(),
                  addresses={key: e[key] for key in KEYS+['deformBuffer', 'hscroll', 'objPlayerSlot', 'scrollXDiff']},
                  samples=samples,
                  limits='Original CPU output after explicit camera/layer/player fixtures. No claim of gameplay routes.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(name, len(samples), 'original CPU scroll fixtures', out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('act', type=int, nargs='?', choices=(1, 2, 3))
    parser.add_argument('era', nargs='?', choices=list('ABCD'))
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    todo = PROGRAMS if args.all else [f'{args.act}{args.era}']
    for p in todo:
        capture(int(p[0]), p[1], sr.ROOT/'build/ww/scroll-retail'/f'R6{p}')


if __name__ == '__main__':
    main()
