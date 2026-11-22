#!/usr/bin/env python3
"""Original power-up mappings over Sonic, including effect/effect overlap.

Read original art/mapping records, not the generated Saturn textures. Check
every visible opaque effect texel (even covered by an earlier reserved slot),
and Sonic's opaque texels beneath blank/transparent effect frames. Background
holes, the HUD bands (above y=56 / below y=184), and arbitrary ordinary actor
overlap are not covered by this fixture. HUD source pixels have their own gate.
"""
import hashlib,json,re
from functools import lru_cache
from convert_assets import ROOT,DATA,palette
from convert_objects import assembly_frames
from sprite_composition import source_sprite
from check_sonic_pixels import integer,signed,texture as sonic_texture
from terrain_pixels import foreground_pixel

def signed16(n):return (n+32768)%65536-32768
def pair(n):return signed16(n>>16),signed16(n&65535)

@lru_cache(maxsize=13)
def texture(mapping):
    path=DATA/'_Objects/Powerup/Data'
    maps=assembly_frames(path/'Mappings.asm',contiguous=True)
    name='Shield' if mapping<4 else 'Invincibility Stars' if mapping<8 else 'Time Warp Stars'
    width=48 if mapping<8 else 64
    art=(path/f'Art ({name}).bin').read_bytes()
    colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
    return source_sprite(maps[mapping],art,colors,width),width

def screen(x,y,cx,cy,width):
    if cy&65535<256 and y&65535>=2048:y-=2048
    elif cy&65535>=1792 and y&65535<256:y+=2048
    dx,dy=signed16(x-cx),signed16(y-cy)
    return dx,dy,signed16(dx+width)>=0 and signed16(dx-width)<320 and 0<=dy<224

def verify(folder):
    log=(folder/'results.log').read_text()
    records=re.findall(r'^Powerup pixels: (\S+) ((?:\d+ ?)+)$',log,re.M)
    sonics={name:list(map(int,line.split())) for name,line in
        re.findall(r'^Powerup Sonic: (\S+) ((?:\d+ ?)+)$',log,re.M)}
    assert len(records)>=250,('missing effect sequences',len(records))
    captures=[];seen=set();totals=dict(effect=0,sonic=0,effect_overlap=0,sonic_overlap=0,foreground=0)
    for name,line in records:
        v=list(map(int,line.split()));s=sonics[name]
        assert len(v)==57 and v[0]==0x504f5756 and len(s)==18 and s[0]==0x534f4e56
        assert v[9]==s[2] and v[11]==s[11] and v[4:6]==s[7:9],('snapshot alignment',name,v[:12],s)
        cx,cy=signed(v[4]),signed(v[5]);pixels={};owners={};mask=set();sonic_mask=set();effect_mask=set()
        def draw(art,width,x,y,flags,owner):
            for py in range(64):
                for px in range(width):
                    sx=width-1-px if flags&1 else px;sy=63-py if flags&2 else py
                    color=int.from_bytes(art[(sy*width+sx)*2:(sy*width+sx)*2+2],'big')
                    if not color:continue
                    dx,dy=x-width//2+px,y-32+py
                    if not(0<=dx<320 and 56<=dy<184):continue
                    point=(dx,dy);mask.add(point)
                    owners.setdefault(point,set()).add(owner)
                    (sonic_mask if owner<0 else effect_mask).add(point)
                    pixels[point]=bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8))
        if not s[13]:draw(sonic_texture(s[3]),64,integer(s[5])-cx,integer(s[6])-cy,s[4]&3,-1)
        # Original priority 1 is in front of Sonic's priority 2. Within the
        # reserved effect slots the earlier submitted opaque pixel wins.
        for n in range(8,-1,-1):
            a,b,c,position,tile=v[12+5*n:17+5*n]
            if not(v[2]&(1<<n)):continue
            animation=(a>>8)&255;mapping=(b>>8)&255;seen.add((animation,mapping))
            assert animation==n and (c>>8)&255==1 and tile==0x544
            x,y=pair(position);dx,dy,visible=screen(x,y,cx,cy,c&255)
            if mapping and visible:
                art,width=texture(mapping);draw(art,width,dx,dy,b&3,n)
        payload=(folder/(name+'.ppm')).read_bytes();header,raw=payload.split(b'255\n',1)
        assert header==b'P6\n330 224\n' and len(raw)==330*224*3
        counts=dict(effect=len(effect_mask),sonic=len(sonic_mask),effect_overlap=0,sonic_overlap=0,foreground=0)
        for x,y in sorted(mask):
            tile=foreground_pixel(['Present','Past','Good Future','Bad Future'][v[11]],x+cx,y+cy,s[12],path=s[17]>>16)
            covered=bool(tile and tile[0]);expected=tile[1] if covered else pixels[x,y]
            actual=raw[(y*330+x+5)*3:(y*330+x+5)*3+3]
            assert actual==expected,('powerup source pixel',name,v[1],x,y,actual,expected,sorted(owners[x,y]),v[:12])
            counts['foreground']+=covered
            counts['effect_overlap']+=sum(n>=0 for n in owners[x,y])>1
            counts['sonic_overlap']+=(-1 in owners[x,y] and len(owners[x,y])>1)
        for key,value in counts.items():totals[key]+=value
        captures.append(dict(name=name,snapshot=v,sonic_snapshot=s,counts=counts,sha256=hashlib.sha256(payload).hexdigest()))
    required={(0,n) for n in range(4)}|{(a,n) for a in range(1,5) for n in range(4,8)}|{(a,n) for a in range(5,9) for n in range(8,13)}
    required|={(a,0) for a in range(2,9)}
    assert required<=seen,('missing target animation/pose pairs',sorted(required-seen))
    assert totals['effect_overlap']>0 and totals['sonic_overlap']>0,totals
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),captures=captures,
        animation_mapping_pairs=sorted(seen),counts=totals,
        source_sha256={name:sha(ROOT/name) for name in ['src/main.c','src/player.c','src/powerup_visual.c','src/powerup_runtime.c',
            'tools/emulator_test.c','tools/check_powerup_pixels.py','tools/sprite_composition.py','tools/terrain_pixels.py']},
        original_sha256={str(path.relative_to(DATA)):sha(path) for path in
            [DATA/'_Objects/Powerup/Data'/name for name in ['Mappings.asm','Art (Shield).bin','Art (Invincibility Stars).bin','Art (Time Warp Stars).bin']]+[DATA/'_Objects/Sonic/Data/Palette.bin']},
        limits='Controlled shield, invincibility and time-star fixtures within y=56..183. Opaque source pixels, their mutual overlap and foreground priority; not HUD bands, transparent background holes, every ordinary actor overlap, or hardware.')
    print('Power-up source pixels:',len(captures),'pictures;',totals)
    return report

if __name__=='__main__':
    report=verify(ROOT/'build/world-qa')
    (ROOT/'dist/powerup-render-report.json').write_text(json.dumps(report,indent=2)+'\n')
