#!/usr/bin/env python3
"""Compare native special Sonic animation and pixels with original DrawObject."""
import ctypes as C,hashlib,json,random,struct,subprocess
from special_assets import ROOT
from special_sonic_assets import pack
from special_sprite_reference import SpriteReference
from test_special_player import Player
class Art(C.Structure):
    _fields_=[('data',C.c_void_p)]+[(n,C.c_uint32) for n in ['length','animations','poses','entries','animation_offset','entry_offset','pose_offset','palette_offset','texture_offset']]
class Sprite(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ['tilt','animation','frame','time','time_copy','art']]
class Pose(C.Structure):
    _fields_=[('pixels',C.c_void_p),('x',C.c_int16),('y',C.c_int16)]+[(n,C.c_uint16) for n in ['width','height','flip','index']]
def state(s):return {n:getattr(s,n) for n,_ in s._fields_}
def canvas(pose):
    packed=C.string_at(pose.pixels,pose.width*pose.height//2);result=bytearray(96*96)
    for y in range(pose.height):
        for x in range(pose.width):
            u=pose.width-1-x if pose.flip&1 else x;v=pose.height-1-y if pose.flip&2 else y;at=v*pose.width+u
            value=(packed[at//2]>>(0 if at&1 else 4))&15
            dx=48+pose.x+x;dy=64+pose.y+y
            if 0<=dx<96 and 0<=dy<96:result[dy*96+dx]=value
    return bytes(result)
def main():
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-dynamiclib','src/special_sprite.c','-o','build/special-sprite.dylib'],cwd=ROOT,check=True)
    subprocess.run(['python3','tools/special_sonic_assets.py'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','tools/special_sprite_sanitize.c','src/special_sprite.c','-o','build/special-sprite-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-sprite-sanitize'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-sprite.dylib'))
    native.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t]
    native.scd_special_sprite_set.argtypes=[C.POINTER(Sprite),C.POINTER(Art),C.c_uint,C.c_int]
    native.scd_special_sprite_tilt.argtypes=[C.POINTER(Sprite),C.c_uint]
    native.scd_special_sprite_choose.argtypes=[C.POINTER(Sprite),C.POINTER(Player),C.POINTER(Art),C.c_int]
    native.scd_special_sprite_advance.argtypes=[C.POINTER(Sprite),C.POINTER(Player),C.POINTER(Art),C.POINTER(Pose)]
    data,animations,poses=pack();buffer=C.create_string_buffer(data);art=Art();assert native.scd_special_art_open(C.byref(art),buffer,len(data))==0
    for length in [0,4,39,len(data)-1]:assert native.scd_special_art_open(C.byref(Art()),buffer,length)==-1
    for offset in range(0,40,4):
        bad=bytearray(data);struct.pack_into('>I',bad,offset,0xffffffff)
        assert native.scd_special_art_open(C.byref(Art()),C.create_string_buffer(bytes(bad)),len(bad))==-1
    reference=SpriteReference();digest=hashlib.sha256();calls=0;pixel_cases=0;fixtures=[];rng=random.Random(27013)
    def compare(s,p,operation,held=0,inactive=0,animation=0):
        nonlocal calls
        expected,flags,sat=reference.run(operation,state(s),p.flags,p.speed,held,inactive,animation)
        pose=Pose();visible=-1
        if operation=='tilt':native.scd_special_sprite_tilt(C.byref(s),held)
        elif operation in ['set','change']:native.scd_special_sprite_set(C.byref(s),C.byref(art),animation,operation=='set')
        elif operation=='choose':native.scd_special_sprite_choose(C.byref(s),C.byref(p),C.byref(art),inactive)
        else:visible=native.scd_special_sprite_advance(C.byref(s),C.byref(p),C.byref(art),C.byref(pose))
        assert state(s)==expected and p.flags==flags,(operation,state(s),expected,p.flags,flags)
        digest.update(bytes(s));digest.update(bytes([p.flags]));digest.update(sat);calls+=1
        return visible,pose,sat
    for tilt in range(256):
        for held in [0,4,8,12]:compare(Sprite(tilt=tilt),Player(),'tilt',held)
    for animation in range(45):
        for operation in ['set','change']:
            compare(Sprite(tilt=5,animation=0,frame=17,time=45,time_copy=9),Player(),operation,animation=animation)
    for tilt in range(10):
        for speed in [0,0x2ff,0x300,0x53f,0x540,0x77f,0x780,0xaff,0xb00,0xffff]:
            for flags in [0,0x10,0x40,0x80,0xc0]:
                for inactive in [0,1]:compare(Sprite(tilt=tilt,animation=rng.randrange(45),frame=1,time=17,time_copy=23),Player(speed=speed,flags=flags),'choose',inactive=inactive)
    for animation,(delay,entries) in enumerate(animations):
        for frame in range(len(entries)):
            s=Sprite(tilt=5,animation=animation,frame=frame,time=delay,time_copy=delay);p=Player(flags=2)
            visible,pose,sat=compare(s,p,'draw');assert visible==0
            expected=reference.pixels(sat,s.art);actual=canvas(pose)
            assert actual==expected,('original sprite pixels',animation,frame,s.art,pose.index,next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),-1))
            def fnv(raw):
                h=2166136261
                for b in raw:h=((h^b)*16777619)&0xffffffff
                return h
            fixtures.append({'animation':animation,'frame':frame,'pose':pose.index,'flip':pose.flip,'texture':fnv(C.string_at(pose.pixels,pose.width*pose.height//2)),'xy':fnv(struct.pack('>hh',160+pose.x,216+pose.y))})
            digest.update(actual);pixel_cases+=1
        for tick in range(40):
            s=Sprite(tilt=5,animation=animation,frame=tick%len(entries),time=(tick*17)&255,time_copy=delay,art=63);p=Player(flags=[0,2,4,6][tick%4])
            visible,pose,sat=compare(s,p,'draw');assert (visible<0)==bool(p.flags&4)
    report={'passed':True,'original_animation_calls':calls,'original_pose_pixel_cases':pixel_cases,'canvas_pixels_compared':pixel_cases*96*96,'state_sat_pixel_sha256':digest.hexdigest(),'pack_sha256':hashlib.sha256(data).hexdigest(),'pack_bytes':len(data),'limits':'Original 68000 tilt/selection/DrawObject and independent SAT decoding; Saturn composite display is a separate gate.'}
    (ROOT/'build/special-reference/sprite-fixtures.json').write_text(json.dumps(fixtures,separators=(',',':'))+'\n')
    (ROOT/'build/special-reference/sprite-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
