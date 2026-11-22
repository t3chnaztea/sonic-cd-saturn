#!/usr/bin/env python3
"""Verify four ordinary CC1 controller routes and preserve their raw evidence.

This gate covers the currently imported act from level select through Act 2.
It does not certify missing actors/art, original-console parity, normal campaign
saves, time travel, Good Future creation, or physical hardware performance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    'A': 'route-target-A-60-takeoff7100',
    'B': 'route-target-B-100-local-jump2229-2485-takeoff9650-9900',
    'C': 'route-target-C-60-local-takeoff6620-9650-9900',
    'D': 'route-target-D-60',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(era, folder, disc_hash):
    report = json.loads((folder/'report.json').read_text())
    assert report['era'] == era and report['probe_completed'] and report['exit_code'] == 0
    assert report['reached_act2'] and report['respawns'] == 0
    assert not report['late_gameplay_intervals']
    assert report['inputs']['dist/sonic-cd-saturn-prototype.bin'] == disc_hash
    # Reject reports from an older native build or controller harness.
    for path, expected in report['inputs'].items():
        assert sha(ROOT/path) == expected, (era, 'stale input', path)
    rows = [list(map(int, line.split(': ', 1)[1].split()))
            for line in (folder/'results.log').read_text().splitlines()
            if line.startswith('CC route: ')]
    assert len(rows) == report['requested_updates'] == report['observations'] == 18000
    assert all(len(row) == 12 for row in rows)
    start = struct.unpack_from('>HH', (ROOT/f'assets/generated/cc31{era}.bin').read_bytes(), 52)
    assert tuple(rows[0][2:4]) == start, (era, 'ordinary spawn', rows[0], start)
    assert rows[0][9:] == [1, 0, 'ABCD'.index(era)]
    assert rows[-1][9:] == [1, 1, 0]
    assert all(row[6] == 0 for row in rows), (era, 'respawn')
    # Logged commands are only Left, Right and Jump, never both directions.
    assert all(row[8] in (64, 65, 128, 129) for row in rows), (era, 'pad command')
    transitions = []
    intervals = 0
    for before, after in zip(rows, rows[1:]):
        assert after[0] == before[0] + 1, (era, 'missing observation')
        gap = after[1] - before[1]
        assert gap > 0
        if before[9:] != after[9:]:
            transitions.append(dict(sequence=after[0], vblanks=gap,
                                    before=before[9:], after=after[9:]))
        else:
            assert gap == 1, (era, 'late gameplay refresh', after[0], gap)
            intervals += 1
    assert len(transitions) == 1 and transitions == report['transitions']
    assert transitions[0]['before'] == [1, 0, 'ABCD'.index(era)]
    assert transitions[0]['after'] == [1, 1, 0]
    assert max(row[2] for row in rows if row[10] == 0) >= 12000
    return dict(reached_act2=True, observations=len(rows), gameplay_intervals=intervals,
                late=0, respawns=0, transition=transitions[0],
                strategy=report['strategy'], retreat=report['retreat'],
                backjump_at=report['backjump_at'], jump_at=report['jump_at'],
                report_sha256=sha(folder/'report.json'), log_sha256=sha(folder/'results.log'),
                harness_binary_sha256=sha(folder/'emulator'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-bin', required=True)
    parser.add_argument('--out', type=Path, default=Path('build/cc1/routes-validation'))
    args = parser.parse_args()
    disc_hash = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    assert disc_hash == args.expected_bin
    routes = {era: verify(era, ROOT/'build/cc1'/name, disc_hash) for era, name in ROUTES.items()}
    out = ROOT/args.out
    out.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for era, name in ROUTES.items():
        folder = ROOT/'build/cc1'/name
        dest = out/era
        dest.mkdir(exist_ok=True)
        files = [folder/f for f in ('report.json', 'results.log', 'core.log')]
        files += sorted(folder.glob('cc-route-*.ppm'))
        for src in files:
            target = dest/src.name
            shutil.copy2(src, target)
            artifacts[str(target.relative_to(ROOT))] = sha(target)
    result = dict(four_era_routes_passed=True, complete_goal=False, hardware_tested=False,
                  disc_sha256=disc_hash, routes=routes, artifacts=artifacts,
                  tool_sha256=sha(Path(__file__)),
                  limits=__doc__.split('\n\n', 1)[1].strip())
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print('CC1 four-era routes: Act 2 reached in all four eras,',
          sum(r['gameplay_intervals'] for r in routes.values()),
          'gameplay intervals, zero late refreshes and respawns.')
    print(out/'report.json')


if __name__ == '__main__':
    main()
