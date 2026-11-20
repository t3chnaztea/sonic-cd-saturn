#!/usr/bin/env python3
"""Check Collision Chaos line-scroll DMA on Saturn, for every act/era."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALL = [f'R3{act}{era}' for act in (1, 2, 3) for era in ('CD' if act == 3 else 'ABCD')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('programs', nargs='*', choices=ALL)
    args = parser.parse_args()
    programs = args.programs or ALL
    out = ROOT / 'build/cc-scroll-target'
    out.mkdir(parents=True, exist_ok=True)
    exe = out / 'emulator-test'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', str(exe)], cwd=ROOT, check=True)
    elf = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
    rows = subprocess.check_output([str(ROOT / '.toolchain/bin/sh-elf-nm'), str(elf)], text=True)
    symbols = {fields[2]: fields[0] for line in rows.splitlines() if len(fields := line.split()) == 3}

    def symbol(name):
        found = [address for key, address in symbols.items()
                 if key == name or key.startswith(name + '.lto_priv.')]
        assert len(found) == 1, (name, found)
        return found[0]

    report = dict(passed=False, status='pending', programs={},
                  disc_sha256=sha(ROOT / 'dist/sonic-cd-saturn-prototype.bin'),
                  inputs={str(p.relative_to(ROOT)): sha(p) for p in
                          [ROOT / 'tools/emulator_test.c', ROOT / 'tools/test_cc_scroll_target.py', elf,
                           ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib']},
                  limits='Target VDP2 line tables and both plane maps versus native WRAM for ordinary level-select play. '
                         'The independent SCR31-33 source comparison runs in test_cc_scroll.py. '
                         'Original plane B cells are checked by test_cc_plane.py. '
                         'Complete rendered scene and physical Saturn acceptance remain separate.')
    report_path = out / 'report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    for name in programs:
        folder = out / name
        folder.mkdir(exist_ok=True)
        env = dict(os.environ, SCD_ZONE='1', SCD_ZONE_ACT=str(int(name[2]) - 1),
                   SCD_ZONE_ERA=str('ABCD'.index(name[3])), SCD_ZONES_TRACE='1',
                   SCD_WORLD_MAILBOX=symbol('_scd_world_mailbox'),
                   QA_R3_SCROLL_BG=symbol('_background_lines'),
                   QA_R3_SCROLL_FG=symbol('_foreground_lines'),
                   QA_R3_BG_MAP=f'{int(symbol("_maps.lto_priv.0"), 16) + 16384:08x}',
                   QA_R3_FG_MAP=symbol('_maps.lto_priv.0'))
        command = [str(exe), str(ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),
                   str(ROOT / 'dist/sonic-cd-saturn-prototype.cue'), str(ROOT / 'assets/private'),
                   str(folder), symbol('_scd_trace_mailbox'), symbol('_scd_audio_mailbox'), 'zones']
        try:
            with (folder / 'results.log').open('w') as stdout, (folder / 'core.log').open('w') as stderr:
                subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                               check=True, timeout=240)
            lines = (folder / 'results.log').read_text().splitlines()
            matches = [re.fullmatch(r'R3 line-scroll transfer: calls=(\d+) ready=(\d+) zone=(\d+) seq=(\d+) frames=(\d+) words=(\d+) active=(\d+) changes=(\d+) mismatches=0', line)
                       for line in lines]
            matches = [match for match in matches if match]
            assert len(matches) == 1, (name, 'missing transfer summary')
            calls, ready, zone, seq, frames, words, active, changes = map(int, matches[0].groups())
            assert frames >= 300 and words == frames * 448, (name, frames, words)
            assert calls >= ready >= zone >= frames and seq >= frames
            assert active > frames and changes > 1, (name, active, changes)
            map_matches = [re.fullmatch(r'R3 BG map transfer: frames=(\d+) cells=(\d+) active=(\d+) mismatches=0', line)
                           for line in lines]
            map_matches = [match for match in map_matches if match]
            assert len(map_matches) == 1, (name, 'missing BG map summary')
            map_frames, map_cells, map_active = map(int, map_matches[0].groups())
            assert map_frames >= 20 and map_cells == map_frames * 4096 and map_active > map_frames
            fg_matches = [re.fullmatch(r'R3 FG map transfer: frames=(\d+) cells=(\d+) active=(\d+) mismatches=0', line)
                          for line in lines]
            fg_matches = [match for match in fg_matches if match]
            assert len(fg_matches) == 1, (name, 'missing FG map summary')
            fg_frames, fg_cells, fg_active = map(int, fg_matches[0].groups())
            assert fg_frames >= 20 and fg_cells == fg_frames * 4096 and fg_active > fg_frames
            entry = [re.fullmatch(r't=180 seq=\d+ x=(\d+) y=(\d+) .*', line)
                     for line in lines]
            entry = [match for match in entry if match]
            assert len(entry) == 1, (name, 'missing level-entry player trace')
            entry_image = folder / 'zones-1-t0180.ppm'
            assert entry_image.exists(), (name, 'missing level-entry image')
            moving = [re.fullmatch(r't=240 seq=\d+ x=(\d+) y=(\d+) .*', line)
                      for line in lines]
            moving = [match for match in moving if match]
            assert len(moving) == 1, (name, 'missing moving player trace')
            moving_image = folder / 'zones-1-t0240.ppm'
            assert moving_image.exists(), (name, 'missing moving image')
            report['programs'][name] = dict(passed=True, frames=frames, words=words,
                                            active_words=active, changed_frames=changes,
                                            map_frames=map_frames, map_cells=map_cells,
                                            map_active_cells=map_active,
                                            foreground_map_frames=fg_frames,
                                            foreground_map_cells=fg_cells,
                                            foreground_map_active_cells=fg_active,
                                            entry_player=[int(v) for v in entry[0].groups()],
                                            entry_image_sha256=sha(entry_image),
                                            moving_player=[int(v) for v in moving[0].groups()],
                                            moving_image_sha256=sha(moving_image),
                                            results_sha256=sha(folder / 'results.log'))
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(f'{name}: {frames} frames, {words} VDP2 words pass', flush=True)
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                          failed_program=name, error=f'{type(error).__name__}: {error}')
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            raise
    report.update(passed=True, status='passed')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {report_path}')


if __name__ == '__main__':
    main()
