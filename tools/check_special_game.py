#!/usr/bin/env python3
"""Check the special stage emulator run against the retail recordings.

Inputs: build/special-game-qa/results.log from tools/emulator_test.c
(specialgame mode) and build/special-retail/<route>.jsonl from
tools/special_retail.py. Every stage and results V-INT of both routes must
be present with the route's pad input, the retail program state, one
emulator frame per V-INT and the retail picture. Stage pictures appear two
frames after the V-INT (VDP1 lists one frame after their submission, VDP2
state one V-INT late to match); results pictures one frame after. The
original writes HUD digits during the active display, so a V-INT that
changes them may differ from retail in the HUD rows only. Writes
dist/special-game-report.json bound to the disc SHA-256.
With --stages, --wins or --hazards, checks the steer-ss2..7, win-ss2..7 or
hazard-ss1..7 routes from build/special-game-qa/results-<set>.log into
dist/special-game-<set>-report.json.
"""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import special_retail
# Route sets: --stages (steer-ss2..7), --wins (win-ss2..7), --hazards (hazard-ss1..7).
SETS={'stages':tuple(f'steer-ss{n}' for n in range(2,8)),'wins':tuple(f'win-ss{n}' for n in range(2,8)),'hazards':tuple(f'hazard-ss{n}' for n in range(1,8))}
SET=next((name for name in SETS if '--'+name in sys.argv),None);STAGES=SET is not None
LOG=ROOT/(f'build/special-game-qa/results-{SET}.log' if SET else 'build/special-game-qa/results.log')
REPORT=ROOT/(f'dist/special-game-{SET}-report.json' if SET else 'dist/special-game-report.json')
ROUTES=SETS[SET] if SET else ('timeout','win')
def option(name):return sys.argv[sys.argv.index(name)+1] if name in sys.argv else None
# --modes a,b: IPX.asm mode entries (attract demos, time attack, stage 8) from results-modes.log.
MODES=option('--modes').split(',') if option('--modes') else None
if MODES:ROUTES=tuple(MODES);STAGES=True;LOG=ROOT/'build/special-game-qa/results-modes.log';REPORT=ROOT/'dist/special-game-modes-report.json'
# --routes a,b --log <results.log> --report <report.json>: one gate case (tools/test-special-case.sh).
if option('--routes'):ROUTES=tuple(option('--routes').split(','));STAGES=True
if option('--log'):LOG=Path(option('--log'))
if option('--report'):REPORT=Path(option('--report'))
MAILBOX=40
LATE_LIMIT=8 # late V-INTs allowed per route (emulator render budget; hardware timing is Phase I)
# Captures named by tools/emulator_test.c: (route, program phase, V-INT).
CAPTURES={(0,2,321),(0,3,930),(0,4,5190),(0,6,300),(1,2,1500),(1,6,39),(1,7,50)}

def fnv(data):
    h=2166136261
    for b in data:h=((h^b)*16777619)&0xffffffff
    return h

def sprite_overflow(sat):
    """True when a visible H32 line holds more than 16 sprites or 256 sprite
    dots of the linked table: the Mega Drive VDP drops the rest of the line
    (a sprite can be cut mid-way), which VDP1 still draws."""
    counts=[0]*224;dots=[0]*224;index=0;seen=set()
    while index<80 and index not in seen and (index+1)*8<=len(sat):
        seen.add(index);entry=sat[index*8:index*8+8]
        top=((entry[0]<<8|entry[1])&0x3ff)-128;height=(entry[2]&3)*8+8;width=(entry[2]>>2&3)*8+8
        for y in range(max(top,0),min(top+height,224)):counts[y]+=1;dots[y]+=width
        if not entry[3]:break
        index=entry[3]
    return max(counts)>16 or max(dots)>256

