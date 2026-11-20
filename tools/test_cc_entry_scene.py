#!/usr/bin/env python3
"""Compare ten original CC idle and moving scenes with the running Saturn image.

Both games have the same player world position and camera at the selected
frame. A fixed five-pixel offset accounts for the Saturn screenshot border.
This checks the rendered Sonic area and the full scene below the HUD without
per-line registration. Later actor motion and other priority cases remain open.
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cc-entry-scene'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(source, target, box):
    x0, x1, y0, y1 = box
    same = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            a = (y * 320 + x) * 3
            b = (y * 330 + x + 5) * 3
            same += source[a:a+3] == target[b:b+3]
    pixels = (x1-x0)*(y1-y0)
    return dict(exact_pixels=same, pixels=pixels, fraction=same/pixels)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target_report_path = ROOT / 'build/cc-scroll-target/report.json'
    target_report = json.loads(target_report_path.read_text())
    disc = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
    assert target_report['status'] == 'passed'
    assert target_report['disc_sha256'] == sha(disc)
    assert list(target_report['programs']) == NAMES
    report_path = OUT / 'report.json'
    report = dict(status='pending', programs={}, disc_sha256=sha(disc),
                  retail_iso_sha256=sha(sr.RETAIL / 'sonic.iso'),
                  target_report_sha256=sha(target_report_path),
                  inputs={name: sha(ROOT / name) for name in
                          ('tools/test_cc_entry_scene.py',
                           'tools/check_cc_scene_stills.py',
                           'tools/capture_cc_scroll.py',
                           'tools/special_retail.py')},
                  limits='Ten idle and ten rightward level-entry frames with equal player '
                         'position and camera; '
                         'fixed five-pixel screenshot border. Full-scene and Sonic-region '
                         'thresholds allow independent animation phase. This does not prove '
                         'later actor motion, other sprite priority cases or Saturn hardware.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    for name in NAMES:
        try:
            row = target_report['programs'][name]
            folder = ROOT / 'build/cc-scroll-target' / name
            target_path = folder / 'zones-1-t0180.ppm'
            assert sha(target_path) == row['entry_image_sha256'], name
            assert sha(folder / 'results.log') == row['results_sha256'], name
            lines = (folder / 'results.log').read_text().splitlines()
            trace = [re.fullmatch(r't=180 seq=\d+ x=(\d+) y=(\d+) .*', line)
                     for line in lines]
            trace = [match for match in trace if match]
            assert len(trace) == 1
            player_target = tuple(map(int, trace[0].groups()))
            assert list(player_target) == row['entry_player']
            core, e, frame, _ = boot(name[3], int(name[2]), 3)
            player = core.work_read(e['objPlayerSlot'], 64)
            player_source = tuple(struct.unpack_from('>I', player, e[key])[0] >> 16
                                  for key in ('oX', 'oY'))
            camera = tuple(struct.unpack('>i', core.work_read(e[key], 4))[0] >> 16
                           for key in ('cameraX', 'cameraY'))
            assert player_source == player_target, (name, player_source, player_target)
            assert camera == (0, player_source[1]-96), (name, camera)
            idle_frame = frame
            screen_x = player_source[0]-camera[0]
            source_path = OUT / f'{name}-original.png'
            sr.png(source_path, core.frame)
            source = source_rgb(core.frame)
            target = subprocess.check_output(['magick', str(target_path),
                                              '-depth', '8', 'rgb:-'])
            assert len(target) == 330*224*3
            scene = exact(source, target, (10, 310, 48, 224))
            sonic = exact(source, target, (max(0, screen_x-20),
                                           min(320, screen_x+20), 70, 110))
            assert scene['fraction'] >= .96, (name, 'scene', scene)
            assert sonic['fraction'] >= .93, (name, 'Sonic region', sonic)
            moving_path = folder / 'zones-1-t0240.ppm'
            assert sha(moving_path) == row['moving_image_sha256'], name
            moving_trace = [re.fullmatch(r't=240 seq=\d+ x=(\d+) y=(\d+) .*', line)
                            for line in lines]
            moving_trace = [match for match in moving_trace if match]
            assert len(moving_trace) == 1
            moving_target = tuple(map(int, moving_trace[0].groups()))
            assert list(moving_target) == row['moving_player']
            for _ in range(38):
                core.pad = 8
                core.run()
                frame += 1
                core.host.chunks.clear()
            moving_player = core.work_read(e['objPlayerSlot'], 64)
            moving_source = tuple(struct.unpack_from('>I', moving_player, e[key])[0] >> 16
                                  for key in ('oX', 'oY'))
            moving_camera = tuple(struct.unpack('>i', core.work_read(e[key], 4))[0] >> 16
                                  for key in ('cameraX', 'cameraY'))
            assert moving_source == moving_target, (name, moving_source, moving_target)
            assert moving_camera == camera, (name, moving_camera, camera)
            moving_source_path = OUT / f'{name}-moving-original.png'
            sr.png(moving_source_path, core.frame)
            moving_rgb = source_rgb(core.frame)
            moving_target_rgb = subprocess.check_output(['magick', str(moving_path),
                                                         '-depth', '8', 'rgb:-'])
            moving_x = moving_source[0] - moving_camera[0]
            moving_scene = exact(moving_rgb, moving_target_rgb, (10, 310, 48, 224))
            moving_sonic = exact(moving_rgb, moving_target_rgb,
                                 (max(0, moving_x-20), min(320, moving_x+20), 70, 110))
            assert moving_scene['fraction'] >= .95, (name, 'moving scene', moving_scene)
            assert moving_sonic['fraction'] >= .90, (name, 'moving Sonic', moving_sonic)
            report['programs'][name] = dict(source_frame=idle_frame,
                                            player=list(player_source),
                                            camera=list(camera),
                                            source_image_sha256=sha(source_path),
                                            target_image_sha256=sha(target_path),
                                            scene=scene, sonic_region=sonic,
                                            moving_player=list(moving_source),
                                            moving_source_frame=frame,
                                            moving_source_image_sha256=sha(moving_source_path),
                                            moving_target_image_sha256=sha(moving_path),
                                            moving_scene=moving_scene,
                                            moving_sonic_region=moving_sonic)
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(name, f"idle {scene['fraction']:.1%}",
                  f"moving {moving_scene['fraction']:.1%}", flush=True)
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          failed_program=name, error=f'{type(error).__name__}: {error}')
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
    report['status'] = 'passed'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {report_path}')


if __name__ == '__main__':
    main()
