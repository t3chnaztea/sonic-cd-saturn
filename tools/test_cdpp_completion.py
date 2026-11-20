#!/usr/bin/env python3
"""Replay CD++ completion recordings on the current BIN. Emulator evidence only.

No arguments requires Act 1 Present and both boss eras in all seven zones.
--case selects a diagnostic subset; it never proves complete coverage.
Missing recordings or unsupported checks fail. Reports remain pending until
the run passes, fails, or is interrupted. Outputs use a fresh run directory.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import cdpp_fuzz as hosts
import test_cdpp_routes as settings

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / 'tests/routes/cdpp/completion'
ZONES = ('ppz', 'cc', 'tt', 'qq', 'ww', 'ss', 'mm')
CASES = {f'{zone}{act}{era}': (zone, act - 1, era)
         for zone in ZONES for act, era in ((1, 'A'), (3, 'C'), (3, 'D'))}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, action='append')
    args = parser.parse_args()
    selected = list(dict.fromkeys(args.case or CASES))
    out = ROOT / 'build/cdpp-completion' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True)
    (out / 'verifier.py').write_bytes(Path(__file__).read_bytes())
    (out / 'recording-metadata.json').write_bytes((ROUTES / 'provenance.json').read_bytes())
    inputs = [Path(__file__).resolve(), ROOT / 'tools/cdpp_fuzz.py',
              ROOT / 'tools/test_cdpp_routes.py', ROOT / 'tools/emulator_test.c',
              ROOT / 'tools/frontend_emulator_test.c', ROOT / 'tools/cc_campaign_search.c',
              ROOT / 'tools/cc3_route_host.c', ROOT / 'tools/tt_route_search.c',
              ROOT / 'tools/qq_route_search.c', ROOT / 'tools/test_mm_campaign.py',
              ROOT / 'tools/test_cc_campaign_route.py']
    inputs += list((ROOT / 'tools').glob('*.h'))
    # Include headers, generated terrain and packs used by the host, not only
    # translation units. Hosts are compiled anew for each run.
    inputs += [p for folder in ('src', 'assets/generated', 'build/probe-source')
               for p in (ROOT / folder).iterdir()
               if p.is_file() and p.suffix in ('.c', '.h', '.H', '.inc', '.bin')]
    report = dict(status='pending', passed=False, hardware_tested=False,
                  coverage_complete=False, required_cases=list(CASES), selected_cases=selected,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  disc_sha256=sha(settings.DISC), cue_sha256=sha(settings.CUE), elf_sha256=sha(settings.ELF),
                  recording_metadata_sha256=sha(out / 'recording-metadata.json'),
                  compiler=subprocess.check_output(['clang', '--version'], text=True).splitlines()[0],
                  inputs={str(p.relative_to(ROOT)): sha(p) for p in sorted(set(inputs))}, cases={})

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    save()
    try:
        # Full QA can regenerate dist in place. Each route run reads one fixed
        # image, including cold boots and any later CD loads.
        disc_dir = out / 'disc'
        disc_dir.mkdir()
        for label, source in (('DISC', settings.DISC), ('CUE', settings.CUE), ('ELF', settings.ELF)):
            snapshot = disc_dir / source.name
            shutil.copyfile(source, snapshot)
            expected = report[{'DISC': 'disc_sha256', 'CUE': 'cue_sha256', 'ELF': 'elf_sha256'}[label]]
            assert sha(snapshot) == expected, f'{label} changed while taking input snapshot'
            setattr(settings, label, snapshot)
        report['input_snapshot'] = str(disc_dir.relative_to(ROOT))
        save()
        manifest = json.loads((out / 'recording-metadata.json').read_text())['recordings']
        missing = []
        for name in selected:
            path = ROUTES / f'{name}.txt'
            if name not in manifest or not path.is_file():
                report['cases'][name] = dict(status='missing', passed=False)
                missing.append(name)
            else:
                assert sha(path) == manifest[name]['sha256'], (name, 'recording hash')
                report['inputs'][str(path.relative_to(ROOT))] = sha(path)
        save()
        if missing:
            raise ValueError('missing CD++ completion recordings: ' + ', '.join(missing))
        syms = settings.symbols()
        settings.OUT = out / 'settings'
        settings.OUT.mkdir()
        settings.report = dict(status='pending', passed=False, cases={}, hardware_tested=False,
                               disc_sha256=report['disc_sha256'])
        settings.save()
        subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', 'tools/frontend_emulator_test.c',
                        '-o', str(settings.OUT / 'frontend_emulator_test')], cwd=ROOT, check=True)
        report['settings_result'] = settings.case_toggle(syms)
        settings.report.update(status='passed', passed=True)
        settings.save()
        exe = out / 'emulator'
        subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', 'tools/emulator_test.c',
                        '-o', str(exe)], cwd=ROOT, check=True)
        built = {}
        for name in selected:
            zone, act, era = CASES[name]
            folder = out / name
            folder.mkdir()
            entry = report['cases'][name] = dict(status='pending', passed=False, flags=31)
            save()
            kind = zone if zone not in ('ppz', 'cc') else 'cc3' if zone == 'cc' and act == 2 else 'cc'
            if kind not in built:
                source, native, original, extra = hosts.HOSTS[kind]
                host = out / kind
                command = ['nice', '-n', '20', 'clang', '-std=gnu11', '-O1', '-fsigned-char',
                           '-fwrapv', '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
                           '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                           '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
                           '-DSCD_PLUS_HOST_FLAGS=31', *extra, source, *native, 'src/player_plus.c',
                           *[f'build/probe-source/{n}.c' for n in hosts.CORE + original], '-o', str(host)]
                entry['compile_command'] = command
                with (out / f'{kind}-compile.log').open('w') as log:
                    subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)
                built[kind] = host
            script, pad = ROUTES / f'{name}.txt', folder / 'rows.txt'
            prefix = [] if kind == 'cc3' else [f'{"p" if zone == "ppz" else ""}{act}:{era}']
            suffix = [era] if kind == 'cc3' else []
            env = {k: v for k, v in os.environ.items() if not k.startswith(('SCD_', 'CC_', 'PPZ_', 'TT_', 'QQ_'))}
            env['ASAN_OPTIONS'] = 'detect_leaks=0'
            with (folder / 'host.log').open('w') as log:
                limit = '40000' if kind in ('cc', 'cc3') else '46000'
                subprocess.run([str(built[kind]), 'replay', *prefix, str(script), *suffix, limit, str(pad)],
                               cwd=ROOT, env=env, stdout=log, stderr=log, check=True, timeout=600)
            host_log = (folder / 'host.log').read_text()
            assert 'Tally complete:' in host_log, (name, 'no tally')
            if kind == 'cc3':
                assert re.search(r'boss_hits=3 music_hits=3', host_log), (name, 'boss did not finish')
            if kind == 'tt':
                tally = re.search(r'Tally complete: sequence=(\d+) act=\d+ era=\d+ score=\d+ min_air=(\d+) boss_hits=(\d+) egg=(\d+)', host_log)
                assert tally and int(tally[2]) > 0, (name, 'air ran out or no tally')
                if act == 2:
                    assert int(tally[3]) >= 4 and int(tally[4]) == 1, (name, 'boss did not finish')
                entry.update(min_air=int(tally[2]), boss_hits=int(tally[3]), egg_seen=int(tally[4]))
            if kind in ('qq', 'ww', 'ss', 'mm'):
                tally = re.search(r'Tally complete: sequence=(\d+) act=\d+ era=\d+ score=\d+ boss_hits=(\d+) lowered=(\d+) grind_left=(-?\d+) escaped=(\d+)', host_log)
                assert tally, (name, 'no tally')
                if act == 2:
                    if kind == 'mm':
                        assert 'MM ending complete: seen=1 hits=4 escaped=1 amy=1 game_end=1' in host_log, (name, 'boss/Amy/game end did not finish')
                        entry['host_ending_complete'] = True
                    elif kind == 'ss':
                        assert 'SS race complete: seen=1 race=1 result=1 escaped=1 stationary=1' in host_log, (name, 'race did not finish')
                        entry['race_complete'] = True
                    else:
                        assert int(tally[2]) >= (4 if kind == 'ww' else 2) and int(tally[5]) == 1, (name, 'boss did not finish')
                entry.update(boss_hits=int(tally[2]), lowered=int(tally[3]), grind_left=int(tally[4]), escaped=int(tally[5]))
            expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
            assert expected, (name, 'empty host replay')
            final = zone == 'mm' and act == 2
            tail = 0 if final else 300
            route_exe = exe
            if final:
                # Keep level-select entry and ordinary controller replay. Reuse
                # the campaign's observer only after EMIE8 ends the route.
                from test_mm_campaign import game_end_harness
                text = (ROOT / 'tools/emulator_test.c').read_text()
                declaration = 'seen=0,phase=0,wait=0,go=0,play=0'
                assert text.count(declaration) == 1, 'ending observer declaration changed'
                (folder / 'campaign_emulator.c').write_text(text.replace(
                    declaration, 'seen=0,wait=0,go=0,phase=0,play=0'))
                route_exe = game_end_harness(folder)
                entry['ending_harness_sha256'] = sha(folder / 'campaign_emulator.c')
            env.update(SCD_ZONE=str(ZONES.index(zone)), SCD_ZONE_ACT=str(act),
                       SCD_ZONE_ERA=str('ABCD'.index(era)), SCD_WORLD_MAILBOX=syms['_scd_world_mailbox'],
                       SCD_OBJECTS_OVERLAY_FAULT=syms['_scd_objects_overlay_fault'],
                       SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                       SCD_ZONE_ROUTE_UPDATES=str(len(expected) + tail), SCD_ZONE_PAD_TAIL=str(tail),
                       SCD_BACKUP_INPUT=str(settings.OUT / 'backup-cdpp.bin'),
                       SCD_ZONE_ROUTE_SHOTS=f'{expected[0][0]+1},{expected[-1][0]}',
                       SCD_ZONE_ROUTE_PEEK=f'{int(syms["_scd_save_mailbox"],16)+44:x}:1')
            with (folder / 'results.log').open('w') as log, (folder / 'core.log').open('w') as core:
                subprocess.run(['nice', '-n', '20', str(route_exe), str(settings.CORE), str(settings.CUE),
                                str(ROOT / 'assets/private'), str(folder), syms['_scd_trace_mailbox'],
                                syms['_scd_audio_mailbox'], 'zones'], cwd=ROOT, env=env,
                               stdout=log, stderr=core, check=True, timeout=1800)
            log = (folder / 'results.log').read_text()
            rows = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines()
                    if line.startswith('CC route: ')]
            assert len(rows) == len(expected) + tail, (name, 'observation count')
            for row in rows:
                row[3] -= (row[3] >= 1 << 31) << 32
            for row, ref in zip(rows, expected):
                assert [row[0], row[8], row[2], row[3]] == ref, (name, 'position', row, ref)
            assert all(b[0] == a[0] + 1 for a, b in zip(rows, rows[1:])), 'lost observation'
            late = [b[0] for a, b in zip(rows, rows[1:]) if a[9:] == b[9:] and b[1] - a[1] > 1]
            transitions = [dict(sequence=b[0], before=a[9:], after=b[9:])
                           for a, b in zip(rows, rows[1:]) if a[9:] != b[9:]]
            peeks = [int(line.split(': ', 1)[1].split()[1], 16) for line in log.splitlines()
                     if line.startswith('Route peek: ')]
            entry.update(matched_positions=len(expected), observations=len(rows), respawns=max(r[6] for r in rows),
                         late_gameplay_intervals=late, stage_transitions=transitions, slot11=peeks, pad_sha256=sha(pad))
            assert all(r[9:12] == [ZONES.index(zone), act, 'ABCD'.index(era)] for r in rows[:len(expected)]), 'early exit'
            assert len(peeks) == 2 and all(v & 65535 == 0x1f1f for v in peeks), ('preset', peeks)
            assert entry['respawns'] == 0 and not late, ('respawn/late interval', entry)
            want = [ZONES.index(zone), 1, 0] if act == 0 else [ZONES.index(zone) + 1, 0, 0]
            if final:
                assert not transitions, ('MM3 must end in the act', transitions)
                ending = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines()
                          if line.startswith('CC game end: ')]
                assert len(ending) == 2 and [e[0] for e in ending] == [1, 2], ('ending/title', ending)
                assert ending[1][1] > ending[0][1] and ending[1][2] >> 17 & 1, ('ending movie not observed', ending)
                entry.update(ending_observed=True, title_frame=ending[1][1], ending_word=ending[1][2])
            else:
                assert len(transitions) == 1 and transitions[0]['after'] == want, ('handoff', transitions)
            entry.update(status='passed', passed=True)
            save()
        assert sha(settings.DISC) == report['disc_sha256'], 'BIN changed during run'
        assert sha(settings.CUE) == report['cue_sha256'], 'CUE changed during run'
        assert sha(settings.ELF) == report['elf_sha256'], 'ELF changed during run'
        assert all(sha(ROOT / path) == digest for path, digest in report['inputs'].items()), 'inputs changed during run'
        report.update(status='passed', passed=True, coverage_complete=set(selected) == set(CASES))
        save()
    except BaseException as error:
        status = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        for entry in report['cases'].values():
            if entry['status'] == 'pending':
                entry.update(status=status, passed=False, error=repr(error))
        report.update(status=status, error=repr(error))
        save()
        print(f'FAIL: CD++ completion; {out}/report.json', flush=True)
        raise
    label = 'PASS' if report['coverage_complete'] else 'PARTIAL PASS'
    print(f'{label}: CD++ completion {len(selected)}/{len(CASES)} cases; {out}/report.json', flush=True)


if __name__ == '__main__':
    main()
