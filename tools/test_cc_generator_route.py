#!/usr/bin/env python3
"""Replay a native-host pad recording from CC1 Past spawn on Saturn.

Proves ordinary generator destruction, its persistent Good Future event and
visible broken pose. Optional routes continue through natural time travel.
Does not prove original whole-act parity, campaign saves or physical hardware
performance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import staged_routes  # tools/ is sys.path[0] when run as a script

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_REPORT = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    global ACTIVE_REPORT
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--travel', action='store_true', help='Continue through a natural Future-post warp into Present.')
    mode.add_argument('--good-future', action='store_true', help='Continue through Present and a second natural warp into Good Future.')
    mode.add_argument('--act2', action='store_true', help='Continue through Good Future, the tally and ordinary Act 2 entry (level select does not save).')
    args = parser.parse_args()
    good = args.good_future or args.act2
    travel = args.travel or good
    tail = 300 if args.act2 else 0
    expected_warps = 2 if good else int(travel)
    suffix = '-act2' if args.act2 else '-good-future' if good else '-travel' if travel else ''
    out = ROOT/f'build/cc1/generator/controller{suffix}-target'
    out.mkdir(parents=True, exist_ok=True)
    native = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c',
              'src/sonic_animation.c', 'src/stage.c', 'src/objects.c']
    generated = [f'build/probe-source/{name}.c' for name in
                 ('interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement')]
    # --act2 uses the fixed-seed search host (tools/cc_campaign_search.c, mode
    # 0@B), which links the same sources as the Saturn build (bumper blocks,
    # R3 boss and pcol). The hand-scripted cc_generator_route.c predates the
    # CC1 HARI3X props and PLAYSP3.C bumpers; its shorter modes remain as-is.
    if args.act2:
        native += ['src/boss.c', 'src/boss_r3.c']
        generated += [f'build/probe-source/{name}.c' for name in ('boss_1', 'boss_3', 'playsp3')]
    route_source = 'tools/cc_campaign_search.c' if args.act2 else 'tools/cc_generator_route.c'
    inputs = [route_source, 'tools/cc_pad_replay.h',
              'tools/emulator_test.c', 'tools/test_cc_generator_route.py',
              'src/main.c', 'src/frame_profile.h', 'src/zone_object_view.inc', 'src/arrival_camera.h', 'assets/generated/ccobj31.bin']
    inputs += [f'assets/generated/{prefix}31{era}.bin' for era in 'ABCD' for prefix in ('cc', 'cccollision')]
    if args.act2:
        inputs += ['assets/generated/cc32A.bin', 'assets/generated/cccollision32A.bin', 'assets/generated/ccobj32.bin']
    inputs += native + generated + [str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').glob('objects*.inc'))]
    hashes = {p: sha(ROOT/p) for p in inputs}
    disc = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    ACTIVE_REPORT = out/'report.json'
    ACTIVE_REPORT.write_text(json.dumps({
        'status': 'pending', 'passed': False, 'disc_sha256': disc,
        'inputs': hashes, 'hardware_tested': False,
    }, indent=2)+'\n')
    host = out/'host'
    subprocess.run(['clang', '-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv',
                    '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
                    '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    route_source, *native, *generated, '-o', host], cwd=ROOT, check=True)
    pad = out/'controller.txt'
    with (out/'host.log').open('w') as log:
        if args.act2:
            script = out/'script.txt'
            staged_routes.search([host, 'search', '0@B', '7', '60000', script], script, 'generator', cwd=ROOT, stdout=log, stderr=log, check=True, timeout=3600)
            subprocess.run([host, 'replay', '0@B', script, '40000', pad], cwd=ROOT, stdout=log, stderr=log, check=True)
        else:
            option = ['--good-future'] if good else ['--travel'] if travel else []
            subprocess.run([host, pad, *option], cwd=ROOT, stdout=log, stderr=log, check=True)
    expected = [list(map(int, line.split())) for line in pad.read_text().splitlines()]
    if args.act2:
        assert 6600 < len(expected) <= 18000
    else:
        assert len(expected) == (6600 if good else 6000 if travel else 4200)
    exe = out/'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',
                                      ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
    env.update(SCD_ZONE='1', SCD_ZONE_ACT='0', SCD_ZONE_ERA='1',
               SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
               SCD_ZONE_ART_MAILBOX=symbols['_scd_zone_art_mailbox'],
               SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
               SCD_ZONE_ROUTE_UPDATES=str(len(expected)+tail), SCD_ZONE_PAD_TAIL=str(tail),
               SCD_SAVE_MAILBOX=symbols['_scd_save_mailbox'])
    if '_scd_frame_profile' in symbols:
        env['SCD_FRAME_PROFILE'] = symbols['_scd_frame_profile']
    command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
               ROOT/'dist/sonic-cd-saturn-prototype.cue', ROOT/'assets/private', out,
               symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
    with (out/'results.log').open('w') as stdout, (out/'core.log').open('w') as stderr:
        subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=True, timeout=600)
    log = (out/'results.log').read_text()
    captures = sorted(set(re.findall(r'^(cc-\S+) frame=', log, re.MULTILINE)))
    rows = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines()
            if line.startswith('CC route: ')]
    future = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines()
              if line.startswith('CC future: ')]
    sprites = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines()
               if line.startswith('CC generator sprite: ')]
    warp = dict(map(int, line.split(': ', 1)[1].split()) for line in log.splitlines() if line.startswith('CC warp: '))
    music = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines() if line.startswith('CC music: ')]
    results = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines() if line.startswith('CC results: ')]
    saves = [list(map(int, line.split(': ', 1)[1].split())) for line in log.splitlines() if line.startswith('CC save: ')]
    assert len(rows) == len(future) == len(expected)+tail == len(warp) == len(music) == len(results) == len(saves)
    for sequence, (actual, world, result, save) in enumerate(zip(rows, future, results, saves), 2):
        assert actual[0] == world[0] == result[0] == save[0] == sequence
        assert actual[6] == 0 and actual[9] == 1, ('respawn/zone', actual)
    for actual, reference, world in zip(rows, expected, future):
        sequence, buttons, x, y = reference
        assert [actual[0], actual[8], actual[2], actual[3]] == [sequence, buttons, x, y]
        assert actual[6] == 0 and actual[9:11] == [1, 0], ('respawn/stage', actual)
        assert actual[11] in ((0, 1, 2) if good else (0, 1) if travel else (1,))
        assert world[0] == sequence
    stages = [(a, b) for a, b in zip(rows, rows[1:]) if a[9:11] != b[9:11]]
    assert len(stages) == int(args.act2)
    if args.act2:
        a, b = stages[0]
        assert a[9:] == [1, 0, 2] and b[9:] == [1, 1, 0] and b[0] == len(expected)+2
        spawn = struct.unpack_from('>HH', (ROOT/'assets/generated/cc32A.bin').read_bytes(), 52)
        assert tuple(b[2:4]) == spawn, ('Act 2 ordinary spawn', b, spawn)
        assert all(r[8:] == [0, 1, 1, 0] for r in rows[len(expected):])
        assert results[len(expected)-1][1] == 6, 'recording must end at the completed tally'
        assert list(dict.fromkeys(r[1] for r in results[:len(expected)])) == list(range(7)), 'complete sign/tally phase sequence'
        score = int(re.search(r'Tally complete: .* score=(\d+)', (out/'host.log').read_text())[1])
        tally_start = next(i for i, r in enumerate(results) if r[1] == 5)
        assert score == future[tally_start][4]+results[tally_start][2], 'tally bonus added once'
        assert all(r[4] == score and r[1] == 0 and r[3] == 0 for r in future[len(expected):])
        assert all(r[3] == 0 for r in results[len(expected):]), 'Act 2 rings reset'
        assert all(r[7:10] == [0x101, 1, 0] for r in saves[len(expected):]), 'earned Act 1 Good Future carried; saving disabled in level select'
    transitions = [(a, b) for a, b in zip(rows, rows[1:]) if a[9:11] == b[9:11] and a[11] != b[11]]
    assert [(a[11], b[11]) for a, b in transitions] == ([(1, 0), (0, 2)] if good else [(1, 0)] if travel else [])
    if travel:
        assert future[len(expected)-1][3] == expected_warps and max(r[2] for r in future) == 230
    else:
        assert all(r[3] == 0 for r in future)
    handoffs = [(a, b) for a, b in zip(rows, rows[1:]) if warp[b[0]]]
    assert len(handoffs) == expected_warps
    for (a, b), transition in zip(handoffs, transitions):
        assert warp[a[0]] == 0 and warp[b[0]] == 240
        # main.c moves Sonic before scd_world_step_vblanks commits the warp.
        # This final movement already matches the host above; the white hold
        # starts at b, so comparing b's position to the prior update is invalid.
        assert b[1]-a[1] == 2, 'unexpected warp setup timing'
        assert future[b[0]-2][2] == 230 and b[0]+1 == transition[1][0]
    late = [(a[0], b[0], b[1]-a[1], b[9:]) for a, b in zip(rows, rows[1:])
            if a[9:] == b[9:] and not warp[b[0]] and b[1]-a[1] != 1]
    assert not late, ('late gameplay intervals', len(late), late[:10])
    assert music[200:300] and all(r[1:] == [13, 13, 3] for r in music[200:300]), 'CC Japanese Past track'
    for a, b in transitions:
        track = 12+b[11]
        settled = music[b[0]-2+100:b[0]-2+200]
        assert len(settled) == 100 and all(r[1:] == [track, track, 3] for r in settled), ('CC Japanese track after arrival', track)
        assert b[1]-a[1] >= 240
    final_track = 12 if args.act2 else 14 if good else 12 if travel else 13
    assert all(r[1:] == [final_track, final_track, 3] for r in music[-100:])
    # The hold must cover all 320x224 game pixels; Saturn's 5-bit white
    # expands to 248 in this core's screenshot, with black overscan borders.
    for number in range(1, expected_warps+1):
        header, size, maximum, pixels = (out/f'cc-warp-white-{number}.ppm').read_bytes().split(b'\n', 3)
        width, height = map(int, size.split())
        assert header == b'P6' and maximum == b'255' and width == 330 and height == 224
        white_row = bytes(15)+bytes([248])*960+bytes(15)
        assert pixels == white_row*height, 'departure hold must be completely white'
    destruction = next(i for i, r in enumerate(future) if r[1])
    assert all(r[1] == 0 for r in future[:destruction])
    assert all(r[1] == 1 for r in future[destruction:len(expected)])
    assert future[destruction][4]-future[destruction-1][4] == 1500
    hit = rows[destruction]
    assert abs(hit[2]-4992) < 50 and abs(hit[3]-624) < 70
    # The Good Future mailbox reports pending_generator one observation after
    # the collision. A spring can clear the rolling flag in that interval.
    # Check the player state immediately before the reported destruction.
    assert destruction > 0 and rows[destruction-1][4]&4, 'attack must be a rolling/jumping contact'
    assert any(r[0] < hit[0] and r[1] in (3, 4, 5, 6) for r in sprites), 'active generator not drawn'
    assert any(r[0] >= hit[0]+60 and r[1] == 1 for r in sprites), 'broken generator not drawn'
    assert all(sha(ROOT/p) == value for p, value in hashes.items()), 'source changed during replay'
    assert sha(ROOT/'dist/sonic-cd-saturn-prototype.bin') == disc
    report = dict(status='passed', passed=True, disc_sha256=disc, observations=len(rows),
                  matched_positions=len(expected), neutral_tail_observations=tail,
                  gameplay_intervals=len(rows)-1-len(transitions)-len(handoffs)-len(stages), late=0, respawns=0,
                  generator_sequence=hit[0], generator_contact=hit[2:4], points=1500,
                  good_future_observations=len(expected)-destruction, broken_pose_verified=True,
                  natural_travel=travel, arrival_era=rows[-1][11],
                  transitions=[dict(sequence=b[0], before=a[11], after=b[11], vblanks=b[1]-a[1]) for a, b in transitions],
                  cutscene_handoffs=[dict(sequence=b[0], vblanks=b[1]-a[1], timer=warp[b[0]]) for a, b in handoffs],
                  white_hold_pixels=320*224*expected_warps,
                  act2_reached=args.act2, act2_good_acts=saves[-1][8] if args.act2 else None,
                  act2_score=future[-1][4] if args.act2 else None,
                  act_transitions=[dict(sequence=b[0], before=a[9:], after=b[9:], vblanks=b[1]-a[1]) for a, b in stages],
                  campaign_save_verified=False,
                  japanese_tracks=[13, 12, 14, 12] if args.act2 else [13, 12, 14] if good else [13, 12] if travel else [13],
                  inputs=hashes, artifacts={p.name: sha(p) for p in
                      [pad, out/'host.log', out/'results.log', out/'core.log',
                       *(out/f'{name}.ppm' for name in captures)]}, hardware_tested=False,
                  limits=('Ordinary destruction, natural Past-to-Present-to-Good-Future travel, tally and Act 2 entry. Level select disables saving; only the live Act 1 Good Future bit is verified. Does not prove campaign save/Continue, whole-act original parity or hardware performance.' if args.act2 else 'Ordinary destruction plus natural Past-to-Present-to-Good-Future travel. Does not prove whole-act original parity, campaign saves or physical hardware performance.' if good else 'Ordinary destruction plus Past-to-Present travel preserving Good Future. Does not prove arrival in the Good Future era, whole-act original parity, campaign saves or physical hardware performance.' if travel else __doc__.split('\n\n', 1)[1].strip()))
    ACTIVE_REPORT.write_text(json.dumps(report, indent=2)+'\n')
    ACTIVE_REPORT = None
    print(f'CC1 generator controller route: {len(expected)} matched positions, {tail} neutral tail observations; {len(transitions)} natural warps, {len(stages)} act transitions, zero late gameplay intervals/respawns')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        if ACTIVE_REPORT is not None and ACTIVE_REPORT.exists():
            report = json.loads(ACTIVE_REPORT.read_text())
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          error=f'{type(error).__name__}: {error}')
            ACTIVE_REPORT.write_text(json.dumps(report, indent=2)+'\n')
        raise
