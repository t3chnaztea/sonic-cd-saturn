#!/usr/bin/env python3
"""Title-card diagnostic against untouched retail RunObjects / HUD clock.

Only the title card is populated in the original object pool. Its real allocator,
draw queue, PLC enqueue, and delete routines execute. The fixture deliberately
drains PLCs after a chosen number of wait updates: this is NOT measured retail
decompression time or a full level-entry reference. The bare native card (no
program) is compared with the zero-extra-wait case; the native player cases
(card + src/world.c) with the PLC 2 wait of their PPZ program, which
tools/title_card_plc.py derives from the retail programs.
"""
import argparse
import hashlib
import json
import struct
import subprocess

from convert_assets import ROOT
from extract_mmd import disc_files
from special_retail import SRC, rs_symbols
from test_sonic_animation import Retail
from title_card_plc import batches


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='current')
    parser.add_argument('--native-card',default='src/title_card.c')
    parser.add_argument('--component-only',action='store_true',help='Compare an archived card without the new player-clock API')
    args=parser.parse_args()
    assert args.label.replace('-','').replace('_','').isalnum()
    out=ROOT/'build/title-card-clock';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    symbols,_=rs_symbols((SRC/'Level/_Definitions.inc').read_text(),{'WORKRAM':0xff0000},0xffffff)
    main_symbols,_=rs_symbols((SRC/'_Include/Main CPU Variables.inc').read_text(),{'WORKRAM':0xff0000},0xffffff)
    symbols.update(main_symbols)
    entries={}
    for name,signature in {
        'objects':'41f8d0007e7f700010106712d040d040',
        'card_init':'117c00020024317c01180008317c0030000a',
        'clock':'43f900ff15140c9900093b3b670000e04a38f7cc6624',
    }.items():
        code=bytes.fromhex(signature)
        assert program.count(code)==1,(name,program.count(code))
        entries[name]=0x200000+program.index(code)
    clock_end=entries['clock']+program[entries['clock']-0x200000:].index(bytes.fromhex('203c72200002'))
    retail=Retail(entries['objects'])

    def byte(address,value):
        data=bytearray(retail.read(address&~1,2));data[address&1]=value
        retail.write(address&~1,data)

    def call(name):
        retail.write(retail.stack,struct.pack('>I',retail.halt))
        for register,value in [(17,0x2700),(15,retail.stack),(16,entries[name])]:
            retail.lib.m68k_set_reg(register,value)
        if name=='clock':
            for _ in range(40):
                if retail.lib.m68k_get_reg(16)==clock_end:break
                retail.cpu.cycles=retail.cpu.refresh_cycles=0
                retail.lib.m68k_run(1)
            assert retail.lib.m68k_get_reg(16)==clock_end
        else:
            retail.cpu.cycles=retail.cpu.refresh_cycles=0
            retail.lib.m68k_run(200000)
            assert retail.lib.m68k_get_reg(16)==retail.halt,hex(retail.lib.m68k_get_reg(16))

    files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    plc_wait={(act,era):max(0,batches(files[f'R1{act+1}{"ABCD"[era]}__.MMD'])-2)
              for act in range(3) for era in range(2 if act==2 else 0,4)}
    timelines=[];milestones=[]
    for act in range(3):
        for extra_wait in sorted({0,1,4,30}|{w for (a,_),w in plc_wait.items() if a==act}):
            # Leave the fixture stack and halt intact; all engine globals,
            # title pool, draw queues and saved state start empty.
            retail.write(0xff1500,bytes(0x500))
            retail.write(0xffa000,bytes(0x6000))
            byte(symbols['act'],act)
            byte(symbols['ctrlLocked'],1)
            byte(symbols['objTtlCardSlot'],0x3c)
            rows=[];wait_updates=0;queued_at=None
            for tick in range(1,241):
                card=retail.read(symbols['objTtlCardSlot'],64)
                if card[36]==10:
                    if wait_updates>=extra_wait:retail.write(symbols['plcBuffer'],bytes(0x80))
                    wait_updates+=1
                pre_locked=retail.read(symbols['ctrlLocked'],2)[0]
                call('clock') # VInt_Level precedes the RunObjects sweep.
                retail.write(symbols['objDrawQueue'],bytes(0x400))
                call('objects')
                card=retail.read(symbols['objTtlCardSlot'],64)
                if card[36]==10 and queued_at is None:
                    queued_at=tick
                    assert any(retail.read(symbols['plcBuffer'],4)), 'real LoadPLC did not queue art'
                views=[]
                queue=retail.read(symbols['objDrawQueue'],0x400)
                for priority in range(8):
                    offset=priority*0x80;size=struct.unpack_from('>H',queue,offset)[0]
                    assert size<=0x7e and not size%2
                    for i in range(2,size+2,2):
                        address=0xff0000|struct.unpack_from('>H',queue,offset+i)[0]
                        actor=retail.read(address,64)
                        assert actor[0]==0x3c
                        x,y=struct.unpack_from('>hh',actor,8)
                        views.append([address,x-128,y-128,actor[26]])
                # Object allocation order, not draw-priority order, is the
                # public native view API contract. Keep real queue evidence.
                views.sort()
                clock=retail.read(0xff1514,4)
                pool=retail.read(symbols['objects'],symbols['objectsEnd']-symbols['objects'])
                rows.append(dict(tick=tick,pre_locked=pre_locked,
                    locked=retail.read(symbols['ctrlLocked'],2)[0],
                    elapsed=clock[1]*3600+clock[2]*60+clock[3],
                    active=int(any(pool[i]==0x3c for i in range(0,len(pool),64))),
                    views=[v[1:] for v in views],queue_addresses=[v[0] for v in views],
                    parent=list(card),plc_head=retail.read(symbols['plcBuffer'],4).hex()))
            unlocked=next(row['tick'] for row in rows if not row['locked'])
            first_tick=next(row['tick'] for row in rows if row['elapsed'])
            assert first_tick==unlocked+1
            assert all(row['elapsed']==max(0,row['tick']-unlocked) for row in rows)
            milestones.append(dict(act=act,extra_wait=extra_wait,queued_at=queued_at,
                unlock_update=unlocked,first_clock_update=first_tick))
            timelines.append(dict(act=act,extra_wait=extra_wait,rows=rows))

    native_source=(ROOT/args.native_card).resolve()
    binary=out/(args.label+'-test')
    subprocess.run(['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror',
        '-Isrc','-fsanitize=address,undefined','-fno-sanitize-recover=all',
        'tools/title_card_test.c',str(native_source),'-o',str(binary)],cwd=ROOT,check=True)
    result=subprocess.run([str(binary)],text=True,capture_output=True,check=True)
    log=out/(args.label+'.log');log.write_text(result.stdout+result.stderr)
    native=[]
    for line in result.stdout.splitlines():
        act,tick,locked,active,count,*v=map(int,line.split())
        assert len(v)==3*count
        native.append(dict(act=act,tick=tick,locked=locked,active=active,views=[v[i:i+3] for i in range(0,len(v),3)]))
    assert len(native)==720
    references={(t['act'],t['extra_wait'],r['tick']):r for t in timelines for r in t['rows']}
    reference={(a,tick):r for (a,w,tick),r in references.items() if not w}
    differences=[]
    for row in native:
        expected=reference[row['act'],row['tick']]
        for field in ['locked','active','views']:
            if row[field]!=expected[field]:
                differences.append(dict(act=row['act'],tick=row['tick'],field=field,
                    native=row[field],retail=expected[field]))
    raw=out/(args.label+'-retail.json')
    raw.write_text(json.dumps(timelines,separators=(',',':'))+'\n')
    player_sources=[];player_rows=[];player_evidence=[]
    if not args.component_only:
        player_sources=['tools/title_player_test.c','src/player.c','src/sonic_animation.c',
            'src/stage.c','src/objects.c','src/world.c','src/act.c','src/boss.c']
        player_sources += [f'build/probe-source/{name}.c' for name in
            ['boss_1','interaction','player','dircol','fcol','etc','equ','movement']]
        player_binary=out/(args.label+'-player-test')
        subprocess.run(['clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv',
            '-fno-strict-aliasing','-Wno-parentheses','-Wno-unused-value',
            '-Isrc','-Iassets/generated','-Ibuild/probe-source','-DR1','-DR11A',
            '-fsanitize=address,undefined','-fno-sanitize-recover=all',
            *player_sources,str(native_source),'-o',str(player_binary)],cwd=ROOT,check=True)
        result=subprocess.run([str(player_binary)],cwd=ROOT,text=True,capture_output=True,check=True)
        player_log=out/(args.label+'-player.log');player_log.write_text(result.stdout+result.stderr)
        player_rows=[list(map(int,line.split())) for line in result.stdout.splitlines()]
        assert len(player_rows)==2400
        for act,era,tick,pre_locked,locked,elapsed,buttons,x,vx in player_rows:
            expected=references[act,plc_wait[act,era],tick]
            for field,value in [('pre_locked',pre_locked),('locked',locked),('elapsed',elapsed)]:
                if value!=expected[field]:
                    differences.append(dict(act=act,era=era,tick=tick,field='player_'+field,
                        native=value,retail=expected[field]))
            assert buttons==(0 if expected['pre_locked'] else 8)
            if tick==131+plc_wait[act,era]:assert vx>0,('first allowed Right input',act,era,x,vx)
        player_evidence=[player_log,player_binary]
    sources=['tools/test_title_card.py','tools/title_card_test.c',args.native_card,'src/title_card.h',
        'tools/test_sonic_animation.py','tools/special_retail.py',
        '.deps/scddisasm/src/Level/_Definitions.inc','.deps/scddisasm/src/_Include/Main CPU Variables.inc',
        '.deps/scddisasm/src/Level/_Objects/Title Card/Main.asm',
        '.deps/scddisasm/src/Level/Palmtree Panic/Title Card Data.asm',
        '.deps/scddisasm/src/Level/Object Functions.asm','.deps/scddisasm/src/Level/Object Spawner.asm',
        '.deps/scddisasm/src/Level/Functions (General).asm','.deps/scddisasm/src/Level/Main.asm',
        '.deps/scddisasm/src/Level/_Objects/HUD and Points/Main.asm']
    sources += player_sources+['src/scd_player.h','tools/title_card_plc.py']
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    report=dict(passed=not differences,scope='isolated_component' if args.component_only else 'component_and_native_player',
        limits='R11A title object with three act-number inputs; empty original scene. Fixture-controlled PLC draining, not original decompression timing. Native player cases are counted separately and omitted with --component-only; no full-entry, target or hardware proof.',
        cases=len(timelines),retail_states=sum(len(t['rows']) for t in timelines),
        native_states=len(native),native_player_states=len(player_rows),mismatches=len(differences),examples=differences[:12],
        milestones=milestones,retail_entries=entries,clock_end=clock_end,
        source_sha256={name:sha(ROOT/name) for name in sources},
        evidence_sha256={str(path.relative_to(ROOT)):sha(path) for path in [log,raw,binary]+player_evidence},
        retail_program_sha256=hashlib.sha256(program).hexdigest(),
        core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'))
    (out/(args.label+'-report.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(milestones=milestones,mismatches=len(differences)),indent=2))
    if differences:raise SystemExit(1)


if __name__=='__main__':main()
