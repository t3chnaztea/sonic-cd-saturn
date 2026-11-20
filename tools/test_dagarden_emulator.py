#!/usr/bin/env python3
"""D.A. Garden emulator route: unlock, enter, change tracks, compare screens with retail, exit.

Beetle Saturn plays dist/sonic-cd-saturn-prototype.bin with the Time Attack fixture whose act
total is just under 37'27"57 (tools/test_frontend_emulator.py ta-thresholds:
fixture-total224756.bin, titleFlags bit 3). The title menu shows D.A. GARDEN at selection 5;
A enters it. From the first D.A. Garden frame the route replays the retail 'zones' pad
(tools/dagarden_retail.py) on the frames the host program (src/dagarden.c) gives each V-INT,
so the Saturn must reach the retail state: at every checkpoint V-INT the mailbox
(src/dagarden_view.inc scd_dagarden_mailbox: track, selection flags, time zone, music) equals
the retail record, and the picture equals the retail picture of that V-INT (H32 widened to
320 dots: Saturn x samples retail floor(x*205/256); colours compared at the Mega Drive's
3 bits per channel). Start exits; the title must return. A second run with the fixture just
over the limit (fixture-total224758.bin) must not offer D.A. GARDEN.
Writes build/dagarden-qa/report.json; exits 0 only on PASS.
"""
import hashlib,json,os,re,struct,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
OUT=ROOT/'build/dagarden-qa';OUT.mkdir(parents=True,exist_ok=True)
import dagarden_retail as dr
import title_menu
RETAIL=dr.OUT;FQA=ROOT/'build/frontend-qa'
DISC=ROOT/'dist/sonic-cd-saturn-prototype.bin';ELF=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'
HARNESS=OUT/'frontend_emulator_test'
ROUTE='zones'
CHECKPOINTS=[30,200,450,560,640,760,1000,1200,1340,1500,1760,1900,2200,2400,2600]
report={'status':'pending','passed':False,'route':ROUTE,'disc_sha256':hashlib.sha256(DISC.read_bytes()).hexdigest(),
    'inputs':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['src/dagarden.c','src/dagarden_view.inc','src/main.c','src/title.c','tools/test_dagarden_emulator.py']},
    'hardware_tested':False}
def write():(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
def fail(msg):
    report['status']='failed';report['error']=msg;write();print('FAIL: D.A. Garden emulator: '+msg);sys.exit(1)
write()

def symbols():
    nm=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),str(ELF)],text=True);s={}
    for row in nm.splitlines():
        p=row.split()
        if len(p)==3:s[re.sub(r'\.lto_priv\.\d+$','',p[2])]=p[0]
    return 'trace=%s,dag=%s,audio=%s,rec=%s'%(s['_scd_trace_mailbox'],s['_scd_dagarden_mailbox'],s['_scd_audio_mailbox'],s['_fe_ta_rec'])

