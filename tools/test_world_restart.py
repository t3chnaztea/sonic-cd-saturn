#!/usr/bin/env python3
"""Death/warp restart ordering against actual world.c and selected main blocks.

The recording is a native state fixture. Hardware calls are stubbed. This does
not establish controller-earned death, full Saturn execution or console parity.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import power_guard
from qa_limits import atomic_json


def block(source, anchor):
    assert source.count(anchor) == 1, anchor
    start = source.index(anchor)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if not depth:
                return start, source[start:end + 1]
    raise AssertionError('unclosed source block')


def health():
    mount = os.environ.get("SCD_QA_MOUNT") or ("/".join(str(ROOT).split("/")[:3]) if str(ROOT).startswith("/Volumes/") else "")
    assert mount and Path(mount).is_mount(), 'the QA volume is not mounted'
    assert shutil.disk_usage(ROOT).free >= 100 * 1024**3, '100 GiB reserve missing'

PREFIX = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "world.h"
#include "act.h"
static scd_player_state player;
static unsigned background_resets, world_vblank_previous, simulation_tick=1;
static unsigned warp_timer, audio_warp_requests, configure_requests;
static unsigned stage_select_single_program, stage_select_finish_reason;
static int warp_destination=-1, warp_saved, replay_active;
static int era, camera_x, zone_art_bank_loaded, boss_clut_state, checkpoint_ramp;
static struct { int ramp; } background_scroll;
scd_act_state scd_act_get(void){return (scd_act_state){0};}
scd_player_state scd_player_get(void){return player;}
scd_checkpoint scd_player_checkpoint(void){return (scd_checkpoint){0};}
void scd_player_warp_save(void){warp_saved=1;}
void scd_player_warp_clear(void){warp_saved=0;}
static int scd_objects_generator(void){return 0;}
static int scd_objects_timepost(void){return 0;}
static void scd_audio_warp(int on){audio_warp_requests+=(unsigned)on;}
static void warp_configure(void){configure_requests++;}
static void scd_audio_era(int value){(void)value;}
static void scd_background_reset(void *value,int x){(void)value;(void)x;}
static void zone_object_art_load(void){}
void stage_select_scene_finish(unsigned reason){stage_select_finish_reason=reason;stage_select_single_program=0;}
static void native_main_boundaries(void){
/* One main-loop iteration preserves the extracted continue statement. */
do {
'''

SUFFIX = r'''
}while(0);
}
int main(int argc,char **argv){
    assert(argc==5 || argc==7);
    unsigned seed=(unsigned)atoi(argv[1]),dead_steps=(unsigned)atoi(argv[2]);
    unsigned reset=(unsigned)atoi(argv[3]),expected=(unsigned)atoi(argv[4]);
    stage_select_single_program=argc==7?(unsigned)atoi(argv[5]):0;
    unsigned expected_finish=argc==7?(unsigned)atoi(argv[6]):0;
    assert(seed>0 && seed<=230 && dead_steps<=200 && reset<=1 && expected<=1);
    assert(stage_select_single_program<=1 && (expected_finish==0 || expected_finish==4));
    player=(scd_player_state){.routine=2,.speed=1536,.x=3000*65536};
    scd_world_zone(0);scd_world_act(0);scd_world_reset(0);scd_world_activate(1);
    while(scd_world_get().ticks<seed)assert(scd_world_step(player)<0);
    player.routine=6;player.speed=0;
    for(unsigned i=0;i<dead_steps;i++)assert(scd_world_step(player)<0);
    unsigned before=scd_world_get().ticks;
    player.routine=2;player.resets=reset;
    if(!reset)player.speed=1536;
    native_main_boundaries();
    unsigned queued=warp_timer!=0;
    printf("{\"seed_ticks\":%u,\"dead_updates\":%u,\"reset\":%u,"
           "\"ticks_before_restart_boundaries\":%u,\"ticks_after\":%u,"
           "\"direction_after\":%d,\"warp_timer\":%u,\"destination\":%d,"
           "\"audio_warp_requests\":%u,\"configure_requests\":%u,"
           "\"expected_queue\":%u,\"observed_queue\":%u,"
           "\"scene_finish_reason\":%u,\"expected_scene_finish\":%u}\n",
           seed,dead_steps,reset,before,scd_world_get().ticks,scd_world_get().direction,
           warp_timer,warp_destination,audio_warp_requests,configure_requests,expected,queued,
           stage_select_finish_reason,expected_finish);
    return queued==expected && stage_select_finish_reason==expected_finish?0:1;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main-source', type=Path, default=ROOT / 'src/main.c',
                        help='Explicit archived source for a red control; normal QA uses current main.c')
    args = parser.parse_args()
    health()
    out = ROOT / 'build/world-restart' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='pending', passed=False, cases=[], hardware_accepted=False,
                  scope='State fixture: actual world.c and verbatim selected main blocks; hardware/services stubbed',
                  main_source=str(args.main_source.resolve()),
                  current_main_under_test=args.main_source.resolve() == (ROOT / 'src/main.c').resolve(),
                  runtime=dict(platform=platform.platform(), uname=list(platform.uname()), python=platform.python_version()))
    atomic_json(out / 'report.json', report)
    try:
        selected_main = args.main_source.resolve()
        inputs = [selected_main, *(ROOT / n for n in ['src/world.c', 'src/world.h', 'src/act.h', 'src/scd_player.h', 'src/stage.h']), Path(__file__).resolve()]
        report['inputs'] = {str(p): power_guard.digest(p) for p in inputs}
        source = selected_main.read_text()
        fragments = [block(source, 'if(!replay_active){\n                if(scd_objects_generator())'),
                     block(source, 'if(player.resets!=background_resets){')]
        early = 'if(player.resets!=background_resets)scd_world_abort();'
        assert source.count(early) <= 1
        if early in source:
            fragments.append((source.index(early), early))
        fragments.sort()
        atomic_json(out / 'fragments.json', [dict(offset=offset, source=text) for offset, text in fragments])
        generated = out / 'main-world-boundaries.c'
        generated.write_text(PREFIX + '\n'.join(text for _, text in fragments) + SUFFIX)
        recording = [dict(id='reset-with-aged-travel', argv=['180', '70', '1', '0']),
                     dict(id='reset-before-commit', argv=['180', '0', '1', '0']),
                     dict(id='normal-travel-control', argv=['230', '0', '0', '1']),
                     dict(id='stage-select-travel-return', argv=['230', '0', '0', '0', '1', '4']),
                     dict(id='stage-select-reset-with-aged-travel', argv=['180', '70', '1', '0', '1', '0'])]
        atomic_json(out / 'fixture-recording.json', dict(kind='native_state_fixture_not_controller_recording', cases=recording))
        report.update(fixture_sha256=power_guard.digest(generated),
                      recording_sha256=power_guard.digest(out / 'fixture-recording.json'),
                      fragments_sha256=power_guard.digest(out / 'fragments.json'))
        compiler = subprocess.check_output(['/usr/bin/xcrun', '--find', 'clang'], text=True).strip()
        sdk = subprocess.check_output(['/usr/bin/xcrun', '--show-sdk-path'], text=True).strip()
        exe = out / 'main-world-boundaries'
        command = ['nice', '-n', '20', compiler, '-std=c11', '-O0', '-g', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-isysroot', sdk,
                   '-I' + str(ROOT / 'src'), str(generated), str(ROOT / 'src/world.c'), '-o', str(exe)]
        report.update(status='building', compiler=dict(path=compiler, sha256=power_guard.digest(Path(compiler))),
                      sdk=sdk, resolved_sdk=str(Path(sdk).resolve()), build_command=command)
        atomic_json(out / 'report.json', report)
        health()
        with (out / 'compile.log').open('w') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
        report.update(status='running', executable_sha256=power_guard.digest(exe))
        atomic_json(out / 'report.json', report)
        for case in recording:
            health()
            result = subprocess.run(['nice', '-n', '20', str(exe), *case['argv']], cwd=ROOT,
                                    capture_output=True, text=True, timeout=10)
            (out / (case['id'] + '.stdout')).write_text(result.stdout)
            (out / (case['id'] + '.stderr')).write_text(result.stderr)
            report['cases'].append(dict(id=case['id'], argv=case['argv'], exit_code=result.returncode,
                                        observed=json.loads(result.stdout), stderr=result.stderr,
                                        passed=result.returncode == 0))
            atomic_json(out / 'report.json', report)
        report['passed'] = all(c['passed'] for c in report['cases'])
        report['status'] = 'passed' if report['passed'] else 'failed'
        report['canonical_result'] = ('PASS' if report['passed'] else 'FAIL') + ': main death/warp boundary ' + str(sum(c['passed'] for c in report['cases'])) + '/' + str(len(recording))
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error), passed=False)
        raise
    finally:
        report['finished'] = datetime.now().astimezone().isoformat()
        report['changed_inputs'] = [p for p, h in report.get('inputs', {}).items()
                                    if not Path(p).is_file() or power_guard.digest(Path(p)) != h]
        if report['changed_inputs']:
            report.update(status='invalidated', passed=False, canonical_result='FAIL: main death/warp inputs changed')
        atomic_json(out / 'report.json', report)
    print(report['canonical_result'], flush=True)
    print('report=' + str(out / 'report.json'), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
