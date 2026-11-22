#!/usr/bin/env python3
"""Diagnostic original/target CC stills at matched terrain camera positions.

The source player is moved through the level to settle its camera. Per-line
horizontal registration absorbs differences in scroll animation phase. This
diagnostic does not accept motion, actors, or sprite priority.
"""
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

import special_retail as sr
from capture_cc_plane import walk
from capture_cc_scroll import boot

ROOT = Path(__file__).resolve().parents[1]
NAMES = [f'R3{act}{era}' for act in (1, 2, 3)
         for era in ('CD' if act == 3 else 'ABCD')]
OUT = ROOT / 'build/cc-scene-audit'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbols():
    elf = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
    rows = subprocess.check_output([str(ROOT / '.toolchain/bin/sh-elf-nm'), str(elf)], text=True)
    found = {fields[2]: fields[0] for line in rows.splitlines()
             if len(fields := line.split()) == 3}
    def one(name):
        matches = [address for key, address in found.items()
                   if key == name or key.startswith(name + '.lto_priv.')]
        assert len(matches) == 1, (name, matches)
        return matches[0]
    return one('_scd_world_mailbox'), one('_scd_trace_mailbox'), one('_scd_audio_mailbox')


def source_rgb(frame):
    width, height, data = frame
    assert (width, height) == (320, 224)
    src_levels = (0, 32, 65, 98, 139, 172, 205, 238)
    dst_levels = (0, 32, 64, 104, 136, 176, 208, 248)
    def convert(value):
        return dst_levels[min(range(8), key=lambda i: abs(value - src_levels[i]))]
    result = bytearray(width * height * 3)
    for i in range(width * height):
        value = data[2*i] | data[2*i+1] << 8
        result[3*i:3*i+3] = bytes((convert((value >> 11) * 255 // 31),
                                    convert(((value >> 5) & 63) * 255 // 63),
                                    convert((value & 31) * 255 // 31)))
    return result


def compare(source, target):
    # A line can move horizontally as the original and target scroll timers
    # advance at different points. Report registration, never use it as a pass.
    regions = {}
    for lo, hi in ((48, 112), (112, 224), (48, 224)):
        matches = 0
        shifts = []
        for y in range(lo, hi):
            choices = []
            for dx in range(0, 17):
                same = 0
                for x in range(16, 304):
                    a = (y * 320 + x) * 3
                    b = (y * 330 + x + dx) * 3
                    same += source[a:a+3] == target[b:b+3]
                choices.append((same, dx))
            same, dx = max(choices)
            matches += same
            shifts.append(dx)
        regions[f'{lo}-{hi}'] = dict(exact_pixels=matches,
                                      pixels=(hi-lo)*288,
                                      fraction=matches/((hi-lo)*288),
                                      shifts=sorted(set(shifts)))
    return regions


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    disc = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
    report_path = OUT / 'report.json'
    report = dict(status='pending', disc_sha256=sha(disc), programs={},
                  inputs={name: sha(ROOT / name) for name in
                          ('tools/check_cc_scene_stills.py', 'tools/capture_cc_plane.py',
                           'tools/capture_cc_scroll.py', 'tools/special_retail.py',
                           'tools/emulator_test.c',
                           'build/cc-scroll-target/emulator-test',
                           'build/saturn/sonic-cd-saturn-prototype.elf',
                           '.deps/beetle-saturn/mednafen_saturn_libretro.dylib')} |
                         {'private_original_iso': sha(sr.RETAIL / 'sonic.iso')},
                  limits='Diagnostic stills. Source player is repositioned to match target camera. '
                         'Each scanline chooses its best 0-16 pixel horizontal registration. '
                         'This can hide scroll defects; it does not prove timing, actor motion, '
                         'sprite priority, or Saturn hardware presentation.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    exe = ROOT / 'build/cc-scroll-target/emulator-test'
    assert exe.exists()
    world, trace, audio = symbols()
    for name in NAMES:
        folder = OUT / name
        folder.mkdir(exist_ok=True)
        env = dict(os.environ, SCD_ZONE='1', SCD_ZONE_ACT=str(int(name[2])-1),
                   SCD_ZONE_ERA=str('ABCD'.index(name[3])),
                   SCD_WORLD_MAILBOX=world, SCD_ZONES_TRACE='1')
        command = [str(exe), str(ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),
                   str(ROOT / 'dist/sonic-cd-saturn-prototype.cue'),
                   str(ROOT / 'assets/private'), str(folder), trace, audio, 'zones']
        try:
            with (folder / 'results.log').open('w') as stdout, (folder / 'core.log').open('w') as stderr:
                subprocess.run(command, cwd=ROOT, env=env, stdout=stdout,
                               stderr=stderr, check=True, timeout=240)
            lines = (folder / 'results.log').read_text().splitlines()
            player = [re.fullmatch(r't=300 seq=\d+ x=(\d+) y=(\d+) .*', line)
                      for line in lines]
            player = [match for match in player if match]
            assert len(player) == 1, (name, 'target player trace')
            px, py = map(int, player[0].groups())
            screen = [re.fullmatch(r'Screen Sonic: zones-1-start screen=(\d+),(\d+) drawn=.*', line)
                      for line in lines]
            screen = [match for match in screen if match]
            assert len(screen) == 1, (name, 'target screen trace')
            sx, sy = map(int, screen[0].groups())
            camera = (px-sx, py-sy)
            core, e, frame, _ = boot(name[3], int(name[2]), 3)
            desired_y = camera[1]
            for _ in range(4):
                frame = walk(core, e, frame, camera[0], desired_y)
                actual = tuple(struct.unpack('>i', core.work_read(e[key], 4))[0] >> 16
                               for key in ('cameraX', 'cameraY'))
                if actual == camera:
                    break
                desired_y += camera[1]-actual[1]
            assert actual == camera, (name, camera, actual)
            sr.png(folder / 'source.png', core.frame)
            target_path = folder / 'zones-1-start.ppm'
            target = subprocess.check_output(['magick', str(target_path),
                                              '-depth', '8', 'rgb:-'])
            assert len(target) == 330*224*3, (name, len(target))
            source = source_rgb(core.frame)
            report['programs'][name] = dict(target_player=[px, py], target_screen=[sx, sy],
                                            camera=list(camera), source_frame=frame,
                                            source_player_y=desired_y+96,
                                            scene=compare(source, target),
                                            target_sha256=sha(target_path),
                                            source_sha256=sha(folder / 'source.png'))
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(name, f"{report['programs'][name]['scene']['48-224']['fraction']:.1%}",
                  'diagnostic still pixels', flush=True)
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
