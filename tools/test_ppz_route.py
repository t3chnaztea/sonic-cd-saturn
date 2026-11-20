#!/usr/bin/env python3
"""Replay native-host Palmtree Panic pad routes from level select into the next act.

tools/cc_campaign_search.c (PPZ modes ``p<act>:<era>``) replays a found pad
script (``--routes DIR``: DIR/p<act><era>.txt, or the ``found`` variant) through
the tally and records ``sequence pad x y``. The Saturn harness replays only
that pad plus a neutral tail and stops at the first observed position that
differs. Gates: every position matched, zero respawns, zero late gameplay
intervals, and one ordinary handoff: Act 1 -> Act 2 (Present), Act 2 -> Act 3
(Bad Future: level select earns no Good Future), Act 3 -> Collision Chaos
Act 1. The chained sequence/journey scripts (pS, pJ) are host-only here.
Unless --no-retail, the host route is also compared whole-window with the
retail act program (tools/retail_parity.py, round 1); that comparison is
evidence, not a pass gate. --host-only stops after the host replay and the
retail comparison (no Saturn build inputs, no emulator run). Does not prove
hardware performance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c',
          'src/sonic_animation.c', 'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/objects.c']
ORIGINAL = ['boss_1', 'boss_3', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
TAIL = 300


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(log, label):
    return [list(map(int, line.split(': ', 1)[1].split()))
            for line in log.splitlines() if line.startswith(label + ': ')]


def retail_parity(host, act, era, script, out, updates):
    """Whole-window retail parity for one PPZ act (0-based) and era through
    tools/retail_parity.py: round 1, PPZ_ROUTE env, no water lag sync."""
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    import retail_parity as rp
    return rp.retail_parity(host, lambda h, s, rows: [h, 'replay', f'p{act}:{era}', s, '40000', rows], 'PPZ_ROUTE',
                            1, act + 1, era, script, out, updates, lag_sync=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--era', choices=list('ABCD'), action='append')
    parser.add_argument('--routes', type=Path, default=Path(os.environ.get('SCD_PPZ_ROUTES', ROOT / 'tests/routes/ppz')),
                        help='directory holding p<act><era>[.found].txt (default tests/routes/ppz, or SCD_PPZ_ROUTES)')
    parser.add_argument('--no-retail', action='store_true', help='skip the retail parity comparison')
    parser.add_argument('--host-only', action='store_true', help='host replay and retail parity only (no Saturn run)')
    args = parser.parse_args()
    act = args.act - 1
    eras = args.era or (list('CD') if act == 2 else list('ABCD'))
    base = ROOT / f'build/ppz{args.act}/controller'
    base.mkdir(parents=True, exist_ok=True)
    host = base / 'cc_campaign_search'
    original = [f'build/probe-source/{n}.c' for n in ORIGINAL]
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated',
                    '-Ibuild/probe-source', '-DR1', '-DR11A',
                    'tools/cc_campaign_search.c', *NATIVE, *original, '-o', host], cwd=ROOT, check=True)
    exe = base / 'emulator'
    symbols, disc = {}, None
    if not args.host_only:
        subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include',
                        'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
        listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',
                                          ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        disc = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    inputs = ['tools/cc_campaign_search.c', 'tools/test_ppz_route.py', 'tools/emulator_test.c', 'src/main.c', *NATIVE, *original]
    summary = []
    for era in eras:
        out = base / era
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / 'report.json'
        report = {'status': 'pending', 'passed': False, 'act': args.act, 'era': era, 'disc_sha256': disc,
                  'inputs': {p: sha(ROOT/p) for p in inputs}, 'hardware_tested': False}
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        try:
            source = next(p for p in (args.routes/f'p{act}{era}.found.txt', args.routes/f'p{act}{era}.txt') if p.is_file())
            pad, script = out / 'controller.txt', out / 'script.txt'
            script.write_text(source.read_text())
            with (out/'host.log').open('w') as log:
                subprocess.run([host, 'replay', f'p{act}:{era}', script, '40000', pad],
                               cwd=ROOT, stdout=log, stderr=log)
            host_log = (out/'host.log').read_text()
            tally = re.search(r'Tally complete: sequence=(\d+) era=(\d+) good_future=(\d+) generator=(\d+) warps=\d+ score=(\d+)', host_log)
            expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
            report.update(script_source=str(source), script_sha256=sha(script))
            # Parity is measured even when the host route no longer finishes
            # (the window is then the script's pad length).
            if not args.no_retail:
                window = len(expected) if tally else sum(int(l.split()[0]) for l in script.read_text().splitlines() if l.strip())
                report.update(retail_parity=retail_parity(host, act, era, script, out, window))
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            if args.host_only:
                parity = report.get('retail_parity', {})
                report.update(status='host-only', limits='Host replay and retail parity only; no Saturn replay.',
                              tally_sequence=int(tally[1]) if tally else None)
                report_path.write_text(json.dumps(report, indent=2) + '\n')
                summary.append(f'{era}: host {len(expected)} positions' + ('' if tally else ' (no tally)')
                               + (f', retail match {parity.get("contiguous")} contiguous, '
                                  f'{parity.get("matched")}/{parity.get("compared")} total' if parity else ''))
                continue
            assert tally, 'host route did not finish the tally: ' + (host_log.strip().splitlines() or [''])[-1]
            report.update(pad_sha256=sha(pad), tally_sequence=int(tally[1]), act_score=int(tally[5]))
            env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            for k in ('SCD_ZONE_ROUTE_SHOTS', 'SCD_ZONE_ROUTE_PEEK', 'SCD_TRACE_ACTWK', 'SCD_ZONE_ACTORS', 'SCD_ZONE_ROUTE_ART_MISS'):  # route-<update>.ppm captures, mailbox peeks
                if k in os.environ:
                    env[k] = os.environ[k]
            env.update(SCD_ZONE='0', SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
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
            log = (out/'results.log').read_text()
            rows, future = records(log, 'CC route'), records(log, 'CC future')
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
            era_index = 'ABCD'.index(era)
            assert all(r[9:12] == [0, act, era_index] for r in rows[:len(expected)]), 'left the act or era early'
            report.update(matched_positions=len(expected), observations=len(rows), respawns=respawns,
                          late_gameplay_intervals=late, stage_transitions=stages)
            assert respawns == 0, 'respawn'
            assert not late, ('late gameplay interval', late[:3])
            want = [0, 1, 0] if act == 0 else [0, 2, 3] if act == 1 else [1, 0, 0]
            assert len(stages) == 1 and stages[0]['after'] == want, ('handoff', stages)
            report.update(handoff_sequence=stages[0]['sequence'], status='passed', passed=True,
                          limits=__doc__.split('\n\n', 1)[1].strip())
            parity = report.get('retail_parity', {})
            summary.append(f'{era}: {len(expected)} positions, tally {tally[1]}, handoff {want} at {stages[0]["sequence"]}'
                           + (f', retail match {parity.get("contiguous")} contiguous, {parity.get("matched")}/{parity.get("compared")} total' if parity else ''))
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          error=repr(error)[:2000])
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    if args.host_only:
        print(f'HOST-ONLY: PPZ{args.act} host routes; ' + '; '.join(summary))
        return
    print(f'PASS: PPZ{args.act} controller routes with 0 respawns and 0 late intervals; ' + '; '.join(summary))


if __name__ == '__main__':
    main()
