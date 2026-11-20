#!/usr/bin/env python3
"""Replay ordinary native-host CC3 pad routes from level select into Tidal Tempest.

tools/cc3_route_host.c searches pad input only (Go-Explore over pad
prefixes, fixed seed) for each future, then replays the found script and
records ``sequence pad x y`` from the Act 3 entry through the boss, the
capsule and the tally. The Saturn harness replays that pad plus a neutral
tail and stops at the first observed position that differs. Gates: every
position matched, zero respawns, zero late gameplay intervals, three boss
hits landed after the entrance lift started the boss track (requested
throughout the fight and playing on the CD), and one ordinary Act 3 -> Tidal Tempest Act 1 handoff carrying the
score. Level select disables saving, so the save written at that handoff
and a cold Continue from it are not covered here. Does not prove hardware
performance.
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
SEEDS = {'C': 1, 'D': 1}
SEARCH_ITERATIONS = 200000
TAIL = 600


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def earned_backup(variant, reported):
    """Find a campaign save in this checkout, including pre-move reports."""
    relative = Path('build/cc2/campaign') / f'{variant}-act3/backup-after.bin'
    path = Path(reported)
    assert path == relative or (path.is_absolute() and path.parts[-len(relative.parts):] == relative.parts), (
        'unexpected earned backup path', reported)
    return ROOT / relative


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
    parser.add_argument('--era', choices=list('CD'), action='append')
    parser.add_argument('--continue', dest='cont', action='store_true',
                        help='start from the earned CC3-entry save (build/cc2/campaign) through the real Continue menu; '
                             'also prove the Tidal Tempest checkpoint and a cold Continue into it')
    parser.add_argument('--no-retail', action='store_true', help='skip the retail parity comparison')
    parser.add_argument('--host-only', action='store_true', help='search, host replay and retail parity only (no Saturn run)')
    args = parser.parse_args()
    eras = args.era or list('CD')
    base = ROOT / 'build/cc3/controller'
    base.mkdir(parents=True, exist_ok=True)
    host = base / 'host'
    original = [f'build/probe-source/{n}.c' for n in ORIGINAL]
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv',
                    '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
                    '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
                    'tools/cc3_route_host.c', *NATIVE, *original, '-o', host], cwd=ROOT, check=True)
    exe = base / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    if args.cont:
        # tools/test_cc_campaign_route.py's derived harness: Continue replaces
        # the level-select entry; gameplay RAM is never written.
        from test_cc_campaign_route import campaign_harness
        exe = campaign_harness(base / 'continue', False, None)
        entry = json.loads((ROOT/'build/cc2/campaign/report.json').read_text())
        assert entry['passed'], 'earned CC3-entry saves'
    listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',
                                      ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    disc = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    if args.cont:
        assert entry['disc_sha256'] == disc, 'earned CC3-entry saves belong to an older disc'
        assert all(sha(ROOT/p) == digest for p, digest in entry['host_inputs'].items()), 'earned CC3-entry sources changed'
    inputs = ['tools/cc3_route_host.c', 'tools/test_cc3_route.py', 'tools/emulator_test.c',
              'tools/cc_pad_replay.h', 'src/main.c', 'assets/generated/ccobj33.bin', *NATIVE, *original]
    inputs += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').glob('objects*.inc'))]
    summary = []
    for era in eras:
        out = base / ('continue' if args.cont else '') / era
        out.mkdir(parents=True, exist_ok=True)
        variant = 'good' if era == 'C' else 'bad'
        earned = entry[variant] if args.cont else None
        backup = earned_backup(variant, earned['backup']) if earned else None
        report_path = out / 'report.json'
        era_inputs = inputs + [f'assets/generated/cc33{era}.bin', f'assets/generated/cccollision33{era}.bin']
        report = {'status': 'pending', 'passed': False, 'era': era, 'disc_sha256': disc,
                  'inputs': {p: sha(ROOT/p) for p in era_inputs}, 'hardware_tested': False}
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        try:
            script = out / 'script.txt'
            with (out/'search.log').open('w') as log:
                staged_routes.search([host, 'search', era, str(SEEDS[era]), str(SEARCH_ITERATIONS), script], script, f'cc3{era}',
                                     cwd=ROOT, stdout=log, stderr=log, check=True, timeout=1800)
            pad = out / 'controller.txt'
            with (out/'host.log').open('w') as log:
                subprocess.run([host, 'replay', script, era, '20000', pad, out/'host-trace.txt'],
                               cwd=ROOT, stdout=log, stderr=log, check=True)
            host_log = (out/'host.log').read_text()
            tally = re.search(r'Tally complete: sequence=(\d+) era=(\d+) score=(\d+) rings=(\d+) boss_hits=(\d+) music_hits=(\d+)', host_log)
            assert tally and int(tally[5]) == int(tally[6]) == 3, 'host route did not beat the boss under its track and finish the tally'
            trace = [line.split() for line in (out/'host-trace.txt').read_text().splitlines()]
            music_at = next(int(r[0]) for r in trace if r[13] == '1')
            third_hit = next(int(r[0]) for r in trace if r[14] == '3')
            expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
            if not args.no_retail and not args.cont:
                report.update(retail_parity=retail_parity(host, lambda sc: [sc, era], era, script, out,
                                                          len(expected), 3, '20000'))
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
            env.update(SCD_ZONE='1', SCD_ZONE_ACT='2', SCD_ZONE_ERA=str('ABCD'.index(era)),
                       SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                       SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                       SCD_ZONE_ROUTE_UPDATES=str(len(expected)+TAIL), SCD_ZONE_PAD_TAIL=str(TAIL))
            if '_scd_frame_profile' in symbols:
                env['SCD_FRAME_PROFILE'] = symbols['_scd_frame_profile']
            if args.cont:
                assert len(backup.read_bytes()) == 32768 and sha(backup) == earned['backup_sha256']
                report.update(entry_backup=str(backup.relative_to(ROOT)), entry_backup_sha256=sha(backup))
                env.update(SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_BACKUP_INPUT=str(backup),
                           SCD_BACKUP_OUTPUT=str(out/'backup-after.bin'))
            command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                       ROOT/'dist/sonic-cd-saturn-prototype.cue', ROOT/'assets/private', out,
                       symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
            with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
                result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                        stdout=stdout, stderr=stderr, timeout=1800)
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
            assert all(r[9:12] == [1, 2, era_index] for r in rows[:len(expected)]), 'left Act 3 early'
            scores = {r[0]: f[4] for r, f in zip(rows, future)}
            # BOSS_3.C jaba_s_chk (after the entrance lift) requests the boss
            # track: src/main.c cue 8, audio mailbox slot+2 = 10. It must be
            # requested from that update through the third hit and be the
            # CD's playing track during the fight.
            music = {m[0]: m[1:] for m in records(log, 'CC music')}
            zone_track = 12 + era_index
            fight = [music[s] for s in range(music_at + 2, third_hit)]
            assert all(m[0] == zone_track for s, m in music.items() if 300 <= s < music_at - 1), 'zone track before the lift'
            assert all(m[0] == 10 for m in fight), ('boss track requested during the fight', music_at, third_hit)
            boss_playing = sum(m[1] == 10 and m[2] == 3 for m in fight)
            assert boss_playing > 120, ('boss track playing during the fight', boss_playing)
            report.update(matched_positions=len(expected), observations=len(rows), respawns=respawns,
                          late_gameplay_intervals=late, stage_transitions=stages,
                          tally_sequence=int(tally[1]), act3_score=int(tally[3]),
                          boss_music_sequence=music_at, third_hit_sequence=third_hit,
                          pad_sha256=sha(pad), script_sha256=sha(script), seed=SEEDS[era])
            assert respawns == 0, 'respawn'
            assert not late, ('late gameplay interval', late[:3])
            assert len(stages) == 1 and stages[0]['after'] == [2, 0, 0], ('Tidal Tempest Act 1 handoff', stages)
            handoff = stages[0]['sequence']
            assert scores[handoff] == int(tally[3]), ('carried score', scores[handoff], tally[3])
            # ObjResults_NextLevel: rings count into the ring bonus and the next
            # act starts with none; score, lives and time stones carry.
            results = {r[0]: r[1:] for r in records(log, 'CC results')}
            last_act3 = handoff - 1
            act3_rings, tt1_rings = results[last_act3][2], results[handoff][2]
            assert act3_rings == int(tally[4]), ('Act 3 rings at the tally', act3_rings, tally[4])
            assert tt1_rings == 0 and all(results[s][2] == 0 for s in results if s >= handoff), 'Tidal Tempest rings reset'
            if args.cont:
                # main.c's zone change: goodFutureFlags clear, an Act 3 Good
                # Future adds the zone to the saved good zones, and
                # save_checkpoint(0) commits Tidal Tempest Act 1 in the Present.
                saves = {s[0]: s[1:] for s in records(log, 'CC save')}
                before, after = saves[handoff - 1], saves[max(saves)]
                assert before[6] == 1 | 2 << 8 | era_index << 16, ('Act 3 live stage', hex(before[6]))
                assert after[3] == before[3] + 1 and after[4] == 2 and after[6] == 2, ('Tidal Tempest checkpoint', after)
                good_zone = bool((after[5] >> 8) & 2)
                assert good_zone == (era == 'C') and after[5] & 0xff == 0 and after[7] & 0xff == 0, ('saved futures', hex(after[5]))
                prior_zones = before[5] & 0x00ffff00
                assert (after[5] & 0x00ffff00) == (prior_zones | (0x200 if era == 'C' else 0)), ('preserved good zones', hex(after[5]))
                assert (out/'backup-after.bin').read_bytes() != backup.read_bytes(), 'backup RAM did not advance'
                cold = out / 'cold-continue'
                env2 = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
                env2.update(SCD_BACKUP_INPUT=str(out/'backup-after.bin'), SCD_SAVE_OUTPUT_DIR=str(cold))
                with (out/'cold-continue.log').open('w') as output:
                    subprocess.run(['bash', 'tools/test-save-emulator.sh', 'continue'], cwd=ROOT, env=env2,
                                   stdout=output, stderr=subprocess.STDOUT, check=True, timeout=600)
                saved = json.loads((cold/'save.json').read_text())
                mailbox, track = saved['mailbox'][:10], saved['trace'][23] & 0xfff
                assert mailbox[4:6] == after[3:5] and mailbox[7] == 2 and mailbox[9] == 1, ('cold Continue', mailbox)
                # Tidal Tempest Present: slot 10+(2-1)*4 = 14, mailbox track 16.
                assert track == 0x310, ('cold Continue track', hex(track))
                assert (cold/'backup.bin').read_bytes() == (out/'backup-after.bin').read_bytes()
                report.update(save_before=before, save_after=after, good_zone_saved=good_zone,
                              cold_continue_mailbox=mailbox, cold_continue_track=track,
                              backup_after_sha256=sha(out/'backup-after.bin'))
            report.update(handoff_sequence=handoff, carried_score=scores[handoff], act3_tally_rings=act3_rings, tidal_tempest_rings=tt1_rings, boss_track_playing_updates=boss_playing, status='passed', passed=True,
                          limits=__doc__.split('\n\n', 1)[1].strip())
            summary.append(f'{era}: {len(expected)} positions, 3 boss hits, tally {tally[1]}, '
                           f'Tidal Tempest Act 1 at {handoff}, score {scores[handoff]}, rings {act3_rings}->0')
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          error=repr(error)[:2000])
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    if args.host_only:
        print('HOST-ONLY: CC3 host routes; ' + '; '.join(summary))
        return
    print(('PASS: CC3 Continue routes into a saved, cold-Continued Tidal Tempest' if args.cont else 'PASS: CC3 controller routes into Tidal Tempest')+' with 0 respawns and 0 late intervals; ' + '; '.join(summary))


if __name__ == '__main__':
    main()
