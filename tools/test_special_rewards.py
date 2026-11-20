#!/usr/bin/env python3
"""Original UFO item/explosion lifetimes, final draw and pool allocation."""
import ctypes as C,hashlib,json,random,subprocess
from special_assets import ROOT
from special_effect_reference import EffectReference
from test_special_effects import Effect,Context,state

def main():
    subprocess.run(['bash','tools/build-m68k-reference.sh'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-dynamiclib','src/special_effects.c','-o','build/special-rewards.dylib'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','tools/special_reward_sanitize.c','src/special_effects.c','-o','build/special-rewards-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-rewards-sanitize'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-rewards.dylib'))
    native.scd_special_item.argtypes=[C.POINTER(Effect),C.POINTER(Context),C.POINTER(Effect),C.POINTER(C.c_uint)]
    native.scd_special_explosion.argtypes=[C.POINTER(Effect),C.POINTER(Context),C.POINTER(Effect),C.POINTER(C.c_uint)]
    native.scd_special_explosion_slot.argtypes=[C.POINTER(Effect)]
    ref=EffectReference();rng=random.Random(300412);counts={};digest=hashlib.sha256()
    def check(kind,e,c,spawn=0,sounds=(0,0,0)):
        before=state(e),state(c)
        expected,context,_,queue,_=ref.run(*before,operation='step',sounds=sounds)
        drawn=ref.run(*before,operation='actor',sounds=sounds)[0] if e.id else state(Effect())
        out=Effect();sound=C.c_uint()
        if kind=='item':native.scd_special_item(C.byref(e),C.byref(c),C.byref(out),C.byref(sound))
        else:native.scd_special_explosion(C.byref(e),C.byref(c),C.byref(out),C.byref(sound))
        assert state(e)==expected and state(c)==context,(kind,before,[{k:(a[k],b[k]) for k in a if a[k]!=b[k]} for a,b in [(state(e),expected),(state(c),context)]])
        assert state(out)==drawn,('draw',kind,before,state(out),drawn)
        expected_queue=list(sounds)
        if sound.value and 0 in expected_queue:expected_queue[expected_queue.index(0)]=sound.value
        assert queue==expected_queue,(kind,queue,expected_queue)
        digest.update(json.dumps((expected,context,drawn,queue),sort_keys=True).encode());counts[kind]=counts.get(kind,0)+1
    for kind,id in [('item',4),('explosion',12)]:
        for n in range(2048):
            e=Effect(id=id if n%17 else 0,routine=n%2,x=rng.getrandbits(32),y=rng.getrandbits(32),x_velocity=rng.getrandbits(32),y_velocity=rng.getrandbits(32),timer=(rng.getrandbits(8)<<8)|(n%4),flags=n%8,animation=n%4 if id==4 else 0,frame=0 if id==4 else n%5,time=rng.getrandbits(8),time_copy=255 if id==4 else 2,art=29,item_type=n%4)
            c=Context(seed=rng.getrandbits(32),d1=rng.getrandbits(32),ring_direction=n&255)
            check(kind,e,c,n%4,tuple(0 if n&(1<<i) else 0x90+i for i in range(3)))
        for n in range(64):
            e=Effect(id=id,x=0x1001234,y=0x1585678,y_velocity=0x89ab,timer=0xcd00|(n%4));c=Context(d1=rng.getrandbits(32));ticks=0
            while e.id:check(kind,e,c,n%4);ticks+=1;assert ticks<=16
            assert ticks==(16 if id==4 else 12)
    # Every occupancy subset; nonzero routine alone also occupies the word.
    for bits in range(256):
        for routine_only in [False,True]:
            pool=(Effect*8)()
            for i in range(8):
                if bits&(1<<i):
                    if routine_only:pool[i].routine=1
                    else:pool[i].id=12
            got=native.scd_special_explosion_slot(pool);expected=ref.find_explosion([(e.id,e.routine) for e in pool]);assert got==expected
            digest.update(bytes([got&255]));counts['pool']=counts.get('pool',0)+1
    report={'passed':True,'original_calls':counts,'original_pre_deletion_calls':sum(counts[k] for k in ['item','explosion']),'sanitizer_states':131072,'state_sha256':digest.hexdigest(),'limits':'Standalone source item/explosion state, sound requests and allocation. UFO actor integration, explosion-art import and Saturn composites remain separate work.'}
    (ROOT/'build/special-reference/reward-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
