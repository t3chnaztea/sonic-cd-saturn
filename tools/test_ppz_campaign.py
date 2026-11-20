#!/usr/bin/env python3
"""Earned Good Future campaign through Palmtree Panic, from the real title menu.

Three Saturn runs, each from the backup RAM the previous run wrote (no save is
constructed and no gameplay RAM is written):

  --act 1  PPZ1 from NEW GAME on blank backup RAM: Present, natural travel to
           the Past, destroy the robot generator, travel back to the Present
           and on to the Good Future, finish the act there. The Act 2 save must
           carry good-future flag bit 0.
  --act 2  PPZ2 from CONTINUE on the --act 1 save: the same journey in Act 2.
           Both flags set, so the tally must hand off to Act 3 in the Good
           Future (era C).
  --act 3  PPZ3 Good Future from the --act 2 save: boss, capsule, results and
           the Collision Chaos Act 1 save, then a cold Continue of that save.

Original rules (.deps/scddisasm/src): Level/_Objects/Robot Generator/Main.asm
sets goodFuture when the generator is destroyed (and adds 1,500 points);
Level/_Objects/Results/Main.asm:301-310 moves goodFuture into goodFutureFlags
bit (act-1) at the Act 1/2 results and sets goodFuture for Act 3 once the flags
are %11; Results/Main.asm:287-290 clears the flags after Act 3.

Host: tools/cc_campaign_search.c in its Palmtree Panic journey mode (pJ0, pJ1:
Present -> Past -> generator -> Present -> Good Future -> tally, with the natural
warp arrival of src/main.c load_era()) and plain mode p2:C for Act 3. Routes:
tests/routes/ppz/pJ0.txt, pJ1.txt, p2C.txt (the level-select Good Future route).

Not hardware acceptance. Pass --cue/--elf copies so a parallel rebuild cannot
change the disc mid-run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from test_tt_travel import elf_matches_disc  # noqa: E402
from test_cc_campaign_route import campaign_harness  # noqa: E402

CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
NM = ROOT / '.toolchain/bin/sh-elf-nm'
TAIL = 300
NATIVE = [f'src/{n}.c' for n in ('title_card', 'world', 'act', 'player', 'camera_v', 'sonic_animation',
                                 'stage', 'boss', 'boss_r3', 'objects')]
ORIGINAL = ['boss_1', 'boss_3', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
ROUTE = {0: ('pJ0', 'pJ0'), 1: ('pJ1', 'pJ1'), 2: ('p2:C', 'p2C')}
ZONE = 0
NEXT_ZONE = 1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(log, label):
    return [list(map(int, line.split(': ', 1)[1].split()))
            for line in log.splitlines() if line.startswith(label + ': ')]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--script', type=Path, help='another route script for this act')
    parser.add_argument('--backup', type=Path, help='entry backup RAM (default: the previous link of the chain; '
                                                    'none for Act 1, which starts a NEW GAME)')
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--cue', type=Path, default=ROOT/'dist/sonic-cd-saturn-prototype.cue')
    parser.add_argument('--elf', type=Path, default=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    args = parser.parse_args()
    act = args.act - 1
    era = 'C' if act == 2 else 'A'
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='pending', passed=False, hardware_tested=False, zone='PPZ', act=args.act, start_era=era, steps=[])
    report_path = out / 'report.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def run(name, command, env=None, timeout=3600):
        report['steps'].append(dict(name=name, command=list(map(str, command)), status='pending'));save()
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        report['steps'][-1].update(status='passed' if result.returncode == 0 else 'failed', exit_code=result.returncode);save()
        assert result.returncode == 0, (name, result.returncode, out/(name+'.log'))
    save()
    try:
        host = out/'cc_campaign_search'
        original = [f'build/probe-source/{n}.c' for n in ORIGINAL]
        run('compile-host', ['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                             '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source',
                             '-DR1', '-DR11A', 'tools/cc_campaign_search.c', *NATIVE, *original, '-o', host])
        mode, name = ROUTE[act]
        src = args.script or ROOT/f'tests/routes/ppz/{name}.txt'
        script = out/'script.txt'
        script.write_text(src.read_text())
        report.update(script_source=str(src), host_inputs={p: sha(ROOT/p) for p in ['tools/cc_campaign_search.c', *NATIVE, *original]})
        pad = out/'controller.txt'
        env = {k: v for k, v in os.environ.items() if k != 'PPZ_DIRECT_ENTRY'}
        run('host-replay', [host, 'replay', mode, script, 40000, pad], env=env)
        hlog = (out/'host-replay.log').read_text()
        tally = re.search(r'Tally complete: sequence=(\d+) era=(\d+) good_future=(\d+) generator=(\d+) warps=(\d+) '
                          r'score=(\d+) act=(\d+) leg=\d+ lives=\d+ good_flags=(\d+)', hlog)
        assert tally, 'host route did not finish the tally'
        if act < 2:
            assert tally[2] == '2' and tally[3] == '1' and int(tally[4]) > 0 and tally[5] == '3', ('host journey', tally[0])
        else:
            assert tally[2] == '2', ('host Act 3 era', tally[0])
        expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
        report.update(host_tally=tally[0], host_positions=len(expected), script_sha256=sha(script), pad_sha256=sha(pad),
                      host_generator_sequence=int(tally[4]))
        if args.host_only:
            report.update(status='host-only');save()
            print(f'HOST: PPZ{args.act} campaign {len(expected)} positions; {tally[0]}; Saturn verification pending')
            return
        cue, elf = args.cue.resolve(), args.elf.resolve()
        disc = cue.parent/re.search(r'FILE "([^"]+)"', cue.read_text())[1]
        disc_sha, elf_sha = sha(disc), sha(elf)
        assert elf_matches_disc(elf, disc, out), 'ELF program is not the disc A.BIN'
        listing = subprocess.check_output([NM, elf], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        backup = args.backup.resolve() if args.backup else (None if act == 0 else
                                                            (out.parent/f'PPZ{args.act-1}'/'backup-after.bin').resolve())
        if backup:
            assert backup.is_file() and backup.stat().st_size == 32768, ('entry backup', backup)
        backup_sha = sha(backup) if backup else None
        report.update(cue=str(cue), disc_sha256=disc_sha, elf_sha256=elf_sha, entry_backup=str(backup) if backup else None,
                      entry_backup_sha256=backup_sha, harness_sha256=sha(ROOT/'tools/emulator_test.c'),
                      core_sha256=sha(CORE))
        save()
        # NEW GAME (menu entry 1) for Act 1; CONTINUE (entry 2) on the saved Acts 2 and 3.
        exe = campaign_harness(out, False, None, menu=1 if backup is None else 2)
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE=str(ZONE), SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                   SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                   SCD_ZONE_ROUTE_UPDATES=str(len(expected)+TAIL), SCD_ZONE_PAD_TAIL=str(TAIL),
                   SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_BACKUP_OUTPUT=str(out/'backup-after.bin'))
        if backup:
            env['SCD_BACKUP_INPUT'] = str(backup)
        command = [exe, CORE, cue, ROOT/'assets/private', out, symbols['_scd_trace_mailbox'],
                   symbols['_scd_audio_mailbox'], 'zones']
        report['steps'].append(dict(name='saturn', command=list(map(str, command)), status='pending'));save()
        with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=7200)
        report['steps'][-1].update(status='passed' if result.returncode == 0 else 'failed', exit_code=result.returncode);save()
        core = (out/'core.log').read_text()
        assert result.returncode == 0, (re.search(r'CC pad mismatch: .*', core) or [f'emulator exit {result.returncode}'])[0]
        log = (out/'results.log').read_text()
        rows, future = records(log, 'CC route'), records(log, 'CC future')
        saves = {s[0]: s[1:] for s in records(log, 'CC save')}
        results = records(log, 'CC results')
        warp = dict(records(log, 'CC warp'))
        n = len(expected)
        assert len(rows) == len(future) == n + TAIL, ('observation count', len(rows), len(future), n + TAIL)
        for row in rows:
            row[3] -= (row[3] >= 1 << 31) << 32
        mismatch = next(((row[0], row[2:4], ref[2:4]) for row, ref in zip(rows, expected)
                         if [row[0], row[8], row[2], row[3]] != ref), None)
        assert mismatch is None, ('host/Saturn position', mismatch)
        assert all(b[0] == a[0] + 1 for a, b in zip(rows, rows[1:])), 'lost observation'
        respawns = max(r[6] for r in rows)
        assert respawns == 0, 'respawn'
        late = [(a[0], b[0], b[1]-a[1]) for a, b in zip(rows, rows[1:])
                if a[9:] == b[9:] and not warp.get(b[0]) and b[1]-a[1] != 1]
        assert not late, ('late gameplay interval', late[:3])
        changes = [(a, b) for a, b in zip(rows, rows[1:]) if a[9:12] != b[9:12]]
        report.update(stage_transitions=[dict(sequence=b[0], vblanks=b[1]-a[1], before=a[9:12], after=b[9:12])
                                         for a, b in changes])
        assert rows[0][9:12] == [ZONE, act, 'ABCD'.index(era)], ('start', rows[0][9:12])
        before = saves.get(rows[0][0])
        if backup:
            assert before and before[4] & 0xffff == ZONE | act << 8, ('entry save stage', before)
        after = saves[max(saves)]
        # NEW GAME writes its own PPZ1 record first (src/main.c); count from that one.
        count = before[3] if before else 0
        if act < 2:
            # Present -> Past -> Present -> Good Future -> next act.
            assert len(changes) == 4, ('transitions', report['stage_transitions'])
            eras = [a[11] for a, b in changes] + [changes[-1][1][11]]
            assert [a[9:11] for a, b in changes[:3]] == [[ZONE, act]] * 3 and eras[:4] == [0, 1, 0, 2], ('journey', eras)
            (wa, wb) = changes[0]
            assert wb[1]-wa[1] >= 240, 'natural Present -> Past warp'
            gen = next(i for i, f in enumerate(future) if f[1])
            ha, hb = changes[-1]
            assert all(f[1] == 0 for f in future[:gen]) and all(f[1] for f in future[gen:rows.index(ha)+1])
            assert rows[gen][11] == 1 and rows[gen][0] == int(tally[4]), ('generator in the Past', rows[gen][0:12], tally[4])
            assert future[gen][4] - future[gen-1][4] == 1500, 'generator points'
            want = [ZONE, 1, 0] if act == 0 else [ZONE, 2, 2]
            assert ha[9:12] == [ZONE, act, 2] and hb[9:12] == want, ('act handoff', ha[9:12], hb[9:12])
            phases = list(dict.fromkeys(r[1] for r in results if r[0] < hb[0]))
            assert phases[-7:] == list(range(7)), ('Good Future sign/tally sequence', phases)
            stage = ZONE | (act + 1) << 8 | (2 << 16 if act == 1 else 0)
            good = 1 if act == 0 else 3
            assert after[3] == count + 1 and after[4] == stage and after[5] & 0xff == good, ('checkpoint', after, hex(stage))
            facts = dict(warp_sequence=wa[0], arrival_sequence=wb[0], generator_sequence=rows[gen][0],
                         generator_xy=rows[gen][2:4], generator_points=future[gen][4]-future[gen-1][4],
                         eras=eras, handoff_sequence=hb[0], handoff=hb[9:12])
        else:
            assert len(changes) == 1 and changes[0][1][9:12] == [NEXT_ZONE, 0, 0], ('CC handoff', report['stage_transitions'])
            hb = changes[0][1]
            assert all(r[9:12] == [ZONE, 2, 2] for r in rows[:n]), 'left Act 3 Good Future early'
            phases = list(dict.fromkeys(r[1] for r in results if r[0] < hb[0]))
            # Act 3 has the capsule, not the sign: no SCD_ACT_SPIN (src/act.h).
            assert phases == [0, 2, 3, 4, 5, 6], ('Act 3 results sequence', phases)
            assert after[3] == count + 1 and after[4] == NEXT_ZONE, ('CC checkpoint', after)
            # main.c zone change: goodFutureFlags clear; PPZ (zone 0) joins the saved good zones.
            assert after[5] & 0xff == 0 and after[5] & (0x100 << ZONE), ('saved good zones', hex(after[5]))
            facts = dict(handoff_sequence=hb[0], handoff=hb[9:12])
        report.update(save_before=before, save_after=after)
        if backup:
            assert (out/'backup-after.bin').read_bytes() != backup.read_bytes(), 'backup RAM did not advance'
        if act == 2:
            cold = out/'cold-continue'
            cold.mkdir()
            env2 = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            env2.update(SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_SAVE_CASE='continue',
                        SCD_BACKUP_INPUT=str(out/'backup-after.bin'), SCD_BACKUP_OUTPUT=str(cold/'backup.bin'))
            plain = out/'emulator_save'
            run('compile-save-harness', ['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                         '-I.deps/beetle-saturn/libretro-common/include', 'tools/emulator_test.c', '-o', plain])
            with (cold/'results.log').open('w') as o, (cold/'core.log').open('w') as e:
                subprocess.run(list(map(str, [plain, CORE, cue, ROOT/'assets/private', cold, symbols['_scd_trace_mailbox'],
                                              symbols['_scd_audio_mailbox'], 'save'])), cwd=ROOT, env=env2,
                               stdout=o, stderr=e, check=True, timeout=600)
            saved = json.loads((cold/'save.json').read_text())
            mailbox = saved['mailbox'][:10]
            assert mailbox[4:6] == after[3:5] and mailbox[6] == after[5], ('cold Continue', mailbox)
            assert (cold/'backup.bin').read_bytes() == (out/'backup-after.bin').read_bytes()
            facts.update(cold_continue_mailbox=mailbox)
        assert sha(disc) == disc_sha and sha(elf) == elf_sha and (not backup or sha(backup) == backup_sha), \
            'inputs changed during the run'
        report.update(facts, status='passed', passed=True, matched_positions=n, observations=len(rows),
                      respawns=respawns, late_gameplay_intervals=late, backup_after_sha256=sha(out/'backup-after.bin'),
                      limits='Emulator (Beetle Saturn) replay of a native-host pad route from NEW GAME and earned '
                             'Continue saves. Not hardware acceptance or whole-act retail parity.')
        save()
        what = (f"generator at {facts['generator_sequence']}, eras {facts['eras']}, handoff {facts['handoff']}" if act < 2
                else f"boss, results, CC save, cold Continue {facts['cold_continue_mailbox'][4:7]}")
        print(f'PASS: PPZ{args.act} earned campaign; {n} matched positions; 0 respawns; 0 late; {what}; disc {disc_sha[:12]}')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error)[:2000])
        save()
        raise


if __name__ == '__main__':
    main()
