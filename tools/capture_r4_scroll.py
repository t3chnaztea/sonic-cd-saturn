#!/usr/bin/env python3
"""Capture original Sega CD Tidal Tempest (R4) scroll output for camera fixtures.

Boots the original R4<act><era> program (tools/capture_cc_scroll.boot), writes
camera/background-layer fixtures and a water surface, then records the
CPU-produced hscroll table.  R4 has no free-running cloud accumulator, so one
complete scroll() is detected by its water phase word (SCR4*.C waterdirec,
+128 per call), found by RAM diffing because the disassembly does not name it.

Surface: libretro frames end mid main loop, so the measured frame runs
watercnt() (sway + pinned waterHeight2) before scroll(); scroll() reads the
waterHeight that frame leaves, recorded as water_surface (the value before
the frame is kept as water_surface_before).
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot
from zone_object_source import dependencies

KEYS = ['cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg2Y', 'cameraBg3X', 'cameraBg3Y']
WATER = ['waterHeight', 'waterHeight2', 'destWaterHeight']


def words(core):
    return struct.unpack('>32768H', core.work_read(0xff0000, 65536))


def find_phase(core):
    """The one work-RAM word that advances by exactly 128 on each of 6 frames."""
    prev = words(core)
    live = None
    for _ in range(6):
        core.pad = 0
        core.run()
        core.host.chunks.clear()
        now = words(core)
        hit = {i for i in range(32768) if (now[i]-prev[i]) & 0xffff == 128}
        live = hit if live is None else live & hit
        prev = now
    assert len(live) == 1, ('waterdirec not unique', sorted(live)[:8])
    return 0xff0000+2*live.pop()


def bg_y(slot, x, y):
    if slot == '1A':
        # SCR41A scrbinit/scroll: camera Y below 512 draws it, or 512 past X 640.
        return (512 if x >= 640 else y) if y < 512 else ((y-512)*16384*3+0x2000000) >> 16
    return y//2


def capture(act, era, out):
    core, e, frame, program = boot(era, act, 4)
    name = f'R4{act}{era}'
    phase_at = find_phase(core)
    out.mkdir(parents=True, exist_ok=True)
    samples = []
    # Acts 2/3 reach camera Y 2048 (scr_dir_tbl), where zonescrsetsub0 reads
    # hscrollwork rows past the 128 their scroll() writes.
    ys = [0, 240, 360, 600, 1000, 1248, 1296] if act == 1 else [0, 240, 360, 1000, 1296, 1800, 2000]
    fixtures = [(x, y, 0) for x in [0, 1, 31, 255, 1001, 4093, 8191, 11800] for y in ys]
    fixtures += [(x, 360, dx) for x in (255, 1001, 4093) for dx in (-16, -1, 1, 16)]
    for index, (x, y, player_dx) in enumerate(fixtures):
        by = bg_y(f'{act}{era}', x, y)
        inputs = dict(cameraX=x, cameraY=y, cameraBgX=x*12//256, cameraBgY=by,
                      cameraBg2X=x*24//256, cameraBg2Y=by, cameraBg3X=x*16//256, cameraBg3Y=by)
        # Surface above the screen (all wet), mid-screen, or below it (dry).
        surface = y+(-40, 112, 400)[index % 3]
        player = bytearray(core.work_read(e['objPlayerSlot'], 64))
        struct.pack_into('>I', player, e['oX'], (x+160+player_dx)*65536)
        # Keep Sonic out of the act 2 bottom pits: a fall ends scroll()
        # updates.  R4 scroll() never reads the player; when he is above the
        # camera window the measured frame may move the camera, and the
        # recorded actual camera is what the gate compares.
        struct.pack_into('>I', player, e['oY'], min(y+96, 1800)*65536)
        player[e['oXVel']:e['oXVel']+6] = bytes(6)
        player[e['oFlags']] = 2
        player[e['oRoutine']] = 2
        player[0x2c] = 0
        player[0x30:0x32] = struct.pack('>H', 120)

        def pin():
            core.work_write(e['objPlayerSlot'], player)
            for key, value in inputs.items():
                core.work_write(e[key], struct.pack('>I', value*65536))
            for key in WATER:
                core.work_write(e[key], struct.pack('>H', surface & 0xffff))
        for _ in range(32):
            pin()
            core.pad = 0
            core.run()
            frame += 1
            core.host.chunks.clear()
        pin()
        before = struct.unpack('>H', core.work_read(phase_at, 2))[0]
        used_surface = struct.unpack('>h', core.work_read(e['waterHeight'], 2))[0]
        for waited in range(1, 121):
            core.pad = 0
            core.run()
            frame += 1
            core.host.chunks.clear()
            after = struct.unpack('>H', core.work_read(phase_at, 2))[0]
            if after != before:
                assert (after-before) & 0xffff == 128, ('unexpected scroll updates', name, index, before, after)
                break
            used_surface = struct.unpack('>h', core.work_read(e['waterHeight'], 2))[0]
        else:
            raise RuntimeError(f'{name} fixture {index}: no original scroll update')
        after_surface = struct.unpack('>h', core.work_read(e['waterHeight'], 2))[0]
        scroll = core.work_read(e['hscroll'], 1024)
        deform = core.work_read(e['deformBuffer'], 512)
        actual = {key: struct.unpack('>i', core.work_read(e[key], 4))[0] for key in KEYS}
        scroll_dx = struct.unpack('>h', core.work_read(e['scrollXDiff'], 2))[0]
        (out/f'{index:03}-hscroll.bin').write_bytes(scroll)
        (out/f'{index:03}-deform-after.bin').write_bytes(deform)
        samples.append(dict(index=index, frame=frame, waited_vblanks=waited, inputs=inputs, actual_16_16=actual,
                            scroll_x_diff_8_8=scroll_dx, water_phase_before=before, water_surface_before=used_surface, water_surface=after_surface,
                            scroll_sha256=hashlib.sha256(scroll).hexdigest()))
    report = dict(program=name, program_sha256=hashlib.sha256(program).hexdigest(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), dependencies=dependencies(),
                  addresses={key: e[key] for key in KEYS+WATER+['deformBuffer', 'hscroll', 'objPlayerSlot']}|{'waterdirec': phase_at},
                  samples=samples,
                  limits='Original CPU output after explicit camera/player/water fixtures. No claim of gameplay routes.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(name, len(samples), 'original CPU scroll fixtures', out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('act', type=int, choices=(1, 2, 3))
    parser.add_argument('era', choices=list('ABCD'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.act == 3 and args.era in 'AB':
        parser.error('Act 3 has only C and D programs')
    capture(args.act, args.era, args.out or sr.ROOT/'build/tt/scroll-retail'/f'R4{args.act}{args.era}')


if __name__ == '__main__':
    main()
