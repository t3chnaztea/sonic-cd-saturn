#!/usr/bin/env python3
"""Collision Chaos special stage and return: the effect bank follows the mode.

Runs tools/emulator_test.c zones mode with SCD_CC_SPECIAL_ACTWK: the level select
enters CC Act 1 Present, a fixture puts Sonic on the big ring with 50 rings (it
writes actwk[0] and plring; not a controller route), the special stage must load
its effect bank (SFXSP.PCM) and the return to Act 2 must load Collision Chaos's
(SFXZ1.PCM) again. Emulator evidence only.
"""
import hashlib, json, os, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'build/cc-special-bank'
    out.mkdir(parents=True, exist_ok=True)
    exe = out / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm', ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
    env.update(SCD_ZONE='1', SCD_ZONE_ACT='0', SCD_ZONE_ERA='0', SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
               SCD_CC_SPECIAL_ACTWK=symbols['_actwk'], SCD_CC_SPECIAL_RINGS=symbols['_plring'],
               SCD_SFX_BANK_MAILBOX=symbols['_scd_sfx_bank_mailbox'])
    command = [exe, ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib', ROOT / 'dist/sonic-cd-saturn-prototype.cue',
               ROOT / 'assets/private', out, symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
    with (out / 'results.log').open('w') as stdout, (out / 'core.log').open('w') as stderr:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=1800)
    log = (out / 'results.log').read_text()
    passed = re.search(r'^CC special probe passed: (.*)$', log, re.M)
    failure = [l for l in (out / 'core.log').read_text().splitlines() if l.startswith('CC special')]
    report = dict(passed=bool(passed) and result.returncode == 0, summary=passed[1] if passed else None,
                  failure=failure[-1] if failure else None, exit_code=result.returncode,
                  image_sha256=hashlib.sha256((ROOT / 'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest())
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(('PASS' if report['passed'] else 'FAIL') + f": CC special stage and return bank ({report['summary'] or report['failure'] or 'exit ' + str(result.returncode)})")
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
