#!/usr/bin/env python3
"""Build the real-pcol host route and verify it from earned CC1 Continue."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import staged_routes  # tools/ is sys.path[0] when run as a script


ROOT = Path(__file__).resolve().parents[1]
SEARCH_SEED = 23
NATIVE = [
    'src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c',
    'src/sonic_animation.c', 'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/objects.c',
]
ORIGINAL = [
    'boss_1', 'boss_3', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ',
    'movement',
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'build/cc1/generator/campaign-generated')
    parser.add_argument('--milestone', choices=['generator', 'present', 'good-future',
                                               'act2', 'continue'],
                        default='generator')
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT / 'dist'):
        parser.error('output must be a scratch directory outside dist')
    output.mkdir(parents=True, exist_ok=True)
    host = output / 'cc_campaign_generator_route'
    pad = output / 'controller.txt'
    original = [f'build/probe-source/{name}.c' for name in ORIGINAL]
    # Continue uses the fixed-seed search route (tools/cc_campaign_search.c):
    # CC1 Present -> Past generator -> Present -> Good Future -> tally. The
    # hand-scripted cc_campaign_generator_route.c predates the HARI3X props
    # and bumper blocks; its partial milestones remain diagnostic only.
    search = args.milestone == 'continue'
    route_source = 'tools/cc_campaign_search.c' if search else 'tools/cc_campaign_generator_route.c'
    inputs = [route_source, *NATIVE, *original]
    for name in inputs:
        if not (ROOT / name).is_file():
            parser.error(f'missing source: {name}')
    command = [
        'clang', '-std=gnu11', '-O1', '-fsigned-char', '-fwrapv',
        '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
        '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
        *inputs, '-o', str(host),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    with (output / 'host.log').open('w') as log:
        if search:
            script = output / 'cc1.script'
            staged_routes.search([str(host), 'search', '0', str(SEARCH_SEED), '60000', str(script)], script, 'campaign-cc1', cwd=ROOT,
                                 stdout=log, stderr=subprocess.STDOUT, check=True, timeout=3600)
            subprocess.run([str(host), 'replay', '0', str(script), '40000', str(pad)], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        else:
            subprocess.run([str(host), str(pad), '--' + args.milestone], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    with (output / 'replay.log').open('w') as log:
        subprocess.run(['python3', 'tools/test_cc_campaign_route.py',
                        '--pad', str(pad), '--require', args.milestone,
                        '--tail', '300' if args.milestone != 'generator' else '0',
                        '--output', str(output / 'target')], cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
    target = json.loads((output / 'target/report.json').read_text())
    expected = {'generator': (8779, 8780, 1),
                'present': (12857, 8780, 2),
                'good-future': (13529, 8780, 3),
                'act2': (15349, 8780, 4),
                'continue': None}[args.milestone]
    if search:
        tally = re.search(r'Tally complete: sequence=\d+ era=2 good_future=1 generator=(\d+) warps=3',
                          (output / 'host.log').read_text())
        assert tally, 'search route did not earn the Good Future tally'
        expected = (len(pad.read_text().splitlines()), int(tally[1]), 4)
    assert target['passed'] and target['matched_positions'] == expected[0]
    assert target['position_mismatches'] == 0 and target['generator_sequence'] == expected[1]
    assert len(target['stage_transitions']) == expected[2]
    report = {
        'passed': True,
        'host_source_sha256': {name: sha256(ROOT / name) for name in inputs},
        'milestone': args.milestone,
        'pad_sha256': sha256(pad),
        'disc_sha256': target['disc_sha256'],
        'earned_backup_sha256': target['earned_backup_sha256'],
        'matched_positions': target['matched_positions'],
        'generator_sequence': target['generator_sequence'],
        'hardware_tested': False,
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'CC1 campaign {args.milestone}: {expected[0]}/{expected[0]} '
          f'positions matched; generator sequence {expected[1]}; pad SHA-256 {report["pad_sha256"]}')


if __name__ == '__main__':
    main()
