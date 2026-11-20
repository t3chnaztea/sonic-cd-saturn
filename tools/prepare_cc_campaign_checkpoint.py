#!/usr/bin/env python3
"""Earn a CC1 Present checkpoint by normal play, then prove cold Continue."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cc1/generator'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
BACKUP = OUT / 'campaign-sequence.bin'
COLD = OUT / 'campaign-continue'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, command, **settings):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SCD_')}
    env.update({key: str(value) for key, value in settings.items()})
    log_path = OUT / f'campaign-checkpoint-{name}.log'
    with log_path.open('w') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        print(log_path.read_text()[-6000:])
        raise SystemExit(f'{name} failed with exit {result.returncode}; {log_path}')
    return log_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ppz3-report', type=Path,
                        help='use the earned PPZ3 Good Future handoff as the CC1 checkpoint')
    parser.add_argument('--output', type=Path, default=OUT / 'campaign-checkpoint-report.json')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    disc_hash = digest(DISC)
    if args.ppz3_report:
        source = args.ppz3_report.resolve()
        ppz3 = json.loads(source.read_text())
        backup = source.parent / 'backup-after.bin'
        for act in (1, 2, 3):
            link = source.parent.parent / f'PPZ{act}' / 'report.json'
            record = json.loads(link.read_text())
            saved = link.parent / 'backup-after.bin'
            assert record['passed'] and record['status'] == 'passed' and record['disc_sha256'] == disc_hash
            assert record['zone'] == 'PPZ' and record['act'] == act
            assert len(saved.read_bytes()) == 32768 and digest(saved) == record['backup_after_sha256']
            if act == 1:
                assert record['entry_backup'] is None, 'PPZ1 did not start a New Game'
            else:
                previous = source.parent.parent / f'PPZ{act-1}' / 'backup-after.bin'
                assert Path(record['entry_backup']).resolve() == previous.resolve()
                assert record['entry_backup_sha256'] == digest(previous)
        assert ppz3['passed'] and ppz3['status'] == 'passed' and ppz3['zone'] == 'PPZ' and ppz3['act'] == 3
        assert ppz3['disc_sha256'] == disc_hash, 'PPZ3 used a different BIN'
        assert ppz3['handoff'] == [1, 0, 0], 'PPZ3 did not enter CC1 Present'
        assert ppz3['save_after'][3:5] == [4, 1], 'expected generation-4 CC1 checkpoint'
        flags = ppz3['save_after'][5]
        assert flags & 0xff == 0 and flags & 0x100, 'PPZ Good Future was not saved'
        assert ppz3['cold_continue_mailbox'][4:7] == [4, 1, flags]
        assert len(backup.read_bytes()) == 32768 and digest(backup) == ppz3['backup_after_sha256']
        report = dict(passed=True, disc_sha256=disc_hash, generation=4, zone=1,
                      act=0, era=0, saved_flags=flags, backup_path=str(backup),
                      backup_sha256=digest(backup), ppz3_report=str(source),
                      ppz3_report_sha256=digest(source), hardware_tested=False,
                      source='Earned PPZ3 Good Future handoff and cold Continue; no constructed save record.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        assert digest(DISC) == disc_hash and digest(backup) == report['backup_sha256']
        print(f'PASS: earned PPZ3 to CC1 checkpoint; backup {report["backup_sha256"]}; {args.output}')
        return
    run('sequence', ['bash', 'tools/test-sequence-emulator.sh'],
        SCD_BACKUP_OUTPUT=BACKUP)
    sequence_report_path = ROOT / 'dist/sequence-report.json'
    sequence = json.loads(sequence_report_path.read_text())
    assert sequence['passed'] and sequence['disc_sha256'] == disc_hash
    assert [sequence['next_zone'], sequence['next_zone_act']] == [1, 1]
    assert len(BACKUP.read_bytes()) == 32768
    backup_hash = digest(BACKUP)
    run('continue', ['bash', 'tools/test-save-emulator.sh', 'continue'],
        SCD_BACKUP_INPUT=BACKUP, SCD_SAVE_OUTPUT_DIR=COLD)
    cold_path = COLD / 'save.json'
    cold = json.loads(cold_path.read_text())
    assert cold['mailbox'][:10] == [0x53415645, 0, 1, 0, 4, 1, 0, 1, 0, 1]
    assert cold['trace'][23] & 0xfff == 0x30c, 'CC Present Japanese track 12'
    assert cold['trace'][11] == 0 and cold['trace'][12] >> 16 == 0
    assert cold['trace'][13] & 255 == 3, 'Continue begins with three lives'
    assert digest(COLD / 'backup.bin') == backup_hash, 'Continue changed backup RAM'
    assert digest(DISC) == disc_hash
    report = dict(passed=True, disc_sha256=disc_hash, generation=4, zone=1,
                  act=0, era=0, japanese_track=12, save_session_enabled=True,
                  backup_unchanged=True,
                  source='Actual New Game → PPZ Acts 1–3 → CC1 auto-save; no constructed save record.',
                  sequence_report_sha256=digest(sequence_report_path),
                  backup_sha256=backup_hash, cold_report_sha256=digest(cold_path),
                  inputs={name: digest(ROOT / name) for name in
                          ('tools/prepare_cc_campaign_checkpoint.py',
                           'tools/test-sequence-emulator.sh',
                           'tools/test-save-emulator.sh', 'tools/emulator_test.c')},
                  hardware_tested=False,
                  limits='Proves earned CC1 campaign entry and cold Continue, not the later generator-to-Act-2 saved route.')
    path = args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: earned CC1 Present generation 4; cold Continue track 12; backup {backup_hash}; {path}')


if __name__ == '__main__':
    main()
