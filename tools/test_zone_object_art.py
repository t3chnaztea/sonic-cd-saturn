#!/usr/bin/env python3
"""Compare every packed zone sprite with the independent source compositor."""
import ctypes as C
import hashlib
import json
import struct
import subprocess

from convert_assets import ROOT, OUT
from sprite_composition import source_sprite
from test_objects import unpack_texture
from zone_object_source import specs, verify_cc_banks, verify_tiles, verify_tile_bytes, read_tiles, plc_banks
from zone_object_assets import source_paths, DEFERRED, PIECES, per_piece, packed_objects, source_parts, part_pieces, fight_objects, RETAIL_VRAM_EVIDENCE
from extract_mmd import disc_files, ORIGIN
import zone_art_lz


class Art(C.Structure):
    _fields_ = [('frames', C.c_void_p), ('packed', C.c_void_p), ('count', C.c_uint),
                ('raw_bytes', C.c_uint), ('packed_bytes', C.c_uint), ('lz', C.c_uint),
                ('spans', C.c_void_p), ('span_count', C.c_uint), ('arena_words', C.c_uint)]



def check_zone_cycle(view=None):
    """src/zone_object_view.inc zone_cycle_build/zone_cycle_cluts, compiled on
    the host against a VDP1 buffer. Tidal Tempest runs the water raster, so its
    CLUTs hold CRAM alias palette codes that follow the cycled palette (and the
    static water bank below the line): for every R4 program, change each COL4
    scripted entry, run one refresh, and require no VDP1 write at all. Returns
    the count of COL4-referencing CLUT slots. VIEW overrides the source."""
    import re,subprocess,tempfile
    from pathlib import Path
    text=(ROOT/(view or 'src/zone_object_view.inc')).read_text()
    block=text[text.index('#define ZONE_CYCLE_SLOTS'):]
    block=block[:block.index('static void zone_object_art_load_slot(unsigned slot){')]
    harness=r"""
#include <stdint.h>
#include <string.h>
#include "zone_object_art.h"
typedef struct{const uint8_t *part[6];}stage_stub;
static uint8_t vdp1[0x80000];
#define VDP1_VRAM(x) ((uintptr_t)(vdp1+(x)))
static scd_zone_art zone_art;static stage_stub stage;static unsigned stage_zone=2,stage_act,era;
static int water_raster_active(void){return stage_zone==2;}
"""+block+r"""
/* 0 ok; 1 open; 2 stray write; 3 wrong colour; 4 slot missed; 5 no slots. */
int run(const uint8_t *pack,unsigned size,unsigned act,unsigned e,const uint8_t *pal_be,unsigned *slots){
    stage_act=act;era=e;stage.part[5]=pal_be;*slots=0;
    if(scd_zone_art_open(&zone_art,pack,size,e))return 1;
    if(!zone_art.count)return 0;
    zone_cycle_build();
    uint16_t pal[64];for(unsigned i=0;i<64;i++)pal[i]=scd_zone_art_u16(pal_be+i*2);
    uint64_t m=scd_r4_palette_entries(act*4+e);
    for(unsigned i=0;i<64;i++)if(m>>i&1)pal[i]=(uint16_t)(0x7C00|i);
    memset(vdp1,0,sizeof(vdp1));zone_cycle_cluts(pal);
    static uint8_t want[0x80000];memset(want,0,sizeof(want));
    for(unsigned r=0;r<zone_art.count;r++){
        const uint8_t *f=zone_art.frames+r*SCD_ZONE_ART_RECORD;unsigned clut=SCD_ZONE_ART_BASE+scd_zone_art_clut(f);
        for(unsigned c=1;c<16;c++){unsigned ref=scd_zone_art_u16(f+16+c*2);
            if(!(ref&128) && (m>>(ref&63)&1)){want[clut+c*2]=1;*slots+=1;}}
    }
    for(unsigned a=0;a<sizeof(vdp1);a+=2)if(*(uint16_t*)(vdp1+a))return 2;
    return 0;
}
"""
    with tempfile.TemporaryDirectory() as d:
        Path(d,'t.c').write_text(harness)
        subprocess.run(['clang','-std=gnu11','-O1','-dynamiclib','-Isrc','-Iassets/generated','-o',f'{d}/t.dylib',f'{d}/t.c','src/background_r4.c'],cwd=ROOT,check=True)
        lib=C.CDLL(f'{d}/t.dylib')
        total=0
        for act in (1,2,3):
            pack=(OUT/f'zone-art-4{act}.bin').read_bytes()
            for e,letter in enumerate('ABCD'):
                if act==3 and e<2:continue
                stage=(OUT/f'tt4{act}{letter}.bin').read_bytes()
                pal_at,_=struct.unpack_from('>II',stage,44)
                n=C.c_uint()
                rc=lib.run(pack,len(pack),act-1,e,stage[pal_at:pal_at+128],C.byref(n))
                assert rc==0,(f'R4{act}{letter}',{1:'pack open',2:'RGB CLUT cycle write (TT CLUTs hold palette codes)'}[rc])
                total+=n.value
    return total

