#!/usr/bin/env python3
"""Run one release gate case whose tool writes a fixed report, and bind it to the BIN.

  python3 tools/gate_case.py --report build/ending-test/report.json --out DIR -- CMD...

Runs CMD from the repository root, then copies REPORT to DIR/report.json. When
the tool's report has no disc_sha256, it is taken from the report's own
recorded input hash of dist/sonic-cd-saturn-prototype.bin, and only when that
equals the BIN on disk now. A report that is older than the run, names a
different BIN or does not say passed fails the case. Exit status is the
tool's, or 1 when the report check fails.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DISC = 'dist/sonic-cd-saturn-prototype.bin'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    assert command, 'no command'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    code = subprocess.run(command, cwd=ROOT).returncode
    source = args.report if args.report.is_absolute() else ROOT/args.report
    disc = hashlib.sha256((ROOT/DISC).read_bytes()).hexdigest()
    if not source.is_file() or source.stat().st_mtime < start - 1:
        print(f'FAIL: no fresh report {source}')
        return 1
    report = json.loads(source.read_text())
    recorded = report.get('disc_sha256') or (report.get('inputs') or {}).get(DISC)
    if recorded != disc:
        print(f'FAIL: report names BIN {str(recorded)[:12]}, tested {disc[:12]}')
        return 1
    report['disc_sha256'] = disc
    report['gate_case_source'] = str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source)
    (out/'report.json').write_text(json.dumps(report, indent=1) + '\n')
    shutil.copystat(source, out/'report.json')
    ok = code == 0 and report.get('passed') is True
    print(('PASS' if ok else 'FAIL') + f': {" ".join(command[1:3])}; report {out/"report.json"}')
    return 0 if ok else (code or 1)


if __name__ == '__main__':
    sys.exit(main())
