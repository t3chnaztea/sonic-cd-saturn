#!/usr/bin/env python3
"""Capture PLAYSUB flower art and its natural seed-to-flower palette transition.

Rounds 7 and 8 (every act) and the acts whose badnik explosions grow flowers
without their own capsule-flower art: Collision Chaos Acts 1-2, Quartz
Quadrant Acts 1-3 and Wacky Workbench Acts 1-2.

This is an asset fixture. It inserts a flower through the existing retail
fixture, then observes its untouched initialization, fall, landing and growth.
No route or hardware acceptance is implied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import zone_object_source as source

ROOT = Path(__file__).resolve().parents[1]
ACTS = {3: (1, 2), 4: (1, 2), 5: (1, 2, 3), 6: (1, 2), 7: (1, 2, 3), 8: (1, 2, 3)}
PROGRAMS = [f'R{rnd}{act}{era}' for rnd, acts in ACTS.items() for act in acts for era in ('CD' if act == 3 else 'ABCD')]
# The seed's tile base: R7's is $6D7; R8's is read from the capture (pose 0).
SEED_BASE = {7: 0x6d7}
# R42A's fixture spot (camera clamped to x 106) drops the seed down a shaft the
# 2048-line wrap never floors: it takes its growth phases from the era whose
# mapping table and seed tiles it is asserted to share byte for byte.
GROWTH_FROM = {'R42A': 'R42B'}


def verify_flower_tiles(program, record, vram):
    """Each tile the flower reads holds bytes a PLC bank writes there, or no
    bank covers it and it is zero (TT pose 5's $6FE). Returns (plc, dest) pairs."""
    banks, used = source.plc_banks(program), set()
    for tile in sorted(source.read_tiles(record)):
        t = tile % 65536
        covered = [(i, dest, art) for i, _, dest, art in banks if dest <= t and t+32 <= dest+len(art)]
        hit = next(((i, dest) for i, dest, art in covered if art[t-dest:t-dest+32] == vram[t:t+32]), None)
        assert hit or (not covered and vram[t:t+32] == bytes(32)), ('flower tile holds no original PLC bytes', hex(tile))
        if hit:used.add(hit)
    return sorted(used)


def capture(name):
    out = ROOT / 'build/zone-object-source' / (name + '-flower')
    fingerprint = source.dependencies() | {
        'tools/ss_flower_source.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'tools/zone_object_source.py': hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
    }
    report_path = out / 'source.json'
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get('flower_inputs') == fingerprint and previous.get('flower_phases') and (out/'vram.bin').exists():
            if hashlib.sha256((out/'vram.bin').read_bytes()).hexdigest() == previous['vram_sha256']:
                print(f'CACHED: {name} flower seed/growth art')
                return
    phases = {}
    chosen = None

    def watch(core, engine, elapsed):
        nonlocal chosen
        if chosen is None:
            x = struct.unpack('>h', core.work_read(engine['cameraX'], 2))[0] + 224
            candidates = []
            for at in range(engine['dynObjects'], engine['objectsEnd'], 64):
                actor = core.work_read(at, 64)
                if actor[0] == 31 and actor[engine['oSubtype']] == 1 and struct.unpack_from('>h', actor, 8)[0] == x:
                    candidates.append(at)
            assert len(candidates) == 1, (name, 'injected flower', candidates)
            chosen = candidates[0]
        actor = core.work_read(chosen, 64)
        assert actor[0] == 31, (name, 'flower removed', elapsed)
        pose, tile = actor[26], struct.unpack_from('>H', actor, 2)[0]
        phases.setdefault(pose, {'tile': tile, 'actor': actor.hex(), 'elapsed': elapsed})
        if name in GROWTH_FROM:return set(phases) >= {0, 1}
        assert elapsed < 1800, (name, 'flower never completed growth', sorted(phases))
        return set(phases) == set(range(8))

    # Start above the ordinary fixture row so both seed poses occur before
    # landing. Only the initial asset-fixture placement is changed.
    source.capture(name, out, objects=[(31, 31, 8, 1, 0)], actor_y_offset=-64,
                   keep_good_future=name.endswith('C'), watch=watch)
    report = json.loads(report_path.read_text())
    record, = report['objects']
    if name in GROWTH_FROM:
        sibling = ROOT / 'build/zone-object-source' / (GROWTH_FROM[name] + '-flower')
        # zone_object_assets.py walks the eras in order: capture the donor first.
        if not (sibling/'source.json').exists():capture(GROWTH_FROM[name])
        other = json.loads((sibling/'source.json').read_text())
        mine, theirs = (out/'vram.bin').read_bytes(), (sibling/'vram.bin').read_bytes()
        tiles = sorted(source.read_tiles(record))
        assert other['objects'][0]['address'] == record['address'], (name, 'mapping table differs')
        assert all(mine[t % 65536:t % 65536+32] == theirs[t % 65536:t % 65536+32] for t in tiles), (name, 'seed tiles differ')
        assert {int(k) for k in other['flower_phases']} == set(range(8))
        phases = {int(k): v for k, v in other['flower_phases'].items()}
    # PLC 1 writes the seed tiles ($6D7-$6FD) at level start; a later section
    # list may overwrite other parts of that bank (TT), so check tile by tile as
    # R5-R8 do (zone_object_source.verify_tile_bytes). TT's own mapping table
    # reads one tile past the bank in pose 5 ($6FE): no PLC writes it and it is
    # zero in VRAM, so retail draws it transparent (as the boss-entry check).
    program = source.disc_files((ROOT/'build/retail/sonic.iso').read_bytes())[name+'__.MMD']
    report.setdefault('object_plcs', {})[31] = verify_flower_tiles(program, record, (out/'vram.bin').read_bytes())
    report['plc_unverified'] = [k for k in report.get('plc_unverified', []) if k != 31]
    # GetLevelBlock sets bit15 while the seed checks a high-priority
    # chunk. Keep priority as a live view variant rather than baking the
    # fixture's collision layer into every flower.
    base = SEED_BASE.get(int(name[1]), phases[0]['tile'] & 0x1fff)
    assert record['tile'] & 0x7fff == base, (name, 'seed base', record['tile'])
    record['tile'] = base
    frames = []
    for pose, encoded in enumerate(record['frames']):
        expected = base if pose < 4 else base + 0x2000
        assert phases[pose]['tile'] & 0x7fff == expected, (name, pose, phases[pose], expected)
        assert struct.unpack_from('>I', bytes.fromhex(phases[pose]['actor']), 4)[0] == record['address']
        mapping = bytearray.fromhex(encoded)
        # Retail ObjFlower_Growing changes palette line 0 to 1. Encode that
        # live base delta in each grown pose while keeping one kind31 record.
        for piece in range(mapping[0]):
            at = 3 + 5 * piece
            word = struct.unpack_from('>H', mapping, at)[0]
            struct.pack_into('>H', mapping, at, word + expected - record['tile'])
        frames.append(mapping.hex())
    record['frames'] = frames
    # The priority view variant needs a type|subtype<<8 lookup (ZAR3/ZAR4);
    # Collision Chaos's ZAR2/ZAR5 lookup keys kind 31 alone.
    if int(name[1]) != 3:
        report['objects'].append(dict(record, kind=31 | 1 << 8, tile=0x8000 | base,
                                      variant_source='GetLevelBlock collision-layer priority bit15'))
    report.update(flower_inputs=fingerprint, flower_phases=phases,
                  flower_palette_proof=f'Observed untouched flower poses: 0..3 base{base:04X}, 4..7 base{base+0x2000:04X}; mapping pointer unchanged.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {name} flower eight poses and seed/growth palette transition')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', choices=PROGRAMS, action='append')
    args = parser.parse_args()
    for program in args.program or PROGRAMS:
        capture(program)
