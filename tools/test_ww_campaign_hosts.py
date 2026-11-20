#!/usr/bin/env python3
"""Replay all stored WW earned routes before the long Saturn release matrix."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
# Output volume: SCD_OUTPUT_VOLUME if set, else the mount point that holds the repo.
VOLUME = Path(os.environ.get('SCD_OUTPUT_VOLUME') or next(p for p in (ROOT, *ROOT.parents) if os.path.ismount(p)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guard():
    assert os.path.ismount(VOLUME), 'output volume unmounted'
    subprocess.run(['df', '-k', VOLUME], check=True, stdout=subprocess.DEVNULL)
    assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3, 'output volume below 100 GiB'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    args = parser.parse_args()
    source = args.source_root.resolve()
    guard()
    out = ROOT / 'build/ww-campaign-hosts' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'tmp').mkdir()
    inputs = [p for directory in ('src', 'build/probe-source', 'assets/generated')
              for p in (source / directory).glob('*') if p.is_file() and
              (p.suffix in ('.c', '.h', '.H', '.inc') or p.name.startswith('ww') and p.suffix == '.bin')]
    inputs += [source / name for name in ('tools/test_ww_campaign.py', 'tools/qq_route_search.c',
               'tools/test_qq_route.py', 'tools/test_tt_travel.py', 'tools/test_cc_campaign_route.py',
               'tests/routes/ww/campaign/ww1-good.txt', 'tests/routes/ww/campaign/ww2-good.txt',
               'tests/routes/ww/ww3C.txt')]
    inputs.append(Path(__file__).resolve())
    report = dict(status='pending', passed=False, source_root=str(source),
                  inputs={}, steps=[],
                  limits='Host earned-route preflight only. Saturn, save-chain, Continue and hardware gates remain separate.')
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        report['inputs'] = {str(p): sha(p) for p in inputs}
        save()
        for act in (1, 2, 3):
            guard()
            command = ['nice', '-n', '20', 'python3', str(source / 'tools/test_ww_campaign.py'),
                       '--act', str(act), '--host-only', '--output', str(out / f'WW{act}')]
            step = dict(act=act, command=command, status='pending')
            report['steps'].append(step)
            save()
            with (out / f'WW{act}.log').open('w') as log:
                proc = subprocess.Popen(command, cwd=source, stdout=log, stderr=subprocess.STDOUT,
                                        env={**os.environ, 'TMPDIR': str(out / 'tmp')}, start_new_session=True)
                deadline = time.monotonic() + 300
                try:
                    while proc.poll() is None:
                        guard()
                        assert time.monotonic() < deadline, f'WW{act} host preflight timeout'
                        time.sleep(1)
                except BaseException:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait()
                    raise
            step.update(status='passed' if proc.returncode == 0 else 'failed', returncode=proc.returncode)
            save()
            assert proc.returncode == 0, f'WW{act} host preflight failed: {out / f"WW{act}.log"}'
            child_path = out / f'WW{act}/report.json'
            child = json.loads(child_path.read_text())
            assert child['status'] == 'host-only' and child['host_positions'] > 0
            step.update(report=str(child_path), report_sha256=sha(child_path),
                        positions=child['host_positions'], script_sha256=child['script_sha256'])
            print((out / f'WW{act}.log').read_text().strip(), flush=True)
        report['changed_inputs'] = [name for name, digest in report['inputs'].items() if sha(Path(name)) != digest]
        assert not report['changed_inputs'], 'host preflight inputs changed'
        report.update(status='passed', passed=True)
        print(f'PASS: WW earned-route host preflight 3/3; {out / "report.json"}')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
