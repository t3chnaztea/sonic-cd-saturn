#!/usr/bin/env python3
"""Match complete effect updates to untouched retail 68000 execution."""
import ctypes as C
import hashlib,json,random,struct,subprocess
from test_sonic_animation import Retail
from powerup_assets import generate
from convert_assets import ROOT
from extract_mmd import disc_files
from retail_span import disc_span

class State(C.Structure):
    _fields_=[('x',C.c_int16),('y',C.c_int16),('tile',C.c_uint16)]+[(n,C.c_uint8) for n in
        ['active','routine','animation','previous','cursor','timer','mapping','sprite_flags','flags','phase','priority','width']]
class Context(C.Structure):
    _fields_=[('x',C.c_int16),('y',C.c_int16)]+[(n,C.c_uint8) for n in
        ['flags','shield','invincible','travel','zone','layer','powerup','record_index']]+[('history',(C.c_int16*2)*64)]
OFFSETS=dict(x=8,y=12,tile=2,active=0,routine=36,animation=28,previous=29,cursor=27,timer=30,
    mapping=26,sprite_flags=1,flags=34,phase=48,priority=24,width=25)

def retail_reference():
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    # Dispatcher, four offsets and the initializer through its RTS.
    code=disc_span('R11A__.MMD',0x63f6,82,'784b7bd064b3b1dc050140084e87fafbd7b7c4049d81719c5e7f9b9667237ae5')
    assert program.count(code)==1
    entry=0x200000+program.index(code);retail=Retail(entry);draw=0x203af2
    assert program[draw-0x200000:draw-0x200000+6]==bytes.fromhex('08a800070001')
    def byte(address,value):
        data=bytearray(retail.read(address&~1,2));data[address&1]=value;retail.write(address&~1,data)
    def original(s,c):
        actor=bytearray(64)
        for name,offset in OFFSETS.items():
            value=getattr(s,name)
            if name in ('x','y'):struct.pack_into('>h',actor,offset,value)
            elif name=='tile':struct.pack_into('>H',actor,offset,value)
            else:actor[offset]=value
        retail.write(retail.actor,actor)
        player=bytearray(64);struct.pack_into('>h',player,8,c.x);struct.pack_into('>h',player,12,c.y);player[34]=c.flags
        retail.write(0xffd000,player)
        retail.write(0xffcb00,b''.join(struct.pack('>hh',*p) for p in c.history))
        retail.write(0xfff7a8,struct.pack('>H',c.record_index))
        for address,value in [(0xff151e,c.shield),(0xff151f,c.invincible),(0xff1521,c.travel),
                (0xff1506,c.zone),(0xff1956,c.layer),(0xff156b,c.powerup)]:byte(address,value)
        retail.write(retail.stack,struct.pack('>I',retail.halt))
        for reg,value in [(17,0x2700),(15,retail.stack),(8,retail.actor),(16,entry)]:retail.lib.m68k_set_reg(reg,value)
        for _ in range(300):
            pc=retail.lib.m68k_get_reg(16)
            if pc in (draw,retail.halt):break
            retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1)
        assert pc in (draw,retail.halt),('retail did not return/submit',hex(pc))
        raw=retail.read(retail.actor,64);expected=State()
        for name,offset in OFFSETS.items():
            setattr(expected,name,struct.unpack_from('>h' if name in ('x','y') else '>H',raw,offset)[0]
                if name in ('x','y','tile') else raw[offset])
        return expected,retail.read(0xff156a,2)[1],int(pc==draw)
    original.entry=entry;original.draw=draw
    return original

