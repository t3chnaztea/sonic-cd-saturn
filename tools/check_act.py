#!/usr/bin/env python3
"""Require a complete ordinary-spawn act and exact sanitized host replay."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'build/act-qa'
log=(folder/'results.log').read_text();host=(folder/'host-results.log').read_text()
m=re.search(r'Full Present act: states=(\d+) elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) checkpoint=(\d+) sections=5 frames=(\d+)',log)
assert m,'missing target act completion'
states,elapsed,score,bonus,lives,checkpoint,frames=map(int,m.groups())
h=re.search(r'Full act host/Saturn match: (\d+) states, (\d+) words; elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) hurt_ticks=(\d+) ramp_ticks=(\d+) checkpoint=(\d+)',host)
assert h,'missing sanitized complete-state replay'
values=list(map(int,h.groups()))
assert values[:6]==[states,states*16,elapsed,score,bonus,lives]
assert values[-1]==checkpoint and values[-2]>0 and checkpoint>0
captures={}
from hud_pixels import verify as verify_hud
rings=int((folder/'player-target-trace.txt').read_text().splitlines()[-1].split()[10],16)>>16
hud_count=verify_hud((folder/'act-complete.ppm').read_bytes(),score,rings,elapsed,lives,0,check_rings=rings!=0)
for name in ['act-spawn','act-ramp-clear','act-middle','act-lower-route','act-late-route','act-signpost','act-complete']:
    raw=(folder/f'{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(data)==330*224*3
    assert len(set(data[i:i+3] for i in range(0,len(data),3)))>=16
    captures[name]=hashlib.sha256(raw).hexdigest()
# The sequence gate has always required zero late intervals; this route is
# measured the same way and must meet the same bar. The ring-loss overrun in
# V0.057 was visible here first and passed unnoticed.
from act_pacing import measure
pacing=measure(log,(folder/'player-target-trace.txt').read_text())
if pacing['late']:
    # Replace any earlier functional-only green report for this same disc.
    (ROOT/'dist/act-report.json').write_text(json.dumps(
        {'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
         'passed':False,'failure':'act pacing regression','pacing':pacing,
         'functional_route_and_host_replay_passed':True,'hardware_tested':False},indent=2)+'\n')
    raise AssertionError(('act pacing regression',pacing))
from results_pixels import draw,maps,art,colors,number_art,verify_pixels
complete=(folder/'act-complete.ppm').read_bytes().split(b'255\n',1)[1]
for index,width in [(0,144),(2,208)]:verify_pixels(complete,draw(maps[index],art,colors,width),width,160,76)
verify_pixels(complete,draw(bytes([8])+maps[1][1:41],art,colors,256),256,112,144)
for value,digits,x,y in [(score,7,184,112),(0,5,200,136),(0,5,200,160)]:
    for n,c in enumerate(str(value).rjust(digits)):
        if c!=' ':verify_pixels(complete,draw(bytes([1,0,1,0,int(c)*2,252]),number_art,colors,8),8,x+4+n*8,y)
report={'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'passed':True,'start':'ordinary fresh Present spawn, no position/inventory/placement edits','inputs':'only Right and Jump through the Saturn controller interface','states':states,'semantic_words':states*16,'elapsed_ticks':elapsed,'score':score,'bonus':bonus,'lives':lives,'checkpoint':checkpoint,'emulator_frames':frames,'hurt_ticks':values[-3],'ramp_ticks':values[-2],'host_sanitizers':'address and undefined behavior','captures':captures,'trace_sha256':hashlib.sha256((folder/'player-target-trace.txt').read_bytes()).hexdigest(),'hardware_tested':False,'limits':'One deterministic route through the currently imported Act 1 objects; omitted objects, original-console parity, subsequent acts and hardware acceptance remain open.'}
report['original_hud_pixels']=hud_count
report['pacing']=pacing
(ROOT/'dist/act-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Complete Present act passed: {states} matched states, score {score}, bonus {bonus}')
