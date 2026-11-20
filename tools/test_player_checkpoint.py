#!/usr/bin/env python3
"""Verify checkpoint protection against original save/load/player code.

Clock observations are reported separately; test_checkpoint_clock.py is the
saved-clock old/new parity gate. This test still accepts old clock behavior
when checking the historical missing-protection failure.
"""
import argparse,hashlib,json,struct,subprocess
from convert_assets import ROOT
from extract_mmd import disc_files
from test_sonic_animation import Retail

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='current')
    parser.add_argument('--native-player',default='src/player.c');args=parser.parse_args()
    out=ROOT/'build/player-checkpoint';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    signatures={
        'save':'13f900ff152200ff152333f8d00800ff152433f8d00c00ff1526',
        'load':'4df8d0000c39000200ff15226700ff2013f900ff152300ff1522',
        'player':'43f8d0007001134000004a3900ff15226706337c007800304e75',
        'clear':'13c000ff151e13c000ff151f13c000ff152013c000ff1521',
        'clock':'43f900ff15140c9900093b3b670000e04a38f7cc662452210c11003c'}
    entries={}
    for name,hexcode in signatures.items():
        code=bytes.fromhex(hexcode);assert program.count(code)==1
        entries[name]=0x200000+program.index(code)
    clock_end=entries['clock']+program[entries['clock']-0x200000:].index(bytes.fromhex('203c72200002'))
    retail=Retail(entries['save'])
    def byte(address,value):
        data=bytearray(retail.read(address&~1,2));data[address&1]=value;retail.write(address&~1,data)
    def call(name):
        retail.write(retail.stack,struct.pack('>I',retail.halt))
        for reg,value in [(17,0x2700),(15,retail.stack),(8,0xffd000),(14,0xffd000),(16,entries[name]),(0,0)]:retail.lib.m68k_set_reg(reg,value)
        if name in ('clear','clock'):
            end=clock_end if name=='clock' else entries[name]+len(bytes.fromhex(signatures[name]))
            for _ in range(40):
                if retail.lib.m68k_get_reg(16)==end:break
                retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1)
            assert retail.lib.m68k_get_reg(16)==end
        else:
            retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(30000)
            assert retail.lib.m68k_get_reg(16)==retail.halt
    for name in ['prepare_probe.py','prepare_player.py']:subprocess.run(['python3','tools/'+name],cwd=ROOT,check=True)
    sources=['tools/player_checkpoint_test.c',args.native_player,'src/sonic_animation.c','src/stage.c','src/objects.c','src/act.c']
    sources += [f'build/probe-source/{n}.c' for n in ['interaction','player','dircol','fcol','etc','equ','movement']]
    subprocess.run(['clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv','-fno-strict-aliasing',
        '-Wno-parentheses','-Wno-unused-value','-Isrc','-Iassets/generated','-Ibuild/probe-source','-DR1','-DR11A',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all']+sources+['-o',str(out/'test')],cwd=ROOT,check=True)
    log=out/(args.label+'.log')
    with log.open('w') as f:subprocess.run([str(out/'test')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    cases=0;failures=[];clocks=[];ids=set();eras=set()
    for line in log.read_text().splitlines():
        tag,*parts=line.split();assert tag=='checkpoint' and len(parts)==16
        era,id,ticks,x,y,hurt,rings,shield,inv,shoes,lives,score,elapsed,saved,protected,expired=map(int,parts)
        retail.write(0xff1500,bytes(0x500));retail.write(0xffd000,bytes(64));retail.write(0xfff700,bytes(0x100))
        if id:
            retail.write(0xffd008,struct.pack('>I',3000<<16));retail.write(0xffd00c,struct.pack('>I',64<<16))
            packed=(ticks//3600)<<16|(ticks//60%60)<<8|ticks%60
            retail.write(0xff1514,struct.pack('>I',packed));byte(0xff1522,1)
            call('save');retail.write(0xffd000,bytes(64))
            retail.write(0xff1512,struct.pack('>H',17));call('load')
        call('player');call('clear')
        actor=retail.read(0xffd000,64);expected_hurt=struct.unpack_from('>H',actor,48)[0]
        actual=[hurt,rings,shield,inv,shoes];expected=[expected_hurt,0,0,0,0]
        if id:
            actual += [x,y,protected,expired];expected += [struct.unpack_from('>h',actor,8)[0],struct.unpack_from('>h',actor,12)[0],expected_hurt,1]
            raw=retail.read(0xff1514,4).hex();call('clock')
            time=retail.read(0xff1514,4);reference=time[1]*3600+time[2]*60+time[3]
            assert reference==min(ticks,18000)//60*60,('source clock first update',ticks,raw,time.hex())
            clocks.append(dict(saved_ticks=ticks,native_reload=elapsed,retail_preupdate=raw,retail_first_update=reference))
            ids.add(id)
        else:eras.add(era)
        if actual!=expected:failures.append(dict(era=era,id=id,native=actual,retail=expected))
        cases+=1
    assert cases==259 and ids==set(range(1,256)) and eras==set(range(4))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=not failures,cases=cases,checkpoint_ids=len(ids),fresh_start_eras=sorted(eras),
        mismatches=len(failures),examples=failures[:8],protected_updates=255*120 if not failures else None,
        retail_entries=entries,clock_end=clock_end,clock_observations=clocks,
        retail_program_sha256=hashlib.sha256(program).hexdigest(),core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        log_sha256=sha(log),source_sha256={name:sha(ROOT/name) for name in [args.native_player,'src/scd_player.h','tools/player_checkpoint_test.c','tools/test_player_checkpoint.py',
            '.deps/scddisasm/src/Level/Main.asm','.deps/scddisasm/src/Level/Load Saved Data.asm',
            '.deps/scddisasm/src/Level/_Objects/Checkpoint/Main.asm','.deps/scddisasm/src/Level/_Objects/HUD and Points/Main.asm']},
        limits='Checkpoint protection, saved positions and clean inventory through real native death/reload; clock observations are not a clock parity gate. Camera, first movement flags and physical console remain separate.')
    (out/(args.label+'-report.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('Retail/native checkpoint:',cases,'cases;',len(failures),'mismatches; clock rounding separately observed')
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
