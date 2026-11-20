#!/usr/bin/env python3
"""Compare native UFO primitives with executed source, including wrap edges."""
import ctypes as C,hashlib,json,random,struct,subprocess
from special_assets import ROOT,SOURCE,sine_table
from special_ufo_reference import UFOReference
class UFO(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ['x','y','x_velocity','y_velocity','sprite_x','sprite_y']]+[(n,C.c_uint16) for n in ['path_offset','path_time','z']]+[(n,C.c_uint8) for n in ['id','flags','player_collision','item','unknown']]
class Path(C.Structure):_fields_=[('data',C.c_void_p),('size',C.c_size_t)]
def state(u):return {n:getattr(u,n) for n,_ in u._fields_}
def main():
    subprocess.run(['python3','tools/special_ufo_assets.py'],cwd=ROOT,check=True)
    subprocess.run(['bash','tools/build-m68k-reference.sh'],cwd=ROOT,check=True)
    sources=['src/special_ufo.c','src/special.c'];opts=['clang','-std=c11','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated']
    subprocess.run(opts+['-O2','-dynamiclib']+sources+['-o','build/special-ufo.dylib'],cwd=ROOT,check=True)
    subprocess.run(opts+['-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','tools/special_ufo_sanitize.c']+sources+['-o','build/special-ufo-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-ufo-sanitize'],cwd=ROOT,check=True)
    lib=C.CDLL(str(ROOT/'build/special-ufo.dylib'));pointer=C.POINTER(UFO)
    lib.scd_special_ufo_path_open.argtypes=[C.POINTER(Path),C.c_void_p,C.c_size_t]
    for name in ['follow','move']:getattr(lib,'scd_special_ufo_'+name).argtypes=[pointer,C.POINTER(Path)]
    lib.scd_special_ufo_project.argtypes=[pointer,C.c_uint16,C.c_uint16,C.c_uint]
    lib.scd_special_ufo_on_screen.argtypes=[pointer]
    lib.scd_special_ufo_collision.argtypes=[pointer,C.c_uint16,C.c_uint16,C.c_uint16,C.c_uint8,C.POINTER(C.c_uint8)]
    lib.scd_special_ufo_distance.argtypes=[C.c_uint16]*4;lib.scd_special_ufo_distance.restype=C.c_uint32
    lib.scd_special_ufo_animation.argtypes=[C.c_uint32];lib.scd_special_ufo_animation.restype=C.c_uint
    ref=UFOReference();digest=hashlib.sha256();counts={};rng=random.Random(30030)
    table=sine_table()
    def sine(a):return (-1 if a&256 else 1)*table[(a&127)^(127 if a&128 else 0)]
    def check(kind,u,path=b'',sx=2048,sy=2048,sz=352,sid=1,collision=0,yaw=0):
        before=state(u);expected,expected_col,d0=ref.run(kind,before,path,sx,sy,sz,sid,collision,sine(yaw),sine(yaw+128))
        col=C.c_uint8(collision)
        if kind in ['follow','move']:
            data=C.create_string_buffer(path);p=Path();assert lib.scd_special_ufo_path_open(C.byref(p),data,len(path))==0
            assert getattr(lib,'scd_special_ufo_'+kind)(C.byref(u),C.byref(p))==0
        elif kind=='project':assert lib.scd_special_ufo_project(C.byref(u),sx,sy,yaw)==0
        elif kind=='screen':lib.scd_special_ufo_on_screen(C.byref(u))
        elif kind=='collision':lib.scd_special_ufo_collision(C.byref(u),sx,sy,sz,sid,C.byref(col))
        elif kind=='distance':
            actual=lib.scd_special_ufo_distance(u.x>>16,u.y>>16,sx,sy);assert actual==d0,(kind,before,sx,sy,actual,d0)
            digest.update(struct.pack('>I',actual))
        assert state(u)==expected,(kind,before,sx,sy,yaw,{k:(state(u)[k],expected[k]) for k in expected if state(u)[k]!=expected[k]})
        assert col.value==expected_col,(kind,before,sx,sy,sz,sid,collision,col.value,expected_col)
        digest.update(json.dumps((expected,expected_col),sort_keys=True).encode());counts[kind]=counts.get(kind,0)+1
    paths=sorted((SOURCE/'Data').glob('Stage */UFO *.bin'))+[SOURCE/'Data/Time UFO Path.bin'];assert len(paths)==49
    path_hash=hashlib.sha256();nodes=0;cycles=0
    for p in paths:
        data=p.read_bytes();path_hash.update(data);nodes+=(len(data)-4)//10
        u=UFO(id=2,path_offset=2,x=0x1234,y=0xabcd,item=data[0],unknown=data[1])
        check('follow',u,data)
        duration=sum(struct.unpack_from('>H',data,i)[0] for i in range(2,len(data)-2,10))
        for _ in range(duration*2):check('move',u,data)
        cycles+=2
    print('Original UFO paths PASS:',len(paths),nodes,cycles,counts,flush=True)
    # Legal synthetic paths cover signed DIVS overflow, duration 1/32767 and
    # word-wrap snaps with nonzero fractions, without executing zero divisors.
    for n in range(512):
        vals=[rng.randrange(65536) for _ in range(4)];duration=[1,2,3,31,32767][n%5]
        data=struct.pack('>BB6H',n%4,n&255,duration,*vals,65535)
        check('follow',UFO(id=2,path_offset=2,x=rng.getrandbits(32),y=rng.getrandbits(32)),data)
    for n in range(2048):
        u=UFO(id=2,x=rng.getrandbits(32),y=rng.getrandbits(32),z=rng.randrange(65536),sprite_x=rng.getrandbits(32),sprite_y=rng.getrandbits(32),flags=n&255)
        sx=rng.randrange(65536);sy=rng.randrange(65536);yaw=n&511
        # Original zero-divisor trap has no return; native has a safe error.
        trial=UFO.from_buffer_copy(u)
        if lib.scd_special_ufo_project(C.byref(trial),sx,sy,yaw)==0:check('project',u,sx=sx,sy=sy,yaw=yaw)
        check('screen',u);check('distance',u,sx=sx,sy=sy)
    for yaw in range(512):
        for dx,dy in [(0,0),(1,0),(0,64),(-32,28),(32,-28)]:
            check('project',UFO(id=2,x=(2048+dx)<<16,y=(2048+dy)<<16,z=256,sprite_x=0x1234,sprite_y=0x5678),yaw=yaw)
    # Near misses and exact inclusive boundaries, including signed-word edges.
    for center in [0,16,2048,32751,32767,32768,65520,65535]:
        for dx in [-33,-32,0,32,33]:
            for dy in [-29,-28,0,28,29]:
                for z in [527,528,575,623,624]:
                    check('collision',UFO(id=2,x=center<<16,y=center<<16),sx=(center+dx)&65535,sy=(center+dy)&65535,sz=z)
    for n in range(256):check('collision',UFO(id=2,x=2048<<16,y=2048<<16,player_collision=n),sz=576,sid=n%2,collision=n//2)
    # Independently read the original distance-to-animation table.
    source=(SOURCE/'Objects/UFO/Main.asm').read_text().split('\n.Frames:',1)[1].split('SpawnUFOs:',1)[0]
    import re
    frames=[int(v.strip(),0) for row in re.findall(r'dc\.b\s+([^\n]+)',source) for v in row.split(',')]
    assert len(frames)==82
    for distance in list(range(0x600))+[65535,0xffffffff]:
        assert lib.scd_special_ufo_animation(distance)==frames[min(distance,0x500)>>4]
    print('Original UFO geometry PASS:',counts,flush=True)
    report={'passed':True,'original_calls':counts,'source_paths':49,'source_nodes':nodes,'complete_path_cycles':cycles,'paths_sha256':path_hash.hexdigest(),'state_sha256':digest.hexdigest(),'sanitizer_states':65536,'limits':'Native path/move/projection/distance/onscreen/collision primitives only; no Saturn integration, UFO art, bonuses, shadows or win states yet.'}
    (ROOT/'build/special-reference/ufo-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
