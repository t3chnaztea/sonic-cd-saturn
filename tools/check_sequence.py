#!/usr/bin/env python3
"""Require Act 1 Present, Act 2 Present and Act 3 (bad future) with the boss, the capsule,
the automatic advance to Collision Chaos Act 1 in one run after NEW GAME, without debug input."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'build/sequence-qa'
log=(folder/'results.log').read_text()
pattern=r'{}: states=(\d+) elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) checkpoint=(\d+) sections=5 frames=(\d+)'
act1=re.search(pattern.format('Full Present act'),log);act2=re.search(pattern.format('Full Act 2 Present'),log);act3=re.search(pattern.format('Full Act 3'),log)
assert act1 and act2 and act3,'missing act completion'
a1=list(map(int,act1.groups()));a2=list(map(int,act2.groups()));a3=list(map(int,act3.groups()))
end=re.search(r'Act 3 end: advanced to zone (\d+) act (\d+) after (\d+) frames',log)
assert end,'missing automatic next-zone entry after the Act 3 tally'
assert (int(end[1]),int(end[2]))==(1,1),'sequence advanced to the wrong stage'
host_pattern=r'Full act host/Saturn match: (\d+) states, (\d+) words; elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+)'
h1=re.search(host_pattern,(folder/'host-act1.log').read_text());h2=re.search(host_pattern,(folder/'host-act2.log').read_text());h3=re.search(host_pattern,(folder/'host-act3.log').read_text())
assert h1 and h2 and h3,'missing host replay'
assert list(map(int,h1.groups()))==[a1[0],a1[0]*16,a1[1],a1[2],a1[3],a1[4]],'Act 1 host replay differs'
assert list(map(int,h2.groups()))==[a2[0],a2[0]*16,a2[1],a2[2],a2[3],a2[4]],'Act 2 host replay differs'
assert list(map(int,h3.groups()))==[a3[0],a3[0]*16,a3[1],a3[2],a3[3],a3[4]],'Act 3 host replay differs'
from act_pacing import measure
timing_ends=list(re.finditer(r'^Act pacing:.*$',log,re.M))
assert len(timing_ends)==3,'missing per-act sequence pacing'
pacing={};start=0
for n,(end_match,trace_name) in enumerate(zip(timing_ends,['player-target-trace.txt','act2-target-trace.txt','act3-target-trace.txt']),1):
    pacing[str(n)]=measure(log[start:end_match.end()],(folder/trace_name).read_text())
    start=end_match.end()
if not all(p['late']==0 for p in pacing.values()):
    # Replace any earlier functional-only green report for this same disc.
    # A stricter failed check must not leave a publishable stale success.
    failure={'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
             'passed':False,'failure':'sequence pacing regression','pacing':pacing,
             'pacing_log_sha256':hashlib.sha256((folder/'results.log').read_bytes()).hexdigest(),
             'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'functional_routes_and_host_replays_passed':True,'hardware_tested':False}
    (ROOT/'dist/sequence-report.json').write_text(json.dumps(failure,indent=2)+'\n')
    raise AssertionError(('sequence pacing regression',pacing))
# Score and lives carry into Act 2 (the host replay starts from them); rings and time restart.
assert a1[2]<50000 and a2[2]>a1[2] and a3[2]>=a2[2]+1000 and a3[4]>=1,'progress was not carried'
captures={}
for name in ['act-spawn','act-signpost','act-complete','act2-spawn','act2-signpost','act2-complete','act3-spawn','act3-boss','act3-boss-defeated','act3-capsule','act3-complete','act3-next-zone']:
    raw=(folder/f'{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(data)==330*224*3
    captures[name]=hashlib.sha256(raw).hexdigest()
assert captures['act3-next-zone'] not in (captures['act3-complete'],captures['act3-spawn']),'next-zone picture still shows Palmtree Panic'
report={'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'passed':True,
        'pacing':pacing,'pacing_log_sha256':hashlib.sha256((folder/'results.log').read_bytes()).hexdigest(),
        'act1':dict(zip(['states','elapsed','score','bonus','lives','checkpoint','frames'],a1)),
        'act2':dict(zip(['states','elapsed','score','bonus','lives','checkpoint','frames'],a2)),
        'act3':dict(zip(['states','elapsed','score','bonus','lives','checkpoint','frames'],a3)),'next_zone':int(end[1]),'next_zone_act':int(end[2]),'next_zone_frames':int(end[3]),
        'captures':captures,
        'act1_trace_sha256':hashlib.sha256((folder/'player-target-trace.txt').read_bytes()).hexdigest(),
        'act2_trace_sha256':hashlib.sha256((folder/'act2-target-trace.txt').read_bytes()).hexdigest(),
        'act3_trace_sha256':hashlib.sha256((folder/'act3-target-trace.txt').read_bytes()).hexdigest(),
        'hardware_tested':False,
        'limits':'Present routes in Acts 1 and 2, so goodFutureFlags select the bad future for Act 3. The good-future Act 3 and travel between eras are not part of this run.'}
(ROOT/'dist/sequence-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f"Zone sequence passed: Act 1 score {a1[2]}, Act 2 score {a2[2]}, Act 3 score {a3[2]}, lives {a3[4]}, advanced to Collision Chaos Act 1")
