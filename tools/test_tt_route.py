#!/usr/bin/env python3
"""Replay native-host Tidal Tempest pad routes on Saturn into the next act or zone.

tools/tt_route_search.c searches pad input only (fixed-seed Go-Explore over
pad prefixes) for one act and era from the level-select spawn, then replays
the found script and records ``sequence pad x y``. The host run must finish
the tally without a warp, a death or drowning (the air counter never reaches
the drowning branch). The Saturn harness replays only that pad plus a
neutral tail and stops at the first observed position that differs. Gates:
every position matched, zero respawns, zero late gameplay intervals, and one
ordinary handoff: Act 1 -> Act 2 (Present), Act 2 -> Act 3 (Bad Future:
level select has no Good Futures), Act 3 (C/D) -> Quartz Quadrant Act 1.
--continue starts instead from an earned save through the real Continue menu:
Act 1 (A) from the CC3 -> Tidal Tempest save (tools/test_cc3_route.py
--continue), Act 2 (A) from the save the Act 1 continue run wrote, Act 3 (D:
no Good Futures were earned) from the Act 2 one. Each run must commit the
next act's save; Act 3 also cold-Continues the Quartz Quadrant save.
Does not prove original whole-act parity or hardware performance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c', 'src/sonic_animation.c',
          'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/boss_r4.c', 'src/objects.c', 'src/water.c']
ORIGINAL = ['boss_1', 'boss_3', 'boss_4', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
SEED = 41
ITERATIONS = 200000
TAIL = 300


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(log, label):
    return [list(map(int, line.split(': ', 1)[1].split()))
            for line in log.splitlines() if line.startswith(label + ': ')]


def retail_parity(host, act, era, script, out, updates):
    """Whole-window retail parity for one TT act (0-based) and era through
    tools/retail_parity.py: round 4, TT_ROUTE env, retail lag drives the water."""
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    import retail_parity as rp
    return rp.retail_parity(host, lambda h, s, rows: [h, 'replay', f'{act}:{era}', s, '46000', rows], 'TT_ROUTE',
                            4, act + 1, era, script, out, updates, lag_sync=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--era', choices=list('ABCD'), action='append')
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--iterations', type=int, default=ITERATIONS)
    parser.add_argument('--host-only', action='store_true', help='search and host replay only (no Saturn run)')
    parser.add_argument('--script', type=Path, help='use this pad script instead of searching (a found route)')
    parser.add_argument('--routes', type=Path, default=Path(os.environ.get('SCD_TT_ROUTES', ROOT / 'tests/routes/tt')) if os.environ.get('SCD_TT_ROUTES', 'x') else None,
                        help='use DIR/tt<act><era>.txt per era instead of searching (default tests/routes/tt; SCD_TT_ROUTES= searches)')
    parser.add_argument('--no-retail', action='store_true', help='skip the retail parity comparison')
    parser.add_argument('--continue', dest='cont', action='store_true',
                        help='Act 1: start from the earned CC3 -> Tidal Tempest save through Continue')
    args = parser.parse_args()
    act = args.act - 1
    eras = args.era or (list('CD') if act == 2 else list('ABCD'))
    assert act < 2 or all(e in 'CD' for e in eras), 'Act 3 exists only as the two Futures'
    if args.cont:
        eras = args.era or (['D'] if act == 2 else ['A'])
        assert eras == (['D'] if act == 2 else ['A']), 'a Continue chain plays Acts 1-2 in the Present and Act 3 in the Bad Future'
    base = ROOT / f'build/tt{args.act}/controller' / ('continue' if args.cont else '')
    base.mkdir(parents=True, exist_ok=True)
    host = base / 'tt_route_search'
    original = [f'build/probe-source/{n}.c' for n in ORIGINAL]
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated',
                    '-Ibuild/probe-source', '-DR1', '-DR11A', 'tools/tt_route_search.c', *NATIVE, *original,
                    '-o', host], cwd=ROOT, check=True)
    exe = base / 'emulator'
    if args.cont:
        # tools/test_cc_campaign_route.py's derived harness: Continue replaces
        # the level-select entry; gameplay RAM is never written.
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from test_cc_campaign_route import campaign_harness
        exe = campaign_harness(base, False, None)
    elif not args.host_only:
        subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include',
                        'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    symbols, disc = {}, None
    if not args.host_only:
        listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',
                                          ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        disc = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    inputs = ['tools/tt_route_search.c', 'tools/test_tt_route.py', 'tools/emulator_test.c',
              'src/main.c', f'assets/generated/ttobj4{args.act}.bin', *NATIVE, *original]
    inputs += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').glob('objects*.inc'))]
    summary = []
    for era in eras:
        out = base / era
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / 'report.json'
        era_inputs = inputs + [f'assets/generated/tt4{args.act}{era}.bin', f'assets/generated/ttcollision4{args.act}{era}.bin']
        report = {'status': 'pending', 'passed': False, 'act': args.act, 'era': era, 'disc_sha256': disc,
                  'inputs': {p: sha(ROOT/p) for p in era_inputs}, 'hardware_tested': False}
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        try:
            pad, script = out / 'controller.txt', out / 'script.txt'
            source = args.script or (args.routes / f'tt{args.act}{era}.txt' if args.routes else None)
            if source:
                script.write_text(source.read_text())
                report.update(script_source=str(source), script_source_sha256=sha(source))
            else:
                with (out/'search.log').open('w') as log:
                    subprocess.run([host, 'search', f'{act}:{era}', str(args.seed), str(args.iterations), script],
                                   cwd=ROOT, stdout=log, stderr=log, check=True, timeout=7200)
            with (out/'host.log').open('w') as log:
                replay = subprocess.run([host, 'replay', f'{act}:{era}', script, '46000', pad],
                                        cwd=ROOT, stdout=log, stderr=log)
            host_log = (out/'host.log').read_text()
            # Parity is evidence, so it runs (and is recorded) before the host
            # gates, as in tools/test_qq_route.py.
            if not args.no_retail and not args.cont:
                report.update(retail_parity=retail_parity(host, act, era, script, out, len(pad.read_text().splitlines())))
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            tally = re.search(r'Tally complete: sequence=(\d+) act=\d+ era=\d+ score=(\d+) min_air=(\d+) boss_hits=(\d+) egg=(\d+)', host_log)
            assert tally, ('host route did not finish the tally', host_log.strip().splitlines()[-1:])
            min_air = int(tally[3])
            assert min_air > 0, ('air ran out on the host route', min_air)
            if act == 2:
                assert int(tally[4]) >= 4 and int(tally[5]) == 1, ('host boss', tally[0])
            expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
            report.update(host_tally_sequence=int(tally[1]), host_score=int(tally[2]), min_air=min_air,
                          pad_sha256=sha(pad), script_sha256=sha(script), seed=args.seed, positions=len(expected))
            if args.host_only:
                report.update(status='host-only', limits='Host search and replay only; no Saturn replay.')
                report_path.write_text(json.dumps(report, indent=2) + '\n')
                parity = report.get('retail_parity', {})
                summary.append(f'{era}: host {len(expected)} positions, min air {min_air}, retail match {parity.get("contiguous")} contiguous, {parity.get("matched")}/{parity.get("compared")} total')
                continue
            env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            for k in ('SCD_ZONE_ROUTE_SHOTS', 'SCD_ZONE_ROUTE_PEEK', 'SCD_TRACE_ACTWK', 'SCD_ZONE_ACTORS', 'SCD_ZONE_ROUTE_ART_MISS'):  # route-<update>.ppm captures, mailbox peeks
                if k in os.environ:
                    env[k] = os.environ[k]
            # Special-stage entry evidence (tools/emulator_test.c 'CC special' rows).
            for diagnostic in ('SCD_SPECIAL_STAGE_ADDR', 'SCD_SPECIAL_GAME'):
                if diagnostic in os.environ:
                    env[diagnostic] = os.environ[diagnostic]
            env.update(SCD_ZONE='2', SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
                       SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                       SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                       SCD_ZONE_ROUTE_UPDATES=str(len(expected)+TAIL), SCD_ZONE_PAD_TAIL=str(TAIL))
            if '_scd_frame_profile' in symbols:
                env['SCD_FRAME_PROFILE'] = symbols['_scd_frame_profile']
            if args.cont:
                # Act 1: the earned Good Future CC3 run's save (Tidal Tempest Act 1,
                # Present); Acts 2 and 3: the previous act's continue run.
                backup = (ROOT/'build/cc3/controller/continue/C/backup-after.bin' if act == 0 else
                          ROOT/f'build/tt{args.act-1}/controller/continue/A/backup-after.bin')
                assert backup.exists(), 'earned CC3 -> Tidal Tempest save (tools/test_cc3_route.py --continue)'
                report.update(entry_backup=str(backup.relative_to(ROOT)), entry_backup_sha256=sha(backup))
                env.update(SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_BACKUP_INPUT=str(backup),
                           SCD_BACKUP_OUTPUT=str(out/'backup-after.bin'))
            command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                       ROOT/'dist/sonic-cd-saturn-prototype.cue', ROOT/'assets/private', out,
                       symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
            with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
                result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                        stdout=stdout, stderr=stderr, timeout=3600)
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
            assert all(r[9:12] == [2, act, era_index] for r in rows[:len(expected)]), 'left the act or era early'
            report.update(matched_positions=len(expected), observations=len(rows), respawns=respawns,
                          late_gameplay_intervals=late, stage_transitions=stages)
            assert respawns == 0, 'respawn'
            assert not late, ('late gameplay interval', late[:3])
            want = [2, 1, 0] if act == 0 else [2, 2, 3] if act == 1 else [3, 0, 0]
            assert len(stages) == 1 and stages[0]['after'] == want, ('handoff', stages)
            if args.cont:
                saves = {s[0]: s[1:] for s in records(log, 'CC save')}
                handoff = stages[0]['sequence']
                before, after = saves[handoff - 1], saves[max(saves)]
                assert before[6] & 0xffff == 2 | act << 8, ('live stage before the handoff', hex(before[6]))
                assert after[3] == before[3] + 1 and after[4] & 0xffff == (3 if act == 2 else 2 | (act + 1) << 8), ('checkpoint written', after)  # the stage word carries the era in bits 16+
                assert (out/'backup-after.bin').read_bytes() != backup.read_bytes(), 'backup RAM did not advance'
                report.update(save_before=before, save_after=after, backup_after_sha256=sha(out/'backup-after.bin'))
                if act == 2:
                    cold = out / 'cold-continue'
                    env2 = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
                    env2.update(SCD_BACKUP_INPUT=str(out/'backup-after.bin'), SCD_SAVE_OUTPUT_DIR=str(cold))
                    with (out/'cold-continue.log').open('w') as output:
                        subprocess.run(['bash', 'tools/test-save-emulator.sh', 'continue'], cwd=ROOT, env=env2,
                                       stdout=output, stderr=subprocess.STDOUT, check=True, timeout=600)
                    saved = json.loads((cold/'save.json').read_text())
                    mailbox = saved['mailbox'][:10]
                    assert mailbox[4:6] == after[3:5] and mailbox[7] == 3 and mailbox[9] == 1, ('cold Continue', mailbox)
                    assert (cold/'backup.bin').read_bytes() == (out/'backup-after.bin').read_bytes()
                    report.update(cold_continue_mailbox=mailbox)
            report.update(handoff_sequence=stages[0]['sequence'], status='passed', passed=True,
                          limits=__doc__.split('\n\n', 1)[1].strip())
            parity = report.get('retail_parity', {})
            summary.append(f'{era}: {len(expected)} positions, min air {min_air}, handoff {stages[0]["after"]} at {stages[0]["sequence"]}, retail match {parity.get("contiguous")} contiguous, {parity.get("matched")}/{parity.get("compared")} total')
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          error=repr(error)[:2000])
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    kind = 'host searches' if args.host_only else 'controller routes'
    print(f'PASS: TT{args.act} {kind}' + ('' if args.host_only else ' with 0 respawns and 0 late intervals') + '; ' + '; '.join(summary))


if __name__ == '__main__':
    main()
