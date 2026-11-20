#!/usr/bin/env python3
"""Run native dust/ring/RNG state against the original 68000 object code."""
import ctypes as C,hashlib,json,random,subprocess
from special_assets import ROOT
from special_effect_reference import EffectReference
class Effect(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ['x','y','x_velocity','y_velocity']]+[('timer',C.c_uint16)]+[(n,C.c_uint8) for n in ['id','routine','flags','animation','frame','time','time_copy','art','item_type']]
class Context(C.Structure):_fields_=[('seed',C.c_uint32),('d1',C.c_uint32),('ring_direction',C.c_uint8)]
def state(obj):return {n:getattr(obj,n) for n,_ in obj._fields_}
def main():
    subprocess.run(['bash','tools/build-m68k-reference.sh'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-dynamiclib','src/special_effects.c','-o','build/special-effects.dylib'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','tools/special_effect_sanitize.c','src/special_effects.c','-o','build/special-effects-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-effects-sanitize'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-effects.dylib'));native.scd_special_random.argtypes=[C.POINTER(Context)];native.scd_special_random.restype=C.c_uint32
    native.scd_special_dust.argtypes=[C.POINTER(Effect),C.POINTER(Context),C.c_uint,C.POINTER(Effect)]
    native.scd_special_lost_ring.argtypes=[C.POINTER(Effect),C.POINTER(Context),C.c_uint32,C.c_uint32,C.POINTER(Effect),C.POINTER(C.c_uint)]
    original=EffectReference();rng=random.Random(29013);digest=hashlib.sha256();counts={}
    def check(kind,e,c,held=0,sonic_x=256<<16,sonic_y=344<<16):
        before=(state(e),state(c));expected,ctx,sat,sound,d0=original.run(*before,held,sonic_x,sonic_y,'random' if kind=='random' else 'step')
        visible=original.run(*before,held,sonic_x,sonic_y,'actor')[0] if kind!='random' and e.id else state(Effect())
        drawn=Effect();request=C.c_uint()
        if kind=='random':actual_random=native.scd_special_random(C.byref(c));assert actual_random==d0,(before,actual_random,d0)
        elif kind=='dust':native.scd_special_dust(C.byref(e),C.byref(c),held,C.byref(drawn))
        else:native.scd_special_lost_ring(C.byref(e),C.byref(c),sonic_x,sonic_y,C.byref(drawn),C.byref(request))
        assert state(e)==expected and state(c)==ctx,(kind,before,held,[{k:(got[k],want[k]) for k in got if got[k]!=want[k]} for got,want in [(state(e),expected),(state(c),ctx)]])
        if kind!='random':assert state(drawn)==visible,('final visible state',kind,state(drawn),visible)
        assert sound==([request.value,0,0] if request.value else [0,0,0]),(kind,sound,request.value)
        digest.update(json.dumps((expected,ctx,sound),sort_keys=True).encode());counts[kind]=counts.get(kind,0)+1
    for n in range(1024):check('random',Effect(),Context(seed=0 if n==0 else rng.getrandbits(32),d1=rng.getrandbits(32),ring_direction=n&255))
    for kind,id in [('dust',7),('ring',13)]:
        for n in range(2048):
            e=Effect(id=id,routine=n%2,x=rng.getrandbits(32),y=rng.getrandbits(32),x_velocity=rng.getrandbits(32),y_velocity=rng.getrandbits(32),timer=rng.getrandbits(16),flags=n%8,animation=0 if id==7 else 4,frame=n%(3 if id==7 else 4),time=rng.getrandbits(8),time_copy=1 if id==7 else 4,art=29,item_type=rng.getrandbits(8))
            c=Context(seed=rng.getrandbits(32),d1=rng.getrandbits(32),ring_direction=n&255)
            check(kind,e,c,n&15,sonic_x=rng.getrandbits(32),sonic_y=rng.getrandbits(32))
        for n in range(64):
            e=Effect(id=id);c=Context(seed=n*0x1234567,d1=(n*0x789ab)&0xffffffff,ring_direction=n&255)
            ticks=0
            while e.id:
                check(kind,e,c,n&15);ticks+=1;assert ticks<=45
            assert ticks==(6 if id==7 else 45)
        print('Original effect:',kind,'PASS',flush=True)
    report={'passed':True,'sanitizer_states':131072,'original_calls':counts,'original_pre_deletion_calls':counts['dust']+counts['ring'],'state_sha256':digest.hexdigest(),'limits':'Original RunObject dust/lost-ring and RNG state, including D1. Art/SAT pixels and full dispatch integration are separate checks.'}
    (ROOT/'build/special-reference/effect-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
