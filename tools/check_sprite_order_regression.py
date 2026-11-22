#!/usr/bin/env python3
"""Reject preserved pre-fix overlap pictures; preserve exact gameplay traces."""
import contextlib,hashlib,io,json,re
from pathlib import Path
from convert_assets import ROOT
from monitor_pixels import verify_monitor_overlap
from projector_pixels import verify as verify_projector

def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    previous=ROOT/'build/hardware-candidate-v0.050-01'
    manifest=json.loads((previous/'candidate-manifest.json').read_text())
    old=ROOT/'build/pre-v051-qa';new=ROOT/'build';folder=new/'world-qa'
    log=(folder/'results.log').read_text();evidence={};rejected=[]
    def retain(path):
        evidence[str(path.relative_to(ROOT))]=sha(path)
    def baseline(name):
        path=previous/name;assert sha(path)==manifest['files'][name]
        retain(path);return path
    for route in range(5):
        name=f'monitor-{route}-pose-60.ppm'
        after=(folder/name).read_bytes().split(b'255\n',1)[1]
        before=baseline(name).read_bytes().split(b'255\n',1)[1]
        valid=set();old_matches=0
        for tick in range(58,61):
            state,x,y=map(int,re.search(rf'Monitor pixels: route={route} tick={tick} art=(\d+) x=(-?\d+) y=(-?\d+)',log).groups())
            sonic=list(map(int,re.search(rf'^Monitor Sonic: route={route} tick={tick} ((?:\d+ ?)+)$',log,re.M)[1].split()))
            assert state>>8==25
            for raw,is_old in [(after,False),(before,True)]:
                try:checked,overlap=verify_monitor_overlap(raw,state&255,x,y,sonic)
                except AssertionError:continue
                if is_old:old_matches+=1
                else:valid.add((state,x,y,checked,overlap))
        assert len(valid)==1 and not old_matches,('monitor negative control',route,valid,old_matches)
        assert next(iter(valid))[-1]>0
        retain(folder/name);rejected.append(name)
    # The original capture-0 object poses/locations are unchanged; only their
    # draw order differs. Use current pose snapshots with the immutable old
    # photograph, so rejection must be a pixel mismatch, not missing metadata.
    prior_log=(old/'world-qa/results.log').read_text()
    pattern=r'Projector sprite: capture=0 data=(\d+) world=(\d+) screen=(\d+)'
    assert sorted(re.findall(pattern,prior_log))==sorted(re.findall(pattern,log))
    baseline('projector-animal-0.ppm')
    with contextlib.redirect_stdout(io.StringIO()):
        verify_projector(folder,log)
        try:verify_projector(previous,log)
        except AssertionError as failure:
            assert failure.args[0][0]=='projector pixel' and failure.args[0][1]==0,failure
        else:raise AssertionError('old projector-over-Sonic picture was accepted')
    rejected.append('projector-animal-0.ppm');retain(folder/'projector-animal-0.ppm')
    routes={}
    for route,path in [('main','emulator-qa/player-target-trace.txt'),
            ('act1','sequence-qa/player-target-trace.txt'),('act2','sequence-qa/act2-target-trace.txt'),
            ('act3','sequence-qa/act3-target-trace.txt')]:
        a=old/path;b=new/path
        left=[line.split() for line in a.read_text().splitlines()]
        right=[line.split() for line in b.read_text().splitlines()]
        assert len(left)==len(right)>0
        for index,(x,y) in enumerate(zip(left,right)):
            assert len(x)==len(y)==18
            # Sequence absolute diagnostic IDs depend on loading latency.
            assert (x if route=='main' else x[1:])==(y if route=='main' else y[1:]),(route,index,x,y)
        routes[route]=len(left);retain(a);retain(b)
    assert routes['main']==16800 and sum(n for r,n in routes.items() if r!='main')==16116
    retain(folder/'results.log');retain(old/'world-qa/results.log')
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
        baseline_disc_sha256=manifest['disc_sha256'],rejected_old_pictures=rejected,
        exact_gameplay_states=routes,evidence_sha256=evidence,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__).resolve(),
            ROOT/'tools/monitor_pixels.py',ROOT/'tools/projector_pixels.py',ROOT/'tools/sprite_priority_reference.py',
            ROOT/'tools/check_sonic_pixels.py',ROOT/'tools/sprite_composition.py',ROOT/'tools/convert_assets.py']},
        limits='Six immutable pre-fix pictures rejected at actual source-pixel overlaps; exact given gameplay routes, not exhaustive actor lifecycle or hardware.')
    (ROOT/'dist/sprite-order-regression-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'rejected_old_pictures':rejected,'exact_gameplay_states':routes},indent=2))
if __name__=='__main__':main()
