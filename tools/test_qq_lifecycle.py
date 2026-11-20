#!/usr/bin/env python3
"""QQ slave-owner fixtures: repeated era loads, game-over/title, special/return.

These fixtures exercise real transition paths after a level-select entry.
They are not proof of natural time-travel routes or whole-act retail parity.
The special fixture writes Sonic's position/rings near the original goal.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['era', 'title', 'special'], action='append')
    args = parser.parse_args()
    out = ROOT/'build/qq-lifecycle'
    out.mkdir(exist_ok=True)
    report = dict(passed=False, status='pending', disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
                  source_sha256={n: sha(ROOT/n) for n in ['tools/test_qq_lifecycle.py', 'tools/emulator_test.c',
                                                          'src/main.c', 'src/audio.c', 'src/special_view.inc', 'src/title_view.inc']},
                  core_sha256=sha(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'), cases={})
    def save(): (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    try:
        exe = out/'emulator'
        subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', 'tools/emulator_test.c', '-o', str(exe)], cwd=ROOT, check=True)
        listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm', ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        for case in args.case or ['era', 'title', 'special']:
            folder = out/case;folder.mkdir(exist_ok=True)
            report['cases'][case] = dict(status='pending', passed=False);save()
            env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            env.update(SCD_ZONE='3', SCD_ZONE_ACT='0', SCD_ZONE_ERA='0',
                       SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                       SCD_OBJECTS_OVERLAY_FAULT=symbols['_scd_objects_overlay_fault'],
                       SCD_QQ_SLAVE_READY=symbols['_bg_slave_ready'], SCD_TITLE_MAILBOX=symbols['_scd_title_mailbox'])
            if case == 'special':
                # Verify the fixture coordinates against the compiled-original source table.
                original = ROOT/'.deps/soniccd/src/R5/Z51ACT.C'
                placements = [list(map(int, re.findall(r'\d+', line))) for line in original.read_text().splitlines() if '{' in line]
                assert [11064, 948, 151, 0, 64, 0] in placements
                assert [11168, 864, 148, 0, 224, 0] in placements
                report['original_layout_sha256'] = sha(original)
                env.update(SCD_CC_SPECIAL_ACTWK=symbols['_actwk'], SCD_CC_SPECIAL_RINGS=symbols['_plring'],
                           SCD_SFX_BANK_MAILBOX=symbols['_scd_sfx_bank_mailbox'])
            else: env['SCD_QQ_LIFECYCLE'] = case
            command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                       ROOT/'dist/sonic-cd-saturn-prototype.cue', ROOT/'assets/private', folder,
                       symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
            with (folder/'results.log').open('w') as stdout, (folder/'core.log').open('w') as stderr:
                result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=1800)
            text = (folder/'results.log').read_text()
            expected = ('CC special probe passed:' if case == 'special' else f'QQ lifecycle passed: {case}')
            assert result.returncode == 0 and expected in text, (case, result.returncode, (folder/'core.log').read_text()[-1200:])
            if case == 'special': assert 'zone=3 act=1 bank=4 ' in text
            if case == 'era': assert len(re.findall(r'^QQ lifecycle era:', text, re.M)) == 8
            report['cases'][case] = dict(status='passed', passed=True, log_sha256=sha(folder/'results.log'),
                                        summary=next(line for line in text.splitlines() if line.startswith(expected)))
            save();print('PASS: QQ lifecycle '+case, flush=True)
        report.update(status='passed', passed=True)
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error))
        save();raise
    save()
    print('PASS: QQ slave lifecycle: '+', '.join(report['cases']))


if __name__ == '__main__': main()
