#!/usr/bin/env python3
"""Extend a recorded route with a bounded controller-only X target policy."""
import argparse,json
from ppz_journey import ROOT,Journey,describe
def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--label',required=True)
    p.add_argument('--x',type=float,required=True);p.add_argument('--speed',type=int,default=128)
    p.add_argument('--steps',type=int,default=1500);p.add_argument('--spring',action='store_true')
    p.add_argument('--prefix-count',type=int);p.add_argument('--grounded',action='store_true')
    p.add_argument('--run-updates',type=int,default=0);p.add_argument('--jump-updates',type=int,default=0)
    p.add_argument('--launch-direction',choices=['left','right'],default='right')
    p.add_argument('--dash',action='store_true',help='Stop, face launch direction and charge a Classic dash before launch')
    p.add_argument('--box',nargs=4,type=float);a=p.parse_args()
    out=ROOT/'build/ppz-journey'/a.label;out.mkdir(exist_ok=False)
    pads=list(map(int,(ROOT/a.prefix).read_text().split()));pads=pads[:a.prefix_count];j=Journey()
    for pad in pads:
        result,s=j.step(pad);assert not result
    direction=4 if a.launch_direction=='left' else 8
    if a.dash:
        for _ in range(240):
            d=describe(s);stopped=not d['vx'] and not(d['flags']&2)
            facing=bool(d['flags']&1)==(direction==4)
            if stopped and facing:break
            result,s=j.step(direction if stopped else 0);pads.append(direction if stopped else 0);assert not result
        else:raise RuntimeError('Could not stop and face the requested dash direction')
        for tick in range(50):
            pad=2|(16 if 2<=tick<6 else 0)
            result,s=j.step(pad);pads.append(pad);assert not result
    for pad,count in [(direction,a.run_updates),(direction|16,a.jump_updates)]:
        for _ in range(count):
            result,s=j.step(pad);pads.append(pad);assert not result
    springs=s[10]>>16;samples=[];success=False
    for tick in range(a.steps):
        d=describe(s);x=d['x'];vx=d['vx']
        if x<a.x-2 and vx<a.speed:pad=8
        elif x>a.x+2 and vx>-a.speed:pad=4
        elif abs(vx)>48:pad=4 if vx>0 else 8
        else:pad=0
        result,s=j.step(pad);pads.append(pad);d=describe(s)
        if tick%10==0:samples.append(d)
        if result or s[7]:break
        success=a.spring and s[10]>>16>springs
        if a.box:
            x0,x1,y0,y1=a.box;success=x0<=d['x']<x1 and y0<=d['y']<y1
        if a.grounded:success=success and not(d['flags']&2)
        if success:break
    (out/'pads.txt').write_text(''.join(f'{pad}\n' for pad in pads))
    report=dict(success=success,result=result,final=describe(s),springs=s[10]>>16,samples=samples)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2))
if __name__=='__main__':main()
