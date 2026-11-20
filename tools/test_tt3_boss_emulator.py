#!/usr/bin/env python3
"""Tidal Tempest Act 3 boss probe on the Saturn build (both futures).

Runs tools/emulator_test.c zones mode with SCD_TT3_BOSS_ACTWK: the level select
enters R43C or R43D, a fixture places Sonic at the boss (it writes actwk[0]; it
is not a controller route), and the probe requires egg4air (BOSS_4.C) to spawn
and take its four hits, bossflag 4 at the exit, egg4 (BOSS_4_2.C) to spawn and
take its hit, and the capsule, results and the handoff to Quartz Quadrant Act 1
to follow. Emulator evidence only; not a hardware result.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'build/tt3-boss'
    out.mkdir(parents=True, exist_ok=True)
    exe = out / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm', ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    report = {'image_sha256': hashlib.sha256((ROOT / 'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(), 'runs': {}}
    ok = True
    # Optional era filter (C or D) for a single run; the gate runs both.
    for era in [e for e in ('C', 'D') if len(sys.argv) < 2 or e in sys.argv[1:]]:
        run = out / era
        run.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_') or k == 'SCD_TT3_DEBUG'}
        env.update(SCD_ZONE='2', SCD_ZONE_ACT='2', SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'], SCD_TT3_BOSS_ACTWK=symbols['_actwk'],
                   SCD_TT3_BOSS_FLAG=symbols['_bossflag'], SCD_TT3_RINGS=symbols['_plring'])
        command = [exe, ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib', ROOT / 'dist/sonic-cd-saturn-prototype.cue',
                   ROOT / 'assets/private', run, symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
        with (run / 'results.log').open('w') as stdout, (run / 'core.log').open('w') as stderr:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=1500)
        log = (run / 'results.log').read_text()
        passed = re.search(r'^TT3 boss probe passed: (.*)$', log, re.M)
        failure = [l for l in (run / 'core.log').read_text().splitlines() if l.startswith('TT3 boss')]
        # BOSS_4.C: four egg4air hits; the handoff is Quartz Quadrant (zone 3) Act 1.
        good = bool(passed) and result.returncode == 0 and ' hits=4 ' in passed[1] and ' next_zone=3 act=0 ' in passed[1]
        report['runs'][era] = dict(exit_code=result.returncode, passed=good,
                                   summary=passed[1] if passed else None, failure=failure[-1] if failure else None)
        ok &= good
        print(f"R43{era}: {'PASS' if good else 'FAIL'} {passed[1] if passed else (failure[-1] if failure else 'exit ' + str(result.returncode))}")
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(('PASS' if ok else 'FAIL') + ': TT3 boss emulator probe, build/tt3-boss/report.json')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
