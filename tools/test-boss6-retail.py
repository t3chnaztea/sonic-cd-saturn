#!/usr/bin/env python3
"""Trace the complete WW3 boss sequence in the retail R63C/D programs.

The fixture positions Sonic and grants rings. Boss code and objects run from
the retail MMD. This tests phases, not a controller route or Saturn hardware.
"""
import hashlib
import json
import struct
from pathlib import Path

from boss_retail_capture import Driver, boot, live_actors

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'build' / 'boss6-retail-full.json'


def trace(name):
    core, engine, main, program = boot(name)
    drive = Driver(name, core, engine, main)
    started = False
    last_hit = 0
    hits = 0
    phases = []
    scroll_samples = {}
    event_at = {}
    actors = set()
    last_phase = None
    for frame in range(3500):
        boss = drive.actor(52)
        routine = boss[engine['oRoutine']] if boss else -1
        floor = boss[45] if boss else 0  # retail 64-byte sprite_status actfree[3]
        collision = boss[engine['oColType']] if boss else 0
        if routine >= 2:
            started = True
        if frame < 100:
            drive.hold(2480 + frame * 3, 1660, 0)
        elif not started:
            drive.hold(2700, 1660, 0)
        elif boss and routine < 12:
            x, y = struct.unpack_from('>hxxh', boss, 8)
            hittable = collision and (routine == 6 or (floor == 3 and routine == 10))
            if hittable and floor == 3:
                # The camera must catch up before retail sprite collision runs.
                drive.hold(x, y - 20, 1)
            elif hittable and frame % 40 == 0:
                drive.hold(x, y - 20, 1)
            elif hittable and frame % 40 >= 36:
                drive.hold(x - 80, y, 0)
            else:
                drive.hold(2700, (1660, 1148, 636)[min(floor, 2)], 0)
        elif boss and routine < 16:
            drive.hold(2700, 636, 0)
        else:
            drive.hold(3100 if frame % 2 else 3090, 636, 0)
        core.pad = 0
        core.work_write(main['rings'], struct.pack('>H', 50))
        core.run()
        core.host.chunks.clear()
        boss = drive.actor(52)
        routine = boss[engine['oRoutine']] if boss else -1
        floor = boss[45] if boss else -1
        hit = boss[57] if boss else 0  # retail actfree[15]
        hits += hit > last_hit
        last_hit = hit
        actors.update(a[0] for _, a in live_actors(core, engine, {52, 53, 54, 55, 56, 57, 61, 62, 63, 64}))
        phase = (routine, floor)
        if phase != last_phase:
            phases.append({'frame': frame, 'routine': routine, 'floor': floor, 'hits': hits})
            if routine == 10 and floor in (1, 2):
                event_at[floor] = frame
            last_phase = phase
        for level, at in event_at.items():
            if frame == at + 200:
                scroll_samples[level] = struct.unpack('>h', core.work_read(engine['bottomBound'], 2))[0]
    decisive = [p for p in phases if p['floor'] == 3 and p['routine'] in (10, 12, 14, 16, 18)]
    expected = [(10, 3), (12, 4), (14, 4), (16, 4), (18, 4)]
    assert [(p['routine'], p['hits']) for p in decisive] == expected, (name, decisive)
    assert actors == {52, 53, 54, 55, 56, 57, 61, 62, 63, 64}, (name, actors)
    assert set(scroll_samples) == {1, 2}, (name, scroll_samples)
    return {'program_sha256': hashlib.sha256(program).hexdigest(), 'hits': hits,
            'actors': sorted(actors), 'phases': phases, 'decisive': decisive,
            'scroll_samples': scroll_samples}


def main():
    result = {name: trace(name) for name in ('R63C', 'R63D')}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: WW3 retail R63C/D boss fights reach four hits and the escape phase')
    print(OUT)


if __name__ == '__main__':
    main()
