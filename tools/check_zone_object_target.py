#!/usr/bin/env python3
"""Check original sprite pixels and actual uploaded VDP1 bytes for a variant."""
import argparse
import ctypes as C
import hashlib,os
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

from convert_assets import ROOT, OUT
from sprite_composition import source_sprite
from test_objects import unpack_texture
from zone_object_assets import source_paths


# The shipped game (V0.065 zone_cycle_cluts) cycles non-priority TT sprite
# pixels, so that is the default expectation; SCD_CLUT_CYCLE=0 selects the
# static stage colours for bins built before the CLUT-cycle fix.
CLUT_CYCLE=os.environ.get('SCD_CLUT_CYCLE','1')!='0'

def r4_cycles(letter):
    """{CRAM entry: allowed RGB555 colours} of the COL4<letter> palette scripts,
    read from the generated call tables in src/background_r4_palette.inc
    (r4_pal_<L>_other, plus r4_pal_A_start for COL4A): each call pairs a
    script (its first byte is the CRAM entry) with a colour table."""
    text=(ROOT/'src/background_r4_palette.inc').read_text()
    arrays={m[1]:[int(v) for v in m[2].split(',')] for m in re.finditer(r'r4_col4(\w+)\[\d+\] = \{([^}]*)\}',text)}
    L=letter.upper();out={}
    for table in [f'r4_pal_{L}_other']+(['r4_pal_A_start'] if L=='A' else []):
        body=re.search(table+r'\[\d+\] = \{(.*?)\};',text)[1]
        for cnt,col in re.findall(r'\{\d+,r4_col4(\w+),r4_col4(\w+)\}',body):
            out.setdefault(arrays[cnt][0]&63,set()).update(c&0x7FFF for c in arrays[col])
    return out


def r5_cycles(letter):
    """{CRAM entry: allowed RGB555 colours} for Quartz Quadrant, read from
    src/background_r5_palette.inc: every COL5<letter> colchgsub script
    (r5_<L>_colchgNN = {adr,tate,yoko,time,colours}; entry adr+i takes
    colours[k*yoko+i]) plus each 16-63 entry that enkeichg's colorset2 changes
    between zone5color0 and zone5color1 (both values). The masks must equal
    zone_cycle_r5 in src/zone_object_view.inc, the slots the game refreshes."""
    text=(ROOT/'src/background_r5_palette.inc').read_text()
    arrays={m[1]:[int(v) for v in m[2].split(',')] for m in re.finditer(r'static const uint16_t (r5_\w+)\[\d+\] = \{([^}]*)\}',text)}
    L=letter.upper();out={}
    for adr,tate,yoko,col in re.findall(rf'static const r5_script r5_{L}_\w+ = \{{(\d+),(\d+),(\d+),\d+,(r5_\w+)\}}',text):
        adr,tate,yoko=int(adr),int(tate),int(yoko)
        for i in range(yoko):out.setdefault(adr+i,set()).update(arrays[col][k*yoko+i]&0x7FFF for k in range(tate))
    z0,z1=arrays[f'r5_{L}_zone0'],arrays[f'r5_{L}_zone1']
    for i in range(48):
        if z0[i]!=z1[i] or 16+i in out:out.setdefault(16+i,set()).update({z0[i]&0x7FFF,z1[i]&0x7FFF})
    view=(ROOT/'src/zone_object_view.inc').read_text()
    masks=[int(v,16) for v in re.findall(r'0x([0-9a-f]+)ull',re.search(r'zone_cycle_r5\[4\]=\{(.*?)\};',view,re.S)[1])]
    assert masks['ABCD'.index(L)]==sum(1<<i for i in out),(L,'zone_cycle_r5 mask',hex(masks['ABCD'.index(L)]),hex(sum(1<<i for i in out)))
    return out


