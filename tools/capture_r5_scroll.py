#!/usr/bin/env python3
"""Capture original Sega CD Quartz Quadrant (R5) scroll output for camera fixtures.

Boots the original R5<act><era> program (tools/capture_cc_scroll.boot), pins
camera, background layers and the player, and records the CPU-produced hscroll
table.  R5 scroll() has no free-running counter, so every fixture is pinned
for 32 frames: with the camera on the player's rest point the pinned inputs
are the steady state, and the recorded values are what the last scroll()
used.  enkeino (enkeichg: the player X band that switches the background) is
found by RAM diffing across the three player X bands, because the
disassembly does not name it, and recorded with each sample.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot
from zone_object_source import dependencies
from background_r5_assets import SOURCE, scrbinit

KEYS = ['cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg2Y', 'cameraBg3X', 'cameraBg3Y']


def settle(core, e, x, y, frames, inputs=None, move=(0, 0)):
    player = bytearray(core.work_read(e['objPlayerSlot'], 64))
    struct.pack_into('>I', player, e['oX'], (x+160)*65536)
    struct.pack_into('>I', player, e['oY'], (y+96)*65536)
    player[e['oXVel']:e['oXVel']+6] = bytes(6)
    player[e['oFlags']] = 2
    player[e['oRoutine']] = 2
    player[0x2c] = 0
    player[0x30:0x32] = struct.pack('>H', 120)
    for n in range(frames):
        # The last frame may start the camera `move` short of its rest point, so
        # scroll_h/scroll_v move it (scra_hz/scra_vz != 0) during that scroll().
        dx, dy = move if n == frames-1 else (0, 0)
        core.work_write(e['objPlayerSlot'], player)
        core.work_write(e['cameraX'], struct.pack('>I', (x-dx)*65536))
        core.work_write(e['cameraY'], struct.pack('>I', (y-dy)*65536))
        for key, value in (inputs(x-dx) if inputs else {}).items():
            core.work_write(e[key], struct.pack('>i', value))
        if n == frames-1 and e.get('enkeino_at'):
            e['enkeino_before'] = core.work_read(e['enkeino_at'], 1)[0]
        core.pad = 0
        core.run()
        core.host.chunks.clear()


def find_enkei(core, e, act):
    """The one work-RAM byte that reads 0, 1, 2 with the player in each enkeichg band."""
    snaps = []
    for x in ((1000, 5000, 9500) if act == 1 else (1000, 5000, 8000)):
        settle(core, e, x, 300, 48)
        snaps.append(core.work_read(0xff0000, 65536))
    hits = [i for i in range(65536) if (snaps[0][i], snaps[1][i], snaps[2][i]) == (0, 1, 2)]
    assert len(hits) == 1, ('enkeino not unique', [hex(0xff0000+i) for i in hits[:8]])
    return 0xff0000+hits[0]


def capture(act, era, out):
    core, e, frame, program = boot(era, act, 5)
    name = f'R5{act}{era}'
    enkei_at = find_enkei(core, e, act) if act < 3 else None
    e = dict(e, enkeino_at=enkei_at)
    init = scrbinit((SOURCE/f'SCR5{act}{era}.C').read_text())

    def layers(x):
        # scrbinit(x): distinct layer positions, so a layer swap cannot hide.
        v = [sum(m*((x & 0xffff) >> sh) for sh, m in t) & 0xffff for t in init]
        return dict(cameraBgX=v[0] << 16, cameraBg2X=v[1] << 16, cameraBg3X=v[2] << 16)
    out.mkdir(parents=True, exist_ok=True)
    samples = []
    ys = [0, 120, 240, 360, 500, 640, 784]
    if act == 3:
        xs = [0, 1, 31, 255, 1001, 2047, 3000, 3575]
    else:
        # enkeichg bands (player X = camera X + 160): 3584 and 8960 (act 2: 7168).
        xs = [0, 1, 31, 255, 1001, 3000, 3424, 3425, 5003, 7008, 7009, 8191, 8800, 8801, 10000, 10743]
        if act == 2:
            # Past the Act 2 goal the level ends and the player slot stops
            # holding the fixture.
            xs = [x for x in xs if x < 10000]+[9500]
    # Moving camera: the 68k line builders seed their 16.16 accumulator's
    # fraction from registers scroll() left (scra_hz / scroll_v).
    fixtures = [(x, y, m) for x in xs[4::3] for y in (240, 500) for m in ((5, 0), (-3, 0), (12, 0), (-16, 0), (0, 4), (0, -6), (7, 3))]
    fixtures += [(x, y, (0, 0)) for x in xs for y in ys]
    for index, (x, y, move) in enumerate(fixtures):
        settle(core, e, x, y, 32, layers, move=move)
        frame += 32
        scroll = core.work_read(e['hscroll'], 1024)
        actual = {key: struct.unpack('>i', core.work_read(e[key], 4))[0] for key in KEYS}
        player_x = struct.unpack('>I', core.work_read(e['objPlayerSlot']+e['oX'], 4))[0] >> 16
        enkei = core.work_read(enkei_at, 1)[0] if enkei_at else 0
        (out/f'{index:03}-hscroll.bin').write_bytes(scroll)
        hz, vz = struct.unpack('>hh', core.work_read(e['scrollXDiff'], 4))
        samples.append(dict(index=index, frame=frame, inputs=dict(cameraX=x, cameraY=y, move=list(move)), actual_16_16=actual,
                            scra_hz=hz, scra_vz=vz,
                            player_x=player_x, enkeino=enkei, enkeino_before=e.get('enkeino_before', 0), scroll_sha256=hashlib.sha256(scroll).hexdigest()))
    report = dict(program=name, program_sha256=hashlib.sha256(program).hexdigest(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), dependencies=dependencies(),
                  addresses={key: e[key] for key in KEYS+['hscroll', 'objPlayerSlot']} | {'enkeino': enkei_at},
                  samples=samples,
                  limits='Original CPU output after pinned camera/player fixtures. No claim of gameplay routes.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(name, len(samples), 'original CPU scroll fixtures', out, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('act', type=int, nargs='?', choices=(1, 2, 3))
    parser.add_argument('era', nargs='?', choices=list('ABCD'))
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    todo = [(a, r) for a in (1, 2, 3) for r in 'ABCD' if a < 3 or r in 'CD'] if args.all else [(args.act, args.era)]
    for act, era in todo:
        capture(act, era, sr.ROOT/'build/qq/scroll-retail'/f'R5{act}{era}')


if __name__ == '__main__':
    main()
