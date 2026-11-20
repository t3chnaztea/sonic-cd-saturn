#!/usr/bin/env python3
"""Native contacts and active states against original special-stage 68000 code."""
import ctypes as C,hashlib,json,random,subprocess
from special_assets import ROOT,parts,pack
from special_sonic_assets import pack as art_pack
from special_contact_reference import ContactReference
from test_special import Stage
from test_special_player import Player
from test_special_sprite import Art,Sprite,Pose
class ContactPlayer(C.Structure):
    _fields_=Player._fields_+[(n,C.c_uint8) for n in ['hurt','stamp_c','stamp_tl','stamp_tr','stamp_br','stamp_bl','orientation']]+[(n,C.c_uint32) for n in ['x_velocity','y_velocity']]
class World(C.Structure):
    _fields_=[('timer',C.c_uint32),('rings',C.c_uint16),('splash_timer',C.c_uint16),('dust',C.c_uint16*8)]+[(n,C.c_uint8) for n in ['timer_frames','speedup','inactive','stopped','time_attack','stage_over','ufo_count','time_ufo']]+[('sound',C.c_uint8*3),('lost_rings',C.c_uint8*7)]+[(n,C.c_uint8) for n in ['splash_id','splash_routine','splash_flags','splash_animation','splash_frame','splash_time']]+[('ring_bonus',C.c_uint16),('got_time_stone',C.c_uint8),('time_stone',C.c_uint8*3)]
