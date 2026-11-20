#!/usr/bin/env python3
"""Run the linked WW3 fight through four hits and escape in Beetle Saturn.

The fixture writes Sonic's position and rings. It is not a controller route or
a hardware result. The retail R63C/D trace is in build/boss6-retail-full.json.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'ww3-boss-full'


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = ['tools/test_ww3_boss_full_emulator.py', 'tools/emulator_test.c',
              'src/boss.c', 'src/boss_r6.c', 'src/main.c',
              'build/boss6-retail-full.json',
              'dist/sonic-cd-saturn-prototype.bin',
              '.deps/beetle-saturn/mednafen_saturn_libretro.dylib']
    report = {'status': 'pending', 'passed': False,
              'inputs': {p: digest(p) for p in inputs}, 'runs': {}}
    path = OUT / 'report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    exe = OUT / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm',
                                       ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    retail = json.loads((ROOT / 'build/boss6-retail-full.json').read_text())
    eras = [e for e in 'CD' if len(sys.argv) == 1 or e in sys.argv[1:]]
    assert eras, 'No valid boss era selected'
    for era in eras:
        run = OUT / era
        run.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='4', SCD_ZONE_ACT='2', SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                   SCD_WW3_BOSS_ACTWK=symbols['_actwk'],
                   SCD_WW3_BOSS_FLAG=symbols['_bossflag'],
                   SCD_WW3_RINGS=symbols['_plring'], SCD_WW3_BOSS_FULL='1',
                   SCD_WW3_BOTTOM=symbols['_scralim_down'])
        command = [exe, ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                   ROOT / 'dist/sonic-cd-saturn-prototype.cue', ROOT / 'assets/private', run,
                   symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
        with (run / 'results.log').open('w') as stdout, (run / 'core.log').open('w') as stderr:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                    stdout=stdout, stderr=stderr, timeout=900)
        log = (run / 'results.log').read_text()
        match = re.search(r'^WW3 full probe passed: (.*)$', log, re.M)
        phases = [tuple(map(int, row)) for row in re.findall(
            r'^WW3 full: t=\d+ routine=(\d+) floor=(\d+) hits=(\d+)', log, re.M)]
        phases = phases[phases.index((2, 0, 0)):phases.index((18, 3, 4)) + 1] if (2, 0, 0) in phases and (18, 3, 4) in phases else []
        expected = [(p['routine'], p['floor'], p['hits']) for p in retail['R63' + era]['phases'] if p['routine'] >= 2]
        scroll = {floor: bottom for floor, bottom in re.findall(
            r'^WW3 scroll: floor=(\d+) bottom=(\d+)$', log, re.M)}
        target_scroll = retail['R63' + era]['scroll_samples']
        scroll_match = set(scroll) == set(target_scroll) and all(
            abs(int(scroll[level]) - target_scroll[level]) <= 8 for level in scroll)
        failure = [line for line in (run / 'core.log').read_text().splitlines()
                   if line.startswith('WW3 full:')]
        good = (result.returncode == 0 and bool(match) and 'hits=4 ' in match[1]
                and ' next_zone=5 act=0 ' in match[1] and phases == expected and scroll_match)
        report['runs'][era] = {'passed': good, 'exit_code': result.returncode,
                               'summary': match[1] if match else None,
                               'retail_phases_match': phases == expected,
                               'phase_count': len(phases),
                               'scroll_samples': scroll, 'retail_scroll_samples': target_scroll,
                               'scroll_match': scroll_match,
                               'failure': failure[-1] if failure else None,
                               'log_sha256': digest(run / 'results.log')}
        path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'R63{era}: {"PASS" if good else "FAIL"} '
              f'{match[1] if match else (failure[-1] if failure else result.returncode)}', flush=True)
        if not good:
            report.update(status='failed', passed=False)
            path.write_text(json.dumps(report, indent=2) + '\n')
            raise SystemExit(1)
    report.update(status='passed', passed=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: WW3 boss, capsule, results and next-zone handoff in both futures' if len(eras) == 2
          else f'PASS: WW3 boss, capsule, results and next-zone handoff in R63{eras[0]}')


if __name__ == '__main__':
    main()
