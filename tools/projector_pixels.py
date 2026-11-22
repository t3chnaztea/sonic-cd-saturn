"""Composite original projector/animal sprites with source foreground priority."""
import re
from convert_objects import DATA,assembly_frames,nemesis,palette
from sprite_composition import source_sprite as draw
from terrain_pixels import foreground_pixel
from check_sonic_pixels import integer,signed as signed32,texture as sonic_texture
from sprite_priority_reference import priorities

def frames():
    common=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
    p=DATA/'Palmtree Panic/Objects/Projector/Data';a=DATA/'Palmtree Panic/Objects/Animal/Data';e=DATA/'_Objects/Explosion/Data'
    animal_maps=assembly_frames(a/'Mappings (Flying).asm')+assembly_frames(a/'Mappings (Ground).asm')
    groups=[(assembly_frames(p/'Mappings.asm'),p/'Art.nem',48),(animal_maps,a/'Art.nem',32),(animal_maps,p/'Art (Animals).nem',32),(assembly_frames(e/'Mappings.asm'),e/'Art.nem',64)]
    result={};n=257
    for mappings,path,width in groups:
        art=nemesis(path.read_bytes())
        for m in mappings:
            result[n]=(draw(m,art,common,width),width,263<=n<266 or n>=279);n+=1
    assert n==286
    return result

def signed(word):return word-65536 if word&32768 else word

def pair(word):return signed(word>>16),signed(word&65535)

def verify(folder,log):
    art=frames();counts=[];represented=set();_,source_priority=priorities()
    headers=re.findall(r'Projector pixels: capture=(\d+) era=(\d+) clock=(\d+) count=(\d+)',log)
    assert len(headers)==6,('missing projector captures',headers)
    for c,era,clock,count in headers:
        capture,era,clock,count=map(int,[c,era,clock,count])
        records=re.findall(r'Projector sprite: capture='+c+r' data=(\d+) world=(\d+) screen=(\d+)',log)
        assert len(records)==count and count>0
        layers=[];order=[]
        for data,world,screen in records:
            data,world,screen=map(int,[data,world,screen]);frame=data>>16;flags=data&3
            texture,width,high=art[frame];x,y=pair(screen);wx,wy=pair(world)
            kind=(data>>8)&255
            subtype=(128 if 271<=frame<=278 else 0)|(1 if 266<=frame<=270 or 274<=frame<=278 else 0)
            priority=source_priority(kind,subtype,0);order.append(priority)
            layers.append((priority,texture,width,high,x,y,wx,wy,flags,False))
            represented.add(frame)
        assert order==sorted(order,reverse=True),('original projector/animal priority',capture,order)
        matches=re.findall(r'^Projector Sonic: capture='+c+r' ((?:\d+ ?)+)$',log,re.M)
        assert len(matches)==1,('missing projector Sonic snapshot',capture)
        sonic=list(map(int,matches[0].split()))
        assert len(sonic)==18 and sonic[0]==0x534F4E56 and sonic[3]<198
        if not sonic[13]:
            wx,wy=integer(sonic[5]),integer(sonic[6])
            layers.append((2,sonic_texture(sonic[3]),64,False,wx-signed32(sonic[7]),wy-signed32(sonic[8]),wx,wy,sonic[4]&3,True))
        # All object texels stay in the coverage mask, including those covered
        # by Sonic. Compose source-priority winners; never skip the overlap.
        pixels={};mask=set()
        for priority,texture,width,high,x,y,wx,wy,flags,is_sonic in sorted(layers,key=lambda v:-v[0]):
            # The source mapping origin stays (canvas/2,32) through cropping.
            for py in range(64):
                for px in range(width):
                    sx=width-1-px if flags&1 else px;sy=63-py if flags&2 else py
                    value=int.from_bytes(texture[(sy*width+sx)*2:(sy*width+sx)*2+2],'big')
                    if not value:continue
                    dx,dy=x-width//2+px,y-32+py
                    if not(0<=dx<320 and 44<=dy<184):continue
                    rgb=bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))
                    pixels[dx,dy]=(rgb,high,wx-width//2+px,wy-32+py,is_sonic)
                    if not is_sonic:mask.add((dx,dy))
        raw=(folder/f'projector-animal-{capture}.ppm').read_bytes().split(b'255\n',1)[1]
        eras=['Present','Past','Good Future','Bad Future'];checked=covered=overlap=0
        for x,y in sorted(mask):
            rgb,high,wx,wy,is_sonic=pixels[x,y]
            fg=foreground_pixel(eras[era],wx,wy,clock)
            expected=fg[1] if not high and fg and fg[0] else rgb
            actual=raw[(y*330+x+5)*3:(y*330+x+5)*3+3]
            assert actual==expected,('projector pixel',capture,x,y,wx,wy,actual,expected,high)
            checked+=1;covered+=int(not high and bool(fg and fg[0]));overlap+=is_sonic
        assert checked-covered>32,('insufficient exposed projector/animal pixels',capture,checked,covered)
        counts.append((checked-covered,covered))
        print('Projector/animal source pixels:',capture,'sprite',checked-covered,'foreground',covered,'Sonic overlap',overlap)
    assert 257 in represented and any(261<=n<=262 for n in represented)
    assert any(263<=n<=264 for n in represented) and any(266<=n<=267 for n in represented)
    assert any(271<=n<=272 for n in represented) and any(274<=n<=278 for n in represented)
    assert any(279<=n<=285 for n in represented)
    return counts

if __name__=='__main__':
    from convert_assets import ROOT
    folder=ROOT/'build/world-qa';verify(folder,(folder/'results.log').read_text())
