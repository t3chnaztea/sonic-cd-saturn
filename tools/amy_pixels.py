"""Original Amy, heart and Sonic idle sprites, including foreground priority."""
import re
from convert_objects import DATA,assembly_frames,nemesis,palette
from sprite_composition import source_sprite as draw
from convert_assets import sonic_frame
from terrain_pixels import foreground_pixel,palette_at
from projector_pixels import pair

def verify(folder,log):
    path=DATA/'Palmtree Panic/Objects/Amy Rose/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    amy=palette((path/'Palette.bin').read_bytes());common=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
    textures=[draw(m,art,amy) for m in maps]+[draw(maps[i],art,common) for i in range(8,11)]+[sonic_frame(i) for i in range(1,5)]
    headers=re.findall(r'Amy pixels: capture=(\d+) era=(\d+) clock=(\d+) count=(\d+)',log)
    assert len(headers)==3,('missing Amy captures',headers)
    counts=[];represented=set()
    for c,era,clock,count in headers:
        assert era=='0';clock=int(clock);count=int(count)
        records=re.findall(r'Amy sprite: capture='+c+r' data=(\d+) world=(\d+) screen=(\d+)',log)
        assert len(records)==count and count>=3
        # Original initializers: Amy priority 1, Sonic 2, hearts 3. Saturn
        # painter order must be rear-to-front; do not accept an arbitrary
        # target order merely because its reported intent matches its picture.
        priorities=[{1:2,47:1,48:3}[(int(data)>>8)&255] for data,_,_ in records]
        assert priorities==sorted(priorities,reverse=True),('Original Amy/Sonic/heart priority',c,priorities)
        terrain_colors=bytearray(palette_at('Present',clock));terrain_colors[32:64]=amy
        pixels={};types=set()
        for data,world,screen in records:
            data,world,screen=map(int,[data,world,screen]);frame=data>>16;flags=data&3;kind=(data>>8)&255
            texture=sonic_frame(frame) if kind==1 else textures[frame-286];x,y=pair(screen);wx,wy=pair(world);represented.add((kind,frame));types.add(kind)
            for py in range(64):
                for px in range(64):
                    sx=63-px if flags&1 else px;sy=63-py if flags&2 else py
                    value=int.from_bytes(texture[(sy*64+sx)*2:(sy*64+sx)*2+2],'big')
                    if not value:continue
                    dx,dy=x-32+px,y-32+py
                    if not(0<=dx<320 and 44<=dy<184):continue
                    rgb=bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))
                    pixels[dx,dy]=(rgb,wx-32+px,wy-32+py,kind)
        assert types=={1,47,48},types
        raw=(folder/f'amy-hold-{c}.ppm').read_bytes().split(b'255\n',1)[1]
        checked={1:0,47:0,48:0};covered=0
        for (x,y),(rgb,wx,wy,kind) in pixels.items():
            fg=foreground_pixel('Present',wx,wy,clock,terrain_colors)
            hidden=bool(fg and fg[0]);expected=fg[1] if hidden else rgb
            actual=raw[(y*330+x+5)*3:(y*330+x+5)*3+3]
            assert actual==expected,('Amy source pixel',c,x,y,kind,actual,expected)
            if hidden:covered+=1
            else:checked[kind]+=1
        assert all(n>=8 for n in checked.values()),('insufficient visible source pixels',c,checked)
        counts.append({'capture':int(c),'visible':checked,'foreground':covered})
        print('Amy source pixels:',counts[-1])
    assert (47,300) in represented and len(represented&{(1,1),(1,2),(1,3),(1,4)})>=2,represented
    return counts

if __name__=='__main__':
    from convert_assets import ROOT
    folder=ROOT/'build/world-qa';verify(folder,(folder/'results.log').read_text())
