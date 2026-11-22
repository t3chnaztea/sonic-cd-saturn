"""Measure terrain/sprite presentation coherence from consecutive target pictures.

Static spring anchors come from original PPZ1 placement records, not the target's
screen-coordinate mailbox. Sprite texels come directly from original mappings,
art and palettes. This does not certify the provisional Sonic animation.
"""
from functools import lru_cache
import re, struct
from convert_assets import DATA, assembly_frames, nemesis, palette
from terrain_pixels import foreground_pixel, verify_priority_foreground
from hud_pixels import expected as hud_expected

# These two anchors intersect only the RINGS label, not the changing time
# digits. Its source opacity mask is independent of its red/yellow flash;
# occluded texels cannot establish sprite position and are not counted.
HUD_LABEL={p:c for p,c in hud_expected(0,0,0,3,0).items() if p[0]<61 and 40<=p[1]<56}


@lru_cache(maxsize=32)
def spring_pixels(subtype, flags, frame):
    path=DATA/'_Objects/Spring/Data'
    pose=(3 if subtype&4 else 6 if subtype&8 else 0)+frame
    mapping=assembly_frames(path/'Mappings.asm')[pose]
    art=nemesis((path/('Art (Diagonal).nem' if pose>=6 else 'Art (Normal).nem')).read_bytes())
    pal=(DATA/'Palmtree Panic/Data/Palette (Present).bin' if subtype&2 else DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes()[:32]
    colors=struct.unpack('>16H',palette(pal))
    pixels={}
    for piece in range(mapping[0]):
        y,size,tile,x=struct.unpack_from('>bBHb',mapping,1+5*piece)
        width=8*((size>>2)+1);height=8*((size&3)+1)
        for py in range(height):
            for px in range(width):
                sx=width-1-px if tile&0x800 else px
                sy=height-1-py if tile&0x1000 else py
                cell=(tile&0x7ff)+(sx//8)*(height//8)+sy//8
                packed=art[cell*32+(sy%8)*4+sx%8//2]
                index=(packed>>(0 if sx&1 else 4))&15
                if not index:continue
                dx,dy=x+px,y+py
                if flags&1:dx=-1-dx
                if flags&2:dy=-1-dy
                color=colors[index]
                pixels.setdefault((dx,dy),bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8)))
    return pixels


def springs():
    result=[]
    for x,y,kind,subtype,eras,secondary in struct.iter_unpack('>HHBBBB',(DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes()):
        if x==65535:break
        if kind&127==10 and eras&0x40:
            assert not secondary
            result.append((x,y&4095,subtype,y>>14))
    return result


def samples(log,route):
    pattern=rf'Camera sample: route={route} tick=(\d+) simulation=(\d+) world=(-?\d+),(-?\d+) screen=(-?\d+),(-?\d+) flags=(\d+)'
    result={}
    for row in re.findall(pattern,log):
        tick,simulation,wx,wy,sx,sy,flags=map(int,row)
        assert tick not in result
        result[tick]={'camera':(wx-sx,wy-sy),'simulation':simulation,'world':(wx,wy),'screen':(sx,sy),'flags':flags}
    return result


def identify_terrain(data,candidates):
    matches={}
    for camera in set(candidates):
        try:matches[camera]=verify_priority_foreground(data,'Present',*camera)
        except AssertionError:pass
    assert len(matches)==1,('terrain camera is not uniquely identified',matches,candidates)
    camera,count=next(iter(matches.items()))
    return camera,count


def anchor_match(data,anchor,camera,terrain_camera,pose):
    wx,wy,subtype,flags=anchor
    checked=0
    for (dx,dy),color in spring_pixels(subtype,flags,pose).items():
        x,y=wx-camera[0]+dx,wy-camera[1]+dy
        if not(0<=x<320 and 44<=y<224):continue
        foreground=foreground_pixel('Present',terrain_camera[0]+x,terrain_camera[1]+y)
        if foreground and foreground[0]:continue
        hud=HUD_LABEL.get((x+5,y))
        if hud is not None:continue
        if data[(y*330+x+5)*3:(y*330+x+5)*3+3]!=color:return 0
        checked+=1
    return checked


def analyze(folder):
    log=(folder/'results.log').read_text();records=samples(log,1)
    result=[]
    captures=sorted(folder.glob('camera-1-tick-*.ppm'),key=lambda p:int(p.stem.rsplit('-',1)[1]))
    assert len(captures)==16,('expected consecutive vertical camera captures',len(captures))
    for path in captures:
        tick=int(path.stem.rsplit('-',1)[1]);raw=path.read_bytes()
        header,data=raw.split(b'255\n',1);assert header==b'P6\n330 224\n' and len(data)==330*224*3
        history=[records[tick-lag]['camera'] for lag in range(min(4,tick+1))]
        terrain,count=identify_terrain(data,history)
        matches=[]
        for anchor in springs():
            # Only anchors close enough to occur in any candidate viewport.
            if not any(-32<=anchor[0]-c[0]<352 and 12<=anchor[1]-c[1]<256 for c in history):continue
            options={}
            for camera in set(history):
                for pose in range(3):
                    pixels=anchor_match(data,anchor,camera,terrain,pose)
                    if pixels>=40:options.setdefault(camera,[]).append((pose,pixels))
            if options:matches.append({'anchor':anchor,'cameras':[(c,p) for c,p in sorted(options.items())]})
        # The fixture has only Sonic, two springs, an invisible tag and HUD.
        # Check the exposed bottom foreground independently to catch incomplete
        # framebuffer clearing, not just correct opaque sprite locations.
        # A spring identified above (source pixels at one camera and pose) may
        # reach this band: the original camera frames the fixture's second
        # spring at the bottom right. Its opaque pixels are not background.
        covered=set()
        for m in matches:
            if len(m['cameras'])!=1:continue
            (cx,cy),poses=m['cameras'][0];wx,wy,subtype,flags=m['anchor']
            for pose,_ in poses:
                for (dx,dy) in spring_pixels(subtype,flags,pose):covered.add((wx-cx+dx,wy-cy+dy))
        clear_pixels=0
        for y in range(196,224):
            for x in range(64,304):
                if (x,y) in covered:continue
                pixel=foreground_pixel('Present',terrain[0]+x,terrain[1]+y)
                if pixel is None:continue
                actual=data[(y*330+x+5)*3:(y*330+x+5)*3+3]
                assert actual==pixel[1],('stale framebuffer pixel',tick,x,y,actual,pixel[1])
                clear_pixels+=1
        assert clear_pixels>=1000,('insufficient framebuffer-clear coverage',tick,clear_pixels)
        result.append({'tick':tick,'history':history,'terrain_camera':terrain,'terrain_pixels':count,
                       'clear_pixels':clear_pixels,'sprites':matches})
    return result


def verify_coherence(rows):
    assert len(rows)==16
    assert [r['tick'] for r in rows]==list(range(rows[0]['tick'],rows[0]['tick']+16))
    moving=0;pixels=0
    for row in rows:
        camera=tuple(row['terrain_camera'])
        assert row['terrain_pixels']>=1000
        assert row['sprites'],('no independently identified sprite anchor',row['tick'])
        if len({tuple(c) for c in row['history']})>1:moving+=1
        for sprite in row['sprites']:
            options=sprite['cameras']
            assert len(options)==1,('ambiguous sprite camera',row['tick'],sprite)
            assert tuple(options[0][0])==camera,('sprite/terrain camera drift',row['tick'],camera,sprite)
            pixels+=max(n for _,n in options[0][1])
    assert moving>=5,('insufficient moving camera coverage',moving)
    assert pixels>=2000,('insufficient sprite pixel coverage',pixels)
    return {'captures':len(rows),'moving_captures':moving,'sprite_pixels':pixels,
            'terrain_pixels':sum(r['terrain_pixels'] for r in rows),
            'clear_pixels':sum(r.get('clear_pixels',0) for r in rows)}


def inspect_draw_mode(path):
    from vdp2_title_cycles import state_sections
    vdp=state_sections(path.read_bytes())['VDP1']
    result={name:int.from_bytes(vdp[name],'little') for name in ['PTMR','VDP1_FBCR','VDP1_TVMR']}
    assert result['PTMR']==1,('sprite drawing is not explicitly triggered',result)
    assert result['VDP1_FBCR']&3==3,('completed manual buffer swap required',result)
    # VBE may be armed at this VBlank boundary; its partial erase is only a
    # supplement. Full clearing is independently checked in the pictures.
    assert result['VDP1_TVMR']&~8==0,('normal 16-bit framebuffer required',result)
    return result


if __name__=='__main__':
    import json,sys
    from pathlib import Path
    print(json.dumps(analyze(Path(sys.argv[1])),indent=2))
