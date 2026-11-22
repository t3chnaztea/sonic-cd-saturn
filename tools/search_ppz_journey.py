#!/usr/bin/env python3
"""Bounded controller-policy search, never a gameplay acceptance test."""
import argparse,json,time
from pathlib import Path
from ppz_journey import ROOT,Journey,describe
import os
# Batch job: yield the CPU to foreground work (SCD_NICE=0 disables).
try:
    os.nice(int(os.environ.get('SCD_NICE', '20')))
except PermissionError:  # already at the lowest priority
    pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--prefix',type=Path)
    p.add_argument('--goal',choices=['past','generator','act2'],default='past')
    p.add_argument('--steps',type=int,default=6000);p.add_argument('--start',type=int,default=600)
    p.add_argument('--limit',type=int,default=12);args=p.parse_args()
    out=ROOT/'build/ppz-journey'/args.label;out.mkdir(exist_ok=False)
    prefix=list(map(int,args.prefix.read_text().split())) if args.prefix else []
    j=Journey();records=[];matches=[];started=time.monotonic();trials=0
    for period in range(40,281,20):
        for hold in [1,10,20,30,40]:
            if hold>=period:continue
            for phase in range(0,period,20):
                assert not j.lib.journey_init();pads=[];success=False;result=0
                for tick in range(args.steps):
                    local=tick-len(prefix)
                    pad=prefix[tick] if tick<len(prefix) else 8|(16 if local>=args.start+phase and (local-args.start-phase)%period<hold else 0)
                    result,s=j.step(pad);pads.append(pad)
                    success=s[17]==1 if args.goal=='past' else bool(s[19]) if args.goal=='generator' else s[16]>=1 and s[18]&1
                    if result or success or s[16]>0 or s[7]:break
                row=dict(period=period,hold=hold,phase=phase,steps=len(pads),result=result,success=bool(success),final=describe(s));records.append(row);trials+=1
                if success:
                    path=out/f'match-{len(matches):02}.pads';path.write_text(''.join(f'{pad}\n' for pad in pads));row['pads']=str(path.relative_to(ROOT));matches.append(row)
                    print(json.dumps(row),flush=True)
                if trials%100==0:print('trials',trials,'seconds',round(time.monotonic()-started,1),flush=True)
                if len(matches)>=args.limit:break
            if len(matches)>=args.limit:break
        if len(matches)>=args.limit:break
    (out/'search.json').write_text(json.dumps(dict(goal=args.goal,trials=trials,seconds=time.monotonic()-started,matches=matches,trials_detail=records),indent=2)+'\n')
    print('Finished',trials,'trials;',len(matches),'matches',flush=True)
if __name__=='__main__':main()
