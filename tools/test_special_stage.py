#!/usr/bin/env python3
"""Native special-stage object dispatch against complete original updates."""
import ctypes as C,hashlib,json,subprocess
from special_assets import ROOT,parts,pack
from special_sonic_assets import pack as sonic_pack
from special_effect_assets import pack as sfx_pack
from special_ufo_assets import pack as ufx_pack,paths as ufo_paths
from special_stage_reference import StageReference,fnv_words,effects_hash
from special_effect_reference import FIELDS
from test_special_contacts import ContactPlayer,World,state
from test_special_sprite import Art,Sprite,Pose
from test_special_effect_dispatch import Pool
from test_special import Stage
SOURCES=['src/special.c','src/special_player.c','src/special_sprite.c','src/special_contacts.c','src/special_effects.c','src/special_effects_runtime.c','src/special_ufo.c','src/special_stage.c']
UFO_WORDS=168 # item, eight explosions and three time-stone actors precede UFOs.
def ufo_word(words,index,field):return words[UFO_WORDS+24*index+['x','y','x_velocity','y_velocity','sprite_x','sprite_y','path_offset','path_time','z','id','flags','player_collision','item','unknown','timer','routine'].index(field)]
def main():
    subprocess.run(['python3','tools/special_ufo_assets.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['python3','tools/special_effect_assets.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['bash','tools/build-m68k-reference.sh'],cwd=ROOT,check=True)
    opts=['clang','-std=c11','-Wall','-Wextra','-Werror','-fwrapv','-Isrc','-Iassets/generated']
    subprocess.run(opts+['-O2','-dynamiclib']+SOURCES+['-o','build/special-stage.dylib'],cwd=ROOT,check=True)
    subprocess.run(opts+['-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','tools/special_stage_sanitize.c']+SOURCES+['-o','build/special-stage-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-stage-sanitize'],cwd=ROOT,check=True)
    n=C.CDLL(str(ROOT/'build/special-stage.dylib'))
    n.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t];n.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    n.scd_special_stage_reset.argtypes=[C.c_void_p,C.POINTER(World),C.c_void_p,C.c_size_t,C.c_uint]
    n.scd_special_stage_update.argtypes=[C.c_void_p,C.POINTER(World),C.POINTER(ContactPlayer),C.POINTER(Sprite),C.POINTER(Art),C.POINTER(Art),C.POINTER(Art),C.POINTER(Stage),C.c_uint,C.c_uint,C.c_uint,C.POINTER(Pose),C.POINTER(C.c_int)]
    n.scd_special_stage_words.argtypes=[C.c_void_p,C.POINTER(C.c_uint32)];n.scd_special_stage_words.restype=C.c_uint
    n.scd_special_stage_hash.argtypes=[C.c_void_p];n.scd_special_stage_hash.restype=C.c_uint32
    n.scd_special_effects_hash.argtypes=[C.POINTER(Pool)];n.scd_special_effects_hash.restype=C.c_uint32
    n.scd_special_sprite_set.argtypes=[C.POINTER(Sprite),C.POINTER(Art),C.c_uint,C.c_int]
    n.scd_special_stage_start.argtypes=[C.c_void_p,C.POINTER(World),C.POINTER(ContactPlayer),C.POINTER(Sprite)]
    buffers=[];arts={}
    for name,data in [('sonic',sonic_pack()[0]),('sfx',sfx_pack()[0]),('ufx',ufx_pack()[0])]:
        b=C.create_string_buffer(data);buffers.append(b);arts[name]=Art();assert n.scd_special_art_open(C.byref(arts[name]),b,len(data))==0
    path_data=ufo_paths()[0];path_buffer=C.create_string_buffer(path_data)
    ref=StageReference();digest=hashlib.sha256();report={'routes':[],'forced':{}};totals={'updates':0,'draws':0}
    seen_codes=set();seen_routines=set();full_pool=0;overwrites=0
    def run(label,stage_id,updates,controls,seed=None,world=None,stop=None,program_start=False):
        nonlocal full_pool,overwrites
        components=parts(stage_id);data=C.create_string_buffer(pack(stage_id));stage=Stage();assert n.scd_special_open(C.byref(stage),data,len(data))==0
        start=components[4];p=ContactPlayer(x=int.from_bytes(start[:2],'big')<<16,y=int.from_bytes(start[2:4],'big')<<16,yaw=int.from_bytes(start[4:6],'big')<<16,sprite_y=344<<16,z=352,top_speed=0xa00,routine=1)
        s=Sprite(tilt=5);n.scd_special_sprite_set(C.byref(s),C.byref(arts['sonic']),10,1)
        w=World(timer=100,timer_frames=20,rings=5)
        for key,value in (world or {}).items():setattr(w,key,value)
        st=C.create_string_buffer(65536);assert n.scd_special_stage_reset(st,C.byref(w),path_buffer,len(path_data),stage_id-1)==0
        if program_start:n.scd_special_stage_start(st,C.byref(w),C.byref(p),C.byref(s))
        ref.reset(stage_id,state(p),state(s),state(w),components,program_start)
        pool=Pool.from_buffer(st);words=(C.c_uint32*2048)();pose=Pose();visible=C.c_int();expected=None;log=[]
        for tick in range(updates):
            held,tapped=controls(tick)
            if seed and expected and seed(tick,p,w,expected):ref.write_actor(state(p),state(s),state(w))
            w.sound[:]=[0,0,0];yaw=p.yaw>>16
            expected=ref.step(held,tapped)
            assert n.scd_special_stage_update(st,C.byref(w),C.byref(p),C.byref(s),C.byref(arts['sonic']),C.byref(arts['ufx']),C.byref(arts['sfx']),C.byref(stage),held,tapped,yaw,C.byref(pose),C.byref(visible))==0
            actual=(state(p),state(s),state(w));want=(expected['player'],expected['sprite'],expected['world'])
            assert actual==want,(label,tick,[{k:(a[k],b[k]) for k in a if a[k]!=b[k]} for a,b in zip(actual,want)])
            e=expected['effects']
            for group in ['dust','rings','drawn']:
                got=[{name:getattr(x,name) for name in FIELDS} for x in getattr(pool,group)]
                assert got==e[group],(label,tick,group,[(i,{k:(g[k],v[k]) for k in g if g[k]!=v[k]}) for i,(g,v) in enumerate(zip(got,e[group])) if g!=v])
            assert (pool.context.seed,pool.context.ring_direction,pool.previous_held)==(e['seed'],e['ring_direction'],e['previous_held']),(label,tick,'context')
            count=n.scd_special_stage_words(st,words);native=list(words[:count])
            if native!=expected['words']:
                first=next(i for i,(a,b) in enumerate(zip(native+[None],expected['words']+[None])) if a!=b)
                raise AssertionError((label,tick,'stage words',first,native[max(0,first-4):first+8],expected['words'][max(0,first-4):first+8],expected['draws'][:4]))
            assert n.scd_special_stage_hash(st)==fnv_words(expected['words']) and n.scd_special_effects_hash(C.byref(pool))==effects_hash(e),(label,tick,'hash')
            assert expected['sprite_count']<80,(label,tick,'sprite table cap reached; target does not model it')
            codes={d[7] for d in expected['draws'] if d[6]};seen_codes.update(codes);seen_routines.add(p.routine)
            full_pool+=all(expected['words'][14+14*i+5] for i in range(8))
            if expected['words'][5]==4 and expected['words'][6]==1 and any(ufo_word(expected['words'],i,'routine')==2 and ufo_word(expected['words'],i,'timer')==60 for i in range(7)):overwrites+=1
            digest.update(json.dumps((actual,expected['words']),sort_keys=True).encode());totals['updates']+=1;totals['draws']+=len(expected['draws'])
            log.append((p.routine,w.ufo_count,w.got_time_stone,w.stopped,w.timer,sorted(codes),ufo_word(expected['words'],6,'id'),ufo_word(expected['words'],6,'routine')))
            if stop and stop(tick,p,w):break
        return log
    for stage_id in range(1,9):
        def steer(tick):
            held=4 if 20<=tick<40 else 8 if 60<=tick<90 else 2 if 100<=tick<110 else 0
            if 120<=tick<135 or 170<=tick<180:held|=16
            return held,16 if tick in (120,170) else 0
        run(f'route {stage_id}',stage_id,220,steer)
        report['routes'].append(stage_id);print('Original stage update route:',stage_id,'PASS',flush=True)
    log=run('program start',1,160,lambda t:((4 if 10<=t<60 else 8 if 100<=t<130 else 0)|(16 if t in (50,120) else 0),16 if t in (50,120) else 0),program_start=True)
    # Start2 advances to 0x16 within its own update, so 0x15 is never a post-update state.
    assert log[0][0]==0x14 and {0x14,0x16,0x17,1}<={row[0] for row in log} and {44,45}<=seen_codes,(log[0],log[-1],sorted(seen_codes));report['forced']['program_start']=True
    run('time attack',2,120,lambda t:(8 if t<50 else 0,0),world={'time_attack':1,'timer':0})
    def airborne(p,x,y):
        p.x=(x<<16)|(p.x&65535);p.y=(y<<16)|(p.y&65535);p.routine=2;p.flags=0x80;p.sprite_y=288<<16;p.sprite_velocity=0;p.z=0x240;p.speed=0;p.jump_timer=0
    def hit(targets):
        def seed(tick,p,w,e):
            if tick not in targets:return False
            i=targets[tick];airborne(p,ufo_word(e['words'],i,'x')>>16,ufo_word(e['words'],i,'y')>>16);return True
        return seed
    idle=lambda t:(0,0)
    log=run('ring UFO',1,90,idle,hit({5:0}));assert log[-1][1]==5;report['forced']['ring']=True
    log=run('shoes UFO',1,90,idle,hit({5:2}));assert log[-1][1]==5;report['forced']['shoes']=True
    log=run('double hit',1,90,idle,hit({5:0,6:1}));assert log[-1][1]==4;report['forced']['double']=True
    log=run('time UFO',1,120,idle,hit({4:6}),world={'timer':19,'timer_frames':1});assert log[5][4]>=40,log[:8];report['forced']['time']=True
    def stopped_hit(tick,p,w,e):
        if tick!=4:return False
        airborne(p,ufo_word(e['words'],6,'x')>>16,ufo_word(e['words'],6,'y')>>16);w.stopped=1;return True
    log=run('time UFO stopped',1,60,idle,stopped_hit,world={'timer':19,'timer_frames':1});assert log[-1][4]==18 and log[-1][6:]==(3,1) and log[-1][1]==6,log[-3:];report['forced']['time_stopped']=True
    progress={'next':0,'wait':0}
    def win(tick,p,w,e):
        if not w.ufo_count or tick<4:return False
        progress['wait']-=1
        if p.routine!=1 or progress['wait']>0:return False
        for i in range(6):
            if ufo_word(e['words'],i,'id') and ufo_word(e['words'],i,'routine')==1:
                x,y=ufo_word(e['words'],i,'x')>>16,ufo_word(e['words'],i,'y')>>16
                if 840<=x<3250 and 840<=y<3250:airborne(p,x,y);progress['wait']=24;return True
        return False
    log=run('win path',1,1400,idle,win,world={'timer':19,'timer_frames':1},stop=lambda t,p,w:w.got_time_stone)
    routines={row[0] for row in log}
    assert ref.skipped>=1,'CheckWin did not clear a queued time UFO'
    assert log[-1][2]==1 and set(range(8,19))<=routines,(log[-1],sorted(routines))
    assert {3,4,5}<=seen_codes,sorted(seen_codes)
    report['forced']['win_updates']=len(log)
    assert {1,14,22,30,36,37,43}<=seen_codes and full_pool and overwrites,(sorted(seen_codes),full_pool,overwrites)
    report.update(passed=True,updates=totals['updates'],draw_calls=totals['draws'],visible_draw_objects=sorted(seen_codes),full_explosion_pool_updates=full_pool,item_overwrites=overwrites,cleared_time_ufo_draws_skipped=ref.skipped,state_sha256=digest.hexdigest(),limits='Whole original RunObjects/UpdateTimer update with persistent RAM, including the program start (title card and start poses). The Main CPU program is checked against retail runs by tools/test_special_game.py. The cleared time UFO drawn after CheckWin is skipped natively.')
    (ROOT/'build/special-reference/stage-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
