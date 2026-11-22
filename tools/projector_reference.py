#!/usr/bin/env python3
"""Read pinned projector scripts; independently replay flying-animal byte rules."""
import re
from convert_assets import DATA

def values(text,kind='b'):
    return [int(v.strip().replace('$','0x'),0) for line in text.splitlines()
            if (m:=re.search(r'dc\.'+kind+r'\s+([^;]+)',line)) for v in m[1].split(',')]

def animations():
    scripts=[]
    for file in ['Projector/Data/Animations.asm','Animal/Data/Animations (Flying).asm','Animal/Data/Animations (Ground).asm']:
        data=values((DATA/'Palmtree Panic/Objects'/file).read_text())
        while data:
            end=data.index(255)+1;scripts.append(data[:end]);data=data[end:]
    assert len(scripts)==5 and all(all(v<32 for v in a[1:-1]) for a in scripts)
    return scripts

def explosions():
    text=(DATA/'Palmtree Panic/Objects/Projector/Main.asm').read_text().split('ObjProjector_ExplosionLocs:')[1]
    data=values(text);assert data[-2:]==[255,0]
    signed=lambda n:n if n<128 else n-256
    return [(data[i],signed(data[i+1]),signed(data[i+2])) for i in range(0,len(data)-2,3)]

def sine():
    text=(DATA/'Functions (Misc).asm').read_text().split('SineTable:')[1].split('CalcAngle:')[0]
    data=values(text,'w');assert len(data)==320
    return [n if n<32768 else n-65536 for n in data]

def flying(hologram=False,ticks=1024,fx=0,fy=0):
    """Rows are x16.16,y16.16,phase,direction,flip,frame,draw,anim-index,time.

    Includes the non-drawing initialization tick and the hologram's early
    return every 32 movement ticks. Normal endpoints reflect before advancing.
    """
    table=sine();script=animations()[3 if hologram else 2]
    phase=0 if hologram else 1;direction=0 if hologram else 1
    flip=1;frame=step=timer=0;x=(500<<16)|fx;y=(400<<16)|fy;rows=[]
    for tick in range(ticks):
        draw=False
        if tick:
            x=((500+(table[phase+64]>>(3 if hologram else 1)))<<16)|fx
            y=((400+(table[phase]>>(4 if hologram else 1)))<<16)|fy
            if hologram:
                phase=(phase+4)&255
                if phase&127==0:flip^=1
                else:draw=True
            else:
                candidate=(phase+direction)&255
                if ((candidate-1)&255)<127:phase=candidate
                else:direction=-direction;flip^=1
                draw=True
            if draw:
                timer=(timer-1)&255
                if timer>=128:
                    timer=script[0]
                    if script[1+step]==255:step=0
                    frame=script[1+step];step+=1
        rows.append([x&0xffffffff,y&0xffffffff,phase,direction&255,flip,frame,int(draw),step,timer])
    h=2166136261
    for row in rows:
        for word in row:h=((h^word)*16777619)&0xffffffff
    return rows,h

if __name__=='__main__':
    print('Explosion events:',explosions())
    print('Animation lengths:',[len(a) for a in animations()])
    for holo in [False,True]:
        for fractions in [(0,0),(0x1234,0x5678)]:
            rows,h=flying(holo,1024,*fractions)
            print('Flying',holo,fractions,len(rows),h)
