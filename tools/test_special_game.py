#!/usr/bin/env python3
"""Native special-stage program flow against retail special stage runs.

tools/special_retail.py records the retail programs in the pinned Sega CD
core. The native Main CPU flow (src/special_game.c) runs the same pad script
one V-INT at a time with native Sub CPU updates; the original Sub CPU update
runs in lockstep in the offline 68000 for sprite tables. Every V-INT compares
CRAM, both name tables, the H-scroll table, VSRAM, display mode, the sprite
table on screen and the Main CPU variables. Routes named <route>-ss<n> play
stage n; 'stages' runs the steering route on stages 1-7, 'wins' and
'hazards' the stored win-ss2..7 and hazard-ss1..7 routes (tests/routes/special).
"""
import ctypes as C,json,struct,subprocess,sys
from special_assets import ROOT,parts,pack
from special_sonic_assets import pack as sonic_pack
from special_effect_assets import pack as sfx_pack
from special_ufo_assets import pack as ufx_pack,paths as ufo_paths
from special_main_assets import pack as main_pack,demo as main_demo
from special_stage_reference import StageReference,fnv_words
from test_special_contacts import ContactPlayer,World,state
from test_special_sprite import Art,Sprite,Pose
from test_special import Stage
from test_special_stage import SOURCES
import special_retail
# Stamp types (ObjSonic_StampCollide .Types) and Sonic routines (ObjSonic_Index), Objects/Sonic/Main.asm.
STAMPS=dict(enumerate(['path','bumper','fan','water','rough','spring','hazard','big_booster','small_booster','oil']))
MODES={0:'init',1:'ground',2:'jump',3:'float',4:'bumped',5:'sink',6:'sink2',7:'hurt',**{n:'stone' for n in range(8,13)}}
VIA_FE=False
PHASES=('fade_in','loop','pause','exit_fade','results_fade_in','results','results_fade_out','done')
class Animation(C.Structure):_fields_=[('fan',C.c_uint16),('hazard',C.c_uint16),('delay',C.c_uint16)]
class MainPack(C.Structure):_fields_=[('data',C.c_void_p),('size',C.c_uint32),('offset',C.c_uint32*11),('length',C.c_uint32*11),('stage',C.c_uint16)]
class Main(C.Structure):_fields_=[('palette',C.c_uint16*64),('fade',C.c_uint16*64),('plane_a',C.c_uint16*2048),('plane_b',C.c_uint16*2048),
    ('hscroll',C.c_uint16*256),('hscroll_frac',C.c_uint16*256),('display',C.c_uint16*256),('scroll_offset',C.c_uint32*6),
    ('shift',C.c_uint16),('cycle_index',C.c_uint16),('results_timer',C.c_uint16),('extra_players',C.c_uint16),('icon_frame',C.c_uint16),('icon_timer',C.c_uint16),
    ('scroll_mode',C.c_uint8),('scroll_flags',C.c_uint8),('stone_delay',C.c_uint8),('scroll_disable',C.c_uint8),('time_attack',C.c_uint8),('stage',C.c_uint8),('score_tallied',C.c_uint8),('time_stones',C.c_uint8),
    ('ring_bonus',C.c_uint32),('time_bonus',C.c_uint32),('score',C.c_uint32),('next_life',C.c_uint32),('lives',C.c_uint8),('dirty',C.c_uint32*2),('wave',C.c_uint16),('cycle',(C.c_uint16*4)*8)]
UPDATE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint,C.c_uint)
class Game(C.Structure):_fields_=[('main',Main),('pack',C.c_void_p),('world',C.c_void_p),('player',C.c_void_p),('update',UPDATE),('context',C.c_void_p),
    ('cram',C.c_uint16*64),('hscroll',C.c_uint16*448),('stage_scroll',C.c_uint16*2),
    ('vint',C.c_uint16),('routine',C.c_uint16),('ctrl',C.c_uint16),('saved_ctrl',C.c_uint16),('saved_routine',C.c_uint16),('step',C.c_uint16),('half',C.c_uint16),('vsram_a',C.c_uint16),
    ('phase',C.c_uint8),('sub',C.c_uint8),('paused',C.c_uint8),('display',C.c_uint8),('h40',C.c_uint8),('cram_dirty',C.c_uint8),('sub_over',C.c_uint8),('pending_over',C.c_uint8),
    ('lost',C.c_uint8),('next_stage',C.c_uint8),('stage',C.c_uint8),('time_stones',C.c_uint8),('music',C.c_uint8),('fm_count',C.c_uint8),('fm',C.c_uint8*6),
    ('updates',C.c_int32),('copied',C.c_int32),('image',C.c_int32*2),('shown_image',C.c_int32),('shown_sprites',C.c_int32),('exit_timer',C.c_uint32),('exit_rings',C.c_uint16)]

