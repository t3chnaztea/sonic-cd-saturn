#!/usr/bin/env python3
"""Regenerate the background tables derived from the original game (never in git).

    python3 tools/background_tables.py          regenerate everything
    python3 tools/background_tables.py --check  also run every generator's --check

Inputs: .deps/soniccd (adapted into build/audit/source, text only) and the
retail disc (build/retail/sonic.iso, from tools/extract_mmd.py).  Steps:
  1. tools/audit_source.py --source-only
  2. the scroll IR extractors, tools/scroll/R3..R8/extract.py --round N --write
     (R3-R5, R7, R8 write ir/; R6 writes draft/)
  3. the table and palette generators, which write
     src/background_r3..r7_tables.inc and src/background_r4..r8_palette.inc,
     (--terrain, after the stage packs: the animated-tile art includes).
tools/build.sh runs this before make.
"""
import subprocess
import sys
from pathlib import Path
from native import report_progress

ROOT = Path(__file__).resolve().parents[1]
STEPS = [['tools/audit_source.py', '--source-only']]
STEPS += [[f'tools/scroll/R{r}/extract.py', '--round', str(r), '--write'] for r in (3, 4, 5, 6, 7, 8)]
GENERATORS = ['tools/background_r3_assets.py', 'tools/background_r4_assets.py', 'tools/tt_palette_assets.py',
              'tools/background_r5_assets.py', 'tools/background_r6_assets.py', 'tools/ww_palette_assets.py',
              'tools/background_r7_assets.py', 'tools/ss_palette_assets.py', 'tools/mm_palette_assets.py']
# Animated tile art (retail data -> assets/generated/{tt,ww,mm}_terrain.inc).  They read
# the stage packs and boot the retail programs, so tools/build.sh runs them with
# --terrain after tools/stage_packs.py.
TERRAIN = ['tools/tt_terrain_assets.py', 'tools/qq_terrain_assets.py', 'tools/ww_terrain_assets.py', 'tools/mm_terrain_assets.py']


def retail_iso():
    """build/retail/sonic.iso (Mode 1 user data of data track 2) from the
    sonic.bin/.cue tools/prepare_audio.py extracts from the CHD, if missing."""
    import re
    work = ROOT/'build/retail'
    if (work/'sonic.iso').exists():
        return
    cue, tracks, current = (work/'sonic.cue').read_text(), {}, 0
    for line in cue.splitlines():
        if m := re.search(r'TRACK (\d+)', line):
            current = int(m[1])
            tracks[current] = {}
        if m := re.search(r'INDEX (\d+) (\d+):(\d+):(\d+)', line):
            tracks[current][int(m[1])] = (int(m[2])*60+int(m[3]))*75+int(m[4])
    with (work/'sonic.bin').open('rb') as f:
        data = f.read(tracks[2].get(0, tracks[2][1])*2352)
    (work/'sonic.iso').write_bytes(b''.join(data[i+16:i+2064] for i in range(0, len(data), 2352)))


def ir_inputs():
    """Hash of every input and output of the IR extraction."""
    import hashlib
    h = hashlib.sha256()
    files = sorted((ROOT/'.deps/soniccd/src').glob('R[3-8]/*'))+sorted((ROOT/'tools/scroll').rglob('*.py'))
    files += sorted(p for r in range(3, 9) for d in ('ir', 'draft') for p in (ROOT/f'tools/scroll/R{r}/{d}').glob('*.json'))
    for f in files:
        h.update(str(f.relative_to(ROOT)).encode()+b'\0'+f.read_bytes())
    return h.hexdigest()+'\n'


def main():
    check = '--check' in sys.argv[1:]
    if '--terrain' in sys.argv[1:]:
        for index, g in enumerate(TERRAIN):
            report_progress('Preparing ' + ('Tidal Tempest', 'Quartz Quadrant', 'Wacky Workbench', 'Metallic Madness')[index] + ' animated tiles', index, len(TERRAIN))
            subprocess.run([sys.executable, g], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        report_progress('Animated tiles ready', len(TERRAIN), len(TERRAIN))
        print('animated tile art regenerated')
        return
    total = len(STEPS) + len(GENERATORS)
    report_progress('Checking background source files', 0, total)
    retail_iso()
    (ROOT/'assets/generated').mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, *STEPS[0]], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    # The IR extraction takes ~11 minutes: rerun it only when the upstream
    # source, the extractors or an IR file changed (stamp over all of them).
    stamp = ROOT/'build/scroll-ir.stamp'
    if stamp.exists() and stamp.read_text() == ir_inputs():
        report_progress('Reusing verified scroll tables', len(STEPS), total)
        print('scroll IR cache verified')
    else:
        zones = ('Collision Chaos', 'Tidal Tempest', 'Quartz Quadrant', 'Wacky Workbench', 'Stardust Speedway', 'Metallic Madness')
        for index, step in enumerate(STEPS[1:], 1):
            report_progress('Extracting ' + zones[index - 1] + ' scroll rules', index, total)
            subprocess.run([sys.executable, *step], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        stamp.write_text(ir_inputs())
    labels = ('Collision Chaos scroll tables', 'Tidal Tempest scroll tables', 'Tidal Tempest palettes',
              'Quartz Quadrant scroll tables', 'Wacky Workbench scroll tables', 'Wacky Workbench palettes',
              'Stardust Speedway scroll tables', 'Stardust Speedway palettes', 'Metallic Madness palettes')
    for index, g in enumerate(GENERATORS):
        report_progress('Generating ' + labels[index], len(STEPS) + index, total)
        subprocess.run([sys.executable, g], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    if check:
        for g in GENERATORS:
            subprocess.run([sys.executable, g, '--check'], cwd=ROOT, check=True)
    report_progress('Background tables ready', total, total)
    print('background tables regenerated')


if __name__ == '__main__':
    main()