def r7_cycles(letter,act):
    """Allowed COL7 colors from source tables verified against retail MMDs by
    ss_palette_assets.py --check. Only indices selected by each script count;
    Acts 2/3 use COL7D's alternate final script (entry62 instead of58).
    This validates the color set, not the animation timer phase."""
    text=(ROOT/'src/background_r7_palette.inc').read_text()
    arrays={m[1]:[int(v) for v in m[2].split(',')] for m in
            re.finditer(r'static const uint(?:8|16)_t (r7_\w+)\[\d+\] = \{([^}]*)\}',text)}
    out={};L=letter.upper()
    for script,colors,alt in re.findall(rf'\{{(r7_{L}\d+_script),(r7_{L}\d+_colors),(0|r7_{L}_alt_script)\}}',text):
        values=arrays[alt if act>=2 and alt!='0' else script]
        assert len(values)==2+2*values[1]
        out.setdefault(values[0]&63,set()).update(arrays[colors][values[3+2*i]]&0x7fff
                                                for i in range(values[1]))
    return out


def r8_cycles(letter,act):
    """Allowed COL8 colours: src/background_r8_palette.inc r8_pal_sets[era][act],
    each script {entry, steps, (time, colour index) * steps}. They are the
    entries scd_r8_palette_entries gives src/zone_object_view.inc."""
    text=(ROOT/'src/background_r8_palette.inc').read_text()
    arrays={m[1]:[int(v) for v in m[2].split(',')] for m in
            re.finditer(r'static const uint(?:8|16)_t (r8_\w+)\[\d+\] = \{([^}]*)\}',text)}
    sets=re.findall(r'\{(\d+),\{((?:\{r8_\w+_script,r8_\w+_colors\},?)+)\}\}',re.search(r'r8_pal_sets\[4\]\[3\] = \{(.*)\};',text)[1])
    assert len(sets)==12 and all(int(n)==len(re.findall('script',s)) for n,s in sets)
    out={}
    for script,colors in re.findall(r'\{(r8_\w+_script),(r8_\w+_colors)\}',sets['ABCD'.index(letter.upper())*3+min(act,3)-1][1]):
        values=arrays[script];assert len(values)==2+2*values[1]
        out.setdefault(values[0]&63,set()).update(arrays[colors][values[3+2*i]]&0x7fff for i in range(values[1]))
    return out


def cycles(rnd,letter,act=1):
    return r4_cycles(letter) if rnd==4 else r5_cycles(letter) if rnd==5 else r7_cycles(letter,act) if rnd==7 else r8_cycles(letter,act) if rnd==8 else {}


def retain_palette_latency(candidates, actual, expected):
    """Intersect across the entire capture, never choose a palette per pixel."""
    candidates.intersection_update(lag for lag,value in expected.items() if actual==value)
    assert candidates, 'no consistent indexed CRAM capture latency'


