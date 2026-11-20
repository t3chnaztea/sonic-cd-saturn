#!/usr/bin/env python3
"""Compare EMIE3's live R31A palette with the original rendered scene."""
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot
from check_cc_scene_stills import source_rgb
from test_cc_entry_scene import exact

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cc-emie-palette'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    disc = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
    scroll_path = ROOT / 'build/cc-scroll-target/report.json'
    results_path = ROOT / 'build/cc-scroll-target/R31A/results.log'
    target_path = ROOT / 'build/cc-scroll-target/R31A/zones-1-t0360.ppm'
    report_path = OUT / 'final-report.json'
    report = dict(status='pending', disc_sha256=sha(disc),
                  retail_iso_sha256=sha(sr.RETAIL / 'sonic.iso'),
                  scroll_report_sha256=sha(scroll_path),
                  target_image_sha256=sha(target_path),
                  results_sha256=sha(results_path),
                  inputs={name: sha(ROOT / name) for name in
                          ('tools/test_cc_emie_palette.py',
                           'tools/test_cc_entry_scene.py',
                           'tools/check_cc_scene_stills.py',
                           'tools/capture_cc_scroll.py',
                           'tools/special_retail.py')},
                  limits='One original-versus-Saturn R31A frame at equal player and camera; '
                         'fixed five-pixel screenshot border. Does not prove later actor '
                         'motion, all priority overlaps, or Saturn hardware.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    try:
        scroll = json.loads(scroll_path.read_text())
        assert scroll['status'] == 'passed' and scroll['disc_sha256'] == report['disc_sha256']
        assert scroll['programs']['R31A']['results_sha256'] == report['results_sha256']
        trace = [re.fullmatch(r't=360 seq=\d+ x=(\d+) y=(\d+) .*', line)
                 for line in results_path.read_text().splitlines()]
        trace = [match for match in trace if match]
        assert len(trace) == 1, 'Missing R31A frame-360 player trace'
        target_player = tuple(map(int, trace[0].groups()))
        screen = [re.fullmatch(r'Screen Sonic: zones-1-t0360 screen=(\d+),(\d+) drawn=.*', line)
                  for line in results_path.read_text().splitlines()]
        screen = [match for match in screen if match]
        assert len(screen) == 1, 'Missing R31A frame-360 screen trace'
        target_screen = tuple(map(int, screen[0].groups()))
        target_camera = tuple(a - b for a, b in zip(target_player, target_screen))
        core, e, frame, _ = boot('A', 1, 3)
        for _ in range(158):
            core.pad = 8
            core.run()
            frame += 1
            core.host.chunks.clear()
        player = core.work_read(e['objPlayerSlot'], 64)
        source_player = tuple(struct.unpack_from('>I', player, e[key])[0] >> 16
                              for key in ('oX', 'oY'))
        camera = tuple(struct.unpack('>i', core.work_read(e[key], 4))[0] >> 16
                       for key in ('cameraX', 'cameraY'))
        assert source_player == target_player, (source_player, target_player)
        assert camera == target_camera, (camera, target_camera)
        original_path = OUT / 'R31A-frame360-original.png'
        sr.png(original_path, core.frame)
        source = source_rgb(core.frame)
        target = subprocess.check_output(['magick', str(target_path), '-depth', '8', 'rgb:-'])
        assert len(source) == 320 * 224 * 3 and len(target) == 330 * 224 * 3
        emie = exact(source, target, (80, 105, 75, 112))
        scene = exact(source, target, (10, 310, 48, 224))
        assert emie['exact_pixels'] == 925, emie
        assert scene['fraction'] >= .98, scene
        report.update(status='passed', source_frame=frame,
                      source_player=list(source_player), camera=list(camera),
                      source_image_sha256=sha(original_path), emie_region=emie,
                      scene=scene)
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                      error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {report_path}')


if __name__ == '__main__':
    main()
