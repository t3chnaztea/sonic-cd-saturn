#!/usr/bin/env python3
"""Explore an ordinary Collision Chaos pad route on Saturn; not an acceptance pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--era', choices=list('ABCD'), default='A')
    parser.add_argument('--retreat', type=int, default=60)
    parser.add_argument('--updates', type=int, default=10000)
    parser.add_argument('--strategy', choices=('legacy', 'local'), default='local')
    parser.add_argument('--require-handoff', action='store_true',
                        help='require a controller route into the next act with no respawn or late gameplay frame')
    parser.add_argument('--backjump-at', type=int, action='append', default=[],
                        help='Jump during retreats within 64 pixels of this observed X; repeat for multiple points.')
    parser.add_argument('--jump-at', type=int, action='append', default=[],
                        help='Hold jump when grounded and facing right within 16 pixels of this X; repeat for multiple points.')
    args = parser.parse_args()
    assert 1 <= args.retreat <= 300 and 1 <= args.updates <= 24000
    assert len(args.backjump_at) <= 16 and all(1 <= x <= 16383 for x in args.backjump_at)
    assert len(args.jump_at) <= 16 and all(1 <= x <= 16383 for x in args.jump_at)
    assert not args.backjump_at or args.strategy == 'local'
    suffix = '-local' if args.strategy == 'local' else ''
    if args.backjump_at:
        suffix += '-jump' + '-'.join(map(str,args.backjump_at))
    if args.jump_at:
        suffix += '-takeoff' + '-'.join(map(str,args.jump_at))
    assert args.act != 3 or args.era in 'CD', 'Act 3 has only future eras'
    out = ROOT / f'build/cc{args.act}/route-target-{args.era}-{args.retreat}{suffix}'
    out.mkdir(parents=True, exist_ok=True)
    exe = out / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include', 'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm', ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
    env.update(SCD_ZONE='1', SCD_ZONE_ACT=str(args.act-1), SCD_ZONE_ERA=str('ABCD'.index(args.era)),
               SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'], SCD_ZONE_ROUTE_RETREAT=str(args.retreat),
               SCD_ZONE_ROUTE_UPDATES=str(args.updates))
    if '_scd_frame_profile' in symbols:
        env['SCD_FRAME_PROFILE'] = symbols['_scd_frame_profile']
    if args.strategy == 'local':
        env['SCD_ZONE_ROUTE_LOCAL'] = '1'
    if args.backjump_at:
        env['SCD_ZONE_ROUTE_BACKJUMP_AT'] = ','.join(map(str,args.backjump_at))
    if args.jump_at:
        env['SCD_ZONE_ROUTE_JUMP_AT'] = ','.join(map(str,args.jump_at))
    command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
               ROOT/'dist/sonic-cd-saturn-prototype.cue', ROOT/'assets/private', out,
               symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
    with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=600)
    log = (out/'results.log').read_text()
    summary = re.search(r'CC route ended: (.*)', log)
    rows = [list(map(int, match.groups())) for match in re.finditer(r'^CC route: (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$', log, re.M)]
    paths = ['dist/sonic-cd-saturn-prototype.bin', 'tools/emulator_test.c', 'tools/probe_cc_route.py',
             'src/objects.c', 'src/objects_for3.inc', 'src/objects_cc_traps.inc', 'src/objects_ga.inc',
             'src/objects_cc_enemy.inc', 'src/objects_tentou.inc', 'src/objects_kama.inc',
             'src/objects_banpa.inc', 'src/objects_togeball.inc','src/objects_pocket.inc',
             'src/objects_drumr3.inc',
             'src/objects_cc_generator.inc', 'src/world.c', 'src/act.c',
             f'assets/generated/ccobj3{args.act}.bin']
    future_rows = [list(map(int, match.groups())) for match in re.finditer(
        r'^CC future: (\d+) (\d+) (\d+) (\d+) (\d+)$', log, re.M)]
    report = dict(probe_completed=result.returncode == 0 and summary is not None, exit_code=result.returncode,
                  act=args.act, era=args.era, retreat=args.retreat, strategy=args.strategy,
                  backjump_at=args.backjump_at, jump_at=args.jump_at, requested_updates=args.updates,
                  observations=len(rows), summary=summary[1] if summary else None,
                  max_x=max((r[2] for r in rows), default=0),
                  respawns=max((r[6] for r in rows), default=0),
                  standing_types=sorted({r[5] for r in rows if r[5]}),
                  reached_act2=any(r[9:11] == [1, 1] for r in rows) if args.act==1 else False,
                  reached_next_act=any(r[9:11] == [1, args.act] for r in rows) if args.act<3 else
                                   any(r[9] != 1 for r in rows),
                  good_future_observations=sum(bool(r[1]) for r in future_rows),
                  first_good_future=next((r[0] for r in future_rows if r[1]), None),
                  transitions=[dict(sequence=b[0], vblanks=b[1]-a[1], before=a[9:], after=b[9:])
                               for a,b in zip(rows,rows[1:]) if a[9:] != b[9:]],
                  late_gameplay_intervals=[dict(sequence=b[0], vblanks=b[1]-a[1], x=b[2], y=b[3])
                                           for a,b in zip(rows,rows[1:]) if a[9:] == b[9:] and b[1]-a[1] > 1],
                  inputs={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                  limits='Exploratory Left/Right/Jump route from level-select spawn. No gameplay memory writes. Does not prove a complete act, original-game parity, or final pacing acceptance.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    assert report['probe_completed'] and len(rows) == args.updates
    if args.require_handoff:
        assert args.act<3 and report['reached_next_act']
        assert report['respawns']==0 and not report['late_gameplay_intervals']
        assert sum(a[10]==args.act-1 and b[10]==args.act for a,b in zip(rows,rows[1:]))==1

if __name__ == '__main__':
    main()
