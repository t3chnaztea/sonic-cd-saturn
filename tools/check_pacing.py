#!/usr/bin/env python3
"""Bind a finite pacing measurement to a disc; not a whole-zone speed gate."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('cue',type=Path)
p.add_argument('folder',type=Path)
args=p.parse_args()
cue=args.cue.resolve()
files=re.findall(r'^FILE "([^"]+)" BINARY$',cue.read_text(),re.M)
assert len(files)==1,'expected one BIN containing data and audio'
disc=cue.parent/files[0]
log=(args.folder/'results.log').read_text()
summary=re.findall(r'^Pacing comparison: intervals=(\d+) vblanks=(\d+) late=(\d+) max_gap=(\d+) simulation=(\d+)$',log,re.M)
assert len(summary)==1
intervals,blanks,late,peak,sim=map(int,summary[0])
gaps=[dict(simulation=int(s),vblanks=int(g)) for s,g in re.findall(r'^Pacing gap: simulation=(\d+) vblanks=(\d+)$',log,re.M)]
assert intervals==1800 and sim==1801
assert len(gaps)==late and all(g['vblanks']>1 for g in gaps)
assert blanks==intervals+sum(g['vblanks']-1 for g in gaps)
assert peak==max([1]+[g['vblanks'] for g in gaps])
report={'measurement_complete':True,'disc_sha256':hashlib.sha256(disc.read_bytes()).hexdigest(),
        'cue_sha256':hashlib.sha256(cue.read_bytes()).hexdigest(),
        'harness_sha256':os.environ.get('SCD_PACING_HARNESS_SHA256'),
        'harness_binary_sha256':hashlib.sha256(Path('build/pacing_test').read_bytes()).hexdigest(),
        'log_sha256':hashlib.sha256((args.folder/'results.log').read_bytes()).hexdigest(),
        'intervals':intervals,'vblanks':blanks,'late':late,'max_gap':peak,'gaps':gaps,
        'instrumented_frame_profile':'Frame profile:' in log,
        'hardware_tested':False,
        'limits':'One deterministic Act 1 Present opening route, not locked-60 or whole-zone acceptance; no original-console cadence comparison.'}
(args.folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Pacing: {late} missed-refresh intervals / {intervals}; BIN {report["disc_sha256"]}')