def state(p):return {n:list(getattr(p,n)) if issubclass(t,C.Array) else getattr(p,n) for n,t in p._fields_}
def main():
    subprocess.run(['bash','tools/build-m68k-reference.sh'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-dynamiclib','src/special.c','src/special_player.c','src/special_sprite.c','src/special_contacts.c','-o','build/special-contacts.dylib'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','-Iassets/generated','tools/special_contact_sanitize.c','src/special.c','src/special_player.c','src/special_sprite.c','src/special_contacts.c','-o','build/special-contact-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-contact-sanitize'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-contacts.dylib'))
    native.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t];native.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t]
    args=[C.POINTER(ContactPlayer),C.POINTER(Sprite),C.POINTER(Art),C.POINTER(World)]
    for name in ['contact','bumper']:getattr(native,'scd_special_'+name).argtypes=args
    native.scd_special_contact_state.argtypes=args+[C.c_uint,C.c_uint]
    native.scd_special_player_step.argtypes=args+[C.POINTER(Stage),C.c_uint,C.c_uint]
    native.scd_special_get_contacts.argtypes=[C.POINTER(ContactPlayer),C.POINTER(Stage)]
    native.scd_special_splash.argtypes=[C.POINTER(World),C.POINTER(ContactPlayer)];native.scd_special_timer.argtypes=[C.POINTER(World)]
    native.scd_special_sprite_advance.argtypes=[C.POINTER(Sprite),C.POINTER(ContactPlayer),C.POINTER(Art),C.POINTER(Pose)]
    ab=C.create_string_buffer(art_pack()[0]);art=Art();assert native.scd_special_art_open(C.byref(art),ab,len(ab))==0
    reference=ContactReference();rng=random.Random(28013);digest=hashlib.sha256();counts={};components=parts(1);buf=C.create_string_buffer(pack(1));stage=Stage();assert native.scd_special_open(C.byref(stage),buf,len(buf))==0
    def check(operation,p,s,w,held=0,tapped=0):
        before=(state(p),state(s),state(w));expected=reference.run(operation,*before,components,held,tapped)
        arguments=[C.byref(p),C.byref(s),C.byref(art),C.byref(w)]
        if operation in ['contacts','bumper']:getattr(native,'scd_special_contact' if operation=='contacts' else 'scd_special_bumper')(*arguments)
        elif operation=='sample':native.scd_special_get_contacts(C.byref(p),C.byref(stage))
        elif operation=='state':native.scd_special_contact_state(*arguments,held,tapped)
        elif operation=='timer':native.scd_special_timer(C.byref(w))
        elif operation=='splash':native.scd_special_splash(C.byref(w),C.byref(p))
        else:
            native.scd_special_player_step(*arguments,C.byref(stage),held,tapped)
            native.scd_special_sprite_advance(C.byref(s),C.byref(p),C.byref(art),C.byref(Pose()))
        actual=(state(p),state(s),state(w))
        assert actual==expected,(operation,before,held,tapped,[{k:(got[k],want[k]) for k in got if got[k]!=want[k]} for got,want in zip(actual,expected)])
        digest.update(json.dumps(actual,sort_keys=True).encode());counts[operation]=counts.get(operation,0)+1
    def player(**kw):return ContactPlayer(**(dict(x=1280<<16,y=1280<<16,yaw=128<<16,sprite_y=344<<16,z=352,top_speed=0xa00,routine=1)|kw))
    for mask in range(16):
        for speed in [0,0x100,0xa00,0xffff]:
            p=player(speed=speed,stamp_tl=1 if mask&1 else 0,stamp_tr=1 if mask&2 else 0,stamp_br=1 if mask&4 else 0,stamp_bl=1 if mask&8 else 0)
            check('bumper',p,Sprite(animation=13,frame=4,time=1),World())
    for n in range(2048):
        mask=n%16;kind=rng.choice(list(range(10))+[255]);p=player(speed=rng.randrange(65536),routine=rng.choice([1,4,7,19]),hurt=rng.randrange(256),orientation=n%16,flags=rng.randrange(256),x_velocity=rng.getrandbits(32),y_velocity=rng.getrandbits(32),stamp_c=kind,stamp_tl=1 if mask&1 else 0,stamp_tr=1 if mask&2 else 0,stamp_br=1 if mask&4 else 0,stamp_bl=1 if mask&8 else 0)
        w=World(rings=rng.choice([0,1,2,3,4,5,6,7,8,13,14,999,65535]),ufo_count=0 if n%7==0 else 6,stopped=n%5==0,time_attack=n%2,splash_id=8,splash_flags=n%8)
        w.dust[:]=[rng.choice([0,1,0x700]) for _ in range(8)];w.sound[:]=[rng.choice([0,0x92]) for _ in range(3)];w.lost_rings[:]=[rng.randrange(16) for _ in range(7)]
        check('contacts',p,Sprite(animation=10,frame=0,time=255,time_copy=255),w)
    for routine in list(range(1,24)):
        for n in range(128):
            # Time-stone routines use full byte timers and sprite heights at both sides of 344/448.
            p=player(routine=routine,x_velocity=rng.getrandbits(32),y_velocity=rng.getrandbits(32),bump_time=n%5,hurt=n%5 if n%8 else rng.randrange(256),jump_timer=n%21,sprite_velocity=rng.getrandbits(32),flags=rng.randrange(256),yaw=rng.getrandbits(32),sprite_y=rng.choice([343,344,345,447,448,65535])<<16|rng.randrange(65536),speed=rng.randrange(65536))
            check('state',p,Sprite(animation=13,time=1),World(inactive=n%3==0,splash_id=8),held=n,tapped=(n*7)&255)
    for routine in range(3):
        for n in range(128):
            w=World(splash_id=8,splash_routine=routine,splash_animation=0 if routine<2 else 1,splash_frame=n%(7 if routine<2 else 3),splash_time=(n*17)&255,splash_timer=n%17,splash_flags=n%8,time_attack=n%2,stopped=n%7==0,speedup=n%11)
            check('splash',player(stamp_c=3 if n%3 else 0),Sprite(),w)
    water=[]
    for attack in [0,1]:
        p=player(stamp_c=3);s=Sprite();w=World(timer=100 if not attack else 0,timer_frames=20,ufo_count=6,time_attack=attack)
        for tick in range(80):
            check('splash',p,s,w);check('contacts',p,s,w);check('timer',p,s,w)
        water.append({'time_attack':attack,'timer_after_80_updates':w.timer,'splash_routine':w.splash_routine})
        if not attack:assert w.timer<85
        p.stamp_c=0
        for tick in range(20):check('splash',p,s,w);check('timer',p,s,w)
        assert not w.splash_id
    for id in range(1,9):
        components=parts(id);buf=C.create_string_buffer(pack(id));assert native.scd_special_open(C.byref(stage),buf,len(buf))==0
        for n in range(128):check('sample',player(x=rng.randrange(832,3265)<<16,y=rng.randrange(832,3265)<<16),Sprite(),World())
        p=player(x=int.from_bytes(components[4][:2],'big')<<16,y=int.from_bytes(components[4][2:4],'big')<<16);s=Sprite(tilt=5,animation=10,time=255,time_copy=255);w=World(timer=100,timer_frames=20,ufo_count=6,rings=99)
        for tick in range(180):
            held=(4 if tick<30 else 8 if tick<75 else 2 if tick<100 else 0)|(16 if 110<=tick<125 else 0)
            check('splash',p,s,w);check('step',p,s,w,held,16 if tick==110 else 0);check('timer',p,s,w)
        print('Original contact route:',id,'PASS',flush=True)
    for n in range(512):
        w=World(timer=rng.choice([0,1,14,15,19,20,100,0xffffffff,0x93b39,0x93b3a,0x93b3b,0xff3b3b]),timer_frames=n%23,speedup=n%12,time_attack=n%2,stopped=n%7==0,inactive=n%11==0,time_ufo=n%3)
        w.sound[:]=[0x92,0x93,0x94];check('timer',player(),Sprite(),w)
    report={'passed':True,'sanitizer_states':66688,'original_calls':counts,'water_routes':water,'state_sha256':digest.hexdigest(),'limits':'Original active Sonic/contact/splash/timer routines. CheckWin is stubbed until UFO completion; only the time-UFO spawn ID marker is compared. Dust/lost-ring spawn slots are checked here; their later motion/drawing is separate.'}
    (ROOT/'build/special-reference/contact-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
