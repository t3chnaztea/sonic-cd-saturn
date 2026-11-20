#!/usr/bin/env python3
"""Audit real player calls against original retail 68000 animation execution."""
import hashlib,json,os,struct,subprocess
from pathlib import Path
from test_sonic_animation import Retail,State
from sonic_animation_assets import ROOT,generate

def main():
    source=generate();out=ROOT/'build/player-animation';out.mkdir(exist_ok=True)
    # Only the native adapter has defined actor-word access and is sanitizer-safe.
    for tool in ['prepare_probe.py','prepare_player.py']:
        subprocess.run(['python3',str(ROOT/'tools'/tool)],cwd=ROOT,check=True)
    common=['clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv','-fno-strict-aliasing',
        '-Wno-parentheses','-Wno-unused-value','-Isrc','-Iassets/generated','-Ibuild/probe-source',
        '-DR1','-DR11A','-DSCD_PLAYER_ANIMATION_AUDIT','-fsanitize=address,undefined','-fno-sanitize-recover=all']
    sources=['src/player.c','src/camera_v.c','src/sonic_animation.c','src/stage.c','src/objects.c','src/act.c',
        'tools/player_animation_audit.c']+[f'build/probe-source/{s}.c' for s in ['interaction','player','dircol','fcol','etc','equ','movement']]
    retail=Retail(source['animation_entry']);records={};seen=set();controls=set();mappings=set()
    for name,driver,extra in [('order','tools/player_animation_order_test.c',[]),
            ('replay','tools/player_trace.c',['src/player_replay.c']),
            ('world','tools/world_test.c',['src/world_qa.c','src/world.c','src/background.c','src/background_r3.c'])]:
        exe=out/name;events=out/f'{name}.bin';log=out/f'{name}.log'
        subprocess.run(common+[driver]+sources+extra+['-o',str(exe)],cwd=ROOT,check=True)
        with log.open('w') as f:
            subprocess.run([str(exe)],cwd=ROOT,env={**os.environ,'SCD_ANIMATION_EVENTS':str(events)},stdout=f,stderr=subprocess.STDOUT,check=True)
        data=events.read_bytes();assert data and len(data)%17==0
        for i in range(0,len(data),17):
            row=data[i:i+17];speed,angle,flags,control=struct.unpack('>hBBB',row[6:11])
            expected=retail.step(State.from_buffer_copy(row[:6]),speed,angle,flags,control)
            assert expected==row[11:],(name,i//17,list(row),list(expected))
            seen.add(row[0]);controls.add(control);mappings.add(row[15])
        records[name]={'calls':len(data)//17,'sha256':hashlib.sha256(data).hexdigest(),'log':str(log.relative_to(ROOT))}
        print(f'{name}: {len(data)//17} actual player animation calls match retail exactly',flush=True)
    report={'passed':True,'routes':records,'animation_ids':sorted(seen),'control_flags':sorted(controls),
        'mapping_ids':sorted(mappings),'retail_program_sha256':source['retail_program_sha256'],
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ['src/player.c','src/camera_v.c','src/scd_player.h','src/sonic_animation.c','src/sonic_animation.h',
             'tools/player_animation_order_test.c','tools/player_animation_audit.c','tools/test_player_animation.py']},
        'limits':'Host player update ordering and real inputs; not target frame streaming, renderer pixels or physical hardware.'}
    assert {0,2,5,21,24,26,45}<=seen
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
