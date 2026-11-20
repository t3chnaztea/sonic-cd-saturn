#!/usr/bin/env python3
"""Native stamp animation against the original 68000 map-writing routine."""
import ctypes as C,hashlib,json,struct
from special_assets import ROOT,parts,pack,sine_table
from special_reference import Reference
from test_special import Stage,Camera,Line
class Animation(C.Structure):_fields_=[(n,C.c_uint16) for n in ['fan','hazard','delay']]
def main():
    native=C.CDLL(str(ROOT/'build/special.dylib'))
    native.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    native.scd_special_cache.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t];native.scd_special_cache.restype=C.c_size_t
    native.scd_special_animate.argtypes=[C.POINTER(Stage),C.POINTER(Animation),C.c_void_p,C.c_void_p,C.c_void_p]
    native.scd_special_trace.argtypes=[C.POINTER(Line),Camera]
    native.scd_special_render_cached.argtypes=[C.c_void_p,C.POINTER(Line),C.c_void_p,C.c_uint]
    reference=Reference();digest=hashlib.sha256();cases=0;rendered=0;table=sine_table();records=[];fixtures=[]
    def sine(a):return (-1 if a&256 else 1)*table[(a&127)^(127 if a&128 else 0)]
    for id in range(1,9):
        components=parts(id);cache_sizes=[]
        for seed in [(0,0,0),(4,6,65530)]:
            data=pack(id);buffer=C.create_string_buffer(data);stage=Stage()
            assert native.scd_special_open(C.byref(stage),buffer,len(data))==0
            cache=C.create_string_buffer(0x80000);used=native.scd_special_cache(C.byref(stage),cache,len(cache));assert used;cache_sizes.append(used)
            animation=Animation(*seed);reference.begin_animation(components,seed)
            for tick in range(1,65):
                expected,state=reference.animate()
                count=native.scd_special_animate(C.byref(stage),C.byref(animation),stage.part[1],cache,cache)
                assert (animation.fan,animation.hazard,animation.delay)==state,('source animation state',id,seed,tick)
                assert C.string_at(stage.part[1],32768)==expected,('source animation map',id,seed,tick)
                assert count==len(components[6])//8+(len(components[5])//10 if not(state[2]&1) else 0)
                digest.update(expected);digest.update(struct.pack('>3H',*state));cases+=1
                if seed==(0,0,0) and tick<=24:
                    # Look ahead toward one animated stamp; all cached source
                    # orientations must also agree with the real graphics core.
                    offset=int.from_bytes(components[5][:2],'big');x=(offset//2%128)*32+16;y=(offset//2//128)*32+16
                    camera=(max(832,min(3264,x-192)),max(832,min(3264,y)),352,128,128)
                    lines=(Line*96)();pixels=(C.c_uint8*(256*96))()
                    assert native.scd_special_trace(lines,Camera(*camera))==0
                    trace=reference.trace(camera,sine);gfx=reference.render(components[0],expected,trace)
                    native.scd_special_render_cached(cache,lines,pixels,256)
                    assert bytes(pixels)==gfx,('animated source graphics',id,tick)
                    def fnv(raw):
                        h=2166136261
                        for b in raw:h=((h^b)*16777619)&0xffffffff
                        return h
                    packed=bytes((a<<4)|b for a,b in zip(gfx[::2],gfx[1::2]))
                    fixtures.append({'stage':id,'camera':camera,'trace':fnv(trace),'pixels':fnv(gfx),'texture':fnv(packed),'animation':list(state),'map':fnv(expected)})
                    digest.update(gfx);rendered+=1
        records.append({'stage':id,'cache_bytes':cache_sizes[0]})
        print('Original stamp animation:',id,'map/state/pixels PASS',flush=True)
    report={'passed':True,'original_68000_updates':cases,'full_map_bytes_compared':cases*32768,'render_cases':rendered,'pixels_compared':rendered*256*96,'map_state_pixel_sha256':digest.hexdigest(),'source_updates_per_second':20,'stages':records}
    (ROOT/'build/special-reference/animation-fixtures.json').write_text(json.dumps(fixtures,separators=(',',':'))+'\n')
    (ROOT/'build/special-reference/animation-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
