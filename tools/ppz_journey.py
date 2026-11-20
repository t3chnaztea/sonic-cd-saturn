#!/usr/bin/env python3
"""Controller-only exploratory PPZ journey; reports are never acceptance gates."""
import argparse,ctypes as C,hashlib,json,struct,subprocess
from pathlib import Path
from ppz_journey_manifest import verify as verify_build
ROOT=Path(__file__).resolve().parents[1]
class Object(C.Structure):
    _fields_=[('x',C.c_int16),('y',C.c_int16),('type',C.c_uint8),('subtype',C.c_uint8),('flags',C.c_uint8),('frame',C.c_uint8)]
class Journey:
    def __init__(self):
        self.lib=C.CDLL(str(ROOT/'build/ppz-journey/native.dylib'))
        self.lib.journey_state.restype=C.POINTER(C.c_uint32)
        self.lib.journey_objects.argtypes=[C.POINTER(Object),C.c_uint]
        assert not self.lib.journey_init()
    def state(self):return list(self.lib.journey_state()[:40])
    def objects(self):
        views=(Object*96)();count=self.lib.journey_objects(views,96)
        return [[v.x,v.y,v.type,v.subtype,v.flags,v.frame] for v in views[:count]]
    def step(self,pad):return self.lib.journey_step(pad),self.state()
def signed(n):return n if n<0x80000000 else n-0x100000000
def describe(s):
    return dict(update=s[28],act=s[16]+1,era=s[17],x=signed(s[0])/65536,y=signed(s[1])/65536,
        vx=C.c_int16(s[2]>>16).value,vy=C.c_int16(s[2]&65535).value,speed=C.c_int16(s[3]>>16).value,
        flags=s[3]>>8&255,routine=s[9]>>24,rings=s[8]>>16,lives=s[9]&255,clock=s[29],score=s[30],
        good_flags=s[18],good_future=s[19],warp=s[20],direction=signed(s[21]),transitions=s[22],
        phase=s[25],control=s[26],generator=s[32],post=signed(s[33]),destination=signed(s[35]),pad=s[37])
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True)
    parser.add_argument('--steps',type=int,default=12000);parser.add_argument('--period',type=int,default=0)
    parser.add_argument('--hold',type=int,default=20);parser.add_argument('--start',type=int,default=600)
    parser.add_argument('--script',type=Path,help='JSON list of [begin,end,pad] overrides in global simulation-update order')
    parser.add_argument('--prefix',type=Path,help='Recorded controller pads to replay before exploration')
    parser.add_argument('--prefix-count',type=int,help='Keep only this many prefix inputs')
    parser.add_argument('--append-trace',type=Path,help='Append controller column from an existing target trace')
    parser.add_argument('--until-zone-results',action='store_true',help='Stop at Act 3 completed tally, before non-simulation ending fields')
    parser.add_argument('--until-box',nargs=4,type=float,metavar=('X0','X1','Y0','Y1'))
    parser.add_argument('--until-era',type=int,default=1)
    parser.add_argument('--bunny',action='store_true',help='Jump from observed landings, holding for 40 updates')
    parser.add_argument('--boss-policy',action='store_true',help='Follow the fighting boss and jump from beneath him using controller inputs')
    args=parser.parse_args();out=ROOT/'build/ppz-journey'/args.label;out.mkdir(exist_ok=False)
    script=json.loads(args.script.read_text()) if args.script else []
    prefix=list(map(int,args.prefix.read_text().split())) if args.prefix else []
    if args.prefix_count is not None:prefix=prefix[:args.prefix_count]
    if args.append_trace:
        suffix=[int(line.split()[1]) for line in args.append_trace.read_text().splitlines()]
        assert all(0<=pad<=31 for pad in suffix)
        prefix+=suffix
    build_manifest=verify_build()
    journey=Journey();rows=[];pads=[];samples=[];events=[];result=0;jump_left=0;boss_hold=0;boss_rest=0
    for tick in range(args.steps):
        pad=8
        if args.period and tick>=args.start and (tick-args.start)%args.period<args.hold:pad|=16
        if args.bunny and tick>=len(prefix):
            if jump_left:pad|=16;jump_left-=1
            elif not(journey.state()[3]&512):pad|=16;jump_left=39
        boss_status=journey.lib.scd_boss_status()&0xffffffff
        if args.boss_policy and tick>=len(prefix) and boss_status>>16 and (boss_status>>8&255)==4:
            before=describe(journey.state());boss_x=(journey.lib.scd_boss_position()&0xffffffff)>>16
            dx=boss_x-before['x'];pad=8 if dx>12 else 4 if dx<-12 else 0
            if boss_hold:
                boss_hold-=1;pad|=16
                if not boss_hold:boss_rest=10
            elif boss_rest:boss_rest-=1
            elif not(before['flags']&2) and abs(dx)<=24:boss_hold=20;pad|=16
        for begin,end,value in script:
            if begin<=tick<end:pad=value
        if tick<len(prefix):pad=prefix[tick]
        result,state=journey.step(pad);rows.append([result,*state]);pads.append(pad)
        if tick%30==0 or state[32] or state[33] or state[34] or state[35]!=0xffffffff or result:
            sample=describe(state);sample['objects']=journey.objects();samples.append(sample)
        if state[32] or state[33] or state[34] or state[35]!=0xffffffff or result:events.append(describe(state))
        if result:break
        if args.until_zone_results and state[16]==2 and state[25]==6:break
        if args.until_box and tick>=len(prefix) and state[17]==args.until_era:
            x0,x1,y0,y1=args.until_box;x,y=signed(state[0])/65536,signed(state[1])/65536
            if x0<=x<x1 and y0<=y<y1:break
    (out/'pads.txt').write_text(''.join(f'{p}\n' for p in pads))
    (out/'states.bin').write_bytes(b''.join(struct.pack('<i40I',*row) for row in rows))
    (out/'samples.json').write_text(json.dumps(samples,indent=2)+'\n')
    (out/'events.json').write_text(json.dumps(events,indent=2)+'\n')
    # Replay the same pads through the standalone sanitized actual-code adapter.
    check=subprocess.run([str(ROOT/'build/ppz-journey/sanitized')],input=''.join(f'{p}\n' for p in pads),cwd=ROOT,text=True,capture_output=True)
    (out/'sanitized.log').write_text(check.stdout+check.stderr)
    actual=[list(map(int,line.split())) for line in check.stdout.splitlines()]
    assert actual==rows,'explorer/sanitized replay differs'
    assert check.returncode==(1 if result<0 else 0)
    assert verify_build()==build_manifest,'journey build changed during exploration'
    report=dict(complete=result==1,zone_results_complete=state[16]==2 and state[25]==6,good_future_complete=result==1 and state[17]==2,result=result,updates=len(rows),final=describe(state),events=events,
        build_manifest=build_manifest,recipe={key:str(value) if isinstance(value,Path) else value for key,value in vars(args).items()},
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['src','tools'] for p in (ROOT/folder).glob('*') if p.is_file() and p.suffix in ['.c','.h','.inc','.py','.sh']},
        evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},
        limits='Exploration with shared native logic, no original or Saturn parity claim. Warp/fade/load-only VBlanks omitted; unexpected special-stage entry is a failure. No teleports or direct progression writes.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'folder':str(out),'result':result,'final':describe(state),'events':events},indent=2))
if __name__=='__main__':main()
