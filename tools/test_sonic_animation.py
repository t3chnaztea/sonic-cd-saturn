#!/usr/bin/env python3
"""Compare native animation with the unmodified retail 68000 subroutine.

Runs the pinned Genesis Plus GX CPU in an isolated flat-memory test fixture,
not a gameplay session. Only the retail routine/data execute; the reference
does not share the native dispatcher. No BIOS/disc files are modified.
"""
import ctypes as C
import hashlib,json,random,re,struct,subprocess
from pathlib import Path
from sonic_animation_assets import ROOT,QA,FOLDER,generate
from convert_assets import assembly_frames
from extract_mmd import disc_files
from retail_span import disc_span
from convert_assets import sonic_frame

class State(C.Structure):
    _fields_=[(name,C.c_uint8) for name in ['animation','previous','cursor','timer','mapping','sprite_flags']]
class Memory(C.Structure):
    _fields_=[(name,C.c_void_p) for name in ['base','read8','read16','write8','write16']]
class CpuPrefix(C.Structure):
    _fields_=[('memory_map',Memory*256),('poll',C.c_uint32*3),('cycles',C.c_int),('refresh_cycles',C.c_int),('cycle_end',C.c_uint32)]

MINI_SONIC=0xff195b
class Retail:
    def __init__(self,entry,program_name='R11A__.MMD'):
        self.lib=C.CDLL(str(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'))
        self.ram=C.create_string_buffer(0x1000000);self.base=C.addressof(self.ram)
        self.cpu=CpuPrefix.in_dll(self.lib,'m68k')
        self.lib.m68k_init()
        # m68k.h places the 256 memory-map entries first in m68ki_cpu_core.
        for i in range(256):self.cpu.memory_map[i]=Memory(self.base+i*65536,None,None,None,None)
        program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())[program_name]
        self.write(0x200000,program+bytes(len(program)&1))
        self.entry=entry;self.actor=0xffb000;self.halt=0xff8000;self.stack=0xff7ff0
        self.write(0,struct.pack('>II',self.stack,self.halt))
        self.write(self.halt,bytes.fromhex('60fe')) # BRA to self after RTS
        self.lib.m68k_pulse_reset()
        self.lib.m68k_get_reg.restype=C.c_uint32
        assert self.lib.m68k_get_reg(16)==self.halt
    def write(self,address,data):
        assert address%2==0 and len(data)%2==0
        swapped=bytearray(data);swapped[::2],swapped[1::2]=data[1::2],data[::2]
        C.memmove(self.base+address,bytes(swapped),len(data))
    def read(self,address,size):
        data=C.string_at(self.base+address,size);out=bytearray(data)
        out[::2],out[1::2]=data[1::2],data[::2];return out
    def step(self,state,speed,angle,flags,control,mini=False):
        actor=bytearray(64)
        for at,value in zip([28,29,27,30,26,1],bytes(state)):actor[at]=value
        struct.pack_into('>h',actor,20,speed);actor[38]=angle;actor[34]=flags;actor[44]=control
        actor[22],actor[23]=19,9 # oYRadius/oXRadius: normal standing size
        self.write(self.actor,actor);self.write(self.stack,struct.pack('>I',self.halt))
        # miniSonic ($FF195B, tst.b in ObjSonic_GetMiniAnim of R11A/R81A/R83C).
        word=self.read(MINI_SONIC&~1,2);word[1]=1 if mini else 0;self.write(MINI_SONIC&~1,bytes(word))
        for reg,value in [(17,0x2700),(15,self.stack),(8,self.actor),(16,self.entry)]:self.lib.m68k_set_reg(reg,value)
        self.cpu.cycles=self.cpu.refresh_cycles=0
        self.lib.m68k_run(20000)
        assert self.lib.m68k_get_reg(16)==self.halt,('retail routine failed to return',hex(self.lib.m68k_get_reg(16)))
        result=self.read(self.actor,64)
        changed={28,29,27,30,26,1}
        if mini:
            # .MiniSonicRun curls Sonic on steep angles: oFlags bit 2, 10/5 radii.
            curled=result[34]==flags|4 and result[22]==10 and result[23]==5
            if curled:changed|={34,22,23}
        assert all(result[i]==actor[i] for i in range(64) if i not in changed),'retail animation modified physics state'
        out=bytes(result[at] for at in [28,29,27,30,26,1])
        return (out,curled) if mini else out

def main():
    source=generate()
    binary=QA/'native.dylib'
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-dynamiclib','-Isrc','-Iassets/generated','src/sonic_animation.c','-o',str(binary)],cwd=ROOT,check=True)
    native=C.CDLL(str(binary));native.scd_sonic_animate.argtypes=[C.POINTER(State),C.c_int16,C.c_uint8,C.c_uint8,C.c_uint8]
    retail=Retail(source['animation_entry']);count=0;frames=set();animations=set()
    cases=(QA/'retail-cases.bin').open('wb')
    def check(s,speed,angle,flags,control):
        nonlocal count
        before=bytes(s);expected=retail.step(s,speed,angle,flags,control)
        assert native.scd_sonic_animate(C.byref(s),speed,angle,flags,control)==0
        assert bytes(s)==expected,{'before':list(before),'input':[speed,angle,flags,control],'native':list(bytes(s)),'retail':list(expected)}
        cases.write(before+struct.pack('>hBBB',speed,angle,flags,control)+expected)
        count+=1;frames.add(s.mapping);animations.add(before[0])
    # Script timelines, including loops, delayed transitions and high frame IDs.
    for animation in range(60):
        s=State(animation,255,0,0,0,0xe0)
        for tick in range(600):check(s,768,0,0,0)
    # Every angle, both facings, pushing/ramp combinations and speed boundaries.
    for animation in [0,2,4]:
        for speed in [-32768,-4096,-2560,-1536,-1024,-1,0,1,1023,1024,1535,1536,2047,2048,2559,2560,4096,32767]:
            for angle in range(256):
                for flags,control in [(0,0),(1,0),(32,0),(33,0),(0,2),(1,2)]:
                    check(State(animation,255,0,0,0,0xe0),speed,angle,flags,control)
    # Externally indexed frozen poses must never increment the script cursor.
    for animation,poses in [(44,4),(45,6)]:
        for cursor in range(poses):
            for flags in range(4):
                s=State(animation,animation,cursor,0,0,flags)
                for tick in range(8):check(s,0,0,flags,1)
    rng=random.Random(0x534f4e49);s=State(5,255,0,0,0,0x40)
    for tick in range(20000):
        if tick%41==0:s.animation=rng.randrange(60)
        check(s,rng.randrange(-8192,8193),rng.randrange(256),rng.randrange(64),rng.choice([0,2]))
    # Miniature Sonic (R8 shrink beam) against the retail Metallic Madness
    # programs, whose ObjSonic_Animate copy differs in addresses from R11A.
    native.scd_sonic_animate_mini.argtypes=native.scd_sonic_animate.argtypes
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    mini_count=0;mini_curls=0;mini_programs=[]
    for name in ['R81A__.MMD','R83C__.MMD']:
        body=program[name];hits=list(re.finditer(rb'\x43\xf9(....)\x70\x00\x10\x28\x00\x1c\xb0\x28\x00\x1d',body,re.S))
        assert len(hits)==1;table=struct.unpack('>I',hits[0][1])[0]-0x200000
        for i,script in enumerate(assembly_frames(FOLDER/'Animations.asm')):
            at=table+struct.unpack_from('>H',body,table+i*2)[0]
            assert body[at:at+len(script)]==script,('R8 retail animation mismatch',name,i)
        assert body.count(disc_span('R11A__.MMD',0x593c,10,'27917395ce3f421d73ea1932bdf4518fe012f79c61a0de3c76e8946dbcf9d6ff'))==1,'miniSonic address moved'
        r8=Retail(0x200000+hits[0].start(),name);mini_programs.append({'program':name,'animation_entry':0x200000+hits[0].start()})
        def mini_check(s,speed,angle,flags,control):
            nonlocal mini_count,mini_curls
            before=bytes(s);expected,curled=r8.step(s,speed,angle,flags,control,True)
            result=native.scd_sonic_animate_mini(C.byref(s),speed,angle,flags,control)
            assert result==int(curled) and bytes(s)==expected,{'program':name,'before':list(before),'input':[speed,angle,flags,control],
                'native':list(bytes(s)),'retail':list(expected),'curled':curled,'result':result}
            mini_count+=1;mini_curls+=curled;frames.add(s.mapping)
        for animation in range(60):
            s=State(animation,255,0,0,0,0xe0)
            for tick in range(300):mini_check(s,768,0,0,0)
        for animation in [0,2,4]:
            for speed in [-4096,-1536,-1535,-1,0,1,1023,1024,1535,1536,2047,2048,4096]:
                for angle in range(256):
                    for flags,control in [(0,0),(1,0),(32,0),(33,0),(0,2),(1,2)]:
                        mini_check(State(animation,255,0,0,0,0xe0),speed,angle,flags,control)
        rng=random.Random(0x4d494e49);s=State(5,255,0,0,0,0x40)
        for tick in range(10000):
            if tick%37==0:s.animation=rng.randrange(60)
            mini_check(s,rng.randrange(-8192,8193),rng.randrange(256),rng.randrange(64)&~4,rng.choice([0,2]))
    assert mini_curls,'no mini curl exercised'
    cases.close()
    (QA/'expected-frames.bin').write_bytes(b''.join(sonic_frame(i) for i in range(198)))
    report={'passed':True,'checks':count,'mini_checks':mini_count,'mini_curls':mini_curls,'mini_programs':mini_programs,'mapping_ids_seen':sorted(frames),'animation_ids_seen':sorted(animations),
            'oracle':'Unmodified retail ObjSonic_Animate routine in pinned Genesis Plus GX 68000 CPU: R11A normal-sized Sonic; R81A/R83C miniature Sonic (miniSonic set)',
            'retail_program_sha256':source['retail_program_sha256'],'native_sha256':hashlib.sha256((ROOT/'src/sonic_animation.c').read_bytes()).hexdigest(),
            'core_sha256':hashlib.sha256((ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib').read_bytes()).hexdigest(),
            'scope':'isolated_component','limits':'Isolated animation algorithm/data; player call ordering, frame streaming, target pictures and hardware have separate gates.'}
    # Replay the actual CPU-oracle cases under sanitizers; decode every pose
    # against the independent source mapping/DPLC renderer, with guarded output.
    sanitized=QA/'sanitized-test'
    subprocess.run(['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all','tools/sonic_animation_test.c',
                    'src/sonic_animation.c','src/sonic_art.c','-o',str(sanitized)],cwd=ROOT,check=True)
    result=subprocess.run([str(sanitized)],cwd=ROOT,capture_output=True,text=True,check=True)
    (QA/'sanitized.log').write_text(result.stdout+result.stderr);print(result.stdout,end='',flush=True)
    report.update(sanitizers='address and undefined behavior',decoded_frames=198,decoded_pixels=198*4096,
                  source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                    ['src/sonic_animation.c','src/sonic_animation.h','src/sonic_art.c','src/sonic_art.h',
                     'tools/sonic_animation_assets.py','tools/test_sonic_animation.py','tools/sonic_animation_test.c']},
                  cases_sha256=hashlib.sha256((QA/'retail-cases.bin').read_bytes()).hexdigest(),
                  pack_sha256=source['pack_sha256'])
    (QA/'retail-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Sonic animation: {count} states match retail 68000 execution exactly; {mini_count} miniature states ({mini_curls} curls) match R81A/R83C; {len(frames)} mapping IDs exercised',flush=True)

if __name__=='__main__':main()