def run(name,script,fixture,timeout=3600):
    folder=OUT/name;folder.mkdir(exist_ok=True);(folder/'script.txt').write_text(script)
    env=os.environ.copy();env.update(SCD_SYMS=SYMS,SCD_BACKUP_INPUT=str(fixture),SCD_BACKUP_OUTPUT=str(folder/'backup.bin'))
    args=[HARNESS,ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',ROOT/'dist/sonic-cd-saturn-prototype.cue',ROOT/'assets/private',folder,folder/'script.txt']
    with (folder/'core.log').open('w') as err:
        r=subprocess.run(['nice','-n','20']+list(map(str,args)),env=env,cwd=ROOT,stdout=subprocess.PIPE,stderr=err,text=True,timeout=timeout)
    (folder/'results.log').write_text(r.stdout)
    peeks={}
    for line in r.stdout.splitlines():
        m=re.match(r'frame=\d+ peek (\S+)((?: [0-9a-f]{8})+)$',line)
        if m:peeks[m.group(1)]=[int(x,16) for x in m.group(2).split()]
    return r.returncode,r.stdout,peeks

def host_schedule():
    """Frames from the first D.A. Garden frame to each V-INT (the host lag model is the Saturn's)."""
    subprocess.run([sys.executable,str(ROOT/'tools/test_dagarden.py'),ROUTE],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    out=subprocess.run([str(ROOT/'build/dagarden-host/dagarden_test'),str(ROOT/'assets/generated/dagarden.bin'),str(RETAIL/f'{ROUTE}.pad')],capture_output=True,text=True).stdout
    frame={0:0};f=0
    for l in out.splitlines():
        r=json.loads(l);f+=r['lag_frames']+1;frame[r['v']+1]=f
    return frame

def ppm(path):
    raw=path.read_bytes();parts=raw.split(b'\n',3);w,h=map(int,parts[1].split());return w,h,parts[3]

def compare(shot,retail_rgb565):
    """Fraction of the 320x224 picture equal to the retail picture (3-bit channels). The harness
    frame may carry a border: the best of small offsets is taken."""
    w,h,data=ppm(shot);best=(0,None)
    ref=[struct.unpack_from('<H',retail_rgb565,i*2)[0] for i in range(256*224)]
    q=lambda v8:(v8*7+127)//255
    refq=[((r>>11)*7+15)//31<<6|(((r>>5)&63)*7+31)//63<<3|((r&31)*7+15)//31 for r in ref]
    cols=[x*205//256 for x in range(320)]
    for ox,oy in [(x,y) for y in sorted({0,(h-224)//2,h-224}) for x in sorted({0,(w-320)//2,w-320})]:
            same=0
            for y in range(0,224,2):
                row=(y+oy)*w;rr=y*256
                for x in range(0,320,2):
                    p=(row+x+ox)*3;v=q(data[p])<<6|q(data[p+1])<<3|q(data[p+2])
                    same+=v==refq[rr+cols[x]]
            frac=same/(112*160)
            if frac>best[0]:best=(frac,(ox,oy))
    return best

OPEN='run 200\nuntil TITL 3000\nrun 240\nhold START 4\nrun 90\n'
BUTTONS={1:'UP',2:'DOWN',4:'LEFT',8:'RIGHT',16:'B',32:'C',64:'A',128:'START'}
def buttons(pad):return '+'.join(n for b,n in BUTTONS.items() if pad&b) or 'NONE'

for need in (DISC,ELF):
    if not need.exists():fail(f'{need} missing: build first')
fixture=FQA/'fixture-total224756.bin';locked=FQA/'fixture-total224758.bin'
if not fixture.exists() or not locked.exists():
    subprocess.run([sys.executable,str(ROOT/'tools/test_frontend_emulator.py'),'ta-run','ta-thresholds'],cwd=ROOT,check=True)
subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include','tools/frontend_emulator_test.c','-o',str(HARNESS)],cwd=ROOT,check=True)
SYMS=symbols()
OFFSET=int(os.environ.get('SCD_DAGARDEN_PAD_OFFSET','0'))

# The menu by identity (tools/title_menu.py): each fixture's own options in retail order.
def menu(name,fixture):
    rc,out,probe=run(name,title_menu.PROBE,fixture,timeout=900)
    if rc:fail(f'{name}: harness status {rc}')
    return probe
# Locked: the menu has no D.A. GARDEN, and Right stops on its last option.
cursor,options=title_menu.options(menu('locked-menu',locked))
if title_menu.DA_GARDEN in options:fail('D.A. GARDEN offered with the act total over 37\'27"57')
rc,out,peeks=run('locked',OPEN+title_menu.STEP*(len(options)-cursor)+'peek sel trace 0 4\n',locked,timeout=900)
if rc:fail(f'locked run: harness status {rc}')
locked_sel=peeks['sel'][2]>>16&255
if locked_sel!=len(options)-1:fail(f'locked menu: Right stopped at {locked_sel}, last option {len(options)-1}')
report['locked']={'fixture':locked.name,'menu':[title_menu.NAMES[o] for o in options[1:]],'right_stops_at':locked_sel};write()
walk,position=title_menu.route(menu('menu',fixture),title_menu.DA_GARDEN)
TITLE=OPEN+walk+'peek sel trace 0 4\n'

frame=host_schedule()
pads=[tuple(map(int,l.split())) for l in (RETAIL/f'{ROUTE}.pad').read_text().splitlines()]
events=[]
for i,(v,pad) in enumerate(pads):
    end=pads[i+1][0] if i+1<len(pads) else max(frame)
    if pad:events.append((v,1,pad,frame[end]-frame[v]))
for v in CHECKPOINTS:events.append((v,0,0,0))
events.sort()
# Each event waits for its V-INT in the mailbox (word 1), so frames the Saturn loses to slow
# work cannot shift the pad against the program; holds last the host's frames for the span.
script=TITLE+'tap A\nuntil DAGD 1200\n'
for v,kind,pad,length in events:
    script+=f'until_word dag 4 {v:08x} 4000\n'
    if kind==1:script+=f'hold {buttons(pad)} {length}\n'
    else:script+=f'run 1\npeek v{v} dag 0 24\npeek a{v} audio 0 8\nshot v{v}\n'
script+='until TITL 2000\npeek back trace 0 4\n'
rc,out,peeks=run('zones',script,fixture)
if rc:fail(f'zones run: harness status {rc} ({out.strip().splitlines()[-1] if out.strip() else ""})')
if peeks['sel'][2]>>16&255!=position:fail(f"menu selection {peeks['sel']}, D.A. GARDEN at {position}")
if peeks.get('back',[0])[0]!=0x5449544c:fail('the title did not return after Start')
rows=[json.loads(l) for l in (RETAIL/f'{ROUTE}.jsonl').read_text().splitlines()];rows=[r for r in rows if r['run']]
last={};near={}
for r in rows:
    last[r['v']]=r
    for w in (r['v']-1,r['v'],r['v']+1):near.setdefault(w,[]).append(r['pixels'])
pixels=zipfile.ZipFile(RETAIL/f'{ROUTE}-pixels.zip')
checks=[];ok=True
for v in CHECKPOINTS:
    mb=peeks[f'v{v}'];r=last[v];sel=bytes.fromhex(r['sel'])
    state={'v':mb[1],'lost_frames':mb[21],'track':mb[3]&255,'sel_flags':mb[3]>>8&255,'zone':mb[3]>>16,'music':mb[4]}
    want={'v':v,'track':struct.unpack('>H',sel[2:4])[0],'sel_flags':r['sel_flags'],'zone':r['zone']}
    # The retail V-INT's planet DMA runs for frames past the counter change: the pictures
    # of the neighbouring V-INTs are candidates, the best one counts.
    frac,offset=max(compare(OUT/'zones'/f'v{v}.ppm',pixels.read(k)) for k in dict.fromkeys(near[v]))
    # Saturn disc track of the music the retail program last started (src/music_routes.h):
    # D.A. Garden song slot 37 until a track plays, then the zone's era song.
    audio=peeks[f'a{v}'];want_track={0:39,1:4,2:5}[r['zone']]
    good=all(state[k]==want[k] for k in want if k!='v') and abs(state['v']-v)<=1 and frac>=0.97 and audio[3]==want_track and state['lost_frames']<=8
    ok=ok and good
    checks.append({'v':v,'saturn':state,'retail':want,'picture_equal_fraction':round(frac,4),'offset':offset,'audio_track':peeks[f'a{v}'][3],'audio_cd_status':peeks[f'a{v}'][4],'audio_cd_track':peeks[f'a{v}'][5],'passed':good})
    print(json.dumps(checks[-1]),flush=True)
report['checks']=checks;report['exit']='title returned (TITL)';report['passed']=ok;report['status']='passed' if ok else 'failed';write()
if not ok:fail('checkpoint state or picture differs from retail (build/dagarden-qa/report.json)')
print(f'PASS: D.A. Garden emulator: locked at selection {locked_sel}; {len(checks)} checkpoints equal retail state and picture (min {min(c["picture_equal_fraction"] for c in checks)}); Start returned to the title; disc {report["disc_sha256"][:16]}')
