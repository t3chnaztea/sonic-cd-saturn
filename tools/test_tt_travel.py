#!/usr/bin/env python3
"""Search controller input for one natural TT warp, then observe Saturn arrival.

Port of tools/test_qq_travel.py to Tidal Tempest (round 4, level-select zone 2).
The derived host (tools/tt_route_search.c) changes only search goals and
termination, not the gameplay step: a committed warp (scd_world_step >= 0,
Main.asm ObjSonic_TimeWarp timer 230) ends the run; a warp to another era than
--to, the tally, a death or drowning prunes the branch. The Saturn harness is
tools/emulator_test.c unchanged (snapshotted into the output). No gameplay RAM
writes, debug era keys, or constructed time-post state are used.

Era letters as level select: A Present, B Past, C Good Future, D Bad Future.
Level select starts the Present with no Good Future, so the natural pairs are
A->B (past post), A->D (future post), B->A (future post), C->A / D->A (past post).

Unlike QQ there is no R5 background slave in TT, so the slave-readiness gate is
replaced by: at least 100 resumed post-arrival updates with no late interval.

Emulator mode: pass --cue/--elf copies (not dist/) so a parallel rebuild cannot
change the disc mid-run; the tool checks that the ELF's program matches the
disc's A.BIN sectors before it trusts the ELF's symbols.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from power_guard import ROOT, inputs, on_ac
from test_tt_route import NATIVE, ORIGINAL, records, sha

ZONE = 2
OBJCOPY = ROOT/'.toolchain/bin/sh-elf-objcopy'
OBJDUMP = ROOT/'.toolchain/bin/sh-elf-objdump'
NM = ROOT/'.toolchain/bin/sh-elf-nm'


def once(text, old, new):
    assert text.count(old) == 1, ('derived-source anchor changed', old[:70])
    return text.replace(old, new)


def host_source(want):
    """want: destination era index, or -1 for any era other than the start."""
    text = (ROOT/'tools/tt_route_search.c').read_text()
    text = once(text, 'static void load(void){',
                f'static int travel_destination;\nstatic const int travel_want={want};\nstatic void load(void){{\n    travel_destination=-1;')
    text = once(text, 'if(scd_world_step_vblanks(p,world_vblanks)>=0)dead=2;',
                'int target=scd_world_step_vblanks(p,world_vblanks);if(target>=0){'
                'if(travel_want>=0?target==travel_want:target!=(int)era){travel_destination=target;done=1;}else dead=4;}')
    text = once(text, 'if(result.phase==SCD_ACT_DONE)done=1;', 'if(result.phase){dead=3;done=0;}')
    begin = text.index('static uint32_t cell_key(void){')
    end = text.index('static void archive(void){', begin)
    text = text[:begin] + '''static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();scd_world_state w=scd_world_get();
    unsigned x=(unsigned)(p.x/65536<0?0:p.x/65536>16383?16383:p.x/65536)/32;
    unsigned y=(unsigned)(p.y/65536<0?0:p.y/65536>2047?2047:p.y/65536)/32;
    return x|(y<<9)|((unsigned)(w.direction+1)<<15)|((w.ticks/8)<<17);
}
static double cell_value(void){
    scd_world_state w=scd_world_get();
    return w.ticks*10000.0+(w.direction?1000000.0:0.0)+scd_player_get().x/65536;
}
''' + text[end:]
    old = '''fprintf(stderr,"Tally complete: sequence=%u act=%u era=%u score=%u min_air=%u boss_hits=%u egg=%u\\n",
                    sequence,act,era,p.score,min_air,boss_hits,egg_seen);'''
    new = '''fprintf(stderr,"TT natural travel: sequence=%u act=%u era=%u destination=%d ticks=%u min_air=%u\\n",
                    sequence,act,era,travel_destination,scd_world_get().ticks,min_air);'''
    return once(text, old, new)


def elf_matches_disc(elf, disc, out):
    """The ELF's program (zone overlays stripped, as the Makefile's .bin rule)
    must sit sector by sector in the disc image (Mode 1/2352, 2048-byte payloads)."""
    sections = subprocess.check_output([OBJDUMP, '-h', elf], text=True)
    zones = sorted(set(re.findall(r'\s(\.zone_R\d+)\s', sections)))  # Makefile ZONE_TABLES; .zone_resident stays
    program = out/'program.bin'
    subprocess.run([OBJCOPY, '-O', 'binary', *[a for z in zones for a in ('-R', z)], elf, program], check=True)
    a, b = program.read_bytes(), disc.read_bytes()
    program.unlink()
    start = b.find(a[:2048])
    if start < 0 or (start % 2352) != 16:
        return False
    return all(b[start+k*2352:start+k*2352+2048][:len(a[k*2048:(k+1)*2048])] == a[k*2048:(k+1)*2048]
               for k in range((len(a)+2047)//2048))


def run_travel(spec, argv=None):
    """Shared natural-travel driver (TT here; tools/test_cc_travel.py and
    tools/test_qq_travel.py pass their own spec). spec keys: label ('TT'),
    zone (SCD_ZONE and the observed zone), routes (stored-script folder),
    prefix (script name prefix), host_source(want) -> derived host C text,
    native, original, seed, limit (host replay updates), mode_prefix (host
    mode letter before ACT:ERA, 'p' for PPZ), track (arrival track
    = era slot + 2, src/music_routes.h), optional harness(symbols) -> derived
    emulator C text, settled(log, rows) -> extra post-arrival check, and
    vblank_timer (timeWarpTimer counted per VBlank: 230 may be overshot)."""
    label = spec['label']
    parser = argparse.ArgumentParser(description=spec.get('doc', __doc__), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--act', type=int, choices=(1, 2), default=1)
    parser.add_argument('--era', choices=tuple('ABCD'), default='A')
    parser.add_argument('--to', choices=tuple('ABCD'), help='required destination era (default: any other era)')
    parser.add_argument('--seed', type=int, default=spec['seed'])
    parser.add_argument('--iterations', type=int, default=100000)
    parser.add_argument('--script', type=Path, help=f'a previously searched natural-travel script ({spec["routes"]}/)')
    parser.add_argument('--save-route', action='store_true',
                        help=f'copy a searched script to {spec["routes"]}/{spec["prefix"]}<act><era><to>.txt once the host replay passes')
    parser.add_argument('--prefix', type=Path, help='search prefix script (the search keeps its pads and extends them)')
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--cue', type=Path, default=ROOT/'dist/sonic-cd-saturn-prototype.cue',
                        help='disc cue (use a private copy; its BIN is the FILE named in the cue)')
    parser.add_argument('--elf', type=Path, default=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf',
                        help='ELF for symbols; must match the disc program')
    args = parser.parse_args(argv)
    start_era = 'ABCD'.index(args.era)
    want = 'ABCD'.index(args.to) if args.to else -1
    assert want != start_era, '--to must differ from --era'
    zone = spec['zone']
    out = args.output.resolve();out.mkdir(parents=True, exist_ok=False)
    report = dict(status='pending', passed=False, hardware_tested=False, zone=label,
                  act=args.act, era=args.era, to=args.to, seed=args.seed, iterations=args.iterations,
                  input_sha256=inputs(), steps=[],
                  limits='Native-host positions until warp commit; observed Saturn arrival, arrival track and resumed '
                         'gameplay. No whole-act retail parity or hardware acceptance.')
    def save(): (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(name, command, env=None, timeout=7200):
        report['steps'].append(dict(name=name, command=list(map(str, command)), status='pending'));save()
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        report['steps'][-1].update(status='passed' if result.returncode==0 else 'failed', exit_code=result.returncode);save()
        assert result.returncode == 0, (name, result.returncode, out/(name+'.log'))
    save()
    try:
        source=out/'search.c';source.write_text(spec['host_source'](want))
        report['derived_host_sha256']=sha(source)
        original=[f'build/probe-source/{name}.c' for name in spec['original']]
        run('compile-host', ['clang','-std=gnu11','-O2','-fsigned-char','-fwrapv','-fno-strict-aliasing',
                            '-Wno-parentheses','-Wno-unused-value','-Isrc','-Iassets/generated','-Ibuild/probe-source',
                            '-DR1','-DR11A',*spec.get('defines', ()),source,*spec['native'],*original,'-o',out/'search'])
        mode=spec.get('mode_prefix','')+f'{args.act-1}:{args.era}'
        script=out/'script.txt'
        if args.script:
            script.write_bytes(args.script.read_bytes());report['script_source']=str(args.script)
        else:
            run('search', [out/'search','search',mode,args.seed,args.iterations,script]+([args.prefix.resolve()] if args.prefix else []))
            report['script_source']='search';report['search_prefix']=str(args.prefix) if args.prefix else None
            if args.prefix:report['search_prefix_sha256']=sha(args.prefix)
        pad=out/'controller.txt'
        run('host-replay', [out/'search','replay',mode,script,spec['limit'],pad])
        host_log=(out/'host-replay.log').read_text()
        match=re.search(label+r' natural travel: sequence=(\d+) act=(\d+) era=(\d+) destination=(-?\d+) ticks=(\d+)', host_log)
        # A VBlank-counted timer (spec vblank_timer, lag V-INTs) can pass 230 in one update.
        assert match and (int(match[5])>=230 if spec.get('vblank_timer') else int(match[5])==230), 'host did not complete natural travel'
        destination=int(match[4])
        assert destination != start_era and destination in range(4) and (want < 0 or destination == want)
        expected=[list(map(int,line.split()))[:4] for line in pad.read_text().splitlines()]
        report.update(host_positions=len(expected), destination=destination, destination_era='ABCD'[destination],
                      controller_sha256=sha(pad), script_sha256=sha(script))
        air=re.search(r'min_air=(\d+)', host_log)
        if air:report['host_min_air']=int(air[1])
        if args.save_route and not args.script:
            dest=ROOT/spec['routes']/f'{spec["prefix"]}{args.act}{args.era}{"ABCD"[destination]}.txt'
            dest.parent.mkdir(parents=True, exist_ok=True);dest.write_text(script.read_text())
            report['saved_route']=str(dest.relative_to(ROOT))
        if args.host_only:
            report['status']='host-only';save()
            print(f'HOST: {label}{args.act}{args.era} natural travel to era {"ABCD"[destination]} at sequence {match[1]}, '
                  f'{len(expected)} positions; Saturn verification pending')
            return
        assert on_ac(), 'emulator requires AC power and external power guard'
        cue=args.cue.resolve();elf=args.elf.resolve()
        disc=cue.parent/re.search(r'FILE "([^"]+)"', cue.read_text())[1]
        disc_sha=sha(disc);elf_sha=sha(elf)
        report.update(cue=str(cue), disc=str(disc), disc_sha256=disc_sha, elf_sha256=elf_sha)
        assert elf_matches_disc(elf, disc, out), 'ELF program is not the disc A.BIN; symbols would be wrong'
        listing=subprocess.check_output([NM,elf],text=True)
        symbols={r.split()[2]:r.split()[0] for r in listing.splitlines() if len(r.split())==3}
        harness=out/'emulator.c'
        harness.write_text(spec['harness'](symbols) if spec.get('harness') else (ROOT/'tools/emulator_test.c').read_text())
        report.update(harness_sha256=sha(harness), core_sha256=sha(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'))
        run('compile-emulator', ['clang','-std=gnu11','-Wall','-Wextra','-Werror',
                                '-Itools','-I.deps/beetle-saturn/libretro-common/include',harness,'-o',out/'emulator'])
        env={k:v for k,v in os.environ.items() if not k.startswith('SCD_')}
        tail=400
        env.update(SCD_ZONE=str(zone),SCD_ZONE_ACT=str(args.act-1),SCD_ZONE_ERA=str(start_era),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                   SCD_ZONE_PAD_TRACE=str(pad),SCD_ZONE_ROUTE_RETREAT='100',
                   SCD_ZONE_ROUTE_UPDATES=str(len(expected)+tail),SCD_ZONE_PAD_TAIL=str(tail))
        if '_scd_objects_overlay_fault' in symbols:
            env['SCD_OBJECTS_OVERLAY_FAULT']=symbols['_scd_objects_overlay_fault']
        run('saturn', [out/'emulator',ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                       cue,ROOT/'assets/private',out,
                       symbols['_scd_trace_mailbox'],symbols['_scd_audio_mailbox'],'zones'],env=env,timeout=3600)
        log=(out/'saturn.log').read_text()
        rows=records(log,'CC route');future=records(log,'CC future');music=records(log,'CC music')
        warp=dict(records(log,'CC warp'))
        assert len(rows)==len(future)==len(music)==len(expected)+tail, 'observation count'
        for r in rows:r[3]-=(r[3]>=1<<31)<<32
        assert all([r[0],r[8],r[2],r[3]]==p for r,p in zip(rows,expected)), 'host/Saturn prefix mismatch'
        assert all(b[0]==a[0]+1 for a,b in zip(rows,rows[1:])), 'lost observation'
        assert all(r[9:11]==[zone,args.act-1] and r[6]==0 for r in rows), 'changed act or respawned'
        changes=[(a,b) for a,b in zip(rows,rows[1:]) if a[11]!=b[11]]
        assert len(changes)==1 and [changes[0][0][11],changes[0][1][11]]==[start_era,destination], ('era changes', changes[:3])
        peak=max(r[2] for r in future)
        assert future[-1][3]==1 and (230<=peak<238 if spec.get('vblank_timer') else peak==230), ('warp timer', peak)
        handoffs=[(a,b) for a,b in zip(rows,rows[1:]) if warp[b[0]]]
        assert len(handoffs)==1 and warp[handoffs[0][1][0]]==240, 'one warp handoff'
        assert handoffs[0][1][1]-handoffs[0][0][1]==2
        assert changes[0][1][1]-changes[0][0][1]>=240
        late=[(a[0],b[0],b[1]-a[1]) for a,b in zip(rows,rows[1:])
              if a[9:]==b[9:] and not warp[b[0]] and b[1]-a[1]!=1]
        assert not late, ('late gameplay',late[:10])
        settled=[r for r in rows if r[0]>=changes[0][1][0]+100]
        assert len(settled)>=100, 'resumed gameplay after arrival'
        if spec.get('settled'):spec['settled'](log, settled)
        track=spec['track']+destination
        assert all(r[1:]==[track,track,3] for r in music[-100:]), ('arrival track', music[-1])
        assert sha(disc)==disc_sha and sha(elf)==elf_sha, 'disc or ELF changed during the run'
        report.update(status='passed',passed=True,matched_positions=len(expected),observations=len(rows),
                      transition_sequence=changes[0][1][0],post_arrival_updates=len(settled),
                      late_gameplay_intervals=late,results_sha256=sha(out/'saturn.log'),natural_travel=True)
        save();print(f'PASS: {label}{args.act}{args.era} natural travel to era {"ABCD"[destination]}; '
                     f'{len(expected)} matched positions; {len(settled)} resumed updates; disc {disc_sha[:12]}')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error));save();raise


def main():
    # src/music_routes.h: zone 2 era cue c -> slot 14+c; the audio mailbox reports slot+2.
    run_travel(dict(label='TT', zone=ZONE, routes='tests/routes/tt/travel', prefix='tt', host_source=host_source,
                    native=NATIVE, original=ORIGINAL, seed=41, limit=46000, track=16))


if __name__=='__main__':main()
