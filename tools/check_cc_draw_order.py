#!/usr/bin/env python3
"""Measure original CC draw-queue order along the native natural CC routes.

Native src/main.c submits Sonic first, then reserved effects and pool actors in
slot order (pool[i] is actwk[i+1]); src/sprite_order.h buckets them by priority
with earlier submissions in front. This feeds each native controller route
(build/cc{1,2}/controller/<era>/controller.txt, build/cc3/controller/<era>/...)
into the retail game from the title-card release and, every frame, clears the
retail draw queue (objDrawQueue, ACTION.C actionsub/pbuffer) before the frame
and reads its submissions after. It records:
  * every frame in which a priority level's submissions are not in ascending
    slot order (the only way native slot-order submission can differ);
  * every Sonic priority other than 2 (native draws Sonic at actwk[0].sprpri),
    and how often a dying (priority 0) Sonic is queued within 32 pixels of a
    priority 0/1 actor, where a fixed Sonic priority 2 would reverse the order.
Retail input phase is not calibrated, so retail positions drift from the native
route and Sonic dies; lives are held at 3 so the retail keeps playing. This
samples natural retail object mixes, not frame-matched images.
"""
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cc-draw-order'
VARIANTS = [(1, e) for e in 'ABCD'] + [(2, e) for e in 'ABCD'] + [(3, e) for e in 'CD']
# libretro mask (tools/cc_pad_replay.h) -> Core.pad MD mask (special_retail.Core)
PAD = {1: 16, 16: 1, 32: 2, 64: 4, 128: 8}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def controller(act, era):
    path = ROOT / f'build/cc{act}/controller/{era}/controller.txt'
    return path, [int(line.split()[1]) for line in path.read_text().splitlines()]


def md(pad):
    return sum(v for k, v in PAD.items() if pad & k)


def run(act, era, limit):
    path, pads = controller(act, era)
    core, e, _, _ = boot(era, act, 3)
    queue, base = e['objDrawQueue'], e['objPlayerSlot']
    lives = sr.layout()[0]['lives']
    frames = analyzed = mid_frame = changed = inversions = shared = dying_near = 0
    sonic = Counter()
    submitted = Counter()
    samples = []
    counts = lambda: [struct.unpack('>H', core.work_read(queue + level * 0x80, 2))[0]
                      for level in range(8)]
    xy = lambda d: [struct.unpack_from('>h', d, e[k])[0] for k in ('oX', 'oY')]
    for pad in pads[:limit] + [0] * 60:
        # A frame boundary can fall inside a lagging update (nonzero counts);
        # clear entries only between updates. Counts stay untouched, and
        # entries past a count are never read, so the retail run is unchanged.
        if not any(counts()):
            for level in range(8):
                core.work_write(queue + level * 0x80 + 2, bytes(0x7e))
        word = bytearray(core.work_read(lives & ~1, 2))
        word[lives & 1] = 3
        core.work_write(lives & ~1, bytes(word))
        core.pad = md(pad)
        core.run()
        core.host.chunks.clear()
        frames += 1
        if any(counts()):
            mid_frame += 1
            continue
        data = core.work_read(queue, 0x400)
        player = core.work_read(base, 64)
        queued = {}
        for level in range(8):
            words = struct.unpack_from('>63H', data, level * 0x80 + 2)
            slots = []
            for w in words:
                if not w:
                    break
                slots.append((0xff0000 | w) - base >> 6)
            queued[level] = slots
        sonic_level = [level for level in range(8) if 0 in queued[level]]
        if player[e['oID']] != 1 or len(sonic_level) != 1:
            continue
        analyzed += 1
        # The death update changes sprpri after Sonic has queued.
        changed += sonic_level[0] != player[e['oPriority']]
        sonic[sonic_level[0]] += 1
        sx, sy = xy(player)
        for level, slots in queued.items():
            submitted[level] += len(slots)
            shared += len(slots) > 1 and 0 in slots
            if slots != sorted(slots):
                inversions += 1
                if len(samples) < 20:
                    ids = [core.work_read(base + s * 64, 1)[0] for s in slots]
                    samples.append(dict(frame=frames, priority=level, slots=slots, ids=ids))
        if sonic_level[0] == 0:
            for s in queued[0] + queued[1]:
                if s >= 32:
                    ax, ay = xy(core.work_read(base + s * 64, 64))
                    if abs(ax - sx) <= 32 and abs(ay - sy) <= 32:
                        dying_near += 1
                        break
    return dict(controller=str(path.relative_to(ROOT)), controller_sha256=sha(path),
                frames=frames, frames_mid_update=mid_frame, frames_analyzed=analyzed,
                frames_sprpri_changed_after_queue=changed,
                out_of_slot_order_levels=inversions, samples=samples,
                frames_sonic_shares_priority=shared,
                frames_dying_sonic_near_priority01_actor=dying_near,
                sonic_priority=dict(sonic), submissions=dict(submitted))


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / 'report.json'
    report = dict(status='pending', retail_iso_sha256=sha(sr.RETAIL / 'sonic.iso'),
                  inputs={p: sha(ROOT / p) for p in ('tools/check_cc_draw_order.py',
                                                    'tools/capture_cc_scroll.py',
                                                    'tools/special_retail.py')},
                  frame_limit=limit, variants={}, limits=__doc__.split('\n\n', 1)[1].strip())
    try:
        for act, era in VARIANTS:
            name = f'R3{act}{era}'
            if not (ROOT / f'build/cc{act}/controller/{era}/controller.txt').exists():
                report['variants'][name] = dict(status='no controller route')
                continue
            row = report['variants'][name] = run(act, era, limit)
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(name, row['frames_analyzed'], 'analyzed', row['out_of_slot_order_levels'], 'inversions',
                  row['frames_sonic_shares_priority'], 'shared', row['frames_dying_sonic_near_priority01_actor'],
                  'dying-near', 'sonic', row['sonic_priority'], flush=True)
        report['status'] = 'measured'
    except BaseException as error:
        report['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('MEASURED:', report_path)


if __name__ == '__main__':
    main()