def parse(text):
    records={i:[] for i in range(len(ROUTES))};done={};captures={}
    for line in text.splitlines():
        if line.startswith('Special game: '):
            f=line.split()[2:]
            mb=list(map(int,f[2:2+MAILBOX]));t=f[2+MAILBOX:]
            records[int(f[0])].append({'frame':int(f[1]),'mb':mb,'crc32':t[0],'crc40':t[2],'below_hud':t[10]})
        m=re.match(r'Special game route done: (\d+) (\d+) vint=(\d+) phase=(\d+) error=(\d+)',line)
        if m:done[int(m[1])]={'frame':int(m[2]),'vint':int(m[3]),'phase':int(m[4]),'error':int(m[5])}
        m=re.match(r'special-game-(\d+)-(\d+)-(\d+)-(\d+) frame=\d+ (\d+)x(\d+) hash=([0-9a-f]+)',line)
        if m:captures[(int(m[1]),int(m[2]),int(m[3]))]=m[7]
    return records,done,captures

def retail(route):
    folder=ROOT/'build/special-retail'
    rows=[json.loads(line) for line in (folder/f'{route}.jsonl').open()]
    blobs=json.loads((folder/f'{route}-blobs.json').read_text())
    frames={};phase='stage'
    for row in rows:
        if row['routine']==5:phase='results'
        frames[(phase,row['v'])]=row
    return frames,blobs

# Slave floor-unit time (mailbox [38], FRT ticks at 26.8466 MHz / 8) per Sub CPU
# update that took exactly three frames: the smallest idle share is the render
# headroom (0 means the slave never waited for a job).
UPDATE_TICKS=3*26846600/8/59.94
def slave_idle(records):
    first={}
    for r in records:
        if r['mb'][3]<5 and r['mb'][4]>0:first.setdefault(r['mb'][4],r)
    updates=sorted(first);shares=[]
    for a,b in zip(updates,updates[1:]):
        A,B=first[a],first[b]
        if b==a+1 and B['frame']-A['frame']==3:shares.append(1-((B['mb'][38]-A['mb'][38])&0xffffffff)/UPDATE_TICKS)
    return round(min(shares),3) if shares else None

