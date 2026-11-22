#!/usr/bin/env python3
"""Require the big ring flow in one emulator run: the Act 1 fixture with 50 rings, the big
ring touch, the act tally, Special Stage 1 won with the retail win pad script, and Act 2
starting with time stone 1, no rings and the carried score and lives."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'build/bigring-qa'
log=(folder/'results.log').read_text()
touch=re.search(r'Big ring touched: frame=(\d+) x=(\d+) rings=(\d+)',log)
assert touch and int(touch[3])>=50,'big ring not touched with 50 rings'
m=re.search(r'Big ring: touched=(\d+) tally_score=(\d+) stones=(\d+) act=(\d+) era=(\d+) score=(\d+) lives=(\d+) rings=(\d+) frames=(\d+)',log)
assert m,'special stage did not return to Act 2'
touched,tally,stones,act,era,score,lives,rings,frames=map(int,m.groups())
assert stones&1,'time stone 1 missing after the special stage'
assert act==1 and era==0 and rings==0,'Act 2 did not start in the present with no rings'
# The act tally includes the 50-ring bonus; the special stage results add their bonuses.
assert tally>=5000 and score>tally and lives>=3,'progress was not carried through the special stage'
captures={}
for name in ['bigring-touch','bigring-tally','bigring-special','bigring-results','bigring-act2']:
    raw=(folder/f'{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    # The special stage results screen uses one 16-color palette line plus the back color.
    assert header.startswith(b'P6\n') and len(set(data[i:i+3] for i in range(0,len(data),3)))>=(8 if name=='bigring-results' else 16),name
    captures[name]=hashlib.sha256(raw).hexdigest()
report={'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'passed':True,
        'start':'Act 1 Present at (9800,450) with 50 rings via the Start+Left+C debug entry',
        'inputs':'Right, Left and Jump to reach the big ring; the special stage uses the retail win route pad script (build/special-retail/win.pad)',
        'touch_frame':touched,'touch_x':int(touch[2]),'tally_score':tally,'time_stones':stones,'act':act,'score':score,'lives':lives,
        'emulator_frames':frames,'captures':captures,'hardware_tested':False,
        'limits':'Big ring from a debug fixture in Act 1 Present only; only Special Stage 1 exists, so the big ring deletes itself once time stone 1 is held. No host replay of the gameplay segment (the world probe covers the big ring on the host).'}
(ROOT/'dist/bigring-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Big ring flow passed: tally score {tally}, special stage score {score}, time stones {stones:#04x}, Act 2 loaded')
