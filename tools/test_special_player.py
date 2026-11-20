#!/usr/bin/env python3
"""Compare native motion against the source 68000, including complete air arcs."""
import ctypes as C,hashlib,json,random,struct,subprocess
from special_assets import ROOT,parts,sine_table
from special_player_reference import PlayerReference,ACTOR
from test_special import Camera,Line,Stage
class Player(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ['x','y','yaw','sprite_y','sprite_velocity']]+[(n,C.c_uint16) for n in ['z','speed','top_speed','shoes','jump_timer','bump_time']]+[(n,C.c_uint8) for n in ['routine','flags','scroll']]
def state(p):return {name:getattr(p,name) for name,_ in p._fields_}
def main():
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-dynamiclib','src/special.c','src/special_player.c','-o','build/special-player.dylib'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-player.dylib'));reference=PlayerReference();rng=random.Random(26013);digest=hashlib.sha256();cases=0;arcs=[];fixtures=[]
    for name in ['speed','rotate','air','jump']:
        getattr(native,'scd_special_player_'+name).argtypes=[C.POINTER(Player),C.c_uint,C.c_int]
    for name in ['move','spring','fan']:getattr(native,'scd_special_player_'+name).argtypes=[C.POINTER(Player)]
    def check(operation,p,held=0,tapped=0,inactive=0):
        nonlocal cases
        before=state(p);expected=reference.run(operation,before,held,tapped,inactive)
        fn=getattr(native,'scd_special_player_'+operation)
        if operation in ['speed','rotate','air']:fn(C.byref(p),held,inactive)
        elif operation=='jump':fn(C.byref(p),tapped,inactive)
        else:fn(C.byref(p))
        actual=state(p)
        assert actual==expected,(operation,before,held,tapped,inactive,{k:(actual[k],expected[k]) for k in actual if actual[k]!=expected[k]})
        digest.update(json.dumps(actual,sort_keys=True).encode());cases+=1
    for operation in ['speed','rotate','move','jump','air','spring','fan']:
        for n in range(256):
            p=Player(**{name:rng.getrandbits(C.sizeof(kind)*8) for name,kind in Player._fields_})
            if operation=='air':p.routine=2+n%2
            check(operation,p,n&255,(n*17)&255,n%5==0)
        print('Original special motion:',operation,'256 wrap/controller cases PASS',flush=True)
    probe_hash=2166136261;probe_count=0
    def probe_record(p):
        nonlocal probe_hash,probe_count
        for value in state(p).values():
            for b in struct.pack('>I',value):probe_hash=((probe_hash^b)*16777619)&0xffffffff
        probe_count+=1
    # Every yaw, both signs of speed, and preserved subpixel positions.
    for yaw in range(512):
        p=Player(x=0x340fedc,y=0xcbf0123,yaw=(yaw<<16)|0x9876,speed=0xa00 if yaw&1 else 0xfa00)
        check('move',p);probe_record(p)
    components=parts(1);table=sine_table();rendered=0
    def sine(a):return (-1 if a&256 else 1)*table[(a&127)^(127 if a&128 else 0)]
    native.scd_special_trace.argtypes=[C.POINTER(Line),Camera]
    native.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    native.scd_special_render.argtypes=[C.POINTER(Stage),C.POINTER(Line),C.c_void_p,C.c_uint]
    data=(ROOT/'assets/generated/special1.bin').read_bytes();buffer=C.create_string_buffer(data);stage=Stage();assert native.scd_special_open(C.byref(stage),buffer,len(data))==0
    for launch,held,jump_timer in [('jump',0,0),('jump',0x10,0),('spring',0,0),('spring',0x10,0),('spring',0,20),('fan',0,0)]:
        p=Player(x=1344<<16,y=1312<<16,yaw=128<<16,sprite_y=344<<16,z=352,speed=0xa00,top_speed=0xa00,routine=1,jump_timer=jump_timer)
        check(launch,p,tapped=0x10);probe_record(p);peak=352;count=0
        while p.routine!=1:
            check('air',p,held=held);probe_record(p);count+=1;peak=max(peak,p.z);assert count<200
            camera=(1344,1312,p.z,128,128);trace=reference.reference.trace(camera,sine);lines=(Line*96)();pixels=(C.c_uint8*24576)()
            assert native.scd_special_trace(lines,Camera(*camera))==0
            actual=b''.join(struct.pack('>4H',l.x,l.y,l.dx&65535,l.dy&65535) for l in lines)
            assert actual==trace,('air projection',launch,held,jump_timer,count,p.z)
            native.scd_special_render(C.byref(stage),lines,pixels,256)
            gfx=reference.reference.render(components[0],components[1],trace)
            assert bytes(pixels)==gfx,('air pixels',launch,held,jump_timer,count,p.z)
            def fnv(raw):
                h=2166136261
                for b in raw:h=((h^b)*16777619)&0xffffffff
                return h
            packed=bytes((a<<4)|b for a,b in zip(gfx[::2],gfx[1::2]))
            fixtures.append({'stage':1,'camera':camera,'trace':fnv(trace),'pixels':fnv(gfx),'texture':fnv(packed),'map':fnv(components[1])})
            rendered+=1
        arcs.append({'launch':launch,'held':held,'initial_jump_timer':jump_timer,'updates_to_land':count,'peak_camera_z':peak})
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-DSCD_SPECIAL_PLAYER_QA_MAIN','-Isrc','-Iassets/generated','src/special.c','src/special_player.c','src/special_player_qa.c','-o','build/special-player-sanitize'],cwd=ROOT,check=True)
    observed=subprocess.check_output([ROOT/'build/special-player-sanitize'],cwd=ROOT,text=True)
    assert list(map(int,observed.split()))==[probe_hash,probe_count],('sanitized motion probe',observed,probe_hash,probe_count)
    report={'passed':True,'target_probe_hash':probe_hash,'target_probe_states':probe_count,'original_68000_motion_calls':cases,'state_sha256':digest.hexdigest(),'original_sonic_source_sha256':hashlib.sha256(ACTOR.read_bytes()).hexdigest(),'air_arcs':arcs,'air_render_cases':rendered,'air_source_pixels':rendered*24576,'limits':'Motion primitives only. Sound and splash callees are stubs in the offline oracle. Full object dispatch, stamp collision, UFOs, special-stage entry and results remain pending.'}
    (ROOT/'build/special-reference/air-fixtures.json').write_text(json.dumps(fixtures,separators=(',',':'))+'\n')
    (ROOT/'build/special-reference/player-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