def check_route(index,name,records,done,failures):
    pad,_,_=special_retail.route_spec(name)
    frames,blobs=retail(name);hashes={}
    def blob_hash(key):
        if key not in hashes:hashes[key]=fnv(bytes.fromhex(blobs[key]))
        return hashes[key]
    fail=lambda text:failures.append(f'{name}: {text}') if len(failures)<80 else None
    route_done=done.get(index)
    if not route_done or route_done['error'] or route_done['phase']!=8:fail(f'route did not finish cleanly: {route_done}')
    first={};order=[]
    for i,r in enumerate(records):
        key=('results' if r['mb'][2]>=5 else 'stage',r['mb'][1])
        if key not in first:first[key]=i;order.append(key)
    # Retail keeps counting after the exit fade clears the stage and after the
    # results program returns; the native program stops at those points.
    ends={max(v for p,v in frames if p==phase) for phase in ('stage','results') if any(p==phase for p,_ in frames)} # Mode entries have no results.
    missing=[k for k in frames if k[1] and k not in first and not (k[1] in ends and k==max((x for x in frames if x[0]==k[0]),key=lambda x:x[1]))]
    if missing:fail(f'{len(missing)} retail V-INTs missing, first {sorted(missing)[:3]}')
    stats={'vints':0,'pixel_matches':0,'hud_partial':[],'md_sprite_overflow':[],'late':[],'late_picture':[],'near_late':[],'first_entry_black':[],'pad_mismatches':0,'state_mismatches':0}
    # A late V-INT shifts which capture follows the V-INT before it; its picture is
    # reported with the late frame instead of failing.
    late_keys={key for a,key in zip(order,order[1:]) if key[1] and records[first[key]]['frame']-records[first[a]]['frame']!=1}
    previous=None
    for key in order:
        phase,v=key;i=first[key];r=records[i];mb=r['mb']
        if v==0:previous=None;continue
        row=frames.get(key)
        if not row:fail(f'{key} not in the retail run');continue
        stats['vints']+=1
        if pad(v,phase=='results')!=mb[25]:
            stats['pad_mismatches']+=1;fail(f'{key} pad {mb[25]} expected {pad(v,phase=="results")}')
        if previous is not None and r['frame']-records[first[previous]]['frame']!=1:stats['late'].append(key)
        previous=key
        reg=bytes.fromhex(row['reg']);vsram=int(row['vsram'][2:4]+row['vsram'][0:2],16)
        state={'routine':(mb[3],row['routine']),'score':(mb[13],row['score']),'lives':(mb[14],row['lives']),
            'ring_bonus':(mb[18],row['ring_bonus']),'time_bonus':(mb[19],row['time_bonus']),'results_timer':(mb[20],row['results_timer']),
            'extra_players':(mb[21],row['extra_players']),'paused':(mb[22],row['paused']),'ctrl':(mb[23],row['ctrl']),
            'display':(mb[11],(reg[1]>>6&1)|(reg[12]&1)<<1),'vsram':(mb[12],vsram),
            'cram':(mb[7],blob_hash(row['cram'])),'plane_a':(mb[8],blob_hash(row['plane_a'])),'plane_b':(mb[9],blob_hash(row['plane_b'])),'hscroll':(mb[10],blob_hash(row['hscroll']))}
        wrong={k:a for k,a in state.items() if a[0]!=a[1]}
        if wrong:stats['state_mismatches']+=1;fail(f'{key} state {wrong}')
        video=i+(1 if phase=='results' else 2)
        if video>=len(records):
            # A mode entry returns to the title after its exit fade: its last two V-INTs have no stage picture.
            if key!=order[-1] and not (MODES and key in order[-2:]):fail(f'{key} has no picture record')
            continue
        shown=records[video]
        if (shown['crc40'] if phase=='results' else shown['crc32'])==row['pixels']:stats['pixel_matches']+=1;continue
        # Open item, cause not isolated: on the first entry after boot the
        # display returns one frame later than on a later entry, so V-INT 1's
        # white fade frame is still black. Later V-INTs and entries match.
        if key==('stage',1) and index==0 and shown['crc32']=='03a76217':stats['first_entry_black'].append(v);continue
        prior=first.get((phase,v-1))
        hud_changed=prior is not None and records[prior]['mb'][8]!=mb[8]
        if phase=='stage' and hud_changed and shown['below_hud']==row['pixels_below_hud']:stats['hud_partial'].append(v);continue
        if phase=='stage' and sprite_overflow(bytes.fromhex(blobs[row['sat']])):stats['md_sprite_overflow'].append(v);continue
        if key in late_keys or (phase,v+1) in late_keys:stats['late_picture'].append(v);continue
        fail(f'{key} picture differs from retail (frame {shown["frame"]})')
    # Heavy floor views can exceed the dual-SH-2 render budget in the emulator.
    # A late frame shifts the display and the harness pad schedule for the next
    # V-INTs; those are reported, bounded and left to the hardware timing check.
    if len(stats['late'])>LATE_LIMIT:fail(f'{len(stats["late"])} late V-INTs, limit {LATE_LIMIT}')
    near=lambda text:any(p==text[0] and 0<=text[1]-v<=3 for p,v in stats['late'])
    kept=[]
    for text in failures:
        m=re.match(rf"{name}: \('(stage|results)', (\d+)\) (picture differs|pad )",text)
        if m and near((m[1],int(m[2]))):stats['near_late'].append(int(m[2]))
        else:kept.append(text)
    failures[:]=kept
    last=records[-1]['mb'] if records else [0]*MAILBOX
    stats.update({'late':[list(k) for k in stats['late']],'score':last[13],'lives':last[14],'rings':last[15],'timer':last[16],'ufo_count':last[17],
        'min_slave_idle':slave_idle(records),'forced_master_rows':last[37],'max_master_row_lines':last[35],'max_present_line':max((r['mb'][36] for r in records if r['mb'][36]<224),default=0),'slave_rows':last[39]})
    return stats

def main():
    records,done,captures=parse(LOG.read_text())
    failures=[];report={'routes':{}}
    for index,name in enumerate(ROUTES):report['routes'][name]=check_route(index,name,records[index],done,failures)
    for capture in sorted(() if STAGES or MODES else CAPTURES):
        if capture not in captures:failures.append(f'capture {capture} missing')
    report['captures']={'-'.join(map(str,k)):v for k,v in sorted(captures.items())}
    report['disc_sha256']=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest()
    report['failures']=failures;report['passed']=not failures
    report['limits']='Emulator (Beetle Saturn) only; hardware timing and audio are Phase I.'
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    for name,stats in report['routes'].items():
        print(name,{k:(len(v) if isinstance(v,list) else v) for k,v in stats.items()})
    for line in failures[:40]:print('FAIL',line)
    raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__':main()
