#!/usr/bin/env python3
"""Presentation-state comparison, independent of the legacy physics words."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path):
    rows={}
    for line in path.read_text().splitlines():
        t,f,a,b=line.split();key=int(t),int(f);assert key not in rows
        rows[key]=(int(a,16),int(b,16))
    assert set(rows)=={(t,f) for t in range(28) for f in range(600)}
    return rows
paths=[ROOT/'build/player-host-visual-trace.txt',ROOT/'build/player-reference-visual-trace.txt',ROOT/'build/emulator-qa/player-visual-trace.txt']
host,reference,target=map(read,paths)
for key in host:
    assert host[key]==reference[key]==target[key],('player animation state',key,host[key],reference[key],target[key])
mappings=sorted({a>>24 for a,b in target.values()});assert len(mappings)>=50
report={'passed':True,'states':len(target),'words':len(target)*2,'mapping_ids':mappings,
    'fields':['mapping','sprite flags','animation','previous animation','script cursor','timer','control','disc cursor'],
    'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
    'trace_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    'limits':'Host/SH-2 equivalence for 28 fixtures. Retail execution separately audits real host animation calls; pixels separately checked.'}
(ROOT/'dist/player-visual-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Original Sonic presentation state: {len(target)} exact host/reference/SH-2 states, {len(mappings)} mappings')
