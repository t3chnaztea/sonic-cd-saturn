#!/usr/bin/env python3
"""Pinned Amy byte scripts and independent heart/animation timing references.

Independent reference for the native Amy actor QA. Source: PPZ Objects/Amy Rose/Main.asm and Data/Animations.asm.
"""
import re
from convert_assets import DATA
from projector_reference import sine,values

def animations():
    text=(DATA/'Palmtree Panic/Objects/Amy Rose/Data/Animations.asm').read_text()
    pointers=re.findall(r'dc\.w\s+(\w+)-\.Anim',text);assert len(pointers)==6
    result=[]
    for name in pointers:
        block=re.split(r'\n\w+:',text.split(name+':',1)[1],maxsplit=1)[0]
        data=values(block);stop=data.index(255);assert stop%2==0 and data[stop:]==[255,0]
        result.append(list(zip(data[:stop:2],data[1:stop:2])))
    return result

def animate(sequence):
    """One row per update: input animation, source map frame, cursor and timer."""
    scripts=animations();previous=0;cursor=timer=frame=0;rows=[]
    for animation in sequence:
        if animation!=previous:previous=animation;cursor=timer=0
        timer=(timer-1)&255
        if timer>=128:
            if cursor==len(scripts[animation]):cursor=0
            frame,timer=scripts[animation][cursor];cursor+=1
        rows.append([animation,frame,cursor*2,timer])
    return rows

def fingerprint(rows):
    h=2166136261
    for row in rows:
        for n in row:h=((h^(n&0xffffffff))*16777619)&0xffffffff
    return h

def heart(fx=0,fy=0):
    table=sine();x=(500<<16)|fx;y=(400<<16)|fy
    vx=0;vy=-96;age=0;frame=8;stopped=False;rows=[]
    for tick in range(1,121):
        if not stopped:vx=table[(age*3)&255]>>2
        x+=vx*256;y+=vy*256;age=(age+1)&255
        if age==20:frame+=1
        if age==110:frame+=1;vx=vy=0;stopped=True
        # DeleteObject clears the actor at the end of tick 120.
        rows.append([x&0xffffffff,y&0xffffffff,vx&65535,vy&65535,frame,age,int(stopped),1] if age!=120 else [0]*8)
    return rows

def spawns(ticks,holding=False,initial=0):
    """Carry occurs before allocation; exhausted pools still consume the carry."""
    phase=initial;out=[]
    for tick in range(1,ticks+1):
        total=phase+(16 if holding else 6);phase=total&255
        if total>255:out.append(tick)
    return out,phase

if __name__=='__main__':
    scripts=animations()
    print('Amy animation cycle ticks:',[sum(t+1 for _,t in a) for a in scripts])
    for a in range(6):print('Animation',a,'600 ticks hash',fingerprint(animate([a]*600)))
    print('Animation switches hash',fingerprint(animate([5]*19+[2]*43+[3]*61+[1]*91+[4]*131+[0]*29)))
    for fractions in [(0,0),(0x1234,0x5678)]:print('Heart',fractions,'120 ticks hash',fingerprint(heart(*fractions)))
    for holding in [False,True]:print('Heart spawns',holding,spawns(256,holding))
