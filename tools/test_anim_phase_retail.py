#!/usr/bin/env python3
"""Retail animation-phase models for rings, lost rings and monitors.

Plays the PPZ1A route (tests/routes/ppz/p0A.txt) in the retail R11A program
(tools/retail_probe.py, PREFIX_FRAMES dump) and checks every live object's
mapping frame against the phase models src/objects.c implements:

  ring       Level/Main.asm UpdateGlobalAnims runs once per update after the
             objects; every placed ring copies ringAnimFrame, so the update with
             levelFrames L shows ((L + 6) / 8) & 3 (all rings in phase).
  lost ring  each spill sets ringLossAnimTimer 255; after the objects, while it
             runs, accum += timer, frame = accum >> 9 & 3 (level start clears both).
  monitor    ObjMonitor_Main animates (Ani_Monitor, two updates per frame) only
             when the preceding DrawObject left it on screen; the spawn frame is 0.
  searchlight  SS1A (R71A, tests/routes/ss/ss1A.txt): slight7_move draws a light
             when (levelFrames & 3), or & 1 without userflag.b.l bit 2, equals
             userflag.b.l & 3 ($20F616, $20F66A): every update where an
             on-screen light is due has light tiles in the sprite buffer's link
             chain, and the PC SLIGHT7.C rule (& 6, & 2) must miss some.
  WW tiles   WW1A (R61A, tests/routes/ww/ww1A.txt): VInt_Level runs
             UpdateAnimTiles once per update after LevelStart's setup call, so
             the update with levelFrames L has made L + 1 calls; aniArtFrames and
             aniArtTimers equal src/background_r6.c ww_tick's state after L + 1
             ticks of assets/generated/ww_terrain.inc program 0.

src/world_qa.c checks the port against the same models. Exit 0 and "PASS:" when
every sample matches.
"""
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/anim-phase-retail'
UPDATES = 3000
RING, LOST_RING, MONITOR = 16, 17, 25  # R11A object ids
SEARCHLIGHT = 56  # R71A slight7
LIGHT_TILES = {0x4AF, 0x4BB, 0x4CB}  # its mapping tiles in the R71A sprite list