def main():
    source=generate();out=ROOT/'build/powerup-visual';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    original=retail_reference()
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated',
        '-dynamiclib','src/powerup_visual.c','-o',str(out/'native.dylib')],cwd=ROOT,check=True)
    native=C.CDLL(str(out/'native.dylib'));native.scd_powerup_visual_step.argtypes=[C.POINTER(State),C.POINTER(Context)]
    assert C.sizeof(State)==18 and C.sizeof(Context)==268
    rng=random.Random(0x504f5752);count=0;seen=set();suppressed=0;deleted=0;mixed_calls=0
    with (out/'retail-cases.bin').open('wb') as cases:
        def check(s,c):
            nonlocal count,suppressed,deleted
            before=bytes(s);env=bytes(c);expected,powerup,submitted=original(s,c)
            result=native.scd_powerup_visual_step(C.byref(s),C.byref(c))
            assert result==submitted and bytes(s)==bytes(expected) and c.powerup==powerup,{
                'before':list(before),'env':list(env[:12]),'retail':list(bytes(expected)),
                'native':list(bytes(s)),'submission':[submitted,result],'powerup':[powerup,c.powerup]}
            assert bytes(c)[:10]+bytes(c)[11:]==env[:10]+env[11:],'context changed outside art selection'
            cases.write(before+env+bytes(expected)+bytes([powerup,submitted]));count+=1
            if submitted:seen.add((s.animation,s.mapping))
            if bytes(s)==before and not submitted:suppressed+=1
            if not s.active:deleted+=1
        for animation in range(9):
            for mode in range(4):
                s=State(active=3,animation=animation);c=Context(shield=1,invincible=int(0<animation<5),travel=int(animation>=5))
                for tick in range(600):
                    c.x=(tick*13)%30000-15000;c.y=3000-tick*7;c.flags=(tick//7)&255
                    c.zone=6 if mode&1 else 0;c.layer=(tick//53)&1;c.record_index=(tick*4)&255
                    c.powerup=(c.powerup&127) if mode<2 else (tick//29)%16
                    for n in range(64):c.history[n][0]=(tick*31+n*17)%60000-30000;c.history[n][1]=n*43-1000
                    # Source suppression freezes each actor's animation/phase.
                    if animation==0:c.invincible=int(mode==3 and 100<=tick<300);c.travel=int(mode==2 and 140<=tick<320)
                    elif animation<5:c.travel=int(mode>=2 and 110<=tick<310)
                    check(s,c)
                # Removal must clear all represented actor state.
                c.shield=c.invincible=c.travel=0;check(s,c)
        # All nine reserved actors share the art-selection byte. Early Sonic
        # time-star creation precedes the actor pass; monitor grants are late.
        # Re-granting an existing effect changes ID/animation only, not its
        # routine, cursor or private history phase (the original spawn writes).
        actors=[State() for _ in range(9)];c=Context()
        for tick in range(2000):
            c.x=tick-1000;c.y=800-tick//3;c.flags=(tick//9)&3
            c.record_index=(tick*4)&255
            for n in range(64):c.history[n][0]=tick-n*3;c.history[n][1]=700+n*2-tick//4
            c.powerup=8 if 1200<=tick<1230 else c.powerup&127
            if tick==1230:c.powerup=0
            if tick in (900,1800):c.invincible=0
            if tick==1500:c.shield=0
            c.travel=int(250<=tick<350 or 700<=tick<800 or 1150<=tick<1300)
            if c.travel and not actors[5].active:
                for n in range(5,9):actors[n].active=3;actors[n].animation=n
            for s in actors:
                if s.active:check(s,c);mixed_calls+=1
            if tick in (0,600):c.shield=1;actors[0].active=3
            if tick in (100,600,1000):
                c.invincible=1
                for n in range(1,5):actors[n].active=3;actors[n].animation=n
        # Arbitrary valid internal state, flips, frame timer wrap, script reset,
        # record wrap and global art suppression. Source-scheduled active actor.
        for _ in range(6000):
            animation=rng.randrange(9)
            s=State(x=rng.randrange(-32768,32768),y=rng.randrange(-32768,32768),tile=rng.randrange(65536),
                active=3,routine=2 if not animation else 4 if animation<5 else 6,
                animation=animation,previous=255,cursor=rng.randrange(256),timer=rng.randrange(256),
                mapping=rng.randrange(13),sprite_flags=rng.randrange(256),flags=rng.randrange(256),
                phase=rng.randrange(6)*4,priority=1,width=16)
            c=Context(x=rng.randrange(-32768,32768),y=rng.randrange(-32768,32768),flags=rng.randrange(256),
                shield=rng.randrange(2),invincible=rng.randrange(2),travel=rng.randrange(2),zone=rng.choice([0,6]),
                layer=rng.randrange(2),powerup=rng.randrange(256),record_index=rng.randrange(64)*4)
            for p in c.history:p[0]=rng.randrange(-32768,32768);p[1]=rng.randrange(-32768,32768)
            check(s,c)
    assert all({(a,0)}|{(a,f) for f in (range(1,4) if a==0 else range(4,8) if a<5 else range(8,13))}<=seen for a in [0,2,3,4,5,6,7,8])
    subprocess.run(['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','src/powerup_visual.c','tools/powerup_visual_test.c',
        '-o',str(out/'sanitized')],cwd=ROOT,check=True)
    result=subprocess.run([str(out/'sanitized')],cwd=ROOT,text=True,capture_output=True,check=True)
    (out/'sanitized.log').write_text(result.stdout+result.stderr);print(result.stdout,end='')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    names=['src/powerup_visual.c','src/powerup_visual.h','tools/test_powerup_visual.py','tools/powerup_visual_test.c',
        'tools/powerup_assets.py','assets/generated/powerup-animation.inc','.deps/scddisasm/src/Level/_Objects/Powerup/Main.asm',
        '.deps/scddisasm/src/Level/_Objects/Powerup/Data/Animations.asm','.deps/scddisasm/src/Level/Object Animate.asm']
    report=dict(source,passed=True,cases=count,retail_entry=original.entry,draw_boundary=original.draw,frames=sorted(seen),
        suppressed_updates=suppressed,deleted_updates=deleted,mixed_reserved_slot_updates=mixed_calls,
        cases_sha256=sha(out/'retail-cases.bin'),
        source_sha256={n:sha(ROOT/n) for n in names},core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        limits='Exact isolated original actor updates up to DrawObject; spawn scheduling, camera culling, renderer integration and hardware remain separate gates.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Power-up visual: {count} complete updates match retail; {len(seen)} animation/pose pairs')
if __name__=='__main__':main()
