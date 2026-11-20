#!/usr/bin/env python3
"""Compare real native arrival with untouched retail save/load/init routines.

Executes SaveTimeWarpData, LoadTimeWarpData, LoadPlayer, the level power-up
clear block and ObjSonic_Init. Terrain landing relocation/camera scheduling are
outside this isolated state-boundary proof; fixtures use a clear destination.
"""
import argparse,hashlib,json,struct,subprocess
from convert_assets import ROOT
from extract_mmd import disc_files
from retail_span import disc_span
from test_sonic_animation import Retail

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='current')
    parser.add_argument('--native-player',default='src/player.c');parser.add_argument('--arrival-only',action='store_true');args=parser.parse_args()
    out=ROOT/'build/player-arrival';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    signatures={
        'save':'13f900ff152200ff154633e8000800ff154833e8000c00ff154a33e8001400ff1564',
        'load':'3d7900ff154800083d7900ff154a000c1d7900ff154c00223d7900ff15640014',
        'player':'43f8d0007001134000004a3900ff15226706337c007800304e75',
        'clear':'13c000ff151e13c000ff151f13c000ff152013c000ff1521',
        'init':'54280024117c00130016117c000900174a3900ff195b670c117c000a0016117c00050017'}
    entries={}
    for name,hexcode in signatures.items():
        code=bytes.fromhex(hexcode);assert program.count(code)==1,(name,program.count(code))
        entries[name]=0x200000+program.index(code)
    retail=Retail(entries['save'])
    display_code=disc_span('R11A__.MMD',0x4246,28,'bb3cc9b74ca5d23a57c5927499f9a3558395f2b5fd1757c7f4f036d6b4fbbde7')
    assert program.count(display_code)==1
    display_entry=0x200000+program.index(display_code);display_end=display_entry+len(display_code)
    def byte(address,value):
        data=bytearray(retail.read(address&~1,2));data[address&1]=value;retail.write(address&~1,data)
    def call(name):
        retail.write(retail.stack,struct.pack('>I',retail.halt))
        for reg,value in [(17,0x2700),(15,retail.stack),(8,0xffd000),(14,0xffd000),(16,entries[name]),(0,0)]:retail.lib.m68k_set_reg(reg,value)
        if name=='clear':
            end=entries[name]+len(bytes.fromhex(signatures[name]))
            for _ in range(10):
                if retail.lib.m68k_get_reg(16)==end:break
                retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1)
            assert retail.lib.m68k_get_reg(16)==end
        else:
            retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(30000)
            assert retail.lib.m68k_get_reg(16)==retail.halt,(name,hex(retail.lib.m68k_get_reg(16)))
    for name in ['prepare_probe.py','prepare_player.py']:subprocess.run(['python3','tools/'+name],cwd=ROOT,check=True)
    sources=['tools/player_arrival_test.c',args.native_player,'src/sonic_animation.c','src/stage.c','src/objects.c','src/act.c']
    sources += [f'build/probe-source/{n}.c' for n in ['interaction','player','dircol','fcol','etc','equ','movement']]
    subprocess.run(['clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv','-fno-strict-aliasing',
        '-Wno-parentheses','-Wno-unused-value','-Isrc','-Iassets/generated','-Ibuild/probe-source','-DR1','-DR11A',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all']+sources+['-o',str(out/'test')],cwd=ROOT,check=True)
    log=out/(args.label+'.log')
    with log.open('w') as f:subprocess.run([str(out/'test')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    count=0;failures=[];eras=set();flags=set();powerups=set();display_cases=0
    for line in log.read_text().splitlines():
        tag,*parts=line.split()
        if tag=='display':
            if args.arrival_only:continue
            phase,hurt,control,after,hidden=map(int,parts)
            actor=bytearray(64);struct.pack_into('>H',actor,48,hurt);actor[44]=control;retail.write(0xffd000,actor)
            for reg,value in [(17,0x2700),(15,retail.stack),(8,0xffd000),(16,display_entry)]:retail.lib.m68k_set_reg(reg,value)
            for _ in range(20):
                pc=retail.lib.m68k_get_reg(16)
                if pc in (display_end,0x203af2):break
                retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1)
            assert pc in (display_end,0x203af2)
            expected_hurt=struct.unpack_from('>H',retail.read(0xffd000,64),48)[0]
            assert after==expected_hurt and hidden==int(pc!=0x203af2),('source display decision',phase,hurt,control,after,hidden,expected_hurt,hex(pc))
            display_cases+=1;continue
        assert tag=='arrival' and len(parts)==20
        era,n,rings,lives,score,ticks,frame,mask=map(int,parts[:8]);actor=bytes.fromhex(parts[8]);actual=bytes.fromhex(parts[9]);values=list(map(int,parts[10:]))
        # Isolate scenes; source routines below own the saved/global state.
        retail.write(0xff1500,bytes(0x500));retail.write(0xffd000,actor)
        retail.write(0xff1512,struct.pack('>H',rings));retail.write(0xff1514,struct.pack('>I',((ticks//3600)<<16)|((ticks//60%60)<<8)|(ticks%60)))
        byte(0xff1508,lives);retail.write(0xff1518,struct.pack('>I',score))
        byte(0xff1522,0);byte(0xff151e,mask&1);byte(0xff151f,bool(mask&2));byte(0xff1520,bool(mask&4))
        call('save')
        # Level/Main clears the object pool before loading saved coordinates.
        retail.write(0xffd000,bytes(64));byte(0xff1522,2)
        call('load');call('player');call('clear');call('init')
        expected=bytearray(retail.read(0xffd000,64));expected[4:8]=bytes(4) # native texture/source mapping pointer is not a portable address
        reference_time=struct.unpack('>I',retail.read(0xff1514,4))[0]
        reference_ticks=((reference_time>>16)&255)*3600+((reference_time>>8)&255)*60+(reference_time&255)
        expected_values=[struct.unpack('>H',retail.read(0xff1512,2))[0],retail.read(0xff1508,2)[0],
            struct.unpack('>I',retail.read(0xff1518,4))[0],reference_ticks,frame,
            *retail.read(0xff151e,4)[:3],struct.unpack('>H',retail.read(0xfff760,2))[0],struct.unpack_from('>H',expected,48)[0]]
        if actual!=expected or values!=expected_values:
            failures.append(dict(era=era,case=n,actor_offsets=[i for i in range(64) if actual[i]!=expected[i]],
                native=actual.hex(),retail=expected.hex(),values=values,expected_values=expected_values))
        count+=1;eras.add(era);flags.add(actor[34]);powerups.add(mask)
    assert count==2048 and eras==set(range(4)) and flags==set(range(256)) and powerups==set(range(8))
    assert display_cases==(0 if args.arrival_only else 2080)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=not failures,cases=count,display_cases=display_cases,display_entry=display_entry,
        mismatches=len(failures),examples=failures[:8],retail_entries=entries,
        eras=sorted(eras),flag_values=len(flags),powerup_combinations=sorted(powerups),
        retail_program_sha256=hashlib.sha256(program).hexdigest(),core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        log_sha256=sha(log),source_sha256={name:sha(ROOT/name) for name in [args.native_player,'src/scd_player.h','tools/player_arrival_test.c','tools/test_player_arrival.py',
            '.deps/scddisasm/src/Level/Main.asm','.deps/scddisasm/src/Level/Load Saved Data.asm','.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm']},
        limits='Normal-size Sonic arrival state at clear Act 1 coordinates in all four eras; not terrain relocation, original save-frame/camera scheduling, complete routes or hardware.')
    (out/(args.label+'-report.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('Retail/native arrival:',count,'cases;',len(failures),'mismatches;',display_cases,'source-exact display decisions')
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
