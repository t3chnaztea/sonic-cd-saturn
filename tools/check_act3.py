#!/usr/bin/env python3
"""Require a complete Act 3 (bad future) with the boss, the flower capsule, the
results tally, the advance into the next zone and an exact sanitized host replay."""
import hashlib,json,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'build/act3-qa'
log=(folder/'results.log').read_text();host=(folder/'host-results.log').read_text()
m=re.search(r'Full Act 3: states=(\d+) elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) checkpoint=(\d+) sections=5 frames=(\d+)',log)
assert m,'missing Act 3 completion'
states,elapsed,score,bonus,lives,checkpoint,frames=map(int,m.groups())
# Act 3 ends the zone, and the next zone loads by itself carrying score and lives.
end=re.search(r'Act 3 end: advanced to zone (\d+) act (\d+) after (\d+) frames',log)
assert end,'Act 3 did not advance into the next zone'
assert (int(end[1]),int(end[2]))==(1,1),('Act 3 advanced to the wrong stage',end[1],end[2])
h=re.search(r'Full act host/Saturn match: (\d+) states, (\d+) words; elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) hurt_ticks=(\d+)',host)
assert h,'missing sanitized complete-state replay'
values=list(map(int,h.groups()))
assert values[:6]==[states,states*16,elapsed,score,bonus,lives],'host replay differs'
# The boss (egg1_03 scoreup(100)) adds 1,000 points before the tally.
assert score>=1000+bonus,'boss points missing'
def image(name):
    raw=(folder/f'{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(data)==330*224*3,name
    return raw,data
captures={}
for name in ['act3-spawn','act3-section1','act3-section2','act3-section3','act3-arena','act3-boss','act3-boss-defeated','act3-capsule','act3-complete','act3-next-zone']:
    raw,data=image(name)
    assert len(set(data[i:i+3] for i in range(0,len(data),3)))>=16,name
    captures[name]=hashlib.sha256(raw).hexdigest()
# The next zone is live gameplay, not a text screen, and it is not Palmtree Panic.
assert captures['act3-next-zone']!=captures['act3-complete'],'the next zone screen matches the Act 3 tally'
assert captures['act3-next-zone']!=captures['act3-spawn'],'the next zone screen matches the Palmtree Panic spawn'
from convert_objects import palette
from results_pixels import draw,maps,art,colors,number_art,verify_pixels
complete=image('act3-complete')[1]
from hud_pixels import verify as verify_hud
rings=int((folder/'player-target-trace.txt').read_text().splitlines()[-1].split()[10],16)>>16
hud_pixels=verify_hud(image('act3-complete')[0],score,rings,elapsed,lives,3,check_rings=rings!=0)
# Results/Main.asm: line 2 ("THROUGH Zone X") uses mapping frame 2 + act.
for index,width in [(0,144),(4,208)]:verify_pixels(complete,draw(maps[index],art,colors,width),width,160,76)
for value,digits,x,y in [(score,7,184,112),(0,5,200,136),(0,5,200,160)]:
    for n,c in enumerate(str(value).rjust(digits)):
        if c!=' ':verify_pixels(complete,draw(bytes([1,0,1,0,int(c)*2,252]),number_art,colors,8),8,x+4+n*8,y)
# The bad-future boss palette (PaletteTable entry 5 of R13D) is on screen during the fight.
boss=image('act3-boss')[1];shown={boss[i:i+3] for i in range(0,len(boss),3)}
line=[struct.unpack_from('>H',palette((ROOT/'assets/generated/boss13D.pal').read_bytes()),2*i)[0] for i in range(2,16)]
rgb={bytes(((v&31)*8,((v>>5)&31)*8,((v>>10)&31)*8)) for v in line}
assert len(rgb&shown)>=6,('boss palette colors on screen',len(rgb&shown))
extract=json.loads((ROOT/'build/mmd-extract.json').read_text())
report={'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'passed':True,
        'start':'Act 3 bad future ordinary spawn (64,674) via the Start+Up+C debug entry; stage data from retail R13D__.MMD',
        'inputs':'Right and Jump; Left, Down and waits only inside the route areas and the boss controller in tools/emulator_test.c',
        'states':states,'semantic_words':states*16,'elapsed_ticks':elapsed,'score':score,'bonus':bonus,'lives':lives,
        'emulator_frames':frames,'hurt_ticks':values[-1],'next_zone':int(end[1]),'next_zone_act':int(end[2]),'next_zone_frames':int(end[3]),'host_sanitizers':'address and undefined behavior',
        'boss_palette_colors_on_screen':len(rgb&shown),'captures':captures,
        'original_hud_pixels':hud_pixels,'hud_ring_label_checked':rings!=0,
        'trace_sha256':hashlib.sha256((folder/'player-target-trace.txt').read_bytes()).hexdigest(),
        'r13d_mmd_sha256':extract['programs']['R13D']['mmd_sha256'],'boss_extraction':extract['boss']['checks'],'hardware_tested':False,
        'limits':'One deterministic bad-future route from the debug entry. The good-future Act 3 is covered by the host boss comparison and the extraction checks, not by an emulator route; original-console parity of the boss is not measured.'}
(ROOT/'dist/act3-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Complete Act 3 passed: {states} matched states, score {score}, bonus {bonus}, advanced to zone {end[1]} act {end[2]}')
