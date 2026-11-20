#!/usr/bin/env python3
"""Require a complete Act 2 Present route and exact sanitized host replay."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'build/act2-qa'
log=(folder/'results.log').read_text();host=(folder/'host-results.log').read_text()
m=re.search(r'Full Act 2 Present: states=(\d+) elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) checkpoint=(\d+) sections=5 frames=(\d+)',log)
assert m,'missing target Act 2 completion'
states,elapsed,score,bonus,lives,checkpoint,frames=map(int,m.groups())
h=re.search(r'Full act host/Saturn match: (\d+) states, (\d+) words; elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) hurt_ticks=(\d+) ramp_ticks=(\d+) checkpoint=(\d+)',host)
assert h,'missing sanitized complete-state replay'
values=list(map(int,h.groups()))
assert values[:6]==[states,states*16,elapsed,score,bonus,lives]
assert values[-1]==checkpoint and checkpoint>0
captures={}
for name in ['act2-spawn','act2-section1','act2-section2','act2-section3','act2-section4','act2-signpost','act2-complete']:
    raw=(folder/f'{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(data)==330*224*3
    assert len(set(data[i:i+3] for i in range(0,len(data),3)))>=16
    captures[name]=hashlib.sha256(raw).hexdigest()
from results_pixels import draw,maps,art,colors,number_art,verify_pixels
complete=(folder/'act2-complete.ppm').read_bytes().split(b'255\n',1)[1]
from hud_pixels import verify as verify_hud
rings=int((folder/'player-target-trace.txt').read_text().splitlines()[-1].split()[10],16)>>16
hud_pixels=verify_hud((folder/'act2-complete.ppm').read_bytes(),score,rings,elapsed,lives,0,check_rings=rings!=0)
# Results/Main.asm: line 2 ("THROUGH Zone X") uses mapping frame 2 + act.
for index,width in [(0,144),(3,208)]:verify_pixels(complete,draw(maps[index],art,colors,width),width,160,76)
verify_pixels(complete,draw(bytes([8])+maps[1][1:41],art,colors,256),256,112,144)
for value,digits,x,y in [(score,7,184,112),(0,5,200,136),(0,5,200,160)]:
    for n,c in enumerate(str(value).rjust(digits)):
        if c!=' ':verify_pixels(complete,draw(bytes([1,0,1,0,int(c)*2,252]),number_art,colors,8),8,x+4+n*8,y)
travel=re.search(r'Act 2 travel: case=past era=(\d+) transitions=(\d+) x=(\d+) y=(\d+)',(folder/'travel-past/results.log').read_text())
assert travel and travel[1]=='1' and travel[2]=='1','Act 2 past travel did not arrive in the past'
for name in ['act2-travel-past-cutscene','act2-travel-past-arrival']:
    raw=(folder/f'travel-past/{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(set(data[i:i+3] for i in range(0,len(data),3)))>=16
    captures[name]=hashlib.sha256(raw).hexdigest()
extract=json.loads((ROOT/'build/mmd-extract.json').read_text())
report={'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'passed':True,
        'start':'Act 2 Present ordinary spawn (80,389) via the Start+C debug entry; stage data from retail R12A__.MMD',
        'inputs':'staged host script tests/routes/ppz/p1A.txt (tools/run-act2-era-script.sh era 0)',
        'states':states,'semantic_words':states*16,'elapsed_ticks':elapsed,'score':score,'bonus':bonus,'lives':lives,'checkpoint':checkpoint,
        'emulator_frames':frames,'hurt_ticks':values[-3],'host_sanitizers':'address and undefined behavior','captures':captures,
        'original_hud_pixels':hud_pixels,'hud_ring_label_checked':rings!=0,
        'trace_sha256':hashlib.sha256((folder/'player-target-trace.txt').read_bytes()).hexdigest(),'travel_past':{'era':int(travel[1]),'arrival_x':int(travel[3]),'arrival_y':int(travel[4])},
        'r12a_mmd_sha256':extract['programs']['R12A']['mmd_sha256'],'hardware_tested':False,
        'limits':'One deterministic Present route and one Present-to-past travel from a room fixture. Future travel through gameplay, routes in the other eras, the springboard and branch objects, big-ring entry and original-console parity remain open.'}
(ROOT/'dist/act2-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Complete Act 2 Present passed: {states} matched states, score {score}, bonus {bonus}')