def probe():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = OUT / 'r11a.frames'
    env = dict(os.environ, TT_PROBE_FRAMES='0:%d:%s' % (UPDATES - 1, frames))
    subprocess.run([sys.executable, 'tools/retail_probe.py', '1', 'A', 'tests/routes/ppz/p0A.txt',
                    str(OUT / 'r11a.rows'), str(UPDATES), '--round', '1'], cwd=ROOT, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    globals_, objects = {}, {}
    for line in frames.read_text().splitlines():
        f = line.split()
        r = int(f[0])
        if f[1] == 'G':
            globals_[r] = int(f[2])
        else:
            slot, oid, sub, routine, frame = map(int, f[2:7])
            objects.setdefault(r, {})[slot] = (oid, sub, routine, frame, int(f[10]), int(f[11]))
    return globals_, objects


def check_rings(level_frames, objects):
    n = bad = 0
    for r, slots in objects.items():
        for oid, sub, routine, frame, render, x in slots.values():
            if oid == RING and routine == 2 and r > 0:
                n += 1
                bad += frame != ((level_frames[r] + 6) // 8) & 3
    return n, bad


def check_lost_rings(objects):
    n = bad = 0
    timer = accum = shown = 0
    prev = set()
    for r in range(min(objects), max(objects) + 1):
        live = {s: v for s, v in objects.get(r, {}).items() if v[0] == LOST_RING and v[2] == 2}
        if live and not prev:
            timer = 255
        for v in live.values():
            n += 1
            bad += v[3] != shown
        prev = set(live)
        if timer:
            accum = (accum + timer) & 0xffff
            shown = (accum >> 9) & 3
            timer -= 1
    return n, bad


def check_monitors(objects):
    n = bad = 0
    state = {}
    for r in sorted(objects):
        for slot, (oid, sub, routine, frame, render, x) in objects[r].items():
            if oid != MONITOR or sub >= 8 or routine != 2:
                state.pop(slot, None)
                continue
            prev = objects.get(r - 1, {}).get(slot)
            st = state.get(slot)
            if st is None or st[0] != (sub, x):
                # A slot already live on the first row has an unknown history.
                st = state[slot] = [(sub, x), None if prev and prev[0] == MONITOR and prev[1] == sub else 0]
            elif st[1] is not None and prev[4] & 128:
                st[1] += 1
            if st[1] is None:
                continue
            k = st[1]
            seq = [16, sub, sub, 8, sub, sub, 9, sub, sub]
            n += 1
            bad += frame != (0 if k == 0 else seq[((k - 1) // 2) % 9])
    return n, bad


def check_searchlights():
    frames, sprites = OUT / 'r71a.frames', OUT / 'r71a.spr'
    env = dict(os.environ, TT_PROBE_FRAMES='0:%d:%s' % (UPDATES - 1, frames), TT_PROBE_SPRITES=str(sprites))
    subprocess.run([sys.executable, 'tools/retail_probe.py', '1', 'A', 'tests/routes/ss/ss1A.txt',
                    str(OUT / 'r71a.rows'), str(UPDATES), '--round', '7'], cwd=ROOT, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    camera, lights = {}, {}
    for line in frames.read_text().splitlines():
        f = line.split()
        if f[1] == 'G':
            camera[int(f[0])] = int(f[8])
        elif int(f[3]) == SEARCHLIGHT and int(f[5]) == 2:
            lights.setdefault(int(f[0]), []).append((int(f[11]), int(f[13])))
    retail = lambda level, sub: (level & 3 if sub & 4 else level & 1) == sub & 3
    pc = lambda level, sub: (level & 6 if sub & 4 else level & 2) == sub & 6
    n = bad = pc_bad = 0
    for line in sprites.read_text().splitlines():
        f = line.split()
        r, level = int(f[0]), int(f[1])
        # Lights wholly inside the 320-pixel view; actionsub always draws them.
        on = [sub for x, sub in lights.get(r, []) if 0 <= x - camera[r] < 320]
        if r < 3 or not on:
            continue
        entries = [x.split(':') for x in f[2:]]
        drawn, k = False, 0
        for _ in range(64):
            link, tile = int(entries[k][0], 16), int(entries[k][1], 16)
            drawn = drawn or (tile & 0x7FF) in LIGHT_TILES
            k = link & 0x7F
            if not k:
                break
        # One direction only: a due on-screen light is in the sprite list. The
        # reverse is not checked; lights just off screen wrap into the 9-bit X.
        n += 1
        bad += any(retail(level, sub) for sub in on) and not drawn
        pc_bad += any(pc(level, sub) for sub in on) and not drawn
    return n, bad, pc_bad


def check_ww_tiles():
    aniart = OUT / 'r61a.aniart'
    env = dict(os.environ, TT_PROBE_ANIART=str(aniart))
    subprocess.run([sys.executable, 'tools/retail_probe.py', '1', 'A', 'tests/routes/ww/ww1A.txt',
                    str(OUT / 'r61a.rows'), '1500', '--round', '6'], cwd=ROOT, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    src = (ROOT / 'assets/generated/ww_terrain.inc').read_text()
    program = re.search(r'ww_anim\[12\] = \{\{(\d+),\d+,\{(.*?)\}\}\}', src)
    calls = [tuple(map(int, c[:4])) + (c[4],) for c in
             re.findall(r'\{(\d+),(\d+),(\d+),(\d+),\d+,\d+,(\w+),', program.group(2))][:int(program.group(1))]
    pairs = {m.group(1): list(map(int, m.group(2).split(','))) for m in
             re.finditer(r'static const uint8_t (\w+)\[\d+\] = \{([\d,]+)\}', src)}
    tim, cnt = [0] * len(calls), [0] * len(calls)

    def tick():  # ww_fire for each call of the program
        for i, (script, t, count, frames, name) in enumerate(calls):
            tim[i] = (tim[i] - 1) & 255
            if tim[i] < 128:
                continue
            n = cnt[i] + 1
            if not script:
                tim[i], cnt[i] = t, 0 if n >= frames else n
            else:
                cnt[i] = 0 if n >= count else n
                tim[i] = pairs[name][cnt[i] * 2]
    tick()  # LevelStart's setup call
    made = n = bad = 0
    for line in aniart.read_text().splitlines():
        f = list(map(int, line.split()))
        if f[0] < 1:
            continue
        while made < f[1]:
            tick()
            made += 1
        n += 1
        k = len(calls)
        bad += f[3:3 + k] != cnt or f[9:9 + k] != tim
    return n, bad


def main():
    level_frames, objects = probe()
    results = {'ring': check_rings(level_frames, objects), 'lost ring': check_lost_rings(objects),
               'monitor': check_monitors(objects)}
    ok = True
    for name, (n, bad) in results.items():
        print('%s: %d retail samples, %d mismatches' % (name, n, bad))
        ok = ok and n > 0 and bad == 0
    n, bad, pc_bad = check_searchlights()
    print('searchlight: %d retail samples, %d mismatches (PC SLIGHT7.C rule: %d)' % (n, bad, pc_bad))
    ok = ok and n > 0 and bad == 0 and pc_bad > 0
    n, bad = check_ww_tiles()
    print('WW tiles: %d retail samples, %d mismatches' % (n, bad))
    ok = ok and n > 0 and bad == 0
    print(('PASS: ' if ok else 'FAIL: ') + 'retail R11A/R71A/R61A animation phases match the port models')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
