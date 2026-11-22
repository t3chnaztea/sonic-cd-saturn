#!/usr/bin/env python3
"""Independent cutoff for one owned Node integration process. Offline only."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import signal
import subprocess
import time
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--pyodide',required=True,type=Path)
    parser.add_argument('--seed',type=Path)
    parser.add_argument('--script')
    parser.add_argument('--recipe',type=Path)
    parser.add_argument('--site',type=Path)
    args=parser.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to(ROOT/'build')or out.exists():parser.error('Choose a new directory under build/')
    schedule=json.loads((ROOT/'QA-SCHEDULE.json').read_text())
    def cutoff():
        now=datetime.datetime.now(ZoneInfo(schedule['timezone']))
        if now.weekday()in schedule['blocked_weekdays']:
            start=now.replace(hour=schedule['blocked_start_hour'],minute=0,second=0,microsecond=0)
            end=now.replace(hour=schedule['blocked_end_hour'],minute=0,second=0,microsecond=0)
            if start-datetime.timedelta(minutes=schedule['job_stop_lead_minutes'])<=now<end:
                return 'scheduled shutdown window'
        try:
            current=ROOT.stat()
            if current.st_dev!=mount_device:return 'workspace mount changed'
            if shutil.disk_usage(ROOT).free<100*1024**3:return 'Disk reserve below 100 GiB'
        except OSError:return 'workspace mount lost'
        return None
    mount_device=ROOT.stat().st_dev
    reason=cutoff()
    if reason:raise SystemExit('Integration not started: '+reason)
    command=['node','--v8-pool-size=1',str(ROOT/'tools/test-patcher-pipeline.cjs'),str(out),str(args.runtime.resolve()),str(args.pyodide.resolve())]
    if args.seed:command.extend(['--seed',str(args.seed.resolve())])
    if args.script:command.extend(['--script',args.script])
    if args.recipe:command.extend(['--recipe',str(args.recipe.resolve())])
    if args.site:command.extend(['--site',str(args.site.resolve())])
    with out.with_suffix('.log').open('x')as log:
        child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        print('Started owned integration PID',child.pid,flush=True)
        while child.poll()is None:
            reason=cutoff()
            if reason:
                # This PID is the Popen child created directly above.
                child.send_signal(signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait()
                print('Interrupted owned integration:',reason,flush=True)
                return 1
            time.sleep(1)
    return child.returncode


if __name__=='__main__':raise SystemExit(main())
