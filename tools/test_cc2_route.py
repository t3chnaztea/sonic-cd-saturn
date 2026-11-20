#!/usr/bin/env python3
"""Replay ordinary native-host CC1/CC2 pad routes from level select into the next act.

A fixed-seed native-host Go-Explore (tools/cc_campaign_search.c, mode
``1:ERA``) finds pad input from one era's Act 2 spawn through the tally, and
its replay records ``sequence pad x y``. The Saturn harness replays only that pad (plus a
neutral tail) and stops at the first observed position that differs. Gates:
every position matched, zero respawns, zero late gameplay intervals, and one
ordinary Act 2 -> Act 3 handoff. Level select disables saving and starts with
no Act 1 Good Future, so Act 3 is expected in the Bad Future. Does not prove
original whole-act parity or hardware performance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import staged_routes  # tools/ is sys.path[0] when run as a script

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c',
          'src/sonic_animation.c', 'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/objects.c']
ORIGINAL = ['boss_1', 'boss_3', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
SEEDS = {'A': 41, 'B': 41, 'C': 42, 'D': 41}  # C seeds 24 and 28 are the ring-loss stress routes (qa-loop --seed N --require-ring-loss 30)
ITERATIONS = 60000
TAIL = 300


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(log, label):
    return [list(map(int, line.split(': ', 1)[1].split()))
            for line in log.splitlines() if line.startswith(label + ': ')]


def retail_parity(host, mode, era, script, out, updates, act, limit):
    """Whole-window retail parity for one CC act (1-based) and era through
    tools/retail_parity.py: round 3, CC_ROUTE env, no V-INT lag feed (no water)."""
    import retail_parity as rp
    return rp.retail_parity(host, lambda h, s, rows: [h, 'replay', *mode(s), limit, rows], 'CC_ROUTE',
                            3, act, era, script, out, updates, lag_sync=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--era', choices=list('ABCD'), action='append')
    parser.add_argument('--seed', type=int, help='override the era seed (a reproduction); output goes to controller-seedN')
    parser.add_argument('--require-ring-loss', type=int, default=0,
                        help='stress check: require one update to lose at least this many rings')
    parser.add_argument('--act', type=int, choices=(1, 2), default=2,
                        help='1: CC1 into Act 2 (Present); 2: CC2 into Act 3 (Bad Future)')
    parser.add_argument('--no-retail', action='store_true', help='skip the retail parity comparison')
    parser.add_argument('--host-only', action='store_true', help='search, host replay and retail parity only (no Saturn run)')
    args = parser.parse_args()
    eras = args.era or list('ABCD')
    act = args.act - 1  # act index, as main.c and the host use
    base = ROOT / f'build/cc{args.act}/controller' / (f'seed{args.seed}' if args.seed is not None else '')
    if args.seed is not None:
        SEEDS.update({e: args.seed for e in SEEDS})
    base.mkdir(parents=True, exist_ok=True)
    host = base / 'cc_campaign_search'
    original = [f'build/probe-source/{n}.c' for n in ORIGINAL]
    subprocess.run(['clang', '-std=gnu11', '-O1', '-fsigned-char', '-fwrapv',
                    '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
                    '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
                    'tools/cc_campaign_search.c', *NATIVE, *original, '-o', host], cwd=ROOT, check=True)
    exe = base / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',
                                      ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    disc = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    inputs = ['tools/cc_campaign_search.c', 'tools/test_cc2_route.py', 'tools/emulator_test.c',
              'src/main.c', f'assets/generated/ccobj3{args.act}.bin', *NATIVE, *original]
    inputs += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').glob('objects*.inc'))]
    summary = []
    for era in eras:
        out = base / era
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / 'report.json'
        era_inputs = inputs + [f'assets/generated/cc3{args.act}{era}.bin', f'assets/generated/cccollision3{args.act}{era}.bin']
        report = {'status': 'pending', 'passed': False, 'era': era, 'disc_sha256': disc,
                  'inputs': {p: sha(ROOT/p) for p in era_inputs}, 'hardware_tested': False}
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        try:
            pad, script = out / 'controller.txt', out / 'script.txt'
            with (out/'search.log').open('w') as log:
                staged_routes.search([host, 'search', f'{act}:' + era, str(SEEDS[era]), str(ITERATIONS), script], script,
                                     f'cc{args.act}{era}' + (f'-seed{args.seed}' if args.seed is not None else ''),
                                     cwd=ROOT, stdout=log, stderr=log, check=True, timeout=3600)
            with (out/'host.log').open('w') as log:
                subprocess.run([host, 'replay', f'{act}:' + era, script, '40000', pad],
                               cwd=ROOT, stdout=log, stderr=log, check=True)
            expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
            host_log = (out/'host.log').read_text()
            tally = re.search(r'Tally complete: sequence=(\d+) era=(\d+) good_future=(\d+) generator=(\d+) warps=\d+ score=(\d+)', host_log)
            assert tally, 'host route did not finish the tally'
            if not args.no_retail:
                report.update(retail_parity=retail_parity(host, lambda sc: [f'{act}:' + era, sc], era, script, out,
                                                          len(expected), args.act, '40000'))
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            if args.host_only:
                parity = report.get('retail_parity', {})
                report.update(status='host-only', limits='Host search and replay only; no Saturn replay.')
                report_path.write_text(json.dumps(report, indent=2) + '\n')
                summary.append(f'{era}: host {len(expected)} positions, retail match {parity.get("contiguous")} contiguous, '
                               f'{parity.get("matched")}/{parity.get("compared")} total')
                continue
            env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            for k in ('SCD_ZONE_ROUTE_SHOTS', 'SCD_ZONE_ROUTE_PEEK', 'SCD_TRACE_ACTWK', 'SCD_ZONE_ACTORS', 'SCD_ZONE_ROUTE_ART_MISS'):  # route-<update>.ppm captures, mailbox peeks
                if k in os.environ:
                    env[k] = os.environ[k]
            # Special-stage entry evidence (tools/emulator_test.c 'CC special' rows).
            for diagnostic in ('SCD_SPECIAL_STAGE_ADDR', 'SCD_SPECIAL_GAME'):
                if diagnostic in os.environ:
                    env[diagnostic] = os.environ[diagnostic]
            env.update(SCD_ZONE='1', SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
                       SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                       SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                       SCD_ZONE_ROUTE_UPDATES=str(len(expected)+TAIL), SCD_ZONE_PAD_TAIL=str(TAIL))
            if '_scd_frame_profile' in symbols:
                env['SCD_FRAME_PROFILE'] = symbols['_scd_frame_profile']
            command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                       ROOT/'dist/sonic-cd-saturn-prototype.cue', ROOT/'assets/private', out,
                       symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
            with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
                result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                        stdout=stdout, stderr=stderr, timeout=900)
            core = (out/'core.log').read_text()
            mismatch = re.search(r'CC pad mismatch: .*', core)
            assert result.returncode == 0, mismatch[0] if mismatch else f'emulator exit {result.returncode}'
            rows = records((out/'results.log').read_text(), 'CC route')
            future = records((out/'results.log').read_text(), 'CC future')
            assert len(rows) == len(future) == len(expected) + TAIL, 'observation count'
            for row in rows:  # Y is printed as an unsigned 32-bit word.
                row[3] -= (row[3] >= 1 << 31) << 32
            for row, ref in zip(rows, expected):
                assert [row[0], row[8], row[2], row[3]] == ref, ('position', row, ref)
            assert all(b[0] == a[0] + 1 for a, b in zip(rows, rows[1:])), 'lost observation'
            respawns = max(r[6] for r in rows)
            late = [dict(sequence=b[0], vblanks=b[1]-a[1], x=b[2], y=b[3])
                    for a, b in zip(rows, rows[1:]) if a[9:] == b[9:] and b[1]-a[1] > 1]
            stages = [dict(sequence=b[0], vblanks=b[1]-a[1], before=a[9:], after=b[9:])
                      for a, b in zip(rows, rows[1:]) if a[9:] != b[9:]]
            assert all(r[9:11] == [1, act] and r[11] == 'ABCD'.index(era) for r in rows[:len(expected)]), 'left the act or era early'
            report.update(matched_positions=len(expected), observations=len(rows), respawns=respawns,
                          late_gameplay_intervals=late, stage_transitions=stages,
                          tally_sequence=int(tally[1]), act_score=int(tally[5]), act=args.act,
                          generator_sequence=int(tally[4]) or None, good_future=int(tally[3]),
                          pad_sha256=sha(pad), script_sha256=sha(script), seed=SEEDS[era])
            ring_rows = records((out/'results.log').read_text(), 'CC results')
            ring_loss = max([a[3]-b[3] for a, b in zip(ring_rows, ring_rows[1:]) if b[0] == a[0]+1] or [0])
            report.update(largest_ring_loss=ring_loss)
            assert ring_loss >= args.require_ring_loss, ('ring-loss scatter', ring_loss, args.require_ring_loss)
            assert respawns == 0, 'respawn'
            assert not late, ('late gameplay interval', late[:3])
            assert len(stages) == 1 and stages[0]['before'] == [1, act, 'ABCD'.index(era)], stages
            # Act 2 opens in the Present; level select has no Act 1 Good Future,
            # so Act 3 is the Bad Future.
            assert stages[0]['after'] == ([1, 1, 0] if act == 0 else [1, 2, 3]), ('next act handoff', stages)
            report.update(status='passed', passed=True,
                          limits=__doc__.split('\n\n', 1)[1].strip())
            summary.append(f'{era}: {len(expected)} positions, tally {tally[1]}, Act {args.act + 1} era {stages[0]["after"][2]}')
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          error=repr(error)[:2000])
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    if args.host_only:
        print(f'HOST-ONLY: CC{args.act} host routes; ' + '; '.join(summary))
        return
    print(f'PASS: CC{args.act} controller routes into Act {args.act + 1} with 0 respawns and 0 late intervals; ' + '; '.join(summary))


if __name__ == '__main__':
    main()
