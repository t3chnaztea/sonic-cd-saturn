#!/usr/bin/env python3
"""Earned Good Future campaign through Quartz Quadrant, from the real Continue menu.

Three Saturn runs, each from the backup RAM the previous run wrote (no save is
constructed and no gameplay RAM is written):

  --act 1  QQ1 from the earned TT3 -> Quartz Quadrant save (the TT3 link of
           tools/test_tt_campaign.py, by default <output>/../TT3/backup-after.bin):
           Present, natural travel to the Past, destroy the robot generator,
           finish the act in the Past. The Act 2 save must carry flag bit 0.
  --act 2  QQ2 from the --act 1 save: the same in Act 2. Both flags set, so the
           tally must hand off to Act 3 in the Good Future (era C).
  --act 3  QQ3 Good Future from the --act 2 save: boss, capsule, results and
           the Wacky Workbench Act 1 save, then a cold Continue of that save.

Original rules (.deps/scddisasm/src): Level/_Objects/Robot Generator/Main.asm:84
sets goodFuture when the generator is destroyed (and adds 1,500 points);
Level/_Objects/Results/Main.asm:301-310 moves goodFuture into goodFutureFlags bit
(act-1) at the Act 1/2 results and sets goodFuture for Act 3 once the flags are
%11; Results/Main.asm:287-290 clears the flags after Act 3.

Acts 1-2 host: a derivation of tools/qq_route_search.c (text anchors, like
tools/test_tt_campaign.py) whose step performs the natural warp arrival the way
src/main.c load_era() does (scd_player_arrive, scd_world_arrived, camera)
instead of ending the run. The search may warp only Present -> Past, once, and a
tally before the generator prunes the branch. The search prefix is the start of
the level-select Present route tests/routes/qq/qq<act>A.txt (--prefix-pads);
found routes are kept in tests/routes/qq/campaign/qq<act>-good.txt and replayed
by default. Act 3 replays tests/routes/qq/qq3C.txt (the level-select Good Future
route).

Not hardware acceptance. Pass --cue/--elf copies so a parallel rebuild cannot
change the disc mid-run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from test_qq_route import NATIVE, ORIGINAL, records  # noqa: E402
from test_tt_travel import elf_matches_disc  # noqa: E402
from test_cc_campaign_route import campaign_harness  # noqa: E402

CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
NM = ROOT / '.toolchain/bin/sh-elf-nm'
TAIL = 300
ZONE = 3
NEXT_ZONE = 4
# R5 robot generator placements (type 153, Present+Past), assets/generated/qqobj5{1,2}.bin.
GENERATOR = {0: (3584, 208), 1: (7328, 272)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def once(text, old, new):
    assert text.count(old) == 1, ('derived-source anchor changed', old[:70])
    return text.replace(old, new)


def host_source(source_root):
    text = (source_root / 'tools/qq_route_search.c').read_text()
    text = once(text, '#include "camera_v.h"', '#include "camera_v.h"\n#include "arrival_camera.h"')
    text = once(text, 'static void load(void){\n    memcpy(data,pristine,data_size);', '''static unsigned char era_data[4][400000],era_collision[4][9472];
static size_t era_size[4];
static unsigned start_era,warps,generator_seq,arrival_seq,generator_x,generator_y;
static int pending_arrival=-1;
static void load_eras(void){
    unsigned keep=era;
    for(unsigned e=0;e<4;e++){
        if(act==2 && e<2)continue;
        era=e;read_assets();memcpy(era_data[e],data,data_size);era_size[e]=data_size;memcpy(era_collision[e],collision,9472);
    }
    era=keep;read_assets();
}
/* src/main.c load_era() with travel_loading: the destination era's stage and
   collision, scd_player_arrive, scd_world_arrived and the arrival camera. */
static void arrive(void){
    era=(unsigned)pending_arrival;pending_arrival=-1;
    data_size=era_size[era];memcpy(data,era_data[era],data_size);memcpy(collision,era_collision[era],9472);
    if(stage_open(&stage,data,data_size))exit(2);
    if(scd_player_arrive(&stage,collision,9472,era)){dead=5;return;}
    scd_player_objects_lead();
    scd_world_arrived(era);warps++;arrival_seq=sequence;
    (void)scd_player_music_event();
    scd_player_state a=scd_player_get();
    camera_y=scd_camera_v_begin(ROUTE_ZONE,act,era,a.y/65536,a.resets);camera_x=scd_camera_h();
    {int unused;scd_arrival_camera(a.x/65536,a.y/65536,act,scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&unused);}
    scd_camera_h_sync(camera_x);
    /* The cutscene keeps sampling the last pad request. */
    delayed=buttons;
}
static void load(void){
    era=start_era;warps=generator_seq=arrival_seq=0;pending_arrival=-1;
    data_size=era_size[era];memcpy(pristine,era_data[era],data_size);memcpy(pristine_collision,era_collision[era],9472);
    memcpy(data,pristine,data_size);''')
    text = once(text, 'if(scd_objects_generator())scd_world_generator_destroyed();',
                'if(scd_objects_generator()){scd_world_generator_destroyed();'
                'if(generator_seq || era!=1)dead=7;else generator_seq=sequence;}')
    text = once(text, 'if(scd_world_step_vblanks(p,world_vblanks)>=0)dead=2;',
                '{int target=scd_world_step_vblanks(p,world_vblanks);if(target>=0){'
                'if(!warps && era==0 && target==1)pending_arrival=target;else dead=4;}}')
    text = once(text, 'if(result.phase==SCD_ACT_DONE)done=1;',
                'if(result.phase==SCD_ACT_DONE){if(generator_seq || act==2)done=1;else dead=6;}')
    text = once(text, '''    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
}''', '''    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
    if(pending_arrival>=0 && !dead)arrive();
}''')
    begin = text.index('static uint32_t cell_key(void){')
    end = text.index('static void archive(void){', begin)
    text = text[:begin] + '''static unsigned campaign_phase(void){return act==2?0:generator_seq?2:warps?1:0;}
static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();scd_world_state w=scd_world_get();
    unsigned x=(unsigned)(p.x/65536<0?0:p.x/65536>16383?16383:p.x/65536)/32,y=(unsigned)(p.y/65536<0?0:p.y/65536>2047?2047:p.y/65536)/32;
    if(act==2){unsigned grind=(unsigned)(2400-grind_left)/64;
        return x|(y<<9)|(boss_stage()<<15)|((grind&63)<<18)|((uint32_t)(boss_hits&3)<<24);}
    unsigned travel=campaign_phase()?0:w.direction<0?1+(w.ticks>=60?1:0)+(w.ticks>=150?1:0):w.direction>0?4:0;
    return x|(y<<9)|(travel<<15)|(campaign_phase()<<18);
}
static double cell_value(void){
    scd_player_state p=scd_player_get();scd_world_state w=scd_world_get();int x=p.x/65536,y=p.y/65536;
    if(act==2){
        double v=boss_stage()*100000.0+boss_hits*20000.0+(2400-grind_left)*30.0+x;
        if(boss_stage()>=1 && boss_stage()<4){const sprite_status *m=boss_actor(52);
            if(m){int bx=m->xposi.w.h,by=m->yposi.w.h;v-=sqrt((double)(x-bx)*(x-bx)+(double)(y-by)*(y-by))*20.0;}}
        return v;
    }
    if(campaign_phase()==1)
        return 1000000.0-sqrt((double)(x-(int)generator_x)*(x-(int)generator_x)+(double)(y-(int)generator_y)*(y-(int)generator_y));
    if(campaign_phase()==2)return 2000000.0+x;
    /* Present: arm a Past post, then keep the warp clock running. */
    return (w.direction<0?200000.0+w.ticks*2000.0:w.direction>0?-200000.0:0.0)+x;
}
''' + text[end:]
    text = once(text, '    read_assets();\n    if(!strcmp(argv[1],"search"))',
                '    read_assets();start_era=era;load_eras();\n'
                f'    generator_x=act?{GENERATOR[1][0]}:{GENERATOR[0][0]};generator_y=act?{GENERATOR[1][1]}:{GENERATOR[0][1]};\n'
                '    if(!strcmp(argv[1],"search"))')
    old = '''fprintf(stderr,"Tally complete: sequence=%u act=%u era=%u score=%u boss_hits=%u lowered=%u grind_left=%d escaped=%u\\n",
                    sequence,act,era,p.score,boss_hits,boss_lowered,grind_left,escaped);'''
    new = old + '''
            fprintf(stderr,"QQ campaign: warps=%u arrival=%u generator=%u final_era=%u good_future=%u\\n",
                    warps,arrival_seq,generator_seq,era,(unsigned)scd_world_get().good_future);'''
    return once(text, old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--script', type=Path, help='a searched campaign script (skip the search)')
    parser.add_argument('--search', action='store_true', help='search again instead of tests/routes/qq/campaign/qq<act>-good.txt')
    parser.add_argument('--prefix', type=Path, help='search prefix script (default: the start of tests/routes/qq/qq<act>A.txt)')
    parser.add_argument('--prefix-pads', type=int, default=600, help='pads of the default prefix to keep')
    parser.add_argument('--seed', type=int, default=41)
    parser.add_argument('--iterations', type=int, default=200000)
    parser.add_argument('--backup', type=Path, help='entry backup RAM (default: the previous link of the chain)')
    parser.add_argument('--source-root', type=Path, default=ROOT,
                        help='tree holding src/, tools/qq_route_search.c, build/probe-source and assets/generated '
                             '(a snapshot matching the disc)')
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--cue', type=Path, default=ROOT/'dist/sonic-cd-saturn-prototype.cue')
    parser.add_argument('--elf', type=Path, default=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    args = parser.parse_args()
    act = args.act - 1
    era = 'C' if act == 2 else 'A'
    src_root = args.source_root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='pending', passed=False, hardware_tested=False, zone='QQ', act=args.act, start_era=era, steps=[])
    report_path = out / 'report.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def run(name, command, cwd=ROOT, env=None, timeout=14400):
        report['steps'].append(dict(name=name, command=list(map(str, command)), status='pending'));save()
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        report['steps'][-1].update(status='passed' if result.returncode == 0 else 'failed', exit_code=result.returncode);save()
        assert result.returncode == 0, (name, result.returncode, out/(name+'.log'))
    save()
    try:
        source = out/'campaign_search.c'
        source.write_text(host_source(src_root))
        host = out/'campaign_search'
        original = [f'build/probe-source/{n}.c' for n in ORIGINAL]
        run('compile-host', ['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                             '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source',
                             '-DR1', '-DR11A', source, *NATIVE, *original, '-o', host], cwd=src_root)
        report.update(derived_host_sha256=sha(source), source_root=str(src_root),
                      host_inputs={p: sha(src_root/p) for p in ['tools/qq_route_search.c', *NATIVE, *original,
                                                                 f'assets/generated/qqobj5{args.act}.bin']})
        mode = f'{act}:{era}'
        script = out/'script.txt'
        stored = ROOT/f'tests/routes/qq/campaign/qq{args.act}-good.txt'
        if args.script:
            script.write_text(args.script.read_text());report['script_source'] = str(args.script)
        elif act == 2 or stored.is_file() and not args.search:
            src = ROOT/('tests/routes/qq/qq3C.txt' if act == 2 else f'tests/routes/qq/campaign/qq{args.act}-good.txt')
            script.write_text(src.read_text());report['script_source'] = str(src.relative_to(ROOT))
        else:
            prefix = args.prefix
            if not prefix:
                prefix, left, lines = out/'prefix.txt', args.prefix_pads, []
                for line in (ROOT/f'tests/routes/qq/qq{args.act}A.txt').read_text().splitlines():
                    count, pad = map(int, line.split())
                    if left <= 0:
                        break
                    lines.append(f'{min(count, left)} {pad}');left -= min(count, left)
                prefix.write_text('\n'.join(lines) + '\n')
            report.update(search_prefix=str(prefix), search_prefix_sha256=sha(prefix), seed=args.seed, iterations=args.iterations)
            run('search', [host, 'search', mode, args.seed, args.iterations, script, prefix], cwd=src_root)
        pad = out/'controller.txt'
        run('host-replay', [host, 'replay', mode, script, 46000, pad], cwd=src_root)
        hlog = (out/'host-replay.log').read_text()
        tally = re.search(r'Tally complete: sequence=(\d+) act=\d+ era=(\d+) score=(\d+) boss_hits=(\d+) lowered=(\d+) '
                          r'grind_left=(-?\d+) escaped=(\d+)', hlog)
        camp = re.search(r'QQ campaign: warps=(\d+) arrival=(\d+) generator=(\d+) final_era=(\d+) good_future=(\d+)', hlog)
        assert tally and camp, 'host route did not finish the tally'
        if act < 2:
            assert camp[1] == '1' and int(camp[3]) > int(camp[2]) > 0 and camp[4] == '1' and camp[5] == '1', ('host campaign', camp[0])
        else:
            assert tally[2] == '2', ('host Act 3 era', tally[0])
        expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
        report.update(host_tally=tally[0], host_campaign=camp[0], host_positions=len(expected),
                      script_sha256=sha(script), pad_sha256=sha(pad),
                      host_generator_sequence=int(camp[3]), host_arrival_sequence=int(camp[2]))
        if args.host_only:
            report.update(status='host-only');save()
            print(f'HOST: QQ{args.act} campaign {len(expected)} positions; {camp[0]}; Saturn verification pending')
            return
        cue, elf = args.cue.resolve(), args.elf.resolve()
        disc = cue.parent/re.search(r'FILE "([^"]+)"', cue.read_text())[1]
        disc_sha, elf_sha = sha(disc), sha(elf)
        assert elf_matches_disc(elf, disc, out), 'ELF program is not the disc A.BIN'
        listing = subprocess.check_output([NM, elf], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        backup = (args.backup or out.parent/('TT3' if act == 0 else f'QQ{args.act-1}')/'backup-after.bin').resolve()
        assert backup.is_file() and backup.stat().st_size == 32768, ('entry backup', backup)
        backup_sha = sha(backup)
        report.update(cue=str(cue), disc_sha256=disc_sha, elf_sha256=elf_sha, entry_backup=str(backup),
                      entry_backup_sha256=backup_sha, harness_sha256=sha(ROOT/'tools/emulator_test.c'),
                      core_sha256=sha(CORE))
        save()
        exe = campaign_harness(out, False, None)
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE=str(ZONE), SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                   SCD_OBJECTS_OVERLAY_FAULT=symbols['_scd_objects_overlay_fault'],
                   SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
                   SCD_ZONE_ROUTE_UPDATES=str(len(expected)+TAIL), SCD_ZONE_PAD_TAIL=str(TAIL),
                   SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_BACKUP_INPUT=str(backup),
                   SCD_BACKUP_OUTPUT=str(out/'backup-after.bin'))
        command = [exe, CORE, cue, ROOT/'assets/private', out, symbols['_scd_trace_mailbox'],
                   symbols['_scd_audio_mailbox'], 'zones']
        report['steps'].append(dict(name='saturn', command=list(map(str, command)), status='pending'));save()
        with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=7200)
        report['steps'][-1].update(status='passed' if result.returncode == 0 else 'failed', exit_code=result.returncode);save()
        core = (out/'core.log').read_text()
        assert result.returncode == 0, (re.search(r'CC pad mismatch: .*', core) or [f'emulator exit {result.returncode}'])[0]
        log = (out/'results.log').read_text()
        rows, future = records(log, 'CC route'), records(log, 'CC future')
        saves = {s[0]: s[1:] for s in records(log, 'CC save')}
        results = records(log, 'CC results')
        warp = dict(records(log, 'CC warp'))
        n = len(expected)
        assert len(rows) == len(future) == n + TAIL, ('observation count', len(rows), len(future), n + TAIL)
        for row in rows:
            row[3] -= (row[3] >= 1 << 31) << 32
        mismatch = next(((row[0], row[2:4], ref[2:4]) for row, ref in zip(rows, expected)
                         if [row[0], row[8], row[2], row[3]] != ref), None)
        assert mismatch is None, ('host/Saturn position', mismatch)
        assert all(b[0] == a[0] + 1 for a, b in zip(rows, rows[1:])), 'lost observation'
        respawns = max(r[6] for r in rows)
        assert respawns == 0, 'respawn'
        late = [(a[0], b[0], b[1]-a[1]) for a, b in zip(rows, rows[1:])
                if a[9:] == b[9:] and not warp.get(b[0]) and b[1]-a[1] != 1]
        assert not late, ('late gameplay interval', late[:3])
        changes = [(a, b) for a, b in zip(rows, rows[1:]) if a[9:12] != b[9:12]]
        report.update(stage_transitions=[dict(sequence=b[0], vblanks=b[1]-a[1], before=a[9:12], after=b[9:12])
                                         for a, b in changes])
        assert rows[0][9:12] == [ZONE, act, 'ABCD'.index(era)], ('Continue start', rows[0][9:12])
        before = saves[rows[0][0]]
        assert before[4] & 0xffff == ZONE | act << 8, ('entry save stage', before)
        after = saves[max(saves)]
        if act < 2:
            assert len(changes) == 2, ('transitions', report['stage_transitions'])
            (wa, wb), (ha, hb) = changes
            assert wa[9:12] == [ZONE, act, 0] and wb[9:12] == [ZONE, act, 1] and wb[1]-wa[1] >= 240, 'natural Present -> Past warp'
            assert wb[0] == int(camp[2]) + 1, ('arrival sequence', wb[0], camp[2])
            gen = next(i for i, f in enumerate(future) if f[1])
            assert all(f[1] == 0 for f in future[:gen]) and all(f[1] for f in future[gen:rows.index(ha)+1])
            assert rows[gen][11] == 1 and rows[gen][0] == int(camp[3]), ('generator in the Past', rows[gen][0:12])
            assert future[gen][4] - future[gen-1][4] == 1500, 'generator points'
            want = [ZONE, 1, 0] if act == 0 else [ZONE, 2, 2]
            assert ha[9:12] == [ZONE, act, 1] and hb[9:12] == want, ('act handoff', ha[9:12], hb[9:12])
            phases = list(dict.fromkeys(r[1] for r in results if r[0] < hb[0]))
            assert phases[-7:] == list(range(7)), ('Past sign/tally sequence', phases)
            stage = ZONE | (act + 1) << 8 | (2 << 16 if act == 1 else 0)
            good = 1 if act == 0 else 3
            assert after[3] == before[3] + 1 and after[4] == stage and after[5] & 0xff == good, ('checkpoint', after, hex(stage))
            facts = dict(warp_sequence=wa[0], arrival_sequence=wb[0], arrival_xy=wb[2:4],
                         generator_sequence=rows[gen][0], generator_xy=rows[gen][2:4],
                         generator_points=future[gen][4]-future[gen-1][4], handoff_sequence=hb[0], handoff=hb[9:12])
        else:
            assert len(changes) == 1 and changes[0][1][9:12] == [NEXT_ZONE, 0, 0], ('WW handoff', report['stage_transitions'])
            hb = changes[0][1]
            assert all(r[9:12] == [ZONE, 2, 2] for r in rows[:n]), 'left Act 3 Good Future early'
            phases = list(dict.fromkeys(r[1] for r in results if r[0] < hb[0]))
            # Act 3 has the capsule, not the sign: no SCD_ACT_SPIN (src/act.h).
            assert phases == [0, 2, 3, 4, 5, 6], ('Act 3 results sequence', phases)
            assert after[3] == before[3] + 1 and after[4] == NEXT_ZONE, ('WW checkpoint', after)
            # main.c zone change: goodFutureFlags clear; QQ (zone 3) joins the saved good zones.
            assert after[5] & 0xff == 0 and after[5] & (0x100 << ZONE), ('saved good zones', hex(after[5]))
            facts = dict(handoff_sequence=hb[0], handoff=hb[9:12])
        report.update(save_before=before, save_after=after)
        assert (out/'backup-after.bin').read_bytes() != backup.read_bytes(), 'backup RAM did not advance'
        if act == 2:
            cold = out/'cold-continue'
            cold.mkdir()
            env2 = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            env2.update(SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'], SCD_SAVE_CASE='continue',
                        SCD_BACKUP_INPUT=str(out/'backup-after.bin'), SCD_BACKUP_OUTPUT=str(cold/'backup.bin'))
            plain = out/'emulator_save'
            run('compile-save-harness', ['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                         '-I.deps/beetle-saturn/libretro-common/include', 'tools/emulator_test.c', '-o', plain])
            with (cold/'results.log').open('w') as o, (cold/'core.log').open('w') as e:
                subprocess.run(list(map(str, [plain, CORE, cue, ROOT/'assets/private', cold, symbols['_scd_trace_mailbox'],
                                              symbols['_scd_audio_mailbox'], 'save'])), cwd=ROOT, env=env2,
                               stdout=o, stderr=e, check=True, timeout=600)
            saved = json.loads((cold/'save.json').read_text())
            mailbox = saved['mailbox'][:10]
            assert mailbox[4:6] == after[3:5] and mailbox[6] == after[5], ('cold Continue', mailbox)
            assert (cold/'backup.bin').read_bytes() == (out/'backup-after.bin').read_bytes()
            facts.update(cold_continue_mailbox=mailbox)
        assert sha(disc) == disc_sha and sha(elf) == elf_sha and sha(backup) == backup_sha, 'inputs changed during the run'
        report.update(facts, status='passed', passed=True, matched_positions=n, observations=len(rows),
                      respawns=respawns, late_gameplay_intervals=late, backup_after_sha256=sha(out/'backup-after.bin'),
                      limits='Emulator (Beetle Saturn) replay of a native-host pad route from an earned Continue save. '
                             'Not hardware acceptance or whole-act retail parity.')
        save()
        what = (f"generator at {facts['generator_sequence']}, handoff {facts['handoff']}" if act < 2
                else f"boss, results, WW save, cold Continue {facts['cold_continue_mailbox'][4:7]}")
        print(f'PASS: QQ{args.act} earned campaign; {n} matched positions; 0 respawns; 0 late; {what}; disc {disc_sha[:12]}')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error)[:2000])
        save()
        raise


if __name__ == '__main__':
    main()
