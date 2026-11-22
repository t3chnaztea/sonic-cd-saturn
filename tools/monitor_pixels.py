"""Independent pixel-first source oracle for intact monitor compositions.

Do not use convert_objects.draw: that painter-order implementation originally
hid the icon behind its own casing. Walk the original sprite list at each
destination pixel and stop at the first nontransparent source texel.
"""
import struct
from functools import lru_cache
from convert_assets import DATA,assembly_frames,nemesis,palette

SOURCE=DATA/'_Objects/Monitor and Time Post/Data'

@lru_cache(maxsize=24)
def source_monitor(frame, *, legacy_last=False):
    mapping=assembly_frames(SOURCE/'Mappings.asm')[frame if frame<10 else frame+6]
    art=nemesis((SOURCE/'Art.nem').read_bytes())
    colors=struct.unpack('>16H',palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes()))
    pieces=[]
    for n in range(mapping[0]):
        y,size,tile,x=struct.unpack_from('>bBHb',mapping,1+n*5)
        pieces.append((x,y,8*((size>>2)+1),8*((size&3)+1),tile))
    result=bytearray(32*64*2)
    for y in range(64):
        for x in range(32):
            for ox,oy,w,h,tile in pieces:
                sx,sy=x-16-ox,y-32-oy
                if not(0<=sx<w and 0<=sy<h):continue
                if tile&0x800:sx=w-1-sx
                if tile&0x1000:sy=h-1-sy
                tile_id=(tile&0x7ff)+(sx//8)*(h//8)+sy//8
                packed=art[tile_id*32+(sy&7)*4+(sx&7)//2]
                index=(packed>>(0 if sx&1 else 4))&15
                if not index:continue
                struct.pack_into('>H',result,(y*32+x)*2,colors[index])
                if not legacy_last:break
    return bytes(result)

def verify_monitor_overlap(data,frame,x,y,sonic):
    """Check every opaque monitor pixel, including any original Sonic overlap.

    Sonic priority 2 is in front of PPZ monitor priority 3. This is actor
    ordering, not the source piece-composition rule inside the TV itself.
    """
    from check_sonic_pixels import integer,signed,texture
    assert len(sonic)==18 and sonic[0]==0x534F4E56 and not sonic[13]
    mapping,flags=sonic[3],sonic[4];assert mapping<198
    sx=integer(sonic[5])-signed(sonic[7]);sy=integer(sonic[6])-signed(sonic[8])
    art=texture(mapping);monitor=source_monitor(frame);checked=covered=0
    for py in range(64):
        for px in range(32):
            value=int.from_bytes(monitor[(py*32+px)*2:(py*32+px)*2+2],'big')
            if not value:continue
            dx=x-16+px;dy=y-32+py;ax=dx-sx+32;ay=dy-sy+32
            if 0<=ax<64 and 0<=ay<64:
                if flags&1:ax=63-ax
                if flags&2:ay=63-ay
                foreground=int.from_bytes(art[(ay*64+ax)*2:(ay*64+ax)*2+2],'big')
                if foreground:value=foreground;covered+=1
            assert 0<=dx<320 and 0<=dy<224
            expected=bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))
            actual=data[(dy*330+dx+5)*3:(dy*330+dx+5)*3+3]
            assert actual==expected,('original monitor/Sonic overlap',dx,dy,actual,expected,mapping)
            checked+=1
    return checked,covered