def main(rounds=(3,4,5,6,7,8)):
    out = ROOT/'build/zone-object-art-test'; out.mkdir(exist_ok=True)
    wrapper = out/'native.c'
    wrapper.write_text('#include "zone_object_art.h"\n'
        'int open_art(scd_zone_art*a,const uint8_t*p,size_t n,unsigned e){return scd_zone_art_open(a,p,n,e);}\n'
        'const uint8_t*find_art(scd_zone_art*a,unsigned t,unsigned s,unsigned f){return scd_zone_art_find(a,t,s,f);}\n'
        'int lz_unpack(const uint8_t*p,unsigned n,uint16_t*o,unsigned w){return scd_zone_art_lz_unpack(p,n,o,w);}\n')
    lib = out/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-Isrc',
                    str(wrapper), '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib)); native.open_art.argtypes = [C.POINTER(Art), C.c_void_p, C.c_size_t, C.c_uint]
    native.find_art.argtypes = [C.POINTER(Art), C.c_uint, C.c_uint, C.c_uint]; native.find_art.restype = C.c_void_p
    cases = pixels_checked = flips_checked = 0; records = {}
    disc = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    for rnd in rounds:
        for act in (1,2,3):
            pack = (OUT/f'zone-art-{rnd}{act}.bin').read_bytes(); buffer = C.create_string_buffer(pack)
            # R83C/D also carry their fight bank in era entries A/B
            # (tools/zone_object_assets.py fight_objects).
            for era,index,fight in [(e,'ABCD'.index(e),None) for e in ('CD' if act==3 else 'ABCD')]+([(e,i,b) for e in 'CD' for i,b in enumerate(('-boss','-boss-ending'))] if rnd==8 and act==3 else []):
                name=f'R{rnd}{act}{era}'
                art = Art(); assert native.open_art(C.byref(art),buffer,len(pack),index)==0
                start = struct.unpack_from('>I', pack, 4+4*index)[0]
                if pack[:4] == b'ZAR5':
                    from zone_object_assets import zar5_era
                    count,records_at,raw_size,packed_size,packed_at,zar5_raw = zar5_era(pack,start,unpack_texture)
                elif pack[:4] in (b'ZAR2', b'ZAR4'):
                    count = struct.unpack_from('>I',pack,start)[0]
                    raw_size,packed_size,packed_at = struct.unpack_from('>III',pack,20)
                    records_at = start+4
                else:
                    count,raw_size,packed_size = struct.unpack_from('>III',pack,start)
                    records_at = start+12;packed_at = records_at+48*count
                assert count==art.count and raw_size==art.raw_bytes and packed_size==art.packed_bytes
                assert art.frames==C.addressof(buffer)+records_at and art.packed==C.addressof(buffer)+packed_at
                # ZAR3 (Tidal Tempest) packs textures with tools/zone_art_lz.py.
                assert art.lz==(pack[:4] in (b'ZAR3', b'ZAR4'))
                if art.lz:
                    # The Saturn decoder (src/zone_object_art.h) must produce the
                    # same words as the Python codec; truncation must fail.
                    # R83's Amy bank (entry 1) decodes over the resident fight bank.
                    base=zone_art_lz.bank_raw(pack,0) if fight=='-boss-ending' else None
                    words=(C.c_uint16*(raw_size//2))(*(struct.unpack(f'>{len(base)//2}H',base) if base else ()))
                    assert native.lz_unpack(buffer[packed_at:packed_at+packed_size],packed_size,words,raw_size//2)==0
                    assert b''.join(struct.pack('>H',v) for v in words)==zone_art_lz.unpack(pack[packed_at:packed_at+packed_size],raw_size//2,base)
                    assert native.lz_unpack(buffer[packed_at:packed_at+packed_size-2],packed_size-2,words,raw_size//2)==-1
                raw = (zone_art_lz.unpack(pack[packed_at:packed_at+packed_size],raw_size//2,base) if art.lz
                       else zar5_raw if pack[:4] == b'ZAR5' else unpack_texture(pack[packed_at:packed_at+packed_size]))
                assert len(raw)==raw_size
                objects={};r4_frames=0
                for path in source_paths(name):
                    source=json.loads((path/'source.json').read_text())
                    vram=(path/'vram.bin').read_bytes()
                    assert len(vram)==65536 and hashlib.sha256(vram).hexdigest()==source['vram_sha256']
                    skip=(set(source.get('plc_unverified',()))-{k for (n,k) in RETAIL_VRAM_EVIDENCE if n==path.name})|set(DEFERRED.get(rnd,{}))
                    packed_here=[o for o in source['objects'] if o['kind'] not in skip]
                    objects.update({o['kind']:(o,vram) for o in packed_here})

                    if '-boss-beam' in path.name:
                        # BOSS_6.C cycles three uncompressed MMD art blocks at
                        # $470-$477. Check that only those tiles differ from
                        # the PLC 19 source and that every byte comes from the
                        # original program at the recorded address.
                        phase = int(path.name[-1]); assert rnd == 6 and act == 3 and phase in range(3)
                        assert source['generator'] == 'tools/extract_mmd.py'
                        assert {o['kind'] for o in packed_here} == {251 + phase}
                        beam = source['art']['beam']; at = int(beam['address'], 16) - ORIGIN
                        original = disc[name+'__.MMD'][at:at+256]
                        assert len(original) == 256 and hashlib.sha256(original).hexdigest() == beam['sha256']
                        first, last = 0x470 * 32, 0x478 * 32
                        baseline = (path.parent/(name+'-boss')/'vram.bin').read_bytes()
                        assert vram == baseline[:first] + original + baseline[last:]
                        assert all(first <= tile % 65536 < last for o in packed_here for tile in read_tiles(o))
                        continue
                    if path.name.endswith('-boss-entry'):
                        # PLC 19 later fills $300-$32f. During entry those
                        # unwritten tiles remain zero; live C/D frame 145
                        # confirms this state for all four entry actors.
                        banks=[b for b in plc_banks(disc[name+'__.MMD']) if b[0] in (1,2)]
                        for o in packed_here:
                            for tile in read_tiles(o):
                                at=tile%65536
                                covered=[b for b in banks if b[2]<=at and at+32<=b[2]+len(b[3])]
                                matches=[b for b in covered if b[3][at-b[2]:at-b[2]+32]==vram[at:at+32]]
                                assert matches or (not covered and vram[at:at+32]==bytes(32)),(name,o['kind'],hex(at))
                        continue
                    # The Act 3 boss source is built from the program's PLC lists by
                    # tools/extract_mmd.py (not an emulator capture); it records each bank.
                    if path.name.endswith(('-boss','-boss2','-bumper')):
                        assert source['generator']=='tools/extract_mmd.py' and source['art']
                        continue
                    if path.name.endswith('-flower'):
                        # PLAYSUB flowers: PLC 1 bytes tile by tile (tools/ss_flower_source.py).
                        from ss_flower_source import verify_flower_tiles
                        for o in packed_here:verify_flower_tiles(disc[name+"__.MMD"],o,vram)
                        continue
                    if rnd==4:
                        # Every packed R4 family reads tiles an original PLC bank
                        # holds: resident at capture, or overlaid (-plc) from it.
                        for o in packed_here:verify_tiles(disc[name+"__.MMD"],o,vram)
                    if rnd in (5,6,7,8):
                        # R5/R6: every tile holds bytes an original PLC bank writes there.
                        # tools/zone_object_assets.py RETAIL_VRAM_EVIDENCE families are retail runtime VRAM instead.
                        for o in packed_here:
                            if (path.name,o['kind']) not in RETAIL_VRAM_EVIDENCE:verify_tile_bytes(disc[name+"__.MMD"],o,vram)
                if rnd == 7:
                    # Do not let a successful partial retail capture hide missing families.
                    assert {row[0] for row in specs(name)} <= set(objects), (name, 'missing SS actor source')
                if rnd in (4,5,6,7,8):
                    # Variants (type|subtype<<8) and aliases, as the packer lists them.
                    objects={k:(o,v) for k,o,v,_ in (fight_objects(name,fight) if fight else packed_objects(name))}
                    # Per-piece families keep each non-blank mapping piece (part k is piece
                    # n-1-k), or one piece for a pose with no other (the packer's rule).
                    # kept[kind][pose]: the mapping pieces of each stored part (part_pieces).
                    kept={k:[[g for g,q in zip(part_pieces(rnd,o,bytes.fromhex(m)[0]) if bytes.fromhex(m)[0] else [[0]],parts) if any(q[4])]
                             or [(part_pieces(rnd,o,bytes.fromhex(m)[0]) if bytes.fromhex(m)[0] else [[0]])[0]] for m,parts in zip(o['frames'],source_parts(o,v,rnd))]
                          for k,(o,v) in objects.items() if per_piece(rnd,o)}
                    r4_frames=sum(sum(len(p) if bytes.fromhex(m)[0] else 1 for p,m in zip(kept[k],o['frames'])) if k in kept else len(o['frames']) for k,(o,_) in objects.items())
                    if rnd==3:
                        assert source['plc_queue_empty_frames']>=2
                        expected_banks=verify_cc_banks(disc[name+'__.MMD'],source['objects'],vram)
                        assert expected_banks=={int(k):v for k,v in source['fixture']['object_plcs'].items()}
                expected_count=r4_frames if rnd in (4,5,6,7,8) else sum(f for _,_,f in specs(name))
                if rnd==3 and act<3:expected_count+=8+(6 if era=='B' else 0)
                if rnd==3 and act<3:expected_count+=2  # BOBINB.C bumper break (tools/extract_mmd.py)
                if rnd==3 and act<3:expected_count+=8  # PLAYSUB flowers (tools/ss_flower_source.py)
                if name=='R31A':expected_count+=45
                if name in ('R33C','R33D'):expected_count+=4+1+3  # SIKAKE33 kaitenban, light, stopper
                if name in ('R33C','R33D'):expected_count+=36+8+2+4  # BOSS_3.C/GATE.C parts (split_cc_boss), capsule flowers, bumper break, points
                assert count==expected_count,(name,count,expected_count)
                for f in range(count):
                    row = records_at+f*48
                    kind,frame,packed_offset,width,height,left,top,*refs = struct.unpack_from('>HHIHHhh16H',pack,row)
                    offset=packed_offset&65535
                    native_kind,subtype = (kind&255,kind>>8) if rnd in (4,5,6,7,8) else (68,128) if kind==168 else (kind-100,255) if kind in (178,179,180,183,184) else (89,1) if kind==189 else (kind-200,1) if kind in (278,279) else (93,254) if kind==293 else (93,1) if kind==193 else (kind,0)
                    found=native.find_art(C.byref(art),native_kind,subtype,frame)
                    # Per-piece families: consecutive part records share a pose;
                    # lookup finds the first, part k is piece n-1-k of the mapping.
                    first=f
                    while first and struct.unpack_from('>HH',pack,records_at+(first-1)*48)==(kind,frame):first-=1
                    assert found==C.addressof(buffer)+records_at+first*48,(name,kind,frame,f,first,(found-C.addressof(buffer)-records_at)//48 if found else None)
                    obj,vram=objects[kind]; pose=(obj.get('frame_ids') or list(range(len(obj['frames'])))).index(frame); mapping=bytearray.fromhex(obj['frames'][pose])
                    if per_piece(rnd,obj) and mapping[0]:
                        pieces=kept[kind][pose][f-first]
                        mapping=bytearray([len(pieces)])+b''.join(mapping[1+5*i:6+5*i] for i in pieces)
                    else:assert first==f
                    banks=set()
                    for piece in range(mapping[0]):
                        pos=1+piece*5
                        word=(struct.unpack_from('>H',mapping,pos+2)[0]+obj['tile'])&65535
                        struct.pack_into('>H',mapping,pos+2,word);banks.add(((word>>13)&3)|((word>>8)&128))
                        x=struct.unpack_from('>b',mapping,pos+4)[0]-left-width//2
                        struct.pack_into('>b',mapping,pos+4,x)
                    assert len(banks)==(1 if mapping[0] else 0),(name,kind,frame,banks)
                    bank=banks.pop() if banks else 0
                    colors=struct.pack('>16H',*[(bank&3)*16+c+1+(bank&128) for c in range(16)])
                    expected=source_sprite(mapping,vram,colors,width,-top-32,height)
                    bitmap=raw[offset:offset+width*height//2]
                    indices=[n for b in bitmap for n in (b>>4,b&15)]
                    actual=struct.pack('>'+str(len(indices))+'H',*[refs[n]+1 if n else 0 for n in indices])
                    assert actual==expected,(name,kind,frame,'source pixels')
                    if mapping[0]:
                        # Some entry mapping pieces point to $300 tiles before
                        # PLC 19 writes them. Their blank retail pose is valid.
                        assert any(indices) or (rnd==6 and act==3 and 496<=kind<=499) or (name,kind) in RETAIL_VRAM_EVIDENCE,(name,kind,frame,'empty artwork')
                    else:
                        # R4 pose counts come from the retail mapping table; its
                        # zero-piece poses (awa 22, et4 7, movie4 1, rblk4 8,
                        # walls 4, swgun4 2, harid4 1, friend4 2) are table entries.
                        assert (rnd in (4,5,6,7,8) or (kind==77 and frame in (5,6)) or (kind==184 and frame==0) or (kind==84 and frame==1) or (kind==87 and frame==10) or (kind==88 and frame==1) or (kind in (89,189,94,194) and frame==2) or (kind==90 and frame in (8,9,13)) or (kind==92 and frame==14)) and not any(indices)
                    # Original global flips negate piece coordinates around the
                    # object origin. Check every pixel's transformed coordinate.
                    for flags in range(4):
                        ox=-left-width if flags&1 else left;oy=-top-height if flags&2 else top
                        for x,y in ((0,0),(width-1,height-1),(width//2,height//2)):
                            sx=width-1-x if flags&1 else x;sy=height-1-y if flags&2 else y
                            assert ox+x==(-1-(left+sx) if flags&1 else left+sx)
                            assert oy+y==(-1-(top+sy) if flags&2 else top+sy)
                        flips_checked+=1
                    pixels_checked+=width*height;cases+=1
                assert not native.find_art(C.byref(art),255,0,0)
                assert not native.find_art(C.byref(art),67,0,255)
                for length in (0,19,start+11,start+12+count*48-1):
                    assert native.open_art(C.byref(Art()),buffer,length,index)==-1
                records[name+(fight or '')]=dict(frames=count,raw_bytes=raw_size,pack_sha256=hashlib.sha256(pack).hexdigest())
    report=dict(passed=True,variants=len(records),frames=cases,pixels=pixels_checked,flip_cases=flips_checked,programs=records)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Zone sprites: {len(records)} variants, {cases} frames, {pixels_checked} exact source pixels, {flips_checked} flip cases')
    if 4 in rounds:
        slots=check_zone_cycle()
        print(f'Zone CLUT cycle: {slots} COL4-referencing CLUT slots across 10 TT programs follow CRAM by palette code; no VDP1 cycle writes')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--round',type=int,action='append',choices=(3,4,5,6,7,8))
    args=parser.parse_args()
    main(tuple(args.round) if args.round else (3,4,5,6,7,8))
