#!/usr/bin/env python3
"""Compare every used CC generator pose with the original loaded sprite bank."""
import hashlib,json,re,struct
from pathlib import Path
from convert_assets import ROOT,OUT
from test_objects import unpack_texture
from sprite_composition import source_sprite
from zone_object_source import dependencies


def verify():
    meta=(OUT/'object-frames.inc').read_text()
    def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',meta)[1].split(',')))
    offsets,widths,heights,tops,banks,shifts=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops','object_stage_palette','object_y_shifts']]
    normal=int(re.search(r'#define OBJECT_BASE_45 (\d+)',meta)[1]);withered=int(re.search(r'#define OBJECT_BASE_86 (\d+)',meta)[1])
    raw=unpack_texture((OUT/'object-art.bin').read_bytes());results={};inputs={}
    for name in ['R31A','R31B','R32A','R32B']:
        folder=ROOT/'build/cc1/generator/art-placement'/name
        source=json.loads((folder/'source.json').read_text());vram=(folder/'vram.bin').read_bytes()
        assert hashlib.sha256(vram).hexdigest()==source['vram_sha256']
        assert source['dependencies']==dependencies()
        assert source['tool_sha256']==hashlib.sha256((ROOT/'tools/zone_object_source.py').read_bytes()).hexdigest()
        assert source['plc_queue_empty_frames']>=2
        stage=(OUT/f'cc{name[1:]}.bin').read_bytes();at,size=struct.unpack_from('>II',stage,44);assert size==128
        palette=stage[at:at+32]
        obj=source['objects'][0];assert obj['kind']==86 and obj['retail_id']==55
        count=0
        for pose,encoded in zip(obj['frame_ids'],obj['frames']):
            mapping=bytearray.fromhex(encoded)
            for i in range(mapping[0]):
                at=3+5*i;struct.pack_into('>H',mapping,at,(struct.unpack_from('>H',mapping,at)[0]+obj['tile'])&65535)
            expected=source_sprite(mapping,vram,palette,80,0,64)
            n=normal+pose if name[-1]=='B' else withered+(pose==2)
            w,h,top,off=widths[n],heights[n],tops[n],offsets[n]
            assert w==80 and not banks[n] and not shifts[n]
            packed=raw[off:off+w*h//2+32];clut=struct.unpack('>16H',packed[-32:]);actual=bytearray(80*64*2)
            for pos,b in enumerate(packed[:-32]):
                for sub,index in enumerate((b>>4,b&15)):struct.pack_into('>H',actual,2*(top*w+2*pos+sub),clut[index])
            assert actual==expected,(name,pose,'original loaded generator pixels')
            count+=w*64
        results[name]=dict(poses=obj['frame_ids'],pixels=count,plc_banks=source['fixture']['object_plcs'])
        for p in [folder/'source.json',folder/'vram.bin']:inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ['tools/test_cc_generator_art.py','tools/convert_objects.py','tools/zone_object_source.py','assets/generated/object-art.bin','assets/generated/object-frames.inc']:
        inputs[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    report=dict(passed=True,variants=results,inputs=inputs,limits='All reachable generator poses in CC Acts 1/2 Present/Past, compared with original loaded banks and native packed textures. Target rendering and ordinary controller routes are separate.')
    (ROOT/'build/cc1/generator/art-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Generator original art:',sum(v['pixels'] for v in results.values()),'exact pixels in four act/era variants')

if __name__=='__main__':verify()
