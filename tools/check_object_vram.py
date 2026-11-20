"""Verify the actual VDP1 object arena in the Past monitor fixture."""
import hashlib,re,struct
from convert_assets import OUT
from test_objects import unpack_texture

def expected_arena(stage_name='ppz1.bin',palette=None):
    """Object arena bytes the build must upload at VDP1 0x1AAC0 for one
    Palmtree Panic program: object-art.bin, high-priority CLUTs on the shared
    0x4050 colour block, stage-palette banks from stage_name's palette (or
    palette, 64 RGB555 words). Returns (bytes, frame layout rows)."""
    text=(OUT/'object-frames.inc').read_text()
    def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
    offsets,widths,heights,banks,high=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_stage_palette','object_high_priority']]
    indices=[list(map(int,row.split(','))) for row in re.findall(r'\{([\d,]+)\}',text.split('object_clut_indices[][16]=',1)[1].split(';',1)[0])]
    expected=bytearray(unpack_texture((OUT/'object-art.bin').read_bytes()))
    colors=[];converted=set()
    for off,w,h,priority,bank in zip(offsets,widths,heights,high,banks):
        assert off%32==0 and (off+w*h//2)%32==0
        if not priority or off in converted:continue
        assert bank==0;converted.add(off)
        for c in range(1,16):
            pos=off+w*h//2+c*2;value=struct.unpack_from('>H',expected,pos)[0]
            if not value:continue
            if value not in colors:colors.append(value)
            struct.pack_into('>H',expected,pos,0x4050+colors.index(value))
    assert len(colors)<=16
    if palette is None:
        stage=(OUT/stage_name).read_bytes();at,size=struct.unpack_from('>II',stage,4+5*8)
        assert size==128;palette=struct.unpack_from('>64H',stage,at)
    for f,(off,w,h,bank) in enumerate(zip(offsets,widths,heights,banks)):
        if bank:
            struct.pack_into('>16H',expected,off+w*h//2,0,*[palette[16*bank+indices[f][c]] for c in range(1,16)])
    return expected,list(zip(offsets,widths,heights,banks))

def verify(path):
    expected,layout=expected_arena()
    actual=path.read_bytes();assert len(actual)==0x80000
    arena=actual[0x1AAC0:0x1AAC0+len(expected)]
    if arena!=expected:
        first=next(i for i,(a,b) in enumerate(zip(arena,expected)) if a!=b)
        raise AssertionError(('VDP1 object readback',hex(0x1AAC0+first),arena[first],expected[first]))
    return {'bytes':len(expected),'frames':len(layout),'sha256':hashlib.sha256(arena).hexdigest(),'palette_alignment':32,'fixture':'Act 1 Past before first monitor break'}
