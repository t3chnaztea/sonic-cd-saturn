#!/usr/bin/env python3
"""Bind the V0.050 presentation-only change to preserved V0.049 target traces."""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def compare(old,new,sequence=False):
    before=[line.split() for line in old.splitlines()]
    after=[line.split() for line in new.splitlines()]
    assert len(before)==len(after)>0,'different route length'
    changes=Counter()
    for index,(a,b) in enumerate(zip(before,after)):
        assert len(a)==len(b)==18
        # Absolute diagnostic sequence IDs can shift with loading; controller
        # input and every gameplay bit must still match, apart from this fix.
        assert a[1:2] == b[1:2] if sequence else a[:2]==b[:2],('different inputs',index)
        x=list(map(lambda s:int(s,16),a[2:]));y=list(map(lambda s:int(s,16),b[2:]))
        for word,(left,right) in enumerate(zip(x,y)):
            if left==right:continue
            assert word==4 and (left&0xffffff)==(right&0xffffff),('non-animation change',index,word,left,right)
            # These are the prior IDs encountered in the measured routes;
            # all are covered by the separate 60-ID retail-prelude matrix.
            assert left>>24 in (2,13,16,45) and right>>24==0,('unexpected animation change',index,left,right)
            changes[f'{left>>24}->0']+=1
    return dict(states=len(before),animation_changes=dict(changes),all_other_bits_identical=True)

def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    old=ROOT/'build/pre-v050-qa';new=ROOT/'build';evidence={};results={}
    cases=[('replay','emulator-qa/player-target-trace.txt',False)]
    cases += [(f'act{n}',f'sequence-qa/{name}',True) for n,name in enumerate(
        ['player-target-trace.txt','act2-target-trace.txt','act3-target-trace.txt'],1)]
    for name,path,sequence in cases:
        a=old/path;b=new/path
        results[name]=compare(a.read_text(),b.read_text(),sequence)
        evidence[str(a.relative_to(ROOT))]=sha(a);evidence[str(b.relative_to(ROOT))]=sha(b)
    assert results['replay']['states']==16800 and results['replay']['animation_changes']=={'16->0':605}
    assert sum(results[n]['states'] for n in ['act1','act2','act3'])==16116
    # Negative controls: no relaxation for a moved coordinate, altered button
    # or unrelated animation. The baseline itself is immutable.
    rows=(new/'emulator-qa/player-target-trace.txt').read_text().splitlines()
    original='\n'.join(rows)
    for field,value in [(1,'999'),(2,'00000001'),(6,'18000000')]:
        altered=rows.copy();head=altered[0].split();head[field]=value;altered[0]=' '.join(head)
        try:compare(original,'\n'.join(altered))
        except AssertionError:pass
        else:raise AssertionError(('negative control accepted',field))
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
        baseline_disc_sha256=json.loads((ROOT/'build/hardware-candidate-v0.049-01/candidate-manifest.json').read_text())['disc_sha256'],
        routes=results,evidence_sha256=evidence,checker_sha256=sha(Path(__file__)),
        limits='These recorded routes only; original prelude and target source-pixel gates independently establish correctness of the changed animations.')
    (ROOT/'dist/air-regression-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
