#!/usr/bin/env python3
"""Reject broken earned-save evidence links without creating game save records."""
import hashlib
import json
from pathlib import Path
import signal
import tempfile

from test_ss_campaign import entry_evidence

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/ss-campaign-evidence'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(status='pending', passed=False, cases=[], inputs={
        name: digest(ROOT/name) for name in (
            'tools/test_ss_campaign.py', 'tools/test_ss_campaign_evidence.py')})
    report_path = OUT/'report.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    save()
    try:
        # These are text sentinels for hashing, never binary saves or emulator inputs.
        with tempfile.TemporaryDirectory(prefix='fixtures-', dir=OUT) as directory:
            fixture = Path(directory)/'hash-sentinel.txt'
            fixture.write_text('hash-check fixture, not a game save\n')
            prior_path = Path(directory)/'preceding-report.json'
            for act, zone, previous in ((0, 'WW', 3), (1, 'SS', 1), (2, 'SS', 2)):
                valid = dict(status='passed', passed=True, zone=zone, act=previous,
                             disc_sha256='same-bin-hash', backup_after_sha256=digest(fixture))
                prior_path.write_text(json.dumps(valid))
                result = entry_evidence(prior_path, fixture, 'same-bin-hash', act)
                assert result == dict(path=str(prior_path), sha256=digest(prior_path),
                                      zone=zone, act=previous), result
                link = f'{zone}{previous}->SS{act+1}'
                report['cases'].append(dict(link=link, case='valid', passed=True))
                for key, value in (('status', 'host-only'), ('passed', False),
                                   ('zone', 'QQ'), ('act', 99),
                                   ('disc_sha256', 'different-bin'),
                                   ('backup_after_sha256', 'different-backup')):
                    prior_path.write_text(json.dumps({**valid, key: value}))
                    try:
                        entry_evidence(prior_path, fixture, 'same-bin-hash', act)
                    except AssertionError:
                        report['cases'].append(dict(link=link, case=key, passed=True))
                    else:
                        raise AssertionError(f'{link}: accepted invalid {key}')
        assert len(report['cases']) == 21
        report.update(status='passed', passed=True,
                      scope='Three earned campaign evidence links; no gameplay, save construction, or Saturn acceptance.')
        save()
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                      error=repr(error))
        save()
        raise
    print('PASS: SS campaign evidence 21 cases; WW3->SS1, SS1->SS2, SS2->SS3; '
          'reject failed status, false pass, wrong zone, act, BIN and backup')


if __name__ == '__main__':
    main()
