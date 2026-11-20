#!/usr/bin/env python3
"""Native special-stage data/projection/pixels versus original CPU and GFX."""
import ctypes as C,hashlib,json,re,struct,subprocess
from special_assets import ROOT,SOURCE,OUT,parts,pack,kosinski,sine_table
from special_reference import Reference
class Camera(C.Structure):_fields_=[(n,C.c_int16) for n in ['x','y','z','pitch','yaw']]
class Line(C.Structure):_fields_=[('x',C.c_uint16),('y',C.c_uint16),('dx',C.c_int16),('dy',C.c_int16)]
class Stage(C.Structure):_fields_=[('part',C.c_void_p*7),('size',C.c_uint32*7),('stage',C.c_uint)]
def main():
    subprocess.run(['clang','-std=c11','-O2','-fwrapv','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-dynamiclib','src/special.c','-o','build/special.dylib'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-fwrapv','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','-Iassets/generated','tools/special_sanitize.c','src/special.c','-o','build/special-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-sanitize'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special.dylib'))
    native.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    native.scd_special_trace.argtypes=[C.POINTER(Line),Camera]
    native.scd_special_render.argtypes=[C.POINTER(Stage),C.POINTER(Line),C.c_void_p,C.c_uint]
    native.scd_special_pixel.argtypes=[C.POINTER(Stage),C.c_int,C.c_int]
    native.scd_special_cache.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    native.scd_special_cache.restype=C.c_size_t
    native.scd_special_render_cached.argtypes=[C.c_void_p,C.POINTER(Line),C.c_void_p,C.c_uint]
    main_source=(SOURCE/'Main.asm').read_text()
    loop=main_source.split('MainLoop:',1)[1].split('\n.Exit:',1)[0]
    assert len(re.findall(r'bsr\.w\s+VSync',loop))==6
    assert len(re.findall(r'bsr\.w\s+UpdateStage',loop))==2
    assert len(re.findall(r'move\.b\s+#60/3,timerFrames',(SOURCE/'Sub.asm').read_text()))==2
    table=sine_table()
    def sine(a):return (-1 if a&256 else 1)*table[(a&127)^(127 if a&128 else 0)]
    for angle in range(1024):assert native.scd_special_sine(angle)==sine(angle)
    reference=Reference();decompressed=0;cases=0;digest=hashlib.sha256();captures=[];fixtures=[]
    for stage_id in range(1,9):
        source=SOURCE/f'Data/Stage {stage_id}'
        for name in ['Stamps.kos','Stamps 1.kos','Stamps 2.kos','Stamp Map.kos']:
            p=source/name
            if not p.exists():continue
            data=p.read_bytes();decoded=kosinski(data)
            assert reference.decompress(data,len(decoded))==decoded,('original Kosinski',stage_id,name)
            decompressed+=1
        data=pack(stage_id);buffer=C.create_string_buffer(data);stage=Stage();assert native.scd_special_open(C.byref(stage),buffer,len(data))==0
        # Every truncated section/header must be rejected.
        for size in [0,3,15,71,len(data)-1]:assert native.scd_special_open(C.byref(Stage()),buffer,size)==-1
        for offset in [0,4,8,12,16,20,24,28]:
            corrupt=bytearray(data);struct.pack_into('>I',corrupt,offset,0xffffffff)
            assert native.scd_special_open(C.byref(Stage()),C.create_string_buffer(bytes(corrupt)),len(corrupt))==-1
        for section,stride in [(5,10),(6,8)]:
            start=struct.unpack_from('>I',data,16+8*section)[0]
            mutations=[(20+8*section,4,0),(20+8*section,4,stride-1),(start,2,1),(start,2,32768),(start+2,2,2044)]
            for offset,width,value in mutations:
                corrupt=bytearray(data);struct.pack_into('>I' if width==4 else '>H',corrupt,offset,value)
                assert native.scd_special_open(C.byref(Stage()),C.create_string_buffer(bytes(corrupt)),len(corrupt))==-1,('malformed animation',stage_id,section,offset,value)
        components=parts(stage_id);start=struct.unpack('>3H',components[4]);lines=(Line*96)();pixels=(C.c_uint8*(256*96))()
        cache=C.create_string_buffer(0x80000);cached_pixels=(C.c_uint8*(256*96))()
        assert native.scd_special_cache(C.byref(stage),cache,0x80000)>0
        assert native.scd_special_cache(C.byref(stage),C.create_string_buffer(0xa400),0xa400)==0
        cameras=[(start[0],start[1],352,128,yaw) for yaw in range(512)] if stage_id==1 else []
        cameras += [(start[0],start[1],z,128,yaw) for z in [352,432,624] for yaw in range(0,512,32)]
        for camera in cameras:
            expected=reference.trace(camera,sine)
            result=native.scd_special_trace(lines,Camera(*camera))
            assert result==0,('native rejected source camera',stage_id,camera)
            actual=b''.join(struct.pack('>4H',l.x,l.y,l.dx&65535,l.dy&65535) for l in lines)
            assert actual==expected,('original 68000 trace',stage_id,camera,next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),-1))
            native.scd_special_render(C.byref(stage),lines,pixels,256)
            native.scd_special_render_cached(cache,lines,cached_pixels,256)
            assert bytes(cached_pixels)==bytes(pixels),('cached renderer',stage_id,camera)
            gfx=reference.render(components[0],components[1],expected)
            assert bytes(pixels)==gfx,('Sega CD graphics operation',stage_id,camera,next((i for i,(a,b) in enumerate(zip(bytes(pixels),gfx)) if a!=b),-1))
            def fnv(raw):
                h=2166136261
                for b in raw:h=((h^b)*16777619)&0xffffffff
                return h
            packed=bytes((a<<4)|b for a,b in zip(gfx[::2],gfx[1::2]))
            fixtures.append({'stage':stage_id,'camera':camera,'trace':fnv(actual),'pixels':fnv(gfx),'texture':fnv(packed)})
            digest.update(actual);digest.update(gfx);cases+=1
            if camera==(start[0],start[1],352,128,128):
                colors=struct.unpack('>32H',components[3]);rgb=bytearray()
                for index in gfx:
                    c=colors[index];rgb.extend(((c&31)*8,((c>>5)&31)*8,((c>>10)&31)*8))
                path=ROOT/f'build/special-reference/stage{stage_id}.ppm';path.write_bytes(b'P6\n256 96\n255\n'+rgb);
                if str(path.relative_to(ROOT)) not in captures:captures.append(str(path.relative_to(ROOT)))
        print('Original special stage:',stage_id,'decoder/trace/graphics PASS',flush=True)
    report={'passed':True,'original_68000_decompressions':decompressed,'projection_and_graphics_cases':cases,'pixels_compared':cases*256*96,'trace_and_pixel_sha256':digest.hexdigest(),'captures':captures,'reference':'Pinned Sega CD original KosDec and GenGfxTraceTbl in Genesis Plus GX, then actual gfx_start/gfx_update','source_update_vblanks':3,'source_updates_per_second':20,'original_main_source_sha256':hashlib.sha256(main_source.encode()).hexdigest(),'sanitized_boundary_rows':78408,'sanitized_wrapped_camera_cases':1024,'original_source_sha256':hashlib.sha256((SOURCE/'Sub.asm').read_bytes()).hexdigest(),'limits':'Floor asset/projection foundation only; target display is a separate gate; gameplay, UFOs and entry/return remain pending.'}
    (ROOT/'build/special-reference/fixtures.json').write_text(json.dumps(fixtures,separators=(',',':'))+'\n')
    (ROOT/'build/special-reference/report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':
    main()
    subprocess.run(['python3','tools/test_special_animation.py'],cwd=ROOT,check=True)
    subprocess.run(['python3','tools/test_special_player.py'],cwd=ROOT,check=True)
    subprocess.run(['python3','tools/test_special_sprite.py'],cwd=ROOT,check=True)
    subprocess.run(['python3','tools/test_special_contacts.py'],cwd=ROOT,check=True)
    for test in ['effects','effect_art','effect_dispatch','effect_loop','ufo','rewards','ufo_art','stage','progress']:
        subprocess.run(['python3','tools/test_special_'+test+'.py'],cwd=ROOT,check=True)
    # Main CPU program flow: native V-INT model against retail runs of the same pad scripts.
    subprocess.run(['python3','tools/special_route.py'],cwd=ROOT,check=True)
    # Stages 1-7: steering routes that exercise each stage's scroll and palette cycle.
    # Stored win routes (stages 2-7) and hazard sweeps (stages 1-7): tests/routes/special.
    for route in ['timeout','win']+[f'steer-ss{n}' for n in range(1,8)]+[f'win-ss{n}' for n in range(2,8)]+[f'hazard-ss{n}' for n in range(1,8)]:
        subprocess.run(['python3','tools/special_retail.py',route],cwd=ROOT,check=True)
        subprocess.run(['python3','tools/test_special_game.py',route],cwd=ROOT,check=True)
