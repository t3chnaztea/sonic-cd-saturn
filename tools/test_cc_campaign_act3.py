#!/usr/bin/env python3
"""Earn Collision Chaos Act 3 entry saves through an ordinary saving campaign.

From the earned CC1 Continue save (tools/prepare_cc_campaign_checkpoint.py),
a fixed-seed native-host Go-Explore (tools/cc_campaign_search.c) finds pad
input for CC1 (Past generator, natural travel to the Good Future, tally) and
for CC2: ``good`` also destroys the Act 2 Past generator (Act 3 Good Future,
R33C); ``bad`` plays the Present without it (Act 3 Bad Future, R33D). Saturn
replays each joined pad with every observed position checked; the game's own
Act 3 checkpoint lands in backup RAM and a cold Continue must reload it.
No save is constructed or edited. Hardware acceptance remains separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import staged_routes  # tools/ is sys.path[0] when run as a script

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cc2/campaign'
NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c', 'src/sonic_animation.c',
          'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/objects.c']
ORIGINAL = ['boss_1', 'boss_3', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
# (search mode, seed); fixed so reruns reproduce the same pad from the same sources.
SEARCH = {'cc1': ('0', 23), 'good': ('1', 31), 'bad': ('1:A', 41)}
ITERATIONS = 60000
TAIL = 300


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def host_pad(host, name):
    mode, seed = SEARCH[name]
    script, pad = OUT / f'{name}.script', OUT / f'{name}-pad.txt'
    with (OUT / f'{name}-search.log').open('w') as log:
        staged_routes.search([host, 'search', mode, str(seed), str(ITERATIONS), script], script, f'campaign-{name}', cwd=ROOT,
                             stdout=log, stderr=subprocess.STDOUT, check=True, timeout=3600)
    with (OUT / f'{name}-replay.log').open('w') as log:
        subprocess.run([host, 'replay', mode, script, '40000', pad], cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    return [line.split() for line in pad.read_text().splitlines()]


ENTRY = []
DIAGNOSTIC = False


def replay(pad, output, require, era=None):
    command = ['python3', 'tools/test_cc_campaign_route.py', '--pad', pad, '--output', output,
               '--tail', str(TAIL), '--require', require, *ENTRY]
    if era:
        command += ['--act3-era', str(era)]
    with (output.parent / f'{output.name}.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    return json.loads((output / 'report.json').read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=['good', 'bad'], action='append')
    parser.add_argument('--checkpoint-report', type=Path,
                        help='verified earned CC1 checkpoint report, for example a PPZ3 handoff')
    parser.add_argument('--diagnostic-checkpoint', type=Path,
                        help='diagnostic only: an earned backup whose checkpoint report failed a non-route gate')
    args = parser.parse_args()
    global DIAGNOSTIC
    if args.checkpoint_report and args.diagnostic_checkpoint:
        parser.error('choose one checkpoint report')
    if args.checkpoint_report:
        report = json.loads(args.checkpoint_report.read_text())
        assert report['passed'] and report['disc_sha256'] == sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
        ENTRY[:] = ['--checkpoint-report', str(args.checkpoint_report), '--backup', report['backup_path']]
    if args.diagnostic_checkpoint:
        report = json.loads(args.diagnostic_checkpoint.read_text())
        ENTRY[:] = ['--checkpoint-report', str(args.diagnostic_checkpoint), '--backup', report['backup_path']]
        DIAGNOSTIC = True
    OUT.mkdir(parents=True, exist_ok=True)
    host = OUT / 'cc_campaign_search'
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated',
                    '-Ibuild/probe-source', '-DR1', '-DR11A', 'tools/cc_campaign_search.c', *NATIVE,
                    *[f'build/probe-source/{n}.c' for n in ORIGINAL], '-o', host], cwd=ROOT, check=True)
    cc1 = host_pad(host, 'cc1')
    (OUT / 'cc1-saturn-pad.txt').write_text(''.join(' '.join(r) + '\n' for r in cc1))
    first = replay(OUT / 'cc1-saturn-pad.txt', OUT / 'cc1-continue', 'continue')
    assert first['passed'] and first['position_mismatches'] == 0
    entry = next(t['sequence'] for t in first['stage_transitions'] if t['before'][1] == 0 and t['after'][1] == 1)
    # Neutral tally/handoff observations between the pad and Act 2, as the
    # verified Continue replay observed them (no input is pressed there).
    observed = {}
    for line in (OUT / 'cc1-continue/results.log').read_text().splitlines():
        if line.startswith('CC route: '):
            r = list(map(int, line.split(': ', 1)[1].split()))
            observed[r[0]] = (r[2], r[3] - ((r[3] >= 1 << 31) << 32))
    last = int(cc1[-1][0])
    # Act 2 after an ordinary act transition starts one observation later than
    # the host's level-select load: host sequence 2 lands on entry + 1.
    gap = [[str(q), '0', str(observed[q][0]), str(observed[q][1])] for q in range(last + 1, entry + 1)]
    summary = {'cc1': dict(positions=len(cc1), report=str(OUT / 'cc1-continue/report.json'),
                           act2_entry=entry, pad_sha256=sha(OUT / 'cc1-saturn-pad.txt'))}
    for variant in args.variant or ['good', 'bad']:
        act2 = host_pad(host, variant)
        joined = cc1 + gap + [[str(int(q) - 1 + entry), b, x, y] for q, b, x, y in act2]
        pad = OUT / f'{variant}-saturn-pad.txt'
        pad.write_text(''.join(' '.join(r) + '\n' for r in joined))
        era = 2 if variant == 'good' else 3
        report = replay(pad, OUT / f'{variant}-act3', 'act3', era)
        assert report['passed'] and report['position_mismatches'] == 0, report.get('late_gameplay_detail')
        backup = OUT / f'{variant}-act3/backup-after.bin'
        summary[variant] = dict(positions=len(joined), act3_era=era, act3=report['act3'],
                                backup=str(backup.relative_to(ROOT)), backup_sha256=sha(backup), pad_sha256=sha(pad))
    summary.update(passed=not DIAGNOSTIC, diagnostic_checkpoint=str(args.diagnostic_checkpoint) if DIAGNOSTIC else None,
                   checkpoint_report=str(args.checkpoint_report) if args.checkpoint_report else None,
                   entry_backup_sha256=sha(Path(ENTRY[-1])) if ENTRY else None,
                   disc_sha256=sha(ROOT / 'dist/sonic-cd-saturn-prototype.bin'),
                   host_inputs={p: sha(ROOT / p) for p in ['tools/cc_campaign_search.c', *NATIVE]},
                   hardware_tested=False, limits=__doc__.split('\n\n', 1)[1].strip())
    (OUT / 'report.json').write_text(json.dumps(summary, indent=2) + '\n')
    for variant in ('good', 'bad'):
        if variant in summary:
            print(f"PASS: CC3 entry {variant}: era {summary[variant]['act3_era']} backup {summary[variant]['backup']} sha256 {summary[variant]['backup_sha256']}")


if __name__ == '__main__':
    main()
