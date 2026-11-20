"""Original PPZ foreground pixels; Act 1 remains the default for existing gates."""
from functools import lru_cache
import re,struct
from convert_assets import DATA,nemesis,layout,palette

@lru_cache(maxsize=1)
def retail_programs():
    from extract_mmd import ISO,disc_files,PROGRAMS
    disc=disc_files(ISO.read_bytes())
    return {name:disc[f'{name}__.MMD'] for name in PROGRAMS}

@lru_cache(maxsize=12)
def source(era,act=1):
    assert act in (1,2,3)
    if act!=1:
        from extract_mmd import extract,template_labels
        programs=retail_programs();template=programs['R11A']
        letter='ABCD'[['Present','Past','Good Future','Bad Future'].index(era)]
        original=extract(template,programs[f'R1{act}{letter}'],template_labels(template))
        return (nemesis(original['tiles_raw']),nemesis(original['blocks_raw']),
                original['chunks'],layout(original['foreground']),
                palette(original['sonic_palette']+original['level_palette']))
    path=DATA/'Palmtree Panic/Data'
    return (nemesis((path/f'Tiles (Act {act} {era}).nem').read_bytes()),
            nemesis((path/f'Blocks (Act {act} {era}).nem').read_bytes()),
            (path/f'Chunks (Act {act} {era}).bin').read_bytes(),
            layout((path/f'Foreground (Act {act} {era}).bin').read_bytes()),
            palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes()+(path/f'Palette ({era}).bin').read_bytes()))

@lru_cache(maxsize=256)
def palette_at(era,frame=0):
    colors=bytearray(source(era)[4]);blocks={};key=None
    for raw in (DATA/f'Palmtree Panic/Palette Cycle ({era}).asm').read_text().splitlines():
        line=raw.split(';',1)[0].strip();label=re.match(r'(PalCycle\w+):',line)
        if label:key=label[1];blocks[key]=[]
        values=re.search(r'dc\.[bw]\s+(.+)',line)
        if values and key:blocks[key].extend(int(v.strip().replace('$','0x'),0) for v in values[1].split(','))
    for key,values in blocks.items():
        if 'Script' not in key:continue
        index,count=values[:2];steps=list(zip(values[2::2],values[3::2]));assert len(steps)==count
        steps=steps[1:]+steps[:1];tick=frame%sum(hold+1 for hold,_ in steps)
        for hold,color_index in steps:
            if tick<=hold:
                color=blocks[key.replace('Script','Colors')][color_index]
                colors[index*2:index*2+2]=palette(struct.pack('>H',color));break
            tick-=hold+1
    for key,index,hold in [('PalCycleData1',53,8),('PalCycleData2',44,6)]:
        if key in blocks:
            start=((frame//hold+1)%3)*4
            colors[index*2:(index+4)*2]=palette(struct.pack('>4H',*blocks[key][start:start+4]))
    return bytes(colors)

def foreground_pixel(era,x,y,frame=0,colors_override=None,path=0,act=1):
    art,blocks,chunks,foreground,_=source(era,act)
    colors=palette_at(era,frame) if colors_override is None else colors_override
    if not (0<=x<16384 and 0<=y<2048):return None
    def word(raw,off):return int.from_bytes(raw[off:off+2],'big')
    raw_chunk=foreground[y//256*64+x//256];chunk=raw_chunk&127
    if not chunk:return None
    if raw_chunk&128 and path:
        chunk+=1
        if chunk==41:chunk=81
    block=word(chunks,(chunk-1)*512+(y%256//16)*32+(x%256//16)*2)
    tx,ty=(x//8)&1,(y//8)&1
    if block&0x800:tx^=1
    if block&0x1000:ty^=1
    tile=word(blocks,(block&1023)*8+ty*4+tx*2)^(block&0x1800)
    px,py=x&7,y&7
    if tile&0x800:px=7-px
    if tile&0x1000:py=7-py
    value=art[(tile&2047)*32+py*4+px//2]
    index=(value>>(0 if px&1 else 4))&15
    if not index:return None
    color=word(colors,(((tile>>13)&3)*16+index)*2)
    return bool(tile&0x8000),bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8))

# The HUD (score/time/rings labels and digits) draws over all terrain; the
# original camera can put priority foreground under it (screen y 44-55).
HUD_BOX=(160,56)
def verify_priority_foreground(data,era,camera_x,camera_y):
    checked=0
    for y in range(44,185):
        for x in range(320):
            if x<HUD_BOX[0] and y<HUD_BOX[1]:continue
            pixel=foreground_pixel(era,camera_x+x,camera_y+y)
            if pixel is None or not pixel[0]:continue
            actual=data[(y*330+x+5)*3:(y*330+x+5)*3+3]
            assert actual==pixel[1],('priority foreground',era,camera_x,camera_y,x,y,actual,pixel[1])
            checked+=1
    assert checked>1000,('insufficient source foreground coverage',checked)
    return checked
