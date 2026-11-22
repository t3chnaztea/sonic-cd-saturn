#!/usr/bin/env python3
"""Capture original Sega CD Metallic Madness (R8) scroll output for camera fixtures.

Boots the original R8<act><era> program (tools/capture_cc_scroll.boot), pins
the camera, the three background layers and Sonic (at the camera's follow
point, so scroll_h/scroll_v leave the camera still) for 8 updates, then
records the CPU-produced hscroll table and the camera/layer words the last
scroll() used.  SCR71B/72B also record waterdirec (the wave phase, +128 per scroll()).

    python3 tools/capture_r8_scroll.py 1 A      one program
    python3 tools/capture_r8_scroll.py --all    all ten
"""
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot
from capture_r4_scroll import find_phase
from zone_object_source import dependencies

ROUND = 8
KEYS = ['cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg2Y', 'cameraBg3X', 'cameraBg3Y']
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']


def pin_run(core, e, player, inputs, phase_at):
    """8 updates with the fixture pinned; the last one must run scroll(): a
    sentinel written over the hscroll buffer before it must be overwritten."""
    phase = None
    for n in range(8):
        if phase_at:
            phase = struct.unpack('>H', core.work_read(phase_at, 2))[0]
        core.work_write(e['objPlayerSlot'], player)
        for key, value in inputs.items():
            core.work_write(e[key], struct.pack('>I', value & 0xffffffff))
        if n == 7:
            core.work_write(e['hscroll'], b'\x55'*1024)
        core.pad = 0
        core.run()
        core.host.chunks.clear()
    table = core.work_read(e['hscroll'], 896)
    done = all(table[i:i+2] != b'\x55\x55' for i in range(0, 896, 2))
    return (True, phase) if done else None


def capture(act, era, out):
    core, e, frame, program = boot(era, act, 8)
    name = f'R8{act}{era}'
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f'{act}{era}')
    phase_at = None  # R8 scroll() has no wave phase
    ys = [0, 96, 240, 600, 1000, 1500, 1808]
    fixtures = [(x, y, None) for x in [0, 1, 31, 255, 1001, 4093, 8191, 11800] for y in ys]
    fixtures += [(rng.randrange(0, 12000), rng.choice(ys), [rng.randrange(0, 1 << 26) for _ in range(3)]) for _ in range(12)]
    samples, skipped = [], []
    for index, (x, y, layers) in enumerate(fixtures):
        u = x & 0xffff
        bg = layers or [((u >> 4)*3) << 16, (u >> 1) << 16, (u >> 2) << 16]
        by = (y & 0xffff) >> 3
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
        phase = None
        for attempt in range(2):
            ok = pin_run(core, e, player, inputs, phase_at)
            if ok:
                break
            # scroll() stopped (Sonic died in a hazard and the level froze):
            # boot the program again and retry the fixture once.
            core, e, frame, program = boot(era, act, ROUND)
        if not ok:
            # this camera/player fixture stops scroll() even after a fresh boot
            # (a hazard at Sonic's pinned spot): record it as skipped
            skipped.append(index)
            core, e, frame, program = boot(era, act, ROUND)
            continue
        phase = ok[1]
        scroll = core.work_read(e['hscroll'], 1024)
        deform = core.work_read(e['deformBuffer'], 512)
        actual = {key: struct.unpack('>i', core.work_read(e[key], 4))[0] for key in KEYS}
        # scra_hz of that update.
        scroll_dx = struct.unpack('>h', core.work_read(e['scrollXDiff'], 2))[0]
        (out/f'{index:03}-hscroll.bin').write_bytes(scroll)
        (out/f'{index:03}-deform-after.bin').write_bytes(deform)
        samples.append(dict(index=index, frame=frame, inputs=inputs, actual_16_16=actual, scroll_x_diff_8_8=scroll_dx, water_phase_before=phase,
                            scroll_sha256=hashlib.sha256(scroll).hexdigest()))
    report = dict(program=name, program_sha256=hashlib.sha256(program).hexdigest(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), dependencies=dependencies(),
                  addresses={key: e[key] for key in KEYS+['deformBuffer', 'hscroll', 'objPlayerSlot', 'scrollXDiff']}|({'waterdirec': phase_at} if phase_at else {}),
                  samples=samples, skipped=skipped,
                  limits='Original CPU output after explicit camera/layer/player fixtures. No claim of gameplay routes.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(name, len(samples), 'original CPU scroll fixtures', len(skipped), 'skipped', out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('act', type=int, nargs='?', choices=(1, 2, 3))
    parser.add_argument('era', nargs='?', choices=list('ABCD'))
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    todo = PROGRAMS if args.all else [f'{args.act}{args.era}']
    for p in todo:
        capture(int(p[0]), p[1], sr.ROOT/'build/mm/scroll-retail'/f'R8{p}')


if __name__ == '__main__':
    main()
