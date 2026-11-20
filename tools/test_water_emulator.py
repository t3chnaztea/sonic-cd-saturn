#!/usr/bin/env python3
"""Tidal Tempest water line on the Saturn build (emulator evidence only).

Runs tools/emulator_test.c zones mode with SCD_WATER_MAILBOX: the level select
enters Tidal Tempest Act 1 (Present unless an era letter is given), a fixture
holds Sonic 60 lines above, 50 below and 400 below the water, and each case
captures 30 consecutive frames with src/water_raster.h's mailbox and CRAM
banks 0 and 1. The check:

- CRAM bank 1 colours 0..63 are the retail water palette (PaletteTable entry 1
  of the program, assets/generated/water_data.h), bank 0 the stage palette;
- in every frame, no row above the switch shows a water-only colour and no row
  from the switch down shows a normal-only colour (NBG and palette-code sprite
  pixels resolve through CRAM), and the switch row is the armed line;
- deep water shows no normal-only colour anywhere (full-screen offsets).

Not a hardware result: SCU timer 0 latency on a real console is unmeasured here.
Usage: python3 tools/test_water_emulator.py [ERA_LETTER...]
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rgb(word):
    c = lambda v: (v << 3) | (v >> 2)
    return (c(word & 31), c((word >> 5) & 31), c((word >> 10) & 31))


def ppm(path):
    data = path.read_bytes()
    parts = data.split(b'\n', 3)
    width, height = map(int, parts[1].split())
    pixels = parts[3]
    return width, height, pixels


def expected_water(era):
    text = (ROOT/'assets/generated/water_data.h').read_text()
    body = text.split('water_palettes[4][64]={', 1)[1].split('};', 1)[0]
    rows = re.findall(r'\{([^}]*)\}', body)
    return [int(v, 16) for v in rows[era].split(',')]


def analyse(run, era, log):
    frames = [m for m in re.finditer(r'^Water frame: (\d+) (\d+) water=(-?\d+) latch=(\d+) line=(\d+) t0=(\d+) isr=(\d+) '
                                     r'vcnt=(\d+) full=(\d+) enabled=(\d+)$', log, re.M)]
    cram = {int(m[1]): [int(v, 16) for v in m[2].split()] for m in re.finditer(r'^Water CRAM: (\d+) (.*)$', log, re.M)}
    water = expected_water(era)
    result = {'frames': len(frames), 'cases': {}}
    ok = len(frames) == 90 and len(cram) == 3
    for case in range(3):
        bank0, bank1 = cram.get(case, [0]*128)[:64], cram.get(case, [0]*128)[64:]
        bank1_ok = [w & 0x7fff for w in bank1] == [w & 0x7fff for w in water]
        normal = {rgb(w) for w in bank0}; wet = {rgb(w) for w in bank1}
        normal_only, water_only = normal - wet, wet - normal
        rows = []
        previous_line = None
        for m in frames:
            if int(m[1]) != case:
                continue
            width, height, pixels = ppm(run/f'water-{case}-{int(m[2]):02d}.ppm')
            top = (height - 224) // 2
            first_water, last_normal = None, None
            for y in range(224):
                row = pixels[(y + top) * width * 3:(y + top + 1) * width * 3]
                colours = {tuple(row[i:i+3]) for i in range(0, len(row), 3)}
                if colours & water_only and first_water is None:
                    first_water = y
                if colours & normal_only:
                    last_normal = y
            line = int(m[5])
            rows.append({'shot': int(m[2]), 'line': line, 'first_water_row': first_water, 'last_normal_row': last_normal,
                         'isr': int(m[7]), 'vcnt': int(m[8]), 'water': int(m[3])})
        # The frame on screen was armed by the latch before the mailbox read, or the one before it.
        good = 0
        for i, r in enumerate(rows):
            candidates = {r['line']} | ({rows[i-1]['line']} if i else set())
            if case == 2:
                fine = r['last_normal_row'] is None
            else:
                fine = any((r['last_normal_row'] is None or r['last_normal_row'] < c) and
                           (r['first_water_row'] is None or r['first_water_row'] >= c) for c in candidates)
            good += fine
        result['cases'][case] = {'bank1_is_water_palette': bank1_ok, 'normal_only_colours': len(normal_only),
                                 'water_only_colours': len(water_only), 'frames_consistent': good, 'rows': rows}
        ok &= bank1_ok and good == len(rows) == 30
    result['passed'] = bool(ok)
    return result


def main():
    eras = [e for e in sys.argv[1:] if e in 'ABCD'] or ['A']
    out = ROOT/'build/water-emulator'
    out.mkdir(parents=True, exist_ok=True)
    exe = out/'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    elf = ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'
    listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm', elf], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    report = {'image_sha256': hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
              'inputs': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                         ['tools/emulator_test.c', 'tools/test_water_emulator.py', 'src/water.c', 'src/water_raster.c']},
              'status': 'pending', 'runs': {}}
    (out/'report.json').write_text(json.dumps(report, indent=1) + '\n')
    ok = True
    for era in eras:
        run = out/era
        run.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='2', SCD_ZONE_ACT='0', SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'], SCD_WATER_MAILBOX=symbols['_scd_water_mailbox'],
                   SCD_WATER_ACTWK=symbols['_actwk'], SCD_WATER_LEVEL=symbols['_waterposi'])
        command = [exe, ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib', ROOT/'dist/sonic-cd-saturn-prototype.cue',
                   ROOT/'assets/private', run, symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
        with (run/'results.log').open('w') as stdout, (run/'core.log').open('w') as stderr:
            code = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=1500).returncode
        result = analyse(run, 'ABCD'.index(era), (run/'results.log').read_text())
        result['exit_code'] = code
        report['runs'][era] = result
        good = result['passed'] and code == 0
        ok &= good
        summary = ' '.join(f"case{c}: bank1={'ok' if v['bank1_is_water_palette'] else 'BAD'} "
                           f"consistent={v['frames_consistent']}/{len(v['rows'])}" for c, v in result['cases'].items())
        print(f"R41{era}: {'PASS' if good else 'FAIL'} {summary}")
    report['status'] = 'passed' if ok else 'failed'
    (out/'report.json').write_text(json.dumps(report, indent=1) + '\n')
    print(('PASS' if ok else 'FAIL') + ': water line emulator probe, build/water-emulator/report.json')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
