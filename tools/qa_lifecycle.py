#!/usr/bin/env python3
"""Bounded same-process host lifecycle fixtures. No console acceptance.

Generated wrappers include existing route hosts. Checkpoint activation, lethal
contact and era arrival are API/placement fixtures, not controller-earned paths.
Real player death/reload executes after the lethal-contact fixture. Object hash
and active-count equality after fresh load check repeatable cleanup, not RSS.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ZONES = ('ppz', 'cc', 'tt', 'qq', 'ww', 'ss', 'mm')
BASE = ['title_card', 'world', 'act', 'player', 'camera_v', 'sonic_animation', 'stage', 'boss', 'boss_r3', 'objects', 'player_plus']
CORE = ['interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement', 'boss_1', 'boss_3', 'playsp3']
CONFIG = {
    'ppz': ('cc_campaign_search.c', [], [], [], 'zone=0;act=0;ppz_mode=PPZ_PLAIN;plain=0;', 'ppz1.bin', 'collision1.bin'),
    'cc': ('cc_campaign_search.c', [], [], [], 'zone=1;act=0;plain=0;', 'cc31B.bin', 'cccollision31B.bin'),
    'tt': ('tt_route_search.c', ['boss_r4', 'water'], ['boss_4'], [], 'act=0;era=0;', 'tt41B.bin', 'ttcollision41B.bin'),
    'qq': ('qq_route_search.c', ['boss_r4', 'boss_r5', 'water'], ['boss_4', 'boss_5'], [], 'act=0;era=0;', 'qq51B.bin', 'qqcollision51B.bin'),
    'ww': ('qq_route_search.c', ['boss_r4', 'boss_r5', 'water', 'boss_r6', 'background_r6'], ['boss_4', 'boss_5', 'boss_6'], ['-DROUTE_WW'], 'act=0;era=0;', 'ww61B.bin', 'wwcollision61B.bin'),
    'ss': ('qq_route_search.c', ['boss_r4', 'boss_r5', 'water', 'boss_r7'], ['boss_4', 'boss_5', 'boss_7'], ['-DROUTE_SS'], 'act=0;era=0;', 'ss71B.bin', 'sscollision71B.bin'),
    'mm': ('qq_route_search.c', ['boss_r4', 'boss_r5', 'water', 'boss_r8'], ['boss_4', 'boss_5', 'boss_8', 'ending_8'], ['-DROUTE_MM'], 'act=0;era=0;', 'mm81B.bin', 'mmcollision81B.bin'),
}
WRAPPER = r'''
#undef main
#include <assert.h>
static uint8_t qa_data[400000],qa_col[9472];
static stage_t qa_stage;
static void qa_clean(void){
    pad_count=0; /* Never append scripts from a previous lifecycle. */
    load();
}
int main(int argc,char **argv){
    assert(argc==2);unsigned cycles=(unsigned)atoi(argv[1]);assert(cycles && cycles<=20);
    QA_SETUP
    read_assets();qa_clean();
    scd_object_stats baseline=scd_objects_get();scd_player_state first=scd_player_get();
    unsigned peak=baseline.active;
    for(unsigned cycle=0;cycle<cycles;cycle++){
        qa_clean();scd_object_stats fresh=scd_objects_get();scd_player_state start=scd_player_get();
        assert(fresh.hash==baseline.hash && fresh.active==baseline.active);
        assert(start.x==first.x && start.y==first.y && !start.resets && !scd_player_checkpoint().id);
        assert(!start.rings && !start.shield && start.lives==3);
        /* Controller-only bounded activity contaminates actors before fixtures. */
        unsigned controller_steps=0;
        for(unsigned i=0;i<300 && !dead && !done;i++){
            step(i<180?0:((i%48)<5?129:128));controller_steps++;
            scd_object_stats objects=scd_objects_get();if(objects.active>peak)peak=objects.active;
        }
        /* Restart at a clean spawn before checkpoint/death fixtures. */
        qa_clean();scd_player_state spawn=scd_player_get();
        scd_player_place(spawn.x/65536,spawn.y/65536,0,0,2);
        assert(scd_player_checkpoint_activate(2));scd_checkpoint saved=scd_player_checkpoint();
        scd_player_points(1230);scd_player_inventory(0,0);scd_player_powerup(4);
        scd_player_place(spawn.x/65536,scralim_down+300,0,0,2);
        scd_objects_hurt(spawn.x/65536-10);assert(scd_player_get().routine==6);
        unsigned death_steps=0;
        while(death_steps<700 && !scd_player_get().resets){scd_player_step(0);death_steps++;}
        scd_player_state restored=scd_player_get();scd_powerup_state powers=scd_player_powerups();
        assert(restored.resets==1 && restored.lives==2 && restored.routine==2);
        assert(restored.x/65536==saved.x && restored.y/65536==saved.y);
        assert(restored.elapsed==saved.elapsed/60*60 && restored.hurt==120);
        assert(restored.score==1230 && !restored.rings && !restored.shield && !powers.shoes && !powers.invincible);
        /* Direct arrival API into Past assets. No time-post/timer path is claimed. */
        size_t n=read_file("assets/generated/" QA_STAGE,qa_data,sizeof(qa_data));
        assert(!stage_open(&qa_stage,qa_data,n));
        assert(read_file("assets/generated/" QA_COLLISION,qa_col,sizeof(qa_col))==9472);
        scd_player_inventory(13,1);scd_player_warp_save();
        assert(!scd_player_arrive(&qa_stage,qa_col,sizeof(qa_col),1));
        scd_player_state arrival=scd_player_get();powers=scd_player_powerups();
        assert(arrival.rings==13 && arrival.score==1230 && arrival.lives==2 && arrival.hurt==120);
        assert(!arrival.shield && !powers.shoes && !powers.invincible && !scd_player_warp_saved());
        assert(scd_player_arrival_clear());
        /* main.c load_era schedules the lead actor update and runs it before
           displaying a warp arrival (1040,1118). Complete that caller boundary;
           a bare arrive() is not a whole loaded stage. */
        scd_player_objects_lead();scd_world_arrived(1);scd_player_objects_lead_run();
        printf("{\"cycle\":%u,\"controller_steps\":%u,\"death_steps\":%u,\"respawns\":%u,\"checkpoint_id\":%u,\"arrival_era\":1,\"peak_active\":%u,\"baseline_hash\":%u}\n",cycle,controller_steps,death_steps,restored.resets,saved.id,peak,baseline.hash);
        fflush(stdout);
    }
    qa_clean();scd_object_stats final=scd_objects_get();
    if(final.hash!=baseline.hash || final.active!=baseline.active)fprintf(stderr,"cleanup mismatch: hash %u/%u active %u/%u\n",final.hash,baseline.hash,final.active,baseline.active);
    assert(final.hash==baseline.hash && final.active==baseline.active && !scd_player_checkpoint().id);
    return 0;
}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def runtime_assets(zone):
    if zone == 'ppz':
        return [f'{prefix}{era}.bin' for prefix in ('ppz', 'collision') for era in range(4)] + [f'{prefix}1{act}{era}.bin' for prefix in ('ppz', 'collision') for act in (2,3) for era in ('ABCD' if act==2 else 'CD')]
    if zone == 'cc':
        return [f'{prefix}31{era}.bin' for prefix in ('cc', 'cccollision') for era in 'ABCD'] + ['ccobj31.bin']
    number={'tt':4,'qq':5,'ww':6,'ss':7,'mm':8}[zone]
    return [f'{prefix}{number}1{era}.bin' for prefix in (zone,zone+'collision') for era in 'AB'] + [f'{zone}obj{number}1.bin']


def inputs(source, zone, generated):
    host, native, original, _, _, _, _=CONFIG[zone]
    units=[source/'src'/f'{name}.c' for name in BASE+native]
    units += [source/'build/probe-source'/f'{name}.c' for name in CORE+original]
    files=set(units+[source/'tools'/host,generated])
    for directory in ('src','assets/generated','build/probe-source'):
        files.update(p for p in (source/directory).rglob('*') if p.is_file() and p.suffix.lower() in ('.h','.inc'))
    files.update(source/'assets/generated'/name for name in runtime_assets(zone))
    return units,{str(p):sha(p) for p in sorted(files)}


def run_case(source, output, zone, flags, cycles, compiler):
    folder=output/f'{zone}-{flags}';folder.mkdir()
    host,_,_,defines,setup,stage,collision=CONFIG[zone]
    generated=folder/'lifecycle.c'
    generated.write_text('#define main qa_route_main\n#include '+json.dumps(str(source/'tools'/host))+'\n'+WRAPPER.replace('QA_SETUP',setup).replace('QA_STAGE',json.dumps(stage)).replace('QA_COLLISION',json.dumps(collision)))
    result={'status':'pending','passed':False,'zone':zone,'flags':flags,'cycles':cycles,'scope':'same-process host; API checkpoint, forced lethal contact, direct era arrival fixtures; not controller-earned transition or console acceptance','compiler':compiler}
    save(folder/'report.json',result)
    try:
        units,hashes=inputs(source,zone,generated);result['inputs']=hashes
        executable=folder/'lifecycle'
        command=['nice','-n','20','clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv','-fno-strict-aliasing','-Wno-parentheses','-Wno-unused-value','-w','-fsanitize=address,undefined','-fno-sanitize-recover=all',f'-I{source}/src',f'-I{source}/assets/generated',f'-I{source}/build/probe-source','-DR1','-DR11A',f'-DSCD_PLUS_HOST_FLAGS={flags}',*defines,str(generated),*map(str,units),'-o',str(executable)]
        result['build_command']=command;save(folder/'report.json',result)
        with (folder/'compile.log').open('w') as log:
            subprocess.run(command,cwd=source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        result['executable_sha256']=sha(executable)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SCD_','PPZ_','CC_','TT_','QQ_'))}
        env['ASAN_OPTIONS']='detect_leaks=0'
        result['command']=['nice','-n','20',str(executable),str(cycles)];save(folder/'report.json',result)
        with (folder/'stdout.log').open('w') as stdout,(folder/'stderr.log').open('w') as stderr:
            subprocess.run(result['command'],cwd=source,env=env,stdout=stdout,stderr=stderr,check=True,timeout=120)
        rows=[json.loads(line) for line in (folder/'stdout.log').read_text().splitlines()]
        if len(rows)!=cycles or any(row.get('cycle')!=i or row.get('respawns')!=1 or row.get('checkpoint_id')!=2 or row.get('arrival_era')!=1 for i,row in enumerate(rows)):
            raise ValueError('missing lifecycle coverage')
        result['results']=rows
        changed=[name for name,digest in hashes.items() if sha(Path(name))!=digest]
        if changed:raise ValueError('input changed: '+str(changed))
        result.update(status='passed',passed=True)
    except BaseException as exc:
        result.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):
            save(folder/'report.json',result);raise
    save(folder/'report.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=ROOT)
    parser.add_argument('--zones',default=','.join(ZONES))
    parser.add_argument('--modes',default='0,31')
    parser.add_argument('--cycles',type=int,default=4)
    parser.add_argument('--jobs',type=int,choices=range(1,5),default=2)
    args=parser.parse_args(argv)
    zones=list(dict.fromkeys(args.zones.split(',')))
    modes=list(dict.fromkeys(args.modes.split(',')))
    if not 1<=args.cycles<=20 or any(z not in ZONES for z in zones) or any(m not in ('0','31') for m in modes):
        parser.error('known zones, modes0/31 and cycles1..20 required')
    source=args.source_root.resolve();base=ROOT/'build/qa-lifecycle';base.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-'),dir=base))
    report={'status':'pending','passed':False,'hardware_tested':False,'source_root':str(source),'cycles':args.cycles,'jobs':args.jobs,'results':[]}
    save(output/'report.json',report)
    try:
        compiler=subprocess.check_output(['clang','--version'],text=True)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures=[pool.submit(run_case,source,output,z,int(m),args.cycles,compiler) for z in zones for m in modes]
            for future in futures:
                report['results'].append(future.result());save(output/'report.json',report)
        report['passed']=all(case['passed'] for case in report['results'])
        report['status']='passed' if report['passed'] else 'failed'
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=f'{type(exc).__name__}: {exc}')
        save(output/'report.json',report);raise
    save(output/'report.json',report)
    print(f'{"PASS" if report["passed"] else "FAIL"}: host lifecycle: {len(report["results"])} zone/mode cases x {args.cycles} cycles; report={output/"report.json"}')
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
