#!/usr/bin/env python3
"""Full native actor-effect loop against composed original object dispatch."""
import ctypes as C,hashlib,json,subprocess
from special_assets import ROOT,parts,pack
from special_effect_loop_reference import EffectLoopReference
from test_special_effect_dispatch import Pool
from test_special_contacts import ContactPlayer,World,state
from test_special_sprite import Art,Sprite,Pose
from test_special_effects import state as effect_state
from special_sonic_assets import pack as sonic_pack
from test_special import Stage

def main():
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-dynamiclib','src/special.c','src/special_player.c','src/special_sprite.c','src/special_contacts.c','src/special_effects.c','src/special_effects_runtime.c','-o','build/special-effect-loop.dylib'],cwd=ROOT,check=True)
    n=C.CDLL(str(ROOT/'build/special-effect-loop.dylib'));n.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t];n.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
    n.scd_special_player_step.argtypes=[C.POINTER(ContactPlayer),C.POINTER(Sprite),C.POINTER(Art),C.POINTER(World),C.POINTER(Stage),C.c_uint,C.c_uint]
    n.scd_special_sprite_advance.argtypes=[C.POINTER(Sprite),C.POINTER(ContactPlayer),C.POINTER(Art),C.POINTER(Pose)];n.scd_special_timer.argtypes=[C.POINTER(World)]
    n.scd_special_effects_before.argtypes=[C.POINTER(Pool),C.POINTER(World),C.POINTER(ContactPlayer)];n.scd_special_effects_after.argtypes=[C.POINTER(Pool),C.POINTER(World),C.POINTER(ContactPlayer),C.c_uint];n.scd_special_effects_hash.argtypes=[C.POINTER(Pool)];n.scd_special_effects_hash.restype=C.c_uint32
    art=Art();ab=C.create_string_buffer(sonic_pack()[0]);assert not n.scd_special_art_open(C.byref(art),ab,len(ab));reference=EffectLoopReference();digest=hashlib.sha256();updates=0;visible=set()
    for id in [1,6]:
        components=parts(id);data=C.create_string_buffer(pack(id));stage=Stage();assert not n.scd_special_open(C.byref(stage),data,len(data))
        def stamp(x,y):
            raw=int.from_bytes(components[1][((y>>5)*128+(x>>5))*2:][:2],'big');return components[2][(raw&2047)>>2]
        for kind in range(1,9):
            x,y=next((x,y) for y in range(848,3264,32) for x in range(848,3264,32) if stamp(x,y)==kind)
            p=ContactPlayer(x=(x<<16)|0x1234,y=(y<<16)|0x5678,yaw=128<<16,sprite_y=344<<16,z=352,top_speed=0xa00,routine=1,x_velocity=0x89ab,y_velocity=0xcdef);s=Sprite(tilt=5,animation=10,time=255,time_copy=255);w=World(timer=100,timer_frames=20,ufo_count=6,rings=99);pool=Pool();reference.reset()
            for tick in range(100):
                w.sound[:]=[0,0,0];held=4 if 40<=tick<55 else 8 if 55<=tick<70 else 0;tapped=16 if tick==80 else 0
                expected=reference.step(state(p),state(s),state(w),components,held,tapped)
                n.scd_special_effects_before(C.byref(pool),C.byref(w),C.byref(p));n.scd_special_player_step(C.byref(p),C.byref(s),C.byref(art),C.byref(w),C.byref(stage),held,tapped);n.scd_special_sprite_advance(C.byref(s),C.byref(p),C.byref(art),C.byref(Pose()));n.scd_special_effects_after(C.byref(pool),C.byref(w),C.byref(p),held);n.scd_special_timer(C.byref(w))
                actual=(state(p),state(s),state(w));assert actual==expected,('composed actor state',id,kind,tick,[{k:(a[k],e[k]) for k in a if a[k]!=e[k]} for a,e in zip(actual,expected)])
                assert [effect_state(e) for e in pool.dust]==reference.dust,('dust',id,kind,tick)
                assert [effect_state(e) for e in pool.rings]==reference.rings,('rings',id,kind,tick)
                assert [effect_state(e) for e in pool.drawn]==reference.drawn,('draws',id,kind,tick,[{k:(a[k],e[k]) for k in a if a[k]!=e[k]} for a,e in zip([effect_state(e) for e in pool.drawn],reference.drawn)])
                target=n.scd_special_effects_hash(C.byref(pool));assert target==reference.hash(),('pool hash',id,kind,tick)
                visible.update(e.id for e in pool.drawn if e.id and not e.flags&4);digest.update(json.dumps(actual,sort_keys=True).encode());digest.update(target.to_bytes(4,'big'));updates+=1
            print('Original composed effects:',id,kind,'PASS',flush=True)
    assert visible=={7,8,13},visible
    report={'passed':True,'updates':updates,'routes':16,'visible_effect_ids':sorted(visible),'state_sha256':digest.hexdigest(),'limits':'Composed original splash/dust/Sonic/shadow/ring/timer calls; stage map animation and Saturn rendering checked separately.'}
    (ROOT/'build/special-reference/effect-loop-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
