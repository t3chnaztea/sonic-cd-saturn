#!/usr/bin/env python3
"""Measure later original/Saturn CC scenes during constant Right input.

This is a diagnostic. It records mismatches instead of accepting motion or
sprite priority. The target screenshots come from test_cc_scroll_target.py.
"""
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot
from check_cc_scene_stills import NAMES, source_rgb
from test_cc_entry_scene import exact

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cc-motion-scene'
TIMES = (300, 360, 420)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one_line(lines, pattern, label):
    matches = [match for line in lines if (match := re.fullmatch(pattern, line))]
    assert len(matches) == 1, (label, len(matches))
    return tuple(map(int, matches[0].groups()))


def exact_shift(source, target, dx, dy, box=(10, 310, 48, 224)):
    left, right, top, bottom = box
    x0, x1 = max(left, -5-dx), min(right, 325-dx)
    y0, y1 = max(top, -dy), min(bottom, 224-dy)
    same = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            a = (y * 320 + x) * 3
            b = ((y+dy) * 330 + x+5+dx) * 3
            same += source[a:a+3] == target[b:b+3]
    pixels = (x1-x0) * (y1-y0)
    return dict(exact_pixels=same, pixels=pixels, fraction=same/pixels)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target_path = ROOT / 'build/cc-scroll-target/report.json'
    target_report = json.loads(target_path.read_text())
    disc = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
    assert target_report['status'] == 'passed'
    assert target_report['disc_sha256'] == sha(disc)
    assert list(target_report['programs']) == NAMES
    report_path = OUT / 'report.json'
    report = dict(status='pending', disc_sha256=sha(disc),
                  retail_iso_sha256=sha(sr.RETAIL / 'sonic.iso'),
                  target_report_sha256=sha(target_path),
                  inputs={name: sha(ROOT / name) for name in
                          ('tools/check_cc_motion_scenes.py',
                           'tools/check_cc_scene_stills.py',
                           'tools/test_cc_entry_scene.py',
                           'tools/capture_cc_scroll.py',
                           'tools/special_retail.py')},
                  programs={},
                  limits='Diagnostic frames 300, 360 and 420 with constant Right input. '
                         'Raw comparisons use a fixed five-pixel screenshot border. '
                         'Aligned comparisons search nearby source frames and camera offsets; '
                         'registration can hide defects. Neither comparison accepts later '
                         'actor motion, sprite priority or hardware.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    for name in NAMES:
        try:
            folder = ROOT / 'build/cc-scroll-target' / name
            lines = (folder / 'results.log').read_text().splitlines()
            assert sha(folder / 'results.log') == target_report['programs'][name]['results_sha256']
            core, e, source_frame, _ = boot(name[3], int(name[2]), 3)
            observations = {}
            holds = []
            previous = None
            source_states = {}
            for update in range(1, 259):
                core.pad = 8
                core.run()
                core.host.chunks.clear()
                source_frame += 1
                time = update + 202
                player = core.work_read(e['objPlayerSlot'], 64)
                position = tuple(struct.unpack_from('>I', player, e[key])[0] >> 16
                                 for key in ('oX', 'oY'))
                speed = struct.unpack_from('>h', player, e['oXVel'])[0]
                state = (position, player[e['oAnimTime']],
                         core.work_read(e['sonicLastFrame'], 4),
                         core.work_read(e['aniArtFrames'], 4))
                if previous == state and speed != 0 and time >= 300:
                    holds.append(time)
                previous = state
                if 300 <= time <= 460:
                    camera = tuple(struct.unpack('>i', core.work_read(e[key], 4))[0] >> 16
                                   for key in ('cameraX', 'cameraY'))
                    source_states[time] = (position, camera, bytes(core.frame[2]))
                if time not in TIMES:
                    continue
                target_player = one_line(lines,
                    rf't={time} seq=\d+ x=(\d+) y=(\d+) .*', (name, time, 'player'))
                target_screen = one_line(lines,
                    rf'Screen Sonic: zones-1-t{time:04d} screen=(\d+),(\d+) drawn=.*',
                    (name, time, 'screen'))
                target_camera = tuple(a-b for a, b in zip(target_player, target_screen))
                source_player = position
                source_camera = tuple(struct.unpack('>i', core.work_read(e[key], 4))[0] >> 16
                                      for key in ('cameraX', 'cameraY'))
                image = folder / f'zones-1-t{time:04d}.ppm'
                target_rgb = subprocess.check_output(['magick', str(image),
                                                      '-depth', '8', 'rgb:-'])
                assert len(target_rgb) == 330 * 224 * 3
                source_image = OUT / f'{name}-t{time:04d}-original.png'
                sr.png(source_image, core.frame)
                source = source_rgb(core.frame)
                scene = exact(source, target_rgb, (10, 310, 48, 224))
                screen_x = source_player[0] - source_camera[0]
                sonic = exact(source, target_rgb,
                              (max(0, screen_x-20), min(320, screen_x+20), 70, 110))
                observations[str(time)] = dict(source_frame=source_frame,
                    source_player=list(source_player), target_player=list(target_player),
                    player_matches=source_player == target_player,
                    source_camera=list(source_camera), target_camera=list(target_camera),
                    camera_matches=source_camera == target_camera,
                    scene=scene, sonic_region=sonic,
                    source_image_sha256=sha(source_image), target_image_sha256=sha(image))
            aligned = {}
            for time in TIMES:
                target_player = observations[str(time)]['target_player']
                target_camera = observations[str(time)]['target_camera']
                image = folder / f'zones-1-t{time:04d}.ppm'
                target_rgb = subprocess.check_output(['magick', str(image),
                                                      '-depth', '8', 'rgb:-'])
                choices = []
                for candidate in range(time, min(time+45, 460)+1):
                    position, camera, frame_data = source_states[candidate]
                    if abs(position[0]-target_player[0]) > 3 or abs(position[1]-target_player[1]) > 4:
                        continue
                    source = source_rgb((320, 224, frame_data))
                    base_dx = camera[0]-target_camera[0]
                    base_dy = camera[1]-target_camera[1]
                    if abs(base_dx) > 15 or abs(base_dy) > 4:
                        continue
                    for dx in range(base_dx-2, base_dx+3):
                        for dy in range(base_dy-1, base_dy+2):
                            match = exact_shift(source, target_rgb, dx, dy)
                            choices.append((match['fraction'], candidate, dx, dy,
                                            position, camera, match))
                if choices:
                    _, candidate, dx, dy, position, camera, match = max(choices)
                    source = source_rgb((320, 224, source_states[candidate][2]))
                    screen_x, screen_y = (position[0]-camera[0],
                                          position[1]-camera[1])
                    sonic = exact_shift(source, target_rgb, dx, dy,
                        (max(0, screen_x-20), min(320, screen_x+20),
                         max(0, screen_y-20), min(224, screen_y+20)))
                    aligned[str(time)] = dict(source_time=candidate,
                        source_player=list(position), source_camera=list(camera),
                        horizontal_shift=dx, vertical_shift=dy,
                        scene=match, sonic_region=sonic)
                else:
                    aligned[str(time)] = None
            report['programs'][name] = dict(frames=observations,
                                            aligned_diagnostics=aligned,
                                            source_gameplay_hold_candidates=holds)
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(name, ' '.join(f'{time}: {observations[str(time)]["scene"]["fraction"]:.1%}'
                                 for time in TIMES), flush=True)
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          failed_program=name, error=f'{type(error).__name__}: {error}')
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
    report['status'] = 'measured'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('MEASURED:', report_path)


if __name__ == '__main__':
    main()
