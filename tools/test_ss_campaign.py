#!/usr/bin/env python3
"""Earned Stardust Speedway Good Future chain from real Continue backups.

SS1/SS2 naturally travel Present -> Past, destroy ET7, then finish in Past.
SS3C must finish the Metal Sonic race and Amy rescue, write the MM1 save,
and cold Continue that exact backup. No constructed saves or gameplay RAM writes.
The entry is the earned WW3 backup. Host-only results never close Saturn gates.
Use --prepare-only to validate/compile the host while route dependencies remain.
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
ZONE = 5
NEXT_ZONE = 6
# R7 Z71ACT.C:226 / Z72ACT.C:67: ID169 -> act41 ET7, eras96 (Present/Past).
GENERATOR = {0: (3824, 1216), 1: (752, 1216)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry_evidence(path, backup, disc_sha, act):
    """Bind each Continue input to the preceding successful same-BIN gate."""
    prior = json.loads(path.read_text())
    expected = ('WW', 3) if act == 0 else ('SS', act)
    assert prior.get('status') == 'passed' and prior.get('passed') is True, 'entry campaign did not pass'
    assert (prior.get('zone'), prior.get('act')) == expected, ('entry campaign link', expected)
    assert prior.get('disc_sha256') == disc_sha, 'entry campaign used a different BIN'
    assert prior.get('backup_after_sha256') == sha(backup), 'entry backup differs from earned output'
    return dict(path=str(path), sha256=sha(path), zone=expected[0], act=expected[1])


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
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    scd_player_objects_lead_run();
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
    if(act==2)return x|(y<<9);
    unsigned travel=(unsigned)(w.direction+1),charge=w.ticks/32;
    unsigned vertical=p.vy<-256?0:p.vy>256?2:1;
    return x|(y<<9)|(travel<<15)|(campaign_phase()<<17)|((charge&31)<<19)|((uint32_t)(plring!=0)<<24)|(vertical<<25);
}
static double cell_value(void){
    scd_player_state p=scd_player_get();scd_world_state w=scd_world_get();int x=p.x/65536,y=p.y/65536;
    if(act==2)return x;
    if(campaign_phase()==1)
        return 1000000.0-sqrt((double)(x-(int)generator_x)*(x-(int)generator_x)+(double)(y-(int)generator_y)*(y-(int)generator_y));
    if(campaign_phase()==2)return 2000000.0+x-(w.direction?2000.0*w.ticks:0.0);
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
            fprintf(stderr,"SS campaign: warps=%u arrival=%u generator=%u final_era=%u good_future=%u\\n",
                    warps,arrival_seq,generator_seq,era,(unsigned)scd_world_get().good_future);'''
    return once(text, old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--script', type=Path, help='a searched campaign script (skip the search)')
    parser.add_argument('--search', action='store_true', help='search again instead of tests/routes/ss/campaign/ss<act>-good.txt')
    parser.add_argument('--prefix', type=Path, help='search prefix script (default: the start of tests/routes/ss/ss<act>A.txt)')
    parser.add_argument('--prefix-pads', type=int, default=600, help='pads of the default prefix to keep')
    parser.add_argument('--seed', type=int, default=41)
    parser.add_argument('--iterations', type=int, default=200000)
    parser.add_argument('--backup', type=Path, help='entry backup RAM (default: the previous link of the chain)')
    parser.add_argument('--entry-report', type=Path, help='preceding passed campaign report (default: beside entry backup)')
    parser.add_argument('--source-root', type=Path, default=ROOT,
                        help='tree holding src/, tools/qq_route_search.c, build/probe-source and assets/generated '
                             '(a snapshot matching the disc)')
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--prepare-only', action='store_true', help='compile derived host; no route or emulator acceptance')
    parser.add_argument('--cue', type=Path, default=ROOT/'dist/sonic-cd-saturn-prototype.cue')
    parser.add_argument('--elf', type=Path, default=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    args = parser.parse_args()
    act = args.act - 1
    era = 'C' if act == 2 else 'A'
    src_root = args.source_root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='pending', passed=False, hardware_tested=False, zone='SS', act=args.act, start_era=era, steps=[])
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
        ss_boss = (src_root/'src/boss_r7.c').is_file()
        assert act < 2 or ss_boss, 'SS3 campaign requires the integrated R7 boss runtime and route host'
        native = NATIVE + (['src/boss_r7.c'] if ss_boss else [])
        original = [f'build/probe-source/{n}.c' for n in (*ORIGINAL, *(['boss_7'] if ss_boss else []))]
        run('compile-host', ['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                             '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source',
                             '-DR1', '-DR11A', '-DROUTE_SS', source, *native, *original, '-o', host], cwd=src_root)
        assets = [f'assets/generated/ss7{args.act}{e}.bin' for e in ('C', 'D') if act == 2]
        if act < 2:
            assets = [f'assets/generated/ss7{args.act}{e}.bin' for e in 'ABCD']
        assets += [f'assets/generated/sscollision7{args.act}{e}.bin' for e in ('CD' if act == 2 else 'ABCD')]
        assets += [f'assets/generated/ssobj7{args.act}.bin']
        includes = sorted(str(p.relative_to(src_root)) for p in (src_root/'src').glob('*.inc'))
        report.update(derived_host_sha256=sha(source), source_root=str(src_root),
                      host_binary_sha256=sha(host),
                      host_inputs={p: sha(src_root/p) for p in ['tools/qq_route_search.c', *native, *original,
                                                                 *assets, *includes, 'tools/prepare_player.py']})
        if args.prepare_only:
            report.update(status='prepared', limits='Derived host compiled; campaign route and Saturn chain unverified.');save()
            print(f'PREPARED: SS{args.act} campaign host; routes and Saturn verification pending')
            return
        mode = f'{act}:{era}'
        script = out/'script.txt'
        stored = ROOT/f'tests/routes/ss/campaign/ss{args.act}-good.txt'
        if args.script:
            script.write_text(args.script.read_text());report['script_source'] = str(args.script)
        elif act == 2 or stored.is_file() and not args.search:
            src = ROOT/('tests/routes/ss/ss3C.txt' if act == 2 else f'tests/routes/ss/campaign/ss{args.act}-good.txt')
            script.write_text(src.read_text());report['script_source'] = str(src.relative_to(ROOT))
        else:
            prefix = args.prefix
            if not prefix:
                prefix, left, lines = out/'prefix.txt', args.prefix_pads, []
                for line in (ROOT/f'tests/routes/ss/ss{args.act}A.txt').read_text().splitlines():
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
        camp = re.search(r'SS campaign: warps=(\d+) arrival=(\d+) generator=(\d+) final_era=(\d+) good_future=(\d+)', hlog)
        assert tally and camp, 'host route did not finish the tally'
        if act < 2:
            assert camp[1] == '1' and int(camp[3]) > int(camp[2]) > 0 and camp[4] == '1' and camp[5] == '1', ('host campaign', camp[0])
        else:
            assert tally[2] == '2', ('host Act 3 era', tally[0])
            race = 'SS race complete: seen=1 race=1 result=1 escaped=1 stationary=1'
            assert race in hlog, 'SS3 race, Eggman escape and Amy result callback not proven'
            report['host_race'] = race
        expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
        report.update(host_tally=tally[0], host_campaign=camp[0], host_positions=len(expected),
                      script_sha256=sha(script), pad_sha256=sha(pad),
                      host_generator_sequence=int(camp[3]), host_arrival_sequence=int(camp[2]))
        if args.host_only:
            report.update(status='host-only');save()
            print(f'HOST: SS{args.act} campaign {len(expected)} positions; {camp[0]}; Saturn verification pending')
            return
        cue, elf = args.cue.resolve(), args.elf.resolve()
        disc = cue.parent/re.search(r'FILE "([^"]+)"', cue.read_text())[1]
        disc_sha, elf_sha = sha(disc), sha(elf)
        assert elf_matches_disc(elf, disc, out), 'ELF program is not the disc A.BIN'
        listing = subprocess.check_output([NM, elf], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
        backup = (args.backup or out.parent/('WW3' if act == 0 else f'SS{args.act-1}')/'backup-after.bin').resolve()
        assert backup.is_file() and backup.stat().st_size == 32768, ('entry backup', backup)
        backup_sha = sha(backup)
        prior_path = (args.entry_report or backup.parent/'report.json').resolve()
        report['entry_evidence'] = entry_evidence(prior_path, backup, disc_sha, act)
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
        entry_good = (0, 1, 3)[act]
        assert before[5] & 0xff == entry_good, ('entry earned acts', before, entry_good)
        assert before[5] & (0x100 << (ZONE-1)), 'entry lost earned Wacky Workbench Good Future'
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
            assert after[5] & ~0xff == before[5] & ~0xff, 'prior campaign flags changed'
            facts = dict(warp_sequence=wa[0], arrival_sequence=wb[0], arrival_xy=wb[2:4],
                         generator_sequence=rows[gen][0], generator_xy=rows[gen][2:4],
                         generator_points=future[gen][4]-future[gen-1][4], handoff_sequence=hb[0], handoff=hb[9:12])
        else:
            assert len(changes) == 1 and changes[0][1][9:12] == [NEXT_ZONE, 0, 0], ('MM handoff', report['stage_transitions'])
            hb = changes[0][1]
            assert all(r[9:12] == [ZONE, 2, 2] for r in rows[:n]), 'left Act 3 Good Future early'
            phases = list(dict.fromkeys(r[1] for r in results if r[0] < hb[0]))
            # scd_act_ss_goal starts at EXIT, without sign spin or capsule delay.
            assert phases == [0, 3, 4, 5, 6], ('Act 3 results sequence', phases)
            assert after[3] == before[3] + 1 and after[4] == NEXT_ZONE, ('MM checkpoint', after)
            assert after[5] & 0xff == 0 and after[5] & (0x100 << ZONE), ('saved good zones', hex(after[5]))
            assert after[5] == (before[5] & ~0xff) | (0x100 << ZONE), 'prior campaign flags lost at MM handoff'
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
            assert mailbox[7] & 0xffffff == NEXT_ZONE and saved['trace'][0] == 0x53434432, ('cold Continue active MM1', mailbox)
            assert (cold/'backup.bin').read_bytes() == (out/'backup-after.bin').read_bytes()
            facts.update(cold_continue_mailbox=mailbox)
        assert sha(disc) == disc_sha and sha(elf) == elf_sha and sha(backup) == backup_sha, 'inputs changed during the run'
        report.update(facts, status='passed', passed=True, matched_positions=n, observations=len(rows),
                      respawns=respawns, late_gameplay_intervals=late, backup_after_sha256=sha(out/'backup-after.bin'),
                      limits='Emulator (Beetle Saturn) replay of a native-host pad route from an earned Continue save. '
                             'Not hardware acceptance or whole-act retail parity.')
        save()
        what = (f"generator at {facts['generator_sequence']}, handoff {facts['handoff']}" if act < 2
                else f"race/Amy, results, MM save, cold Continue {facts['cold_continue_mailbox'][4:7]}")
        print(f'PASS: SS{args.act} earned campaign; {n} matched positions; 0 respawns; 0 late; {what}; disc {disc_sha[:12]}')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error)[:2000])
        save()
        raise


if __name__ == '__main__':
    main()
