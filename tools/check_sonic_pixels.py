#!/usr/bin/env python3
"""Actual streamed Sonic poses against original mapping/DPLC source pixels.

The first eight replay fixtures have no spawned stage actors. High-priority
foreground remains in front of Sonic, using the original path-selected chunk.
This does not claim full transparent/background, other-actor or all-pose target
coverage. All 198 source poses are separately checked in the streaming gate.
"""
import hashlib,json,re
from functools import lru_cache
from pathlib import Path
from convert_assets import ROOT,DATA,sonic_frame
from terrain_pixels import foreground_pixel

def signed(n):return n-(1<<32) if n&(1<<31) else n
def integer(n):
    n=signed(n);return -(abs(n)//65536) if n<0 else n//65536
@lru_cache(maxsize=198)
def texture(n):return sonic_frame(n)

def verify(folder):
    log=(folder/'results.log').read_text();records=re.findall(r'^Sonic native: (\S+) ((?:\d+ ?)+)$',log,re.M)
    assert records,'missing original Sonic target captures'
    captures=[];pixels=0;foreground=0;seen=set();facings=set();eras=set();air={}
    for name,line in records:
        v=list(map(int,line.split()));assert len(v)==18 and v[0]==0x534F4E56
        mapping,flags=v[3],v[4];era=v[11];assert 0<mapping<198 and era<4 and not v[13]
        assert v[16]<8 or (v[16]==9 and 32<=v[2]<=64)
        wx,wy=integer(v[5]),integer(v[6]);cx,cy=signed(v[7]),signed(v[8]);clock=v[12];path=v[17]>>16
        if v[16]==9:
            assert wy+32<508-16,'spring actor could overlap sampled Sonic'
            assert v[2] not in air
            air[v[2]]={'animation':v[10]>>24,'mapping':mapping,'y':wy}
        payload=(folder/(name+'.ppm')).read_bytes();header,raw=payload.split(b'255\n',1)
        assert header==b'P6\n330 224\n' and len(raw)==330*224*3
        art=texture(mapping);checked=covered=0
        for py in range(64):
            for px in range(64):
                sx=63-px if flags&1 else px;sy=63-py if flags&2 else py
                color=int.from_bytes(art[(sy*64+sx)*2:(sy*64+sx)*2+2],'big')
                if not color:continue
                dx,dy=wx-cx-32+px,wy-cy-32+py
                # The HUD draws over Sonic: its ring counter is at y 40 with 16-line digits
                # (src/hud_view.inc), so rows above 56 are HUD, as are the lives rows from 184.
                if not (0<=dx<320 and 56<=dy<184):continue
                rgb=bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8))
                tile=foreground_pixel(['Present','Past','Good Future','Bad Future'][era],wx-32+px,wy-32+py,clock,path=path)
                hidden=bool(tile and tile[0]);expected=tile[1] if hidden else rgb
                actual=raw[(dy*330+dx+5)*3:(dy*330+dx+5)*3+3]
                assert actual==expected,('Original Sonic target pixel',name,mapping,flags,dx,dy,actual,expected,v)
                covered+=hidden;checked+=not hidden
        assert checked>=32,(name,'insufficient visible Sonic pixels',checked,covered,v)
        captures.append({'name':name,'mapping':mapping,'flip':flags&3,'era':era,'visible_pixels':checked,
            'foreground_pixels':covered,'sha256':hashlib.sha256(payload).hexdigest(),'snapshot':v})
        seen.add(mapping);facings.add(flags&3);eras.add(era);pixels+=checked;foreground+=covered
    assert len(seen)>=25 and {0,1}<=facings and eras=={0,1,2,3},(seen,facings,eras)
    assert set(air)==set(range(32,65)),('missing consecutive spring pictures',sorted(air))
    transitions=[tick for tick in sorted(air) if tick>32 and air[tick]['animation']!=air[tick-1]['animation']]
    assert len(transitions)==1 and air[32]['animation']==16 and air[64]['animation']==0,air
    assert air[32]['y']>air[transitions[0]]['y'] and air[64]['y']>air[transitions[0]]['y']
    report={'passed':True,'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
        'captures':captures,'mapping_ids':sorted(seen),'flips':sorted(facings),'eras':sorted(eras),
        'visible_pixels':pixels,'foreground_pixels':foreground,
        'spring_motion':{'consecutive_pictures':len(air),'transition_frames':transitions,'states':air},
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ['src/sonic_view.inc','src/sonic_art.c','src/sonic_frames.c','src/sonic_frames.h','src/sonic_animation.c','src/player.c','src/main.c',
             'tools/sonic_frame_assets.py','assets/generated/sonic-frames.bin',
             'tools/emulator_test.c','tools/check_sonic_pixels.py','tools/terrain_pixels.py','tools/convert_assets.py']},
        'original_art_sha256':{name:hashlib.sha256((DATA/'_Objects/Sonic/Data'/name).read_bytes()).hexdigest()
            for name in ['Art.bin','Mappings.asm','DPLCs.asm','Palette.bin']},
        'limits':'Eight controlled Act 1 fixtures plus one 33-picture yellow-spring apex sequence; not exhaustive poses, transparent surroundings, arbitrary actor overlap or hardware.'}
    print(f'Original Sonic target pixels: {len(captures)} pictures, {len(seen)} mappings, {pixels} visible and {foreground} foreground pixels')
    return report
if __name__=='__main__':
    report=verify(ROOT/'build/emulator-qa')
    (ROOT/'dist/sonic-render-report.json').write_text(json.dumps(report,indent=2)+'\n')
