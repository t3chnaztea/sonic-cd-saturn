#!/usr/bin/env python3
"""Original checkpoint Save/Load -> first HUD tick -> 120 normal ticks.

The native reload publication corresponds to the first initialized actor state:
original Level_MainLoop VInt_Level/UpdateHUD precedes RunObjects, whose
ObjSonic_Init returns without movement or hurt decrement. This checks that
clock boundary, not complete frame, camera, fade or gameplay equivalence.
"""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files
from test_sonic_animation import Retail

def main():
    p=argparse.ArgumentParser();p.add_argument('--label',default='current')
    p.add_argument('--native-player',default='src/player.c');a=p.parse_args()
    out=ROOT/'build/checkpoint-clock';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    signatures={
        'save':'13f900ff152200ff152333f8d00800ff152433f8d00c00ff1526',
        'load':'4df8d0000c39000200ff15226700ff2013f900ff152300ff1522',
        'player':'43f8d0007001134000004a3900ff15226706337c007800304e75',
        'init':'54280024117c00130016117c00090017',
        'clock':'43f900ff15140c9900093b3b670000e04a38f7cc662452210c11003c'}
    entries={}
    for name,s in signatures.items():
        code=bytes.fromhex(s);assert program.count(code)==1,(name,program.count(code))
        entries[name]=0x200000+program.index(code)
    end=entries['clock']+program[entries['clock']-0x200000:].index(bytes.fromhex('203c72200002'))
    retail=Retail(entries['save'])
    def byte(address,value):
        data=bytearray(retail.read(address&~1,2));data[address&1]=value;retail.write(address&~1,data)
    def call(name):
        retail.write(retail.stack,struct.pack('>I',retail.halt))
        for reg,value in [(17,0x2700),(15,retail.stack),(8,0xffd000),(14,0xffd000),(16,entries[name]),(0,0)]:retail.lib.m68k_set_reg(reg,value)
        if name=='clock':
            for _ in range(40):
                if retail.lib.m68k_get_reg(16)==end:break
                retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1)
            assert retail.lib.m68k_get_reg(16)==end
        else:
            retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(30000)
            assert retail.lib.m68k_get_reg(16)==retail.halt
    cases=[(0,m*3600+s*60+f,1+(m*240+s*60+f)%255)
           for m in range(6) for s in [0,1,58,59] for f in range(60)]
    cases += [(era,1234,0) for era in range(4)]
    native=(ROOT/a.native_player).resolve()
    sources=['tools/checkpoint_clock_test.c','src/sonic_animation.c','src/stage.c','src/objects.c','src/act.c']
    sources += [f'build/probe-source/{n}.c' for n in ['interaction','player','dircol','fcol','etc','equ','movement']]
    binary=out/(a.label+'-test')
    subprocess.run(['clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv','-fno-strict-aliasing',
        '-Wno-parentheses','-Wno-unused-value','-Isrc','-Iassets/generated','-Ibuild/probe-source','-DR1','-DR11A',
        '-DSCD_CLOCK_PLAYER="'+str(native)+'"','-fsanitize=address,undefined','-fno-sanitize-recover=all']+
        sources+['-o',str(binary)],cwd=ROOT,check=True)
    log=out/(a.label+'.log');inputs=''.join(f'{e} {t} {i}\n' for e,t,i in cases)
    result=subprocess.run([str(binary)],input=inputs,text=True,capture_output=True,cwd=ROOT,check=True)
    log.write_text(result.stdout+result.stderr)
    rows=result.stdout.splitlines();assert len(rows)==len(cases)
    failures=[];observations=[];checks=0
    for index,(line,(era,ticks,id)) in enumerate(zip(rows,cases)):
        tag,*v=line.split();v=list(map(int,v));assert tag=='clock' and len(v)==125 and v[:3]==[era,ticks,id]
        saved=v[3];assert saved==(min(ticks,18000) if id else 0)
        retail.write(0xff1500,bytes(0x500));retail.write(0xffd000,bytes(64));retail.write(0xfff700,bytes(0x100))
        if id:
            retail.write(0xffd008,struct.pack('>I',3000<<16));retail.write(0xffd00c,struct.pack('>I',64<<16))
            packed=(ticks//3600)<<16|(ticks//60%60)<<8|ticks%60
            retail.write(0xff1514,struct.pack('>I',packed));byte(0xff1522,1);call('save')
            retail.write(0xffd000,bytes(64));call('load')
        call('player');raw=retail.read(0xff1514,4).hex()
        if id:call('clock')
        # Fresh native spawn/reload is a pre-tick zero clock and is checked
        # separately; only the saved-spawn boundary consumes this HUD tick.
        call('init');actor=retail.read(0xffd000,64)
        assert actor[36]==2 and struct.unpack_from('>H',actor,48)[0]==(120 if id else 0)
        expected=[]
        for n in range(121):
            t=retail.read(0xff1514,4);expected.append(t[1]*3600+t[2]*60+t[3])
            if n<120:call('clock')
        if v[4:]!=expected:failures.append(dict(case=index,ticks=ticks,id=id,native=v[4:8],retail=expected[:4]))
        observations.append(dict(era=era,ticks=ticks,id=id,raw_reload=raw,first=expected[0],last=expected[-1]))
        checks+=len(expected)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources += [a.native_player,'tools/test_checkpoint_clock.py','src/scd_player.h',
        '.deps/scddisasm/src/Level/Main.asm','.deps/scddisasm/src/Level/Palette Fade.asm',
        '.deps/scddisasm/src/Level/Load Saved Data.asm','.deps/scddisasm/src/Level/_Objects/Checkpoint/Main.asm',
        '.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm','.deps/scddisasm/src/Level/_Objects/HUD and Points/Main.asm']
    report=dict(passed=not failures,cases=len(cases),states=checks,mismatches=len(failures),examples=failures[:8],
        observations=observations,retail_entries=entries,clock_end=end,
        source_sha256={name:sha(ROOT/name) for name in sources},log_sha256=sha(log),binary_sha256=sha(binary),
        retail_program_sha256=hashlib.sha256(program).hexdigest(),core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        limits='Isolated saved-spawn clock boundary and subsequent ordinary ticks through actual native death/reload; fresh starts remain pre-tick zero. No camera, fade, complete actor initialization or physical-console equivalence.')
    (out/(a.label+'-report.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('Checkpoint clock:',len(cases),'cases;',checks,'states;',len(failures),'mismatching cases')
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
