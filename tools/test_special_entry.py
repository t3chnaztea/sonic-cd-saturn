#!/usr/bin/env python3
"""Big-ring special-stage entry from an act-1/2 window, on the Saturn build.

Replays tests/routes/<zone>/special-entry-<zone><act><era>.pads (WW uses 1B:
WW1A's way to the ring crosses a BLOCK6 train the port does not order as
retail) with the zone's
route tool (host replay, Saturn controller replay, and retail parity where the
tool runs it). The route collects 50+ rings and touches the big ring (Level
End/Main.asm ObjBigRing) instead of passing the sign. tools/emulator_test.c
logs 'CC special' rows (frame, big ring touched, special mode, return act,
time stones, curSpecStage, special game active) whenever one changes. The run
passes when, in order: the big ring is touched, the special stage runs (game
active), curSpecStage advances when it exits, and the next act loads (the
route tool's own handoff check: [zone, act+1, ...]). No input is given in the
special stage, so it times out and no stone is won; the stage after it is the
next missing stone's (special_progress.h).

--stones K (QQ1A only, the route tool's --continue path): Continue from a save
holding stones 1..K with curSpecStage K (tools/special_entry_save.py); the
special stage entered must then be stage K+1 (special_game_view.inc:182,
curSpecStage % 7 + 1).

PPZ uses tools/test-bigring-emulator.sh (the Act 1 debug fixture, stage 1 won).

  test_special_entry.py ZONE [--stones K] [--out DIR]
"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = {  # zone: (window, route tool command)
    'cc': ('cc1A', ['tools/test_cc2_route.py', '--act', '1', '--era', 'A']),
    'tt': ('tt1A', ['tools/test_tt_route.py', '--act', '1', '--era', 'A']),
    'qq': ('qq1A', ['tools/test_qq_route.py', '--act', '1', '--era', 'A']),
    'ww': ('ww1B', ['tools/test_qq_route.py', '--ww', '--act', '1', '--era', 'B']),
    'ss': ('ss2B', ['tools/test_qq_route.py', '--ss', '--act', '2', '--era', 'B']),
    'mm': ('mm1C', ['tools/test_qq_route.py', '--mm', '--act', '1', '--era', 'C']),
}
ZONE = {'cc': 1, 'tt': 2, 'qq': 3, 'ww': 4, 'ss': 5, 'mm': 6}


def symbol(pattern):
    nm = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm', ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    return next(r.split()[0] for r in nm.splitlines() if len(r.split()) == 3 and re.match(pattern, r.split()[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('zone', choices=sorted(WINDOWS) + ['ppz'])
    parser.add_argument('--stones', type=int, choices=range(0, 7), help='QQ1A: Continue from a save with stones 1..K')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    assert args.stones is None or args.zone == 'qq', '--stones uses test_qq_route.py --continue (QQ1A)'
    if args.zone == 'ppz':
        # PPZ: tools/test-bigring-emulator.sh, the Act 1 big-ring fixture (Start+Left+C,
        # 50 rings) through Special Stage 1 won with the retail win pads into Act 2
        # with stone 1 (tools/check_bigring.py writes dist/bigring-report.json).
        out = (args.out or ROOT / 'build/special-entry/ppz').resolve()
        out.mkdir(parents=True, exist_ok=True)
        with (out / 'route.log').open('w') as log:
            tool = subprocess.run(['bash', 'tools/test-bigring-emulator.sh'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        tail = (out / 'route.log').read_text().strip().splitlines()[-1:]
        assert tool.returncode == 0, ('test-bigring-emulator.sh', tail)
        report = json.loads((ROOT / 'dist/bigring-report.json').read_text())
        assert report.get('passed') and report.get('time_stones', 0) & 1, report
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f"PASS: PPZ1A big ring fixture; special stage 1 won (stones {report['time_stones']:#04x}); Act 2 loaded")
        return
    window, cmd = WINDOWS[args.zone]
    route = ROOT / f'tests/routes/{args.zone}/special-entry-{window}.pads'
    out = (args.out or ROOT / ('build/special-entry/' + window + ('' if args.stones is None else f'-k{args.stones}'))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCD_SPECIAL_STAGE_ADDR=symbol(r'_special_cur_stage'),
               SCD_SPECIAL_GAME=symbol(r'_scd_special_game_mailbox$'))
    cmd = ['python3', *cmd]
    if args.zone == 'cc':
        # test_cc2_route.py takes stored scripts through tools/staged_routes.py.
        staged = out / 'staged'
        staged.mkdir(exist_ok=True)
        (staged / f'{window}.script').write_text(route.read_text())
        env['SCD_STAGED_ROUTES'] = str(staged)
        results = ROOT / 'build/cc1/controller/A/results.log'
    elif args.zone == 'tt':
        cmd += ['--script', str(route)]  # test_tt_route.py writes build/tt1/controller
        results = ROOT / 'build/tt1/controller/A/results.log'
    else:
        cmd += ['--script', str(route), '--out', str(out / 'route')]
        results = out / 'route' / ('continue/' if args.stones is not None else '') / window[-1] / 'results.log'
    if args.stones is not None:
        save = out / f'save-k{args.stones}.bin'
        subprocess.run(['python3', 'tools/special_entry_save.py', str(ZONE['qq']), '0', str(args.stones), str(save)], cwd=ROOT, check=True)
        cmd += ['--continue', '--backup', str(save)]
    with (out / 'route.log').open('w') as log:
        tool = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    tail = (out / 'route.log').read_text().strip().splitlines()[-1:]
    assert tool.returncode == 0, ('route tool', tail)
    rows = [list(map(int, l.split()[2:])) for l in results.read_text().splitlines() if l.startswith('CC special: ')]
    rows = [r for r in rows if r[0] >= 355]  # before the first published mailbox the words are unset
    touch = next(i for i, r in enumerate(rows) if r[1] == 1)
    entry = next(i for i, r in enumerate(rows) if i > touch and r[6] == 1)
    exit_ = next(i for i, r in enumerate(rows) if i > entry and r[6] == 0)
    back = next(i for i, r in enumerate(rows) if i > exit_ and r[1] == 0)
    stage_before, stage_after = rows[entry][5], rows[exit_][5]
    stones = rows[entry][4]
    want_before = 0 if args.stones is None else args.stones
    assert stage_before == want_before, ('curSpecStage at entry', stage_before, want_before)
    assert stage_after == (stage_before + 1) % 7, ('curSpecStage after the stage', stage_after)
    assert stones == (0 if args.stones is None else (1 << args.stones) - 1), ('stones held', stones)
    report = dict(passed=True, window=window, route=str(route.relative_to(ROOT)), stones=stones,
                  special_stage=stage_before + 1, touch_frame=rows[touch][0], special_frames=[rows[entry][0], rows[exit_][0]],
                  next_act_frame=rows[back][0], route_tool=tail[0] if tail else '', hardware_tested=False,
                  disc_sha256=__import__('hashlib').sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest())
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {window.upper()} big ring at frame {rows[touch][0]}; special stage {stage_before + 1} '
          f'frames {rows[entry][0]}-{rows[exit_][0]} with stones {stones:#04x}; next act at frame {rows[back][0]}')


if __name__ == '__main__':
    main()
