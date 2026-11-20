#!/usr/bin/env python3
"""Compare Saturn queue ordering with unmodified retail DrawOtherObject calls."""
import ctypes as C
import hashlib,json,random,re,struct,subprocess
from pathlib import Path
from test_sonic_animation import Retail
from extract_mmd import disc_files
from retail_span import disc_span
from convert_assets import ROOT
from sprite_priority_reference import priorities as source_priorities,sources as priority_sources

def main():
    out=ROOT/'build/sprite-order';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    code=disc_span('R11A__.MMD',0x3b80,30,'984ff9bbd4b76445136890e0f1514971d11b393a7bf184291d981fc11c66f8a9')
    assert program.count(code)==1
    entry=0x200000+program.index(code);retail=Retail(entry);queue=0xffac00
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-dynamiclib',
        '-Isrc','tools/sprite_order_test.c','-o',str(out/'native.dylib')],cwd=ROOT,check=True)
    native=C.CDLL(str(out/'native.dylib'))
    native.native_order.argtypes=[C.POINTER(C.c_uint8),C.c_uint,C.POINTER(C.c_uint8)]
    kinds,reference=source_priorities();priority_cases=0
    # Every type objects.c spawns (supported_types, plus tp_setactno children)
    # reaches sprite_draw through scd_objects_views, except the two it never
    # reports. A type without a priority returns -1; src/main.c then draws it
    # at 3 (it used to abort and freeze the game), so this test is what keeps
    # every type mapped. PPZ/CC types use sprite_priority_reference.py; TT
    # types set sprpri at run time per state (tools/test-tt-*.sh compare it
    # against the compiled R4 originals every update) and use the flag path.
    enum={m[1]:int(m[2]) for m in re.finditer(r'(SCD_OBJ_\w+)=(\d+)',(ROOT/'src/scd_objects.h').read_text())}
    table=re.search(r'supported_types\[\d+\]=\{(.*?)\};',(ROOT/'src/objects.c').read_text(),re.S)[1]
    spawned={enum[name] for name in re.findall(r'\[(SCD_OBJ_\w+)\]=1',table)}
    never_viewed={enum['SCD_OBJ_SPIN_TAG'],enum['SCD_OBJ_TUNNEL']}
    # Tidal Tempest actors and zone-local types (136-254) draw at the actor's
    # own sprpri: scd_objects_views ORs sprpri<<5 into the view flags for
    # tt_view_type/tp_type actors (and zone ops set it), and scd_ppz_priority
    # returns flags>>5 for them. Such a type counts as mapped only if the
    # views really carry its sprpri and the header decodes all eight values.
    src=''.join(p.read_text() for p in sorted((ROOT/'src').glob('objects_tt_*.inc')))
    def predicate(fn):
        body=re.search(r'static int '+fn+r'\(unsigned t\)\{(.*?)\n\}',src,re.S)[1]
        return {enum[n] for n in re.findall(r'(SCD_OBJ_\w+)',body)}
    carried=predicate('tt_view_type')|predicate('tt_contact_type')|predicate('tp_type')
    # The views OR sprpri<<5 for these classes after the zone gate.
    objects=(ROOT/'src/objects.c').read_text()
    assert all(fragment in objects for fragment in (
        'tt_view_type(type)?VIEW_TT:0',
        'tp_type(type)?VIEW_TT_RIDE:0',
        'const unsigned cls=view_class[type];',
        'const int tt_view=tt && (cls&VIEW_TT),tt_ride=tt && (cls&VIEW_TT_RIDE);',
        'if(tt_view || tt_ride)views[n-1].flags|=(uint8_t)((o->sprpri&7)<<5);',
    )),'objects.c no longer carries sprpri in TT view flags'
    spawned|={enum[n] for n in re.findall(r'tp_setactno\([^,;]+,\s*(SCD_OBJ_\w+)\)',src) if n in enum}
    native.native_priority_flags.argtypes=[C.c_uint,C.c_uint,C.c_uint]
    flag_path=set()
    for kind in spawned-never_viewed-set(kinds):
        if kind in carried and all(native.native_priority_flags(kind,0,p<<5)==p for p in range(8)):flag_path.add(kind)
    missing=sorted(spawned-never_viewed-set(kinds)-flag_path)
    assert not missing,f'spawnable object types without a draw priority: {missing}'
    for kind in spawned-never_viewed:assert native.native_priority(kind,0,0)>=0,kind
    for kind in kinds:
        for subtype in range(256):
            for frame in range(16):
                # Ring/Main.asm ObjRing_Collect and ObjLostRing_Collect set
                # oPriority to 1 before Ani_Ring's mapping frames 4-7.
                expected=1 if kind in (16,17) and 4<=frame<8 else reference(kind,subtype,frame)
                assert native.native_priority(kind,subtype,frame)==expected,(kind,subtype,frame)
                priority_cases+=1
    rng=random.Random(0x53505249);calls=0;cases=[]
    for n in [0,1,2,7,8,31,63,96,129,160]+[rng.randrange(161) for _ in range(502)]:
        priorities=[rng.randrange(8) for _ in range(n)]
        assert max([priorities.count(p) for p in range(8)])<=63
        retail.write(queue,bytes(1024))
        for i,priority in enumerate(priorities):
            actor=0xffb000+i*64;data=bytearray(64);data[0]=1;data[24]=priority
            retail.write(actor,data);retail.write(retail.stack,struct.pack('>I',retail.halt))
            for reg,value in [(17,0x2700),(15,retail.stack),(9,actor),(16,entry)]:retail.lib.m68k_set_reg(reg,value)
            retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1000)
            assert retail.lib.m68k_get_reg(16)==retail.halt
            assert retail.read(actor,64)==data
            calls+=1
        raw=retail.read(queue,1024);front=[]
        for p in range(8):
            size=struct.unpack_from('>H',raw,p*128)[0]
            assert size<=126 and size%2==0
            front += [(struct.unpack_from('>H',raw,p*128+k)[0]-0xb000)//64 for k in range(2,size+1,2)]
        expected=bytes(reversed(front));assert len(expected)==n
        before=(C.c_uint8*n)(*priorities);actual=(C.c_uint8*n)()
        assert native.native_order(before,n,actual)==n and bytes(actual)==expected
        cases.append(bytes([n])+bytes(priorities)+expected)
    (out/'retail-cases.bin').write_bytes(b''.join(cases))
    subprocess.run(['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Isrc',
        '-DSCD_ORDER_TEST_MAIN','-fsanitize=address,undefined','-fno-sanitize-recover=all',
        'tools/sprite_order_test.c','-o',str(out/'sanitized')],cwd=ROOT,check=True)
    result=subprocess.run([str(out/'sanitized')],cwd=ROOT,capture_output=True,text=True,check=True)
    (out/'sanitized.log').write_text(result.stdout+result.stderr);print(result.stdout,end='')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=True,cases=len(cases),retail_calls=calls,retail_entry=entry,
        priority_cases=priority_cases,priority_kinds=kinds,priority_source_sha256=priority_sources,
        retail_program_sha256=hashlib.sha256(program).hexdigest(),
        core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        source_sha256={n:sha(ROOT/n) for n in ['src/sprite_order.h','tools/sprite_order_test.c',
            'tools/test_sprite_order.py','tools/sprite_priority_reference.py','.deps/scddisasm/src/Level/Object Functions.asm']},
        cases_sha256=sha(out/'retail-cases.bin'),
        limits='Retail queue ordering and source-derived PPZ priority metadata. Actor scheduling, rendered pixels and native timing are separate checks. No emulation of original overflow limits.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{calls} retail queue calls; {len(cases)} complete lists exactly reversed for Saturn')
if __name__=='__main__':main()
