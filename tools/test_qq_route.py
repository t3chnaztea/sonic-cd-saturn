#!/usr/bin/env python3
"""Replay native-host Quartz Quadrant pad routes on Saturn into the next act or zone.

Forked from tools/test_tt_route.py. tools/qq_route_search.c searches pad input
only (fixed-seed Go-Explore over pad prefixes) for one act and era from the
level-select spawn, then replays the found script and records
``sequence pad x y``. The host run must finish the tally without a warp or a
death. The Saturn harness replays only that pad plus a neutral tail and stops
at the first observed position that differs. Gates: every position matched,
zero respawns, zero late gameplay intervals, and one ordinary handoff: Act 1
-> Act 2 (Present), Act 2 -> Act 3 (Bad Future: level select has no Good
Futures), Act 3 (C/D) -> Wacky Workbench Act 1.
--continue starts instead from an earned save through the real Continue menu:
Act 1 (A) from the TT3 -> Quartz Quadrant save (tools/test_tt_route.py --act 3
--continue), Act 2 (A) from the save the Act 1 continue run wrote, Act 3 (D:
no Good Futures were earned) from the Act 2 one. Each run must commit the
next act's save; Act 3 also cold-Continues the Wacky Workbench save.
Routes come from the search or from tests/routes/qq/qq<act><era>.txt, which
must themselves be search output (never hand-edited).
Each level-select window also runs whole-window host/retail parity through
tools/retail_parity.py (round 5, QQ_ROUTE env; lag sync feeds retail lag
V-INTs to levelVIntCounter, the lost-ring floor cadence); --no-retail skips it. Parity is evidence, not a pass gate.
Does not prove hardware performance.
--ww runs the same controller-only search and Saturn replay for Wacky
Workbench Acts 1 to 3. Its route is not hardware acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ZONE = 3  # level-select zone index: Quartz Quadrant (round 5)
NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c', 'src/sonic_animation.c',
          'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/boss_r4.c', 'src/boss_r5.c', 'src/objects.c', 'src/water.c']
ORIGINAL = ['boss_1', 'boss_3', 'boss_4', 'boss_5', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
SEED = 51
ITERATIONS = 200000
TAIL = 300


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(log, label):
    return [list(map(int, line.split(': ', 1)[1].split()))
            for line in log.splitlines() if line.startswith(label + ': ')]


def retail_parity(host, act, era, script, out, updates):
    """Whole-window retail parity for one QQ act (0-based) and era through
    tools/retail_parity.py: round 5, QQ_ROUTE env, retail V-INT lag fed to levelVIntCounter."""
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    import retail_parity as rp
    return rp.retail_parity(host, lambda h, s, rows: [h, 'replay', f'{act}:{era}', s, '46000', rows], 'QQ_ROUTE',
                            5, act + 1, era, script, out, updates, lag_sync=True)


def parity_summary(parity):
    if not parity:
        return ''
    first = parity.get('first_divergence') or {}
    field = parity.get('first_field_divergence') or {}
    return (f', retail {parity.get("contiguous")}/{parity.get("compared")} contiguous'
            f' (first xy split {first.get("sequence")}, first field split {field.get("sequence")} {field.get("fields")})')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), default=1)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--ww', action='store_true', help='Wacky Workbench route instead of Quartz Quadrant')
    selection.add_argument('--ss', action='store_true', help='Stardust Speedway Acts 1 to 3 route (integration in progress)')
    selection.add_argument('--mm', action='store_true', help='Metallic Madness Acts 1 to 3 route (Act 3 ends with EMIE8.C; integration in progress)')
    parser.add_argument('--era', choices=list('ABCD'), action='append')
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--iterations', type=int, default=ITERATIONS)
    parser.add_argument('--host-only', action='store_true', help='search and host replay only (no Saturn run)')
    parser.add_argument('--script', type=Path, help='use this pad script instead of searching (a found route)')
    parser.add_argument('--force-search', action='store_true', help='search even when a stored route exists')
    parser.add_argument('--routes', type=Path, default=Path(os.environ.get('SCD_QQ_ROUTES', ROOT / 'tests/routes/qq')) if os.environ.get('SCD_QQ_ROUTES', 'x') else None,
                        help='use DIR/qq<act><era>.txt per era when present, else search (default tests/routes/qq; SCD_QQ_ROUTES= always searches)')
    parser.add_argument('--save-route', action='store_true', help='copy a searched script to tests/routes/qq/qq<act><era>.txt once the run passes')
    parser.add_argument('--no-retail', action='store_true', help='skip the retail parity comparison')
    parser.add_argument('--continue', dest='cont', action='store_true',
                        help='start from the earned save through Continue (Act 1: the TT3 -> Quartz Quadrant save)')
    parser.add_argument('--backup', type=Path, help='with --continue: this backup RAM image instead of the earned save '
                        '(a crafted save, e.g. stones 1..k for a special stage k+1 entry)')
    parser.add_argument('--require-r5-dispatch', action='store_true',
                        help='require an Act 2 A/C route to exercise the enkeichg N+1 redraw and both SH-2 halves')
    parser.add_argument('--force-r5-fallback', action='store_true',
                        help='Act 2 A/C: the master never notifies the slave (src/main.c bg_slave_mailbox[10]), so the '
                        'first R5 full redraw times out after 30 V-blanks and the master draws both halves; the route '
                        'must still match every position, with one late interval per timeout')
    parser.add_argument('--cue', type=Path, default=ROOT/'dist/sonic-cd-saturn-prototype.cue',
                        help='disc image to replay on (its .bin is hashed into the report)')
    parser.add_argument('--elf', type=Path, default=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf',
                        help='ELF matching --cue, for mailbox symbols')
    parser.add_argument('--out', type=Path, help='report root instead of build/qq<act>/controller')
    args = parser.parse_args()
    assert not args.ww or (args.act in (1, 2, 3) and not args.cont and not args.require_r5_dispatch), '--ww supports level-select Acts 1 to 3'
    assert not args.ss or (args.act in (1, 2, 3) and not args.cont and not args.require_r5_dispatch), '--ss supports level-select Acts 1 to 3'
    assert not args.mm or (args.act in (1, 2, 3) and not args.cont and not args.require_r5_dispatch), '--mm supports level-select Acts 1 to 3'
    zone = 6 if args.mm else 5 if args.ss else 4 if args.ww else ZONE
    prefix = 'mm' if args.mm else 'ss' if args.ss else 'ww' if args.ww else 'qq'
    round_no = 8 if args.mm else 7 if args.ss else 6 if args.ww else 5
    native = NATIVE + (['src/boss_r6.c', 'src/background_r6.c'] if args.ww else ['src/boss_r7.c'] if args.ss else ['src/boss_r8.c'] if args.mm else [])
    original_names = ORIGINAL + (['boss_6'] if args.ww else ['boss_7'] if args.ss else ['boss_8', 'ending_8'] if args.mm else [])
    act = args.act - 1
    eras = args.era or (list('CD') if act == 2 else list('ABCD'))
    assert act < 2 or all(e in 'CD' for e in eras), 'Act 3 exists only as the two Futures'
    if args.cont:
        eras = args.era or (['D'] if act == 2 else ['A'])
        assert eras == (['D'] if act == 2 else ['A']), 'a Continue chain plays Acts 1-2 in the Present and Act 3 in the Bad Future'
    base = (args.out.resolve() if args.out else ROOT / f'build/{prefix}{args.act}/controller') / ('continue' if args.cont else '')
    base.mkdir(parents=True, exist_ok=True)
    host = base / 'qq_route_search'
    original = [f'build/probe-source/{n}.c' for n in original_names]
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated',
                    '-Ibuild/probe-source', '-DR1', '-DR11A', *(['-DROUTE_MM'] if args.mm else ['-DROUTE_SS'] if args.ss else ['-DROUTE_WW'] if args.ww else []),
                    'tools/qq_route_search.c', *native, *original,
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
                                          args.elf], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        disc = sha(args.cue.with_suffix('.bin'))
    inputs = ['tools/qq_route_search.c', 'tools/test_qq_route.py', 'tools/emulator_test.c',
              'src/main.c', f'assets/generated/{prefix}obj{round_no}{args.act}.bin', *native, *original]
    inputs += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').glob('objects*.inc'))]
    summary = []
    for era in eras:
        out = base / era
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / 'report.json'
        era_inputs = inputs + [f'assets/generated/{prefix}{round_no}{args.act}{era}.bin', f'assets/generated/{prefix}collision{round_no}{args.act}{era}.bin']
        report = {'status': 'pending', 'passed': False, 'act': args.act, 'era': era, 'disc_sha256': disc,
                  'inputs': {p: sha(ROOT/p) for p in era_inputs}, 'hardware_tested': False}
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        try:
            pad, script = out / 'controller.txt', out / 'script.txt'
            routes = ROOT / 'tests/routes/mm' if args.mm else ROOT / 'tests/routes/ss' if args.ss else ROOT / 'tests/routes/ww' if args.ww else args.routes
            stored = routes / f'{prefix}{args.act}{era}.txt' if routes else None
            source = args.script or (stored if not args.force_search and stored and stored.exists() else None)
            if source:
                script.write_text(source.read_text())
                report.update(script_source=str(source), script_source_sha256=sha(source))
            else:
                report.update(script_source='search')
                with (out/'search.log').open('w') as log:
                    found = subprocess.run([host, 'search', f'{act}:{era}', str(args.seed), str(args.iterations), script],
                                           cwd=ROOT, stdout=log, stderr=log, timeout=7200)
                assert found.returncode == 0, f'search found no finishing route (exit {found.returncode}, {out/"search.log"})'
            with (out/'host.log').open('w') as log:
                replay = subprocess.run([host, 'replay', f'{act}:{era}', script, '46000', pad],
                                        cwd=ROOT, stdout=log, stderr=log)
            host_log = (out/'host.log').read_text()
            # Parity is evidence, so it runs (and is recorded) before the host gates.
            if not args.no_retail and not args.cont:
                if args.ww or args.ss or args.mm:
                    import sys
                    sys.path.insert(0, str(ROOT / 'tools'))
                    import retail_parity as rp
                    report.update(retail_parity=rp.retail_parity(
                        host, lambda h, s, rows: [h, 'replay', f'{act}:{era}', s, '46000', rows],
                        'QQ_ROUTE', round_no, args.act, era, script, out,
                        len(pad.read_text().splitlines()), lag_sync=True,
                        # MM: RING.C flyringmove's floor check (retail R81D $208E3A:
                        # levelVIntCounter+3 + d7) needs the PPZ/CC alignment: all
                        # five MM1A lost rings of the 658 spill bounce as retail.
                        **(dict(vint_offset=-1) if args.mm else {})))
                else:
                    report.update(retail_parity=retail_parity(host, act, era, script, out, len(pad.read_text().splitlines())))
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            tally = re.search(r'Tally complete: sequence=(\d+) act=\d+ era=\d+ score=(\d+) boss_hits=(\d+) lowered=(\d+) grind_left=(-?\d+) escaped=(\d+)', host_log)
            assert replay.returncode == 0 and tally, ('host route did not finish the tally', host_log.strip().splitlines()[-1:])
            if act == 2 and args.mm:
                assert re.search(r'MM ending complete: seen=1 hits=4 escaped=1 amy=1 game_end=1', host_log), ('host ending', host_log[-1000:])
            elif act == 2 and args.ss:
                assert 'SS race complete: seen=1 race=1 result=1 escaped=1 stationary=1' in host_log, ('host race', host_log[-1000:])
            elif act == 2:
                assert int(tally[3]) >= (4 if args.ww else 2) and int(tally[6]) == 1, ('host boss', tally[0])
            expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
            # MM3's ending (EMIE8.C) ends the game: gameplay stops at the host's last row.
            final = args.mm and act == 2
            tail = 0 if final else TAIL
            report.update(host_tally_sequence=int(tally[1]), host_score=int(tally[2]),
                          pad_sha256=sha(pad), script_sha256=sha(script), seed=args.seed, positions=len(expected))
            parity = parity_summary(report.get('retail_parity'))
            if args.host_only:
                report.update(status='host-only', limits='Host search and replay only; no Saturn replay.')
                report_path.write_text(json.dumps(report, indent=2) + '\n')
                summary.append(f'{era}: host {len(expected)} positions, tally at {tally[1]}{parity}')
                continue
            env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            env.update(SCD_ZONE=str(zone), SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
                       SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                       SCD_OBJECTS_OVERLAY_FAULT=symbols['_scd_objects_overlay_fault'],
                       SCD_ZONE_ART_MAILBOX=symbols['_scd_zone_art_mailbox'],
                       SCD_BG_SLAVE_MAILBOX=symbols['_scd_bg_slave_mailbox'],
                       SCD_R5_EVENT_MAILBOX=symbols['_scd_r5_event_mailbox'],
                       SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                       SCD_ZONE_ROUTE_UPDATES=str(len(expected)+tail), SCD_ZONE_PAD_TAIL=str(tail))
            if args.force_r5_fallback:
                env['SCD_BG_SLAVE_FORCE_TIMEOUT'] = '1'
            if os.environ.get('SCD_STALL_CPU') == '1':
                env['SCD_STALL_CPU'] = '1'
            if os.environ.get('SCD_R5_EVENT_TRACE') == '1':
                env['SCD_R5_EVENT_TRACE'] = '1'
            for diagnostic in ('SCD_TRACE_ACTWK', 'SCD_TRACE_RANGE', 'SCD_TRACE_WORDS', 'SCD_ZONE_ACTORS', 'SCD_ZONE_ROUTE_SHOTS', 'SCD_ZONE_ROUTE_PEEK', 'SCD_ZONE_ROUTE_ART_MISS', 'SCD_SPECIAL_STAGE_ADDR', 'SCD_SPECIAL_GAME'):
                if diagnostic in os.environ:
                    env[diagnostic] = os.environ[diagnostic]
            if '_scd_frame_profile' in symbols:
                env['SCD_FRAME_PROFILE'] = symbols['_scd_frame_profile']
            if args.cont:
                # Act 1: the TT3 continue run's save (Quartz Quadrant Act 1, Present);
                # Acts 2 and 3: the previous act's continue run.
                backup = args.backup.resolve() if args.backup else (ROOT/'build/tt3/controller/continue/D/backup-after.bin' if act == 0 else
                          ROOT/f'build/qq{args.act-1}/controller/continue/A/backup-after.bin')
                assert backup.exists(), f'earned save missing: {backup.relative_to(ROOT)}'
                report.update(entry_backup=str(backup.relative_to(ROOT)), entry_backup_sha256=sha(backup))
                env.update(SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_BACKUP_INPUT=str(backup),
                           SCD_BACKUP_OUTPUT=str(out/'backup-after.bin'))
            command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                       args.cue.resolve(), ROOT/'assets/private', out,
                       symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
            with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
                result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                        stdout=stdout, stderr=stderr, timeout=3600)
            core = (out/'core.log').read_text()
            mismatch = re.search(r'CC pad mismatch: .*', core)
            overlay_fault = re.search(r'Zone overlay fault: callsite=(\d+) objects_zone=(\d+) code_zone=(\d+)', core)
            if overlay_fault:
                report['zone_overlay_fault'] = dict(callsite=int(overlay_fault[1]), objects_zone=int(overlay_fault[2]),
                                                    code_zone=int(overlay_fault[3]))
            assert result.returncode == 0, mismatch[0] if mismatch else overlay_fault[0] if overlay_fault else f'emulator exit {result.returncode}'
            log = (out/'results.log').read_text()
            rows, future = records(log, 'CC route'), records(log, 'CC future')
            slave = records(log, 'CC bg slave')
            overruns = records(log, 'CC vdp1 overruns')
            assert len(slave) == 1 and len(slave[0]) == 10, 'background slave counters'
            r5_events = records(log, 'CC r5 events')
            if not args.ww and not args.ss and not args.mm:
                assert len(r5_events) == 1 and len(r5_events[0]) == 9, 'QQ R5 event ledger'
            assert len(rows) == len(future) == len(expected) + tail, 'observation count'
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
            assert all(r[9:12] == [zone, act, era_index] for r in rows[:len(expected)]), 'left the act or era early'
            report.update(matched_positions=len(expected), observations=len(rows), respawns=respawns,
                          late_gameplay_intervals=late, stage_transitions=stages,
                          vdp1_overrun_vblanks=overruns[0][0] if overruns else None,
                          bg_slave_counters=dict(attempts=slave[0][0], entries=slave[0][1],
                                                 completions=slave[0][2], eligibility_fallbacks=slave[0][3],
                                                 map_update_nonzero=slave[0][4], map_update_holds=slave[0][5],
                                                 map_update_full_redraws=slave[0][6],
                                                 full_redraw_slave_unavailable=slave[0][7],
                                                 last_nonzero_map_update=slave[0][8], slave_timeouts=slave[0][9]))
            if r5_events:
                report['r5_events'] = dict(enkei_changes=r5_events[0][0], camera_line_deferrals=r5_events[0][1],
                                       mapwrtb_skip_deferrals=r5_events[0][2], latest_tick=r5_events[0][3],
                                       show_enkei=r5_events[0][4], current_enkei=r5_events[0][5],
                                       transition_holds=r5_events[0][6], transition_full_redraws=r5_events[0][7],
                                       transition_state=r5_events[0][8])
            if args.require_r5_dispatch:
                assert act == 1 and era in 'AC', '--require-r5-dispatch needs QQ Act 2 Present or Good Future'
                assert slave[0][0] and slave[0][1] and slave[0][2], ('R5 slave dispatch', slave[0])
                assert slave[0][4] and slave[0][5] and slave[0][6], ('R5 map update', slave[0])
                assert r5_events[0][0] and r5_events[0][6] and r5_events[0][7], ('R5 enkeichg pair', r5_events[0])
                assert r5_events[0][0] == r5_events[0][6] == r5_events[0][7], ('lost R5 change/hold/redraw', r5_events[0])
                assert slave[0][0] == slave[0][1] == slave[0][2] == r5_events[0][7], ('unmatched slave work', slave[0], r5_events[0])
                assert slave[0][3] == slave[0][7] == 0, ('R5 dispatch fallback/unavailable', slave[0])
            if args.force_r5_fallback:
                assert act == 1 and era in 'AC', '--force-r5-fallback needs QQ Act 2 Present or Good Future'
                # One timeout stops the slave; every later full redraw runs on the master alone.
                assert slave[0][9] == 1 and slave[0][1] == slave[0][2] == 0, ('forced R5 fallback', slave[0])
                assert slave[0][7] == r5_events[0][7] - 1, ('master-only R5 redraws after the fallback', slave[0], r5_events[0])
                assert len(late) == 1, ('one late interval for the 30 V-blank fallback', late[:3])
                late = []
            assert respawns == 0, 'respawn'
            assert not late, ('late gameplay interval', late[:3])
            want = [zone, 1, 0] if act == 0 else [zone, 2, 3] if act == 1 else [zone + 1, 0, 0]
            if final:assert not stages, ('MM3 ends the game in the act', stages)
            else:assert len(stages) == 1 and stages[0]['after'] == want, ('handoff', stages)
            if args.cont:
                saves = {s[0]: s[1:] for s in records(log, 'CC save')}
                handoff = stages[0]['sequence']
                before, after = saves[handoff - 1], saves[max(saves)]
                assert before[6] & 0xffff == ZONE | act << 8, ('live stage before the handoff', hex(before[6]))
                assert after[3] == before[3] + 1 and after[4] & 0xffff == (ZONE + 1 if act == 2 else ZONE | (act + 1) << 8), ('checkpoint written', after)  # the stage word carries the era in bits 16+
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
                    assert mailbox[4:6] == after[3:5] and mailbox[7] == ZONE + 1 and mailbox[9] == 1, ('cold Continue', mailbox)
                    assert (cold/'backup.bin').read_bytes() == (out/'backup-after.bin').read_bytes()
                    report.update(cold_continue_mailbox=mailbox)
            if args.save_route and not source:
                dest = ROOT / f'tests/routes/{prefix}/{prefix}{args.act}{era}.txt'
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(script.read_text())
                report.update(saved_route=str(dest.relative_to(ROOT)))
            # MM Act 3 ends the game: no stage handoff follows the route.
            handoff = f'handoff {stages[0]["after"]} at {stages[0]["sequence"]}' if stages else 'no handoff (game end)'
            report.update(handoff_sequence=stages[0]['sequence'] if stages else None, status='passed', passed=True,
                          limits=__doc__.split('\n\n', 1)[1].strip())
            summary.append(f'{era}: {len(expected)} positions, {handoff}{parity}')
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          error=repr(error)[:2000])
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    kind = 'host searches' if args.host_only else 'controller routes'
    late_text = (' with 0 respawns; forced R5 fallback: 1 slave timeout, its 1 late interval, no other'
                 if args.force_r5_fallback else ' with 0 respawns and 0 late intervals')
    print(f'PASS: {prefix.upper()}{args.act} {kind}' + ('' if args.host_only else late_text) + '; ' + '; '.join(summary))


if __name__ == '__main__':
    main()
