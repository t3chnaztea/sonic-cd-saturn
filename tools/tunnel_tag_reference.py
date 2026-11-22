#!/usr/bin/env python3
"""Independent PPZ future tunnel/tag composition from the pinned 68000 routines.

The path actor runs before the tag at (3872,416). Sonic's movement is owned by
that path; the tag still writes X/G velocity and applies first-entry rolling.
This emits the same five public trace words as the isolated tunnel reference.
"""
from convert_objects import tunnel_paths

def trace(fx=0,fy=0):
    points=tunnel_paths()[1]
    x,y=3848*65536+fx,416*65536+fy
    vx=vy=0;ground=4096;control=129;rolling=False
    routine=1;index=0;steps=0;result=[];contacts=0
    def div(n,d):return (-1 if (n<0)!=(d<0) else 1)*(abs(n)//abs(d))
    def velocity():
        dx,dy=points[index][0]-(x>>16),points[index][1]-(y>>16)
        # SetPlayerSpeed's signed DIVS quotient and dominant-axis branch.
        if abs(dy)>=abs(dx):
            major=-ground if dy<0 else ground
            duration=div(dy*65536,major)
            return div(dx*65536,duration) if dx else 0,major,abs(duration)
        major=-ground if dx<0 else ground
        duration=div(dx*65536,major)
        return major,div(dy*65536,duration) if dy else 0,abs(duration)
    for tick in range(1000):
        if tick:
            if routine==1:
                vx,vy,steps=velocity();routine=2
            else:
                high=((steps>>8)-1)&255;steps=(high<<8)|(steps&255)
                if high<128:x+=vx*256;y+=vy*256
                else:
                    x=(points[index][0]<<16)|(x&65535);y=(points[index][1]<<16)|(y&65535)
                    index+=1
                    if index==len(points):control=0
                    else:vx,vy,steps=velocity()
        if -40<=(x>>16)-3872<40 and -40<=(y>>16)-416<40:
            contacts+=1;vx=(-1 if vx<0 else 1)*max(2560,abs(vx));ground=vx
            if not rolling:rolling=True;y+=5*65536
        result.append([x&0xffffffff,y&0xffffffff,vx&65535,vy&65535,control])
        if not control:break
    else:raise AssertionError('source path did not release')
    h=2166136261
    for row in result:
        for word in row:h=((h^word)*16777619)&0xffffffff
    return result,h,contacts
if __name__=='__main__':
    for fractions in [(0,0),(0x1234,0x5678)]:
        rows,h,contacts=trace(*fractions)
        print(f'fractions={fractions} ticks={len(rows)} hash={h} contacts={contacts} exit={rows[-1]}')