def check(name, folder):
    rnd,act,era=int(name[1]),int(name[2]),'ABCD'.index(name[3])
    # R83C/D fight (era entry A) and Amy (B) banks.
    fight='-boss' if name.endswith('-fight') else '-boss-ending' if name.endswith('-ending') else None
    if fight:era=0 if fight=='-boss' else 1
    pack=(OUT/f'zone-art-{rnd}{act}.bin').read_bytes()
    at=struct.unpack_from('>I',pack,4+era*4)[0]
    if pack[:4]==b'ZAR5':
        from zone_object_assets import zar5_era
        count,records_at,raw_size,packed_size,packed_at,zar5_raw=zar5_era(pack,at,unpack_texture)
    elif pack[:4] in (b'ZAR2',b'ZAR4'):
        count=struct.unpack_from('>I',pack,at)[0]
        raw_size,packed_size,packed_at=struct.unpack_from('>III',pack,20)
        records_at=at+4
    else:
        count,raw_size,packed_size=struct.unpack_from('>III',pack,at)
        records_at=at+12;packed_at=records_at+48*count
    rows=[struct.unpack_from('>HHIHHhh16H',pack,records_at+i*48) for i in range(count)]
    # ZAR3 (Tidal Tempest, Quartz Quadrant) and ZAR4 (Metallic Madness) packs use the word-LZ codec.
    if pack[:4] in (b'ZAR3',b'ZAR4'):
        import zone_art_lz
        raw=bytearray(zone_art_lz.bank_raw(pack,era) if fight else zone_art_lz.unpack(pack[packed_at:packed_at+packed_size],raw_size//2))
    elif pack[:4]==b'ZAR5':raw=bytearray(zar5_raw)
    else:raw=bytearray(unpack_texture(pack[packed_at:packed_at+packed_size]))
    prefix={3:'cc',4:'tt',5:'qq',6:'ww',7:'ss',8:'mm'}[rnd]
    stage=(OUT/f'{prefix}{rnd}{act}{name[3]}.bin').read_bytes()
    pal_at,pal_size=struct.unpack_from('>II',stage,44);assert pal_size==128
    palette=struct.unpack_from('>64H',stage,pal_at)
    def set_cluts(raw,rows):
        for kind,frame,packed_offset,w,h,left,top,*refs in rows:
            offset=packed_offset&65535;clut=packed_offset>>16 or offset+w*h//2
            # Tidal Tempest (water raster on): stage refs are CRAM alias codes 0x80+ref.
            struct.pack_into('>16H',raw,clut,0,*[0x4080+(c&63) if c&128 else 0x0080+c if rnd==4 else palette[c] for c in refs[1:]])
    if fight=='-boss-ending':
        # The Amy bank streams over the fight bank as the Saturn left it (its
        # records' CLUTs already written), keeping the words it does not replace.
        f_at=struct.unpack_from('>I',pack,4)[0];f_count=struct.unpack_from('>I',pack,f_at)[0]
        base=bytearray(zone_art_lz.bank_raw(pack,0))
        set_cluts(base,[struct.unpack_from('>HHIHHhh16H',pack,f_at+12+i*48) for i in range(f_count)])
        raw=bytearray(zone_art_lz.unpack(pack[packed_at:packed_at+packed_size],raw_size//2,bytes(base)))
    set_cluts(raw,rows)
    vdp1=(folder/'zone-art-vdp1.bin').read_bytes()
    assert len(vdp1)==0x80000
    if rnd in (5,8) and CLUT_CYCLE:
        # src/zone_object_view.inc zone_cycle_cluts refreshes the non-priority CLUT
        # slots of COL4/COL5-cycled entries: at the dump each holds a colour of that
        # entry's cycle (or the stage value); every other byte must be exact.
        cyc=cycles(rnd,name[3].lower(),act)
        for kind,frame,packed_offset,w,h,left,top,*refs in rows:
            clut=packed_offset>>16 or (packed_offset&65535)+w*h//2
            for c,ref in enumerate(refs[1:],1):
                if ref and not ref&128 and ref in cyc:
                    v=struct.unpack_from('>H',vdp1,0x71000+clut+c*2)[0]
                    assert v&0x7FFF in cyc[ref]|{palette[ref]&0x7FFF},(name,'cycled CLUT slot',hex(clut+c*2),ref,hex(v))
                    struct.pack_into('>H',raw,clut+c*2,v)
    assert vdp1[0x71000:0x71000+raw_size]==raw,(name,'uploaded VDP1 bytes')
    sources=[];objects={}
    for path in ([] if fight else source_paths(name)):
        source=json.loads((path/'source.json').read_text());vram=(path/'vram.bin').read_bytes()
        sources.append(source)
        objects.update({o['kind']:(o,vram) for o in source['objects']})
    if fight:
        from zone_object_assets import fight_objects
        for kind,o,vram,source in fight_objects(name[:4],fight):
            if source not in sources:sources.append(source)
            objects[kind]=(o,vram)
    log=(folder/'results.log').read_text()
    records={int(case):list(map(int,words.split())) for case,words in re.findall(r'^Zone art sprite: (\d+) ([\d ]+)$',log,re.M)}
    assert set(records)==set(range(count*4)),(name,'missing rendered poses')
    aliases=re.findall(r'^Zone priority palette: (\d+) matched=64$',log,re.M)
    assert list(map(int,aliases))==list(range(count*4)),(name,'missing live high-priority palette checks')
    checked=0;captures={}
    # Current and preceding-video CRAM observations, used ONLY for the
    # entries the Tidal Tempest COL4A-D (Quartz Quadrant COL5A-D) scripts cycle (the water, e.g. 49-52
    # for funsui4), each value checked against that script's colour set.
    # Every other entry comes from the stage file, so a wrong CRAM load can
    # not pass by comparing the capture with itself.
    cram={int(c):[int(w,16) for w in words.split()] for c,words in re.findall(r'^Zone cram: (\d+) ([0-9a-f ]+)$',log,re.M)}
    sprite_cram={int(c):[int(w,16) for w in words.split()] for c,words in re.findall(r'^Zone sprite cram: (\d+) ([0-9a-f ]+)$',log,re.M)}
    cycled=cycles(rnd,name[3].lower(),act)
    def live(case, sprite=False):
        pal=list(palette)
        if not cycled:return pal
        samples=sprite_cram if sprite else cram
        assert case in samples and len(samples[case])==64,(name,case,'missing sprite/live CRAM capture',sprite)
        for i,allowed in cycled.items():
            # A script that has not fired (or is gated off) leaves the stage value.
            v=samples[case][i]&0x7FFF;allowed=allowed|{palette[i]&0x7FFF}
            assert v in allowed,(name,case,i,hex(v),'not in the source palette cycle',sorted(map(hex,allowed)))
            pal[i]=v|(pal[i]&0x8000)
        return pal
    import zone_object_assets as Z
    def pose_index(obj,frame):return obj['frame_ids'].index(frame) if obj.get('frame_ids') else frame
    indexed_latency={0,1}
    for ordinal,(kind,frame,packed_offset,w,h,left,top,*_) in enumerate(rows):
        offset=packed_offset&65535
        if kind not in objects and rnd==4:
            # tools/zone_object_source.py R4_ALIASES: a view subtype packed from
            # another capture (zone_object_assets.packed_objects).
            from zone_object_source import R4_ALIASES
            ck,cs=R4_ALIASES[(kind&255,kind>>8)]
            obj,vram=objects[ck|cs<<8] if ck|cs<<8 in objects else objects[ck]
        else:obj,vram=objects[kind]
        if Z.per_piece(rnd,obj):
            # One record per mapping piece. The probe finds the pose, so every
            # piece record draws the whole pose (first piece at the back) and
            # reports the first piece's command; check this piece's box.
            first=ordinal
            while first and rows[first-1][:2]==(kind,frame):first-=1
            parts=list(Z.source_parts(obj,vram,rnd))[pose_index(obj,frame)]
            for flags in range(4):
                case=ordinal*4+flags;record=records[case];pal=live(case);sprite_pal=live(case,True) if CLUT_CYCLE else palette
                original=[0]*(w*h)
                for pl,pt,pw,ph,px in parts:
                    for y in range(ph):
                        for x in range(pw):
                            v=px[y*pw+x];bx,by=pl+x-left,pt+y-top
                            # Priority pixels (bit 7) read live CRAM through the
                            # 128+ alias. Normal RGB pixels retain the preceding
                            # VDP1 draw's CLUT colors. Both samples must belong
                            # to the original script's allowed colors.
                            if v and 0<=bx<w and 0<=by<h:original[by*w+bx]=(pal if v&128 else sprite_pal)[(v-1)&63]|0x8000
                fk,ff,fo,fw,fh,fl,ft,*_=rows[first]
                gx=160+(-fl-fw if flags&1 else fl);gy=112+(-ft-fh if flags&2 else ft)
                assert record==[kind,frame,gx&0xffffffff,gy&0xffffffff,flags,fw<<16|fh,0x71000+(fo&65535),2],(name,case,'command geometry',record)
                ox=160+(-left-w if flags&1 else left);oy=112+(-top-h if flags&2 else top)
                path=folder/f'zone-art-{case:03d}.ppm';image=path.read_bytes()
                header,rgb=image.split(b'255\n',1);assert header==b'P6\n330 224\n'
                for y in range(h):
                    for x in range(w):
                        sx=w-1-x if flags&1 else x;sy=h-1-y if flags&2 else y
                        color=original[sy*w+sx]
                        if not color:continue
                        px,py=ox+x+5,oy+y
                        if not 5<=px<325 or not 0<=py<224:continue
                        expected=bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8))
                        actual=rgb[(py*330+px)*3:(py*330+px)*3+3]
                        assert actual==expected,(name,case,x,y,actual.hex(),expected.hex())
                        checked+=1
                captures[path.name]=hashlib.sha256(image).hexdigest()
            continue
        mapping=bytearray.fromhex(obj['frames'][pose_index(obj,frame)]);banks=set();prios=set()
        for piece in range(mapping[0]):
            pos=1+piece*5;word=(struct.unpack_from('>H',mapping,pos+2)[0]+obj['tile'])&65535
            struct.pack_into('>H',mapping,pos+2,word);banks.add((word>>13)&3);prios.add(word>>15)
            x=struct.unpack_from('>b',mapping,pos+4)[0]-left-w//2;struct.pack_into('>b',mapping,pos+4,x)
        assert len(banks)==(1 if mapping[0] else 0)
        bank=banks.pop() if banks else 0
        for flags in range(4):
            case=ordinal*4+flags;record=records[case]
            # Live (cycled) CRAM only reaches high-priority pieces (CRAM alias).
            # Indexed priority pixels read current CRAM at display. Normal
            # RGB pixels retain the palette from the preceding VDP1 draw.
            # R7's COL7 cycles reach indexed priority pixels only. Its RGB
            # bank2/3 CLUTs retain stage colors (zone_cycle_cluts is R4/R5).
            colors=struct.pack('>16H',*(live(case) if prios=={1} else live(case,True) if CLUT_CYCLE and rnd!=7 else palette)[bank*16:bank*16+16])
            original=struct.unpack('>'+str(w*h)+'H',source_sprite(mapping,vram,colors,w,-top-32,h))
            alternatives=None
            if rnd==7 and prios=={1}:
                # screenshot() copies the most recent video() image. The log's
                # Zone cram is read after retro_run; Zone sprite cram was saved
                # at the preceding video() callback. Palette DMA may lie between
                # those observations and scanout. Require ONE choice for every
                # indexed pixel in every pose/flip, not a choice per observation.
                alternatives={lag:struct.unpack('>'+str(w*h)+'H',source_sprite(mapping,vram,
                    struct.pack('>16H',*live(case,bool(lag))[bank*16:bank*16+16]),w,-top-32,h))
                    for lag in (0,1)}
            ox=160+(-left-w if flags&1 else left);oy=112+(-top-h if flags&2 else top)
            # ZAR3/ZAR4 kinds are type|subtype<<8 (src/zone_object_view.inc probe).
            native_kind,sub=(kind&255,kind>>8) if pack[:4] in (b'ZAR3',b'ZAR4') else (68,128) if kind==168 else (kind-100,255) if kind in (178,179,180,183,184) else (89,1) if kind==189 else (kind-200,1) if kind in (278,279) else (93,254) if kind==293 else (93,1) if kind==193 else (kind,0)
            assert record==[native_kind|sub<<8,frame,ox&0xffffffff,oy&0xffffffff,flags,w<<16|h,0x71000+offset,2],(name,case,'command geometry',record)
            path=folder/f'zone-art-{case:03d}.ppm';image=path.read_bytes()
            header,rgb=image.split(b'255\n',1);assert header==b'P6\n330 224\n'
            for y in range(h):
                for x in range(w):
                    sx=w-1-x if flags&1 else x;sy=h-1-y if flags&2 else y
                    color=original[sy*w+sx]
                    if not color:continue
                    px,py=ox+x+5,oy+y
                    if not 5<=px<325 or not 0<=py<224:continue
                    expected=bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8))
                    actual=rgb[(py*330+px)*3:(py*330+px)*3+3]
                    if alternatives is not None:
                        choices={lag:bytes(((pixels[sy*w+sx]&31)*8,((pixels[sy*w+sx]>>5)&31)*8,
                                           ((pixels[sy*w+sx]>>10)&31)*8)) for lag,pixels in alternatives.items()}
                        retain_palette_latency(indexed_latency,actual,choices)
                    else:
                        assert actual==expected,(name,case,x,y,actual.hex(),expected.hex())
                    checked+=1
            captures[path.name]=hashlib.sha256(image).hexdigest()
    assert re.search(rf'Zone art passed: .* frames={count} captures={count*4} updates=\d+',log)
    report=dict(passed=True,program=name,frames=count,captures=count*4,source_pixels=checked,
                palette_sampling='Fixed preceding-video sample for VDP1 RGB; current CRAM for indexed priority pixels',
                vdp1_bytes=raw_size,priority_palette_colors=count*4*64,source_capture_sha256=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest(),
                capture_sha256=captures,disc_sha256=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest())
    if rnd==7:
        report['indexed_cram_latency']=sorted(indexed_latency)
        report['palette_sampling']='One whole-capture indexed CRAM sample: 0=post-retro_run, 1=preceding video callback; source cycle colors checked; animation phase tested separately'
    if rnd==3 and act==1:
        # Actual VDP2 CRAM, not the CPU's palette buffer. At the observation
        # boundary DMA may show the preceding simulation frame; require one
        # consistent latency across every capture, never a per-color choice.
        letter='ABCD'[era];ref_path=ROOT/f'build/cc1/palette/original-{letter}.dylib'
        if not ref_path.exists():subprocess.run([sys.executable,str(ROOT/'tools/test_cc_palette.py')],check=True)
        reference=C.CDLL(str(ref_path));reference.init()
        source_pal=json.loads((ROOT/'build/cc1/palette-source.json').read_text())
        indices=[c['index'] for c in source_pal[letter]['cycles']]
        observations=re.findall(r'^Zone palette: (\d+) (\d+) ([0-9a-f ]+)$',log,re.M)
        assert len(observations)==count*4,(name,'missing CRAM captures')
        assert [int(c) for c,_,_ in observations]==list(range(count*4))
        colors=(C.c_uint16*64)();frames={}
        for frame in range(max(int(f) for _,f,_ in observations)+1):
            if frame:reference.clchgctr()
            reference.read_colors(colors)
            expected=list(palette)
            if frame:
                for i in indices:expected[i]=colors[i]
            frames[frame]=expected
        latency={0,1}
        for case,frame,words in observations:
            actual=[int(w,16) for w in words.split()];frame=int(frame)
            assert len(actual)==64
            latency={lag for lag in latency if frame>=lag and actual==frames[frame-lag]}
            assert latency,(name,case,frame,'CRAM differs from original palette routine')
        report['palette']=dict(captures=len(observations),colors=len(observations)*64,
                               consistent_dma_latency=sorted(latency),
                               limits='Original cycle values at the native simulation phase; full original scene/entry phase comparison remains separate.')
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{name}: {count*4} target pictures / {checked} original sprite pixels / {raw_size} VDP1 bytes match')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('program');parser.add_argument('--folder',type=Path)
    args=parser.parse_args();check(args.program,args.folder or ROOT/'build/zone-art-qa'/args.program)
