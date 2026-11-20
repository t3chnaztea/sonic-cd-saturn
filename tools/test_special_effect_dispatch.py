#!/usr/bin/env python3
"""Grounded hazard -> Sonic shadow -> original ring pool register/lifetime QA."""
import ctypes as C,hashlib,json,subprocess
from special_assets import ROOT,parts
from special_contact_reference import ContactReference
from special_effect_reference import EffectReference
from test_special_contacts import ContactPlayer,World,state
from test_special_effects import Effect,Context
from test_special_sprite import Sprite
class Pool(C.Structure):_fields_=[('context',Context),('dust',Effect*8),('rings',Effect*7),('drawn',Effect*16),('previous_held',C.c_uint)]
def main():
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-dynamiclib','src/special.c','src/special_player.c','src/special_sprite.c','src/special_contacts.c','src/special_effects.c','src/special_effects_runtime.c','-o','build/special-effect-dispatch.dylib'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-effect-dispatch.dylib'))
    native.scd_special_effects_after.argtypes=[C.POINTER(Pool),C.POINTER(World),C.POINTER(ContactPlayer),C.c_uint]
    source=ContactReference();effects=EffectReference(source.r);components=parts(1)
    def stamp(x,y):
        raw=int.from_bytes(components[1][((y>>5)*128+(x>>5))*2:][:2],'big');return components[2][(raw&2047)>>2]
    x,y=next((x,y) for y in range(848,3264,32) for x in range(848,3264,32) if stamp(x,y)==6)
    digest=hashlib.sha256();cases=0;ring_calls=0;cleared_before_spawn=0
    for n in range(256):
        p=state(ContactPlayer(x=x<<16,y=y<<16,yaw=128<<16,sprite_y=344<<16,z=352,top_speed=0xa00,speed=(n*113)&65535,routine=1,shoes=n%2));s=state(Sprite(tilt=5,animation=10,time=255,time_copy=255));w=World(timer=100,timer_frames=20,ufo_count=6,rings=[0,1,2,3,7,14,99,65535][n%8]);pool=Pool(context=Context(seed=(n*0x1234567)&0xffffffff,ring_direction=n&255))
        if n%3==0:
            # An earlier existing ring expires before a newly initialized slot.
            pool.rings[0]=Effect(id=13,routine=1,animation=4,time=4,time_copy=4,timer=0x0100,item_type=4,x=256<<16,y=340<<16);w.lost_rings[0]=13;cleared_before_spawn+=1
        p,s,expected_world=source.run('step',p,s,state(w),components)
        d1=source.r.lib.s68k_get_reg(1)&0xffffffff;after_shadow=effects.shadow_d1(d1)
        predicted=(((p['speed']<<8)+0x20000)&0xffff0000)|1
        assert after_shadow==predicted,('original Sonic/shadow retained D1',n,hex(d1),hex(after_shadow),hex(predicted))
        before_world={k:list(v) if isinstance(v,list) else v for k,v in expected_world.items()}
        context=state(pool.context);context['d1']=after_shadow;expected_rings=[];drawn=[]
        for i in range(7):
            actor=state(pool.rings[i]);actor['id']=expected_world['lost_rings'][i]
            visual=effects.run(actor,context,sonic_y=p['sprite_y'],operation='actor',sounds=expected_world['sound'])[0] if actor['id'] else state(Effect())
            actor,context,sat,sounds,_=effects.run(actor,context,sonic_y=p['sprite_y'],sounds=expected_world['sound']);expected_world['sound']=sounds;expected_world['lost_rings'][i]=actor['id'];expected_rings.append(actor);drawn.append(visual);ring_calls+=1
        # Native receives the same post-Sonic world; it derives the register
        # dependency itself, rather than receiving the source D1 value.
        native_world=World(**{k:v for k,v in before_world.items() if not isinstance(v,list)})
        for field in ['dust','sound','lost_rings']:getattr(native_world,field)[:]=before_world[field]
        native.scd_special_effects_after(C.byref(pool),C.byref(native_world),C.byref(ContactPlayer(**p)),0)
        assert state(native_world)==expected_world,('world',n,state(native_world),expected_world)
        assert state(pool.context)==context,('context',n,state(pool.context),context)
        assert [state(e) for e in pool.rings]==expected_rings,('ring states',n)
        assert [state(e) for e in pool.drawn][9:]==drawn,('ring final draw',n)
        digest.update(json.dumps((expected_world,context,expected_rings,drawn),sort_keys=True).encode());cases+=1
    report={'passed':True,'hazard_shadow_cases':cases,'original_ring_slot_calls':ring_calls,'expired_first_slot_cases':cleared_before_spawn,'state_sha256':digest.hexdigest(),'limits':'Original grounded hazard, original Sonic shadow, and priority-two ring slots. Other effect integration is checked separately.'}
    (ROOT/'build/special-reference/effect-dispatch-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