def retail_frames(route):
    """Last recorded frame of every V-INT, split at the results screen's variable clear."""
    folder=ROOT/'build/special-retail';rows=[json.loads(line) for line in (folder/f'{route}.jsonl').open()]
    blobs=json.loads((folder/f'{route}-blobs.json').read_text());phase='stage';frames={}
    for row in rows:
        if row['routine']==5:phase='results'
        frames[(phase,row['v'])]=row
    return frames,blobs

def main():
    # --fe: run the program through the front-end overlay copy (src/special_modes.c,
    # fe_special_zone_ops.vint) instead of the resident one; both must match retail.
    global VIA_FE;VIA_FE='--fe' in sys.argv
    if VIA_FE:sys.argv.remove('--fe')
    route=sys.argv[1] if len(sys.argv)>1 else 'timeout'
    sets={'stages':[f'steer-ss{n}' for n in range(1,8)],'wins':[f'win-ss{n}' for n in range(2,8)],'hazards':[f'hazard-ss{n}' for n in range(1,8)]}
    for name in sets.get(route,[route]):run(name)

def run(route):
    _,_,stage_number=special_retail.route_spec(route)
    if not (ROOT/f'build/special-retail/{route}.jsonl').exists():subprocess.run(['python3','tools/special_retail.py',route],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-fwrapv','-Isrc','-Iassets/generated','-dynamiclib']+SOURCES+['src/special_main.c','src/special_game.c','src/special_modes.c','-o','build/special-game.dylib'],cwd=ROOT,check=True)
    n=C.CDLL(str(ROOT/'build/special-game.dylib'))
    n.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t];n.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    n.scd_special_stage_reset.argtypes=[C.c_void_p,C.POINTER(World),C.c_void_p,C.c_size_t,C.c_uint]
    n.scd_special_stage_start.argtypes=[C.c_void_p,C.POINTER(World),C.POINTER(ContactPlayer),C.POINTER(Sprite)]
    n.scd_special_stage_update.argtypes=[C.c_void_p,C.POINTER(World),C.POINTER(ContactPlayer),C.POINTER(Sprite),C.POINTER(Art),C.POINTER(Art),C.POINTER(Art),C.POINTER(Stage),C.c_uint,C.c_uint,C.c_uint,C.POINTER(Pose),C.POINTER(C.c_int)]
    n.scd_special_stage_words.argtypes=[C.c_void_p,C.POINTER(C.c_uint32)];n.scd_special_stage_words.restype=C.c_uint
    n.scd_special_sprite_set.argtypes=[C.POINTER(Sprite),C.POINTER(Art),C.c_uint,C.c_int]
    n.scd_special_cache.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t];n.scd_special_cache.restype=C.c_size_t
    n.scd_special_animate.argtypes=[C.POINTER(Stage),C.POINTER(Animation),C.c_void_p,C.c_void_p,C.c_void_p]
    n.scd_special_main_open.argtypes=[C.POINTER(MainPack),C.c_void_p,C.c_size_t]
    n.scd_special_game_start.argtypes=[C.POINTER(Game),C.POINTER(MainPack),C.POINTER(World),C.POINTER(ContactPlayer),UPDATE,C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint8,C.c_uint8,C.c_uint8]
    n.scd_special_game_vint.argtypes=[C.POINTER(Game),C.c_uint]
    keep=[];arts={}
    for name,data in [('sonic',sonic_pack()[0]),('sfx',sfx_pack()[0]),('ufx',ufx_pack()[0])]:
        b=C.create_string_buffer(data);keep.append(b);arts[name]=Art();assert n.scd_special_art_open(C.byref(arts[name]),b,len(data))==0
    path_data=ufo_paths()[0];path_buffer=C.create_string_buffer(path_data)
    blob=main_pack(stage_number)[0];main_buffer=C.create_string_buffer(blob);main=MainPack();assert n.scd_special_main_open(C.byref(main),main_buffer,len(blob))==0
    components=parts(stage_number);stage_data=C.create_string_buffer(pack(stage_number));stage=Stage();assert n.scd_special_open(C.byref(stage),stage_data,len(stage_data))==0
    cache=C.create_string_buffer(0x80000);assert n.scd_special_cache(C.byref(stage),cache,0x80000)>0
    cached_map=C.create_string_buffer(32768);C.memmove(cached_map,cache,32768)
    start=components[4];p=ContactPlayer(x=int.from_bytes(start[:2],'big')<<16,y=int.from_bytes(start[2:4],'big')<<16,yaw=int.from_bytes(start[4:6],'big')<<16,sprite_y=344<<16,z=352,top_speed=0xa00,routine=1)
    s=Sprite(tilt=5);n.scd_special_sprite_set(C.byref(s),C.byref(arts['sonic']),10,1)
    # IPX.asm mode entries (special_retail.route_mode): time attack counts up from 0.
    flags,_=special_retail.route_mode(route)
    w=World(timer=0 if flags&2 else 100,timer_frames=20,ufo_count=6,time_attack=flags>>1&1)
    C.memmove(C.addressof(w)+World.time_stone.offset+3,bytes([flags]),1) # scd_special_world.mode
    # fe_special_zone_ops.begin (src/special_modes.h), as src/special_game_view.inc calls it.
    if flags:
        demo=main_demo(stage_number) if flags&5==1 else None
        begin=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_char_p)(C.c_void_p.from_address(C.addressof(C.c_void_p.in_dll(n,'fe_special_zone_ops'))+1*C.sizeof(C.c_void_p)).value)
        begin(C.addressof(w),flags,demo)
    st=C.create_string_buffer(65536);assert n.scd_special_stage_reset(st,C.byref(w),path_buffer,len(path_data),stage_number-1)==0
    n.scd_special_stage_start(st,C.byref(w),C.byref(p),C.byref(s))
    ref=StageReference();ref.reset(stage_number,state(p),state(s),state(w),components,True)
    g=bytearray(ref.r.read(ref.r.prg,0x6000,64));g[6]=flags;ref.r.write(ref.r.prg,0x6000,g) # specStageFlags
    animation=Animation();pose=Pose();visible=C.c_int();words=(C.c_uint32*2048)();sats=[];speedups=[]
    errors=[];touched=set();modes=set()
    @UPDATE
    def update(context,held,tapped):
        try:return checked_update(held,tapped)
        except Exception as error:errors.append(error);return -1
    def checked_update(held,tapped):
        n.scd_special_animate(C.byref(stage),C.byref(animation),stage.part[1],cache,cached_map)
        stamp_map=C.string_at(stage.part[1],32768)
        # GetSubCPUData clears subScrollFlags in Word RAM; mirror it into the original's RAM.
        ref.r.write(ref.r.prg,0x600c,bytes([p.scroll]))
        yaw=p.yaw>>16;expected=ref.step(held,tapped,stamp_map)
        result=n.scd_special_stage_update(st,C.byref(w),C.byref(p),C.byref(s),C.byref(arts['sonic']),C.byref(arts['ufx']),C.byref(arts['sfx']),C.byref(stage),held,tapped,yaw,C.byref(pose),C.byref(visible))
        count=n.scd_special_stage_words(st,words)
        actual=(state(p),state(s),state(w));want=(expected['player'],expected['sprite'],expected['world'])
        if actual!=want:raise AssertionError(('native Sub CPU update',len(sats),held,tapped,[{k:(a[k],b[k]) for k in a if a[k]!=b[k]} for a,b in zip(actual,want)]))
        native=list(words[:count])
        if native!=expected['words']:
            first=next(i for i,(a,b) in enumerate(zip(native+[None],expected['words']+[None])) if a!=b)
            raise AssertionError(('native Sub CPU stage words',len(sats),held,tapped,first,native[max(0,first-4):first+8],expected['words'][max(0,first-4):first+8]))
        if w.ufo_count:touched.add(p.stamp_c) # StampCollide runs stamp types only while UFOs remain.
        modes.add(p.routine);sats.append(expected['sat']);speedups.append(w.speedup);return result
    pad,score,_=special_retail.route_spec(route)
    game=Game();assert n.scd_special_game_start(C.byref(game),C.byref(main),C.byref(w),C.byref(p),update,None,score,0 if flags else 5000,3,0,stage_number)==0,errors
    frames,blobs=retail_frames(route);compared=0;checked=set()
    vint=n.scd_special_game_vint
    if VIA_FE:vint=C.CFUNCTYPE(C.c_int,C.POINTER(Game),C.c_uint)(C.c_void_p.from_address(C.addressof(C.c_void_p.in_dll(n,'fe_special_zone_ops'))).value)
    def words_of(key,count):return list(struct.unpack(f'>{count}H',bytes.fromhex(blobs[key])[:count*2]))
    while True:
        phase_before=game.phase;result=vint(C.byref(game),pad(game.vint+1,game.phase>=5))
        assert result>=0,('native Sub CPU update failed',game.vint,errors)
        if result:break
        key=('results' if game.phase>=5 else 'stage',game.vint)
        if phase_before==4 and game.phase==5:continue # Variable clear inside the last exit-fade V-INT.
        row=frames.get(key);assert row,('retail V-INT missing',key)
        m=game.main;reg=bytes.fromhex(row['reg']);vsram=struct.unpack('<2H',bytes.fromhex(row['vsram']))
        checks={'routine':(game.routine,row['routine']),'cram':(list(game.cram),words_of(row['cram'],64)),
            'plane_a':(list(m.plane_a),words_of(row['plane_a'],2048)),'plane_b':(list(m.plane_b),words_of(row['plane_b'],2048)),
            'hscroll':(list(game.hscroll),words_of(row['hscroll'],448)),'vsram':((game.vsram_a,0),vsram),
            'display':(game.display,reg[1]>>6&1),'h40':(game.h40,reg[12]&1),'paused':(game.paused,row['paused']),'ctrl':(game.ctrl,row['ctrl']),
            'results_timer':(m.results_timer,row['results_timer']),'extra_players':(m.extra_players,row['extra_players']),
            'scroll':((m.shift,m.wave,m.scroll_mode,m.scroll_flags,list(m.scroll_offset)),(row['shift'],row['wave'],row['scroll_mode'],row['scroll_flags'],row['scroll_offset'])),
            'palette_state':((m.cycle_index,m.stone_delay),(row['cycle_index'],row['stone_delay'])),
            'results':((m.ring_bonus,m.time_bonus,m.score_tallied,m.scroll_disable,m.icon_frame,m.icon_timer,m.score,m.lives,m.next_life),
                (row['ring_bonus'],row['time_bonus'],row['score_tallied'],row['scroll_disable'],row['icon_frame'],row['icon_timer'],row['score'],row['lives'],row['next_life']))}
        sat=bytes.fromhex(blobs[row['sat']])
        expected_sat=sats[game.shown_sprites] if game.shown_sprites>=0 else b''
        checks['sprites']=(expected_sat,sat[:len(expected_sat)]) if expected_sat else (bytes(8),sat[:8])
        for name,(native,retail) in checks.items():
            if native!=retail:
                if isinstance(native,list):
                    first=next(i for i,(a,b) in enumerate(zip(native,retail)) if a!=b);native,retail=(first,native[first:first+6]),(first,retail[first:first+6])
                raise AssertionError((route,key,PHASES[game.phase-1],name,'native',native,'retail',retail))
        compared+=1;checked.add(key[0])
    report={'route':route,'stage':stage_number,'vints_compared':compared,'phases':sorted(checked),'sub_updates':game.updates,'score':game.main.score,'lost':game.lost,'time_stones':game.time_stones,
        'hazard_updates':sum(1 for a,b in zip([0]+speedups,speedups) if b>a),'lives':game.main.lives,'timer':game.exit_timer,'ufo_count':w.ufo_count,'stage_over':w.stage_over,
        'stamps':[STAMPS.get(x,x) for x in sorted(touched)],'modes':[MODES.get(x,x) for x in sorted(modes)]}
    print(json.dumps(report))
    # Route outcomes: a win retrieves this stage's time stone; a hazard sweep touches
    # every stamp type with UFOs left, gets hurt and times out. Mode entries (stage 8,
    # time attack, demos) report their outcome for tools/special_mode_gate.py.
    base=route.split('-ss')[0]
    # swin: the stage 8 win ends with every UFO destroyed before time runs out.
    if base=='swin':assert w.ufo_count==0 and w.stage_over,('stage 8 route did not win',report)
    if base=='win' and not flags:assert game.time_stones==1<<(stage_number-1),('no time stone',report)
    if base=='hazard' and not flags:
        assert set(report['stamps'])>=set(STAMPS[k] for k in range(1,9)) and 'hurt' in report['modes'],('stamp types missed',report)
        assert not game.time_stones,('hazard route won',report)
    return report

if __name__=='__main__':main()
