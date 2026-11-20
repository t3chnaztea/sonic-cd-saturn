#!/usr/bin/env python3
"""Tidal Tempest Act 1 Present fire tiles (DEV41A.C cg_change) -> assets/generated/tt_terrain.inc.

    python3 tools/tt_terrain_assets.py           capture retail art, write the include
    python3 tools/tt_terrain_assets.py --check   re-capture and fail if the include differs

DEV41A cycles three 16-tile slots (PC tiles 558, 574, 590; retail 568, 584, 552) through eight frames
(fire0cg-fire7cg) on 24-step scripts, only while camera X < 640 and Y < 352.
DEV41B-D and the Act 2/3 DEV files are stubs.  The PC source names bitmap
numbers, not art, so the art is read from the original: R41A runs from its
start (camera inside the fire area), VRAM tiles 558-605 are recorded every
frame, and each recorded block is labelled with the frame the compiled
original DEV41A schedule shows in that slot at that update.  Every frame
number must map to exactly one 512-byte block per slot across all updates
(one constant offset), and the pack's fire cells must be blank or hold one retail fire frame.  The retail
art differs per slot (16 distinct blocks), so art is keyed by (slot, frame).
"""
import argparse
import ctypes as C
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
SOURCE = ROOT/'build/audit/source/src/R4/DEV41A.C'
OUT = ROOT/'assets/generated/tt_terrain.inc'  # retail art: never under src/
BUILD = ROOT/'build/tt/terrain'
HARNESS = r'''
#include <stdint.h>
typedef struct { char tim; char no; } tile_change_data;
typedef struct { char chgcnt; char dmy; tile_change_data dattbl[25]; int *TileNoTbl[8]; int TileStart; } tile_changes;
typedef struct { unsigned char l, h; } short_chars;
typedef union { short w; short_chars b; } short_union;
typedef struct { short l, h; } int_shorts;
typedef union { int l; int_shorts w; } int_union;
short_union pauseflag; int_union scra_h_posit, scra_v_posit;
unsigned char cgchgtim[6], cgchgcnt[6];
int tiles[2048];
static void ChangeTileBmp(int top, int bmp) { tiles[top & 2047] = bmp; }
%(body)s
void init(void) { for (int i = 0; i < 6; i++) cgchgtim[i] = cgchgcnt[i] = 0; for (int i = 0; i < 2048; i++) tiles[i] = -1; }
void step(int x, int y) { scra_h_posit.l = x * 65536; scra_v_posit.l = y * 65536; cg_change(); }
int tile(int i) { return tiles[i]; }
'''
SLOTS = (558, 574, 590)          # DEV41A.C TileStart of tbl_fir0-2 (PC tile numbers)
# Retail R41A VRAM: per-tile change timing shows tbl_fir0's script animating
# tiles 568-583, tbl_fir1's 584-599 and tbl_fir2's 552-567 (each is idle in a
# different one of the three 120-update cycles).  Retail cells are the authority.
CELLS = (568, 584, 552)


def oracle():
    src = SOURCE.read_text()
    from test_cc_palette import function
    arrays = '\n'.join(m[0] for m in re.finditer(r'static (?:int \w+\[16\]|tile_changes \w+) = \{.*?\n\};|static int \w+\[16\] = \{[^}]*\};', src, re.S))
    m = re.search(r'static unsigned int cg_chg1\(.*?\)\s*\{', src)
    depth, end = 1, m.end()
    while depth:
        depth += (src[end] == '{')-(src[end] == '}')
        end += 1
    body = arrays+'\nstatic unsigned int cg_chg1(tile_changes*, int, unsigned char**, unsigned char**, int*, int*);\n'
    body += function(src, 'cg_change')+'\n'+src[m.start():end]
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD/'original-DEV41A.c'
    path.write_text(HARNESS % dict(body=body))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.step.argtypes = [C.c_int, C.c_int]
    return dll


def schedule(dll, frames, x=0, y=0):
    """Frame number per slot after each update (update 0 is the level-setup call)."""
    dll.init()
    rows = []
    for _ in range(frames):
        dll.step(x, y)
        row = []
        for top in SLOTS:
            bmps = [dll.tile(top+i) for i in range(16)]
            assert bmps[0] < 0 or bmps == list(range(bmps[0], bmps[0]+16)) and bmps[0] % 16 == 0, bmps
            row.append(bmps[0]//16 if bmps[0] >= 0 else None)
        rows.append(tuple(row))
    return rows


def capture(frames):
    from capture_cc_scroll import boot
    core, e, _, program = boot('A', 1, 4)
    cam = [struct.unpack('>h', core.work_read(e[k], 2))[0] for k in ('cameraX', 'cameraY')]
    blocks = []
    for _ in range(frames):
        core.pad = 0
        core.run()
        core.host.chunks.clear()
        blocks.append(tuple(core.swapped(core.vram, c*32, 512) for c in CELLS))
    return blocks, cam, program


def label(blocks, sched):
    """Find the schedule offset at which every (slot, frame) maps to one block.

    Boot leaves the scripts at an arbitrary phase, so the offset spans one
    whole 360-update script period plus the display latency."""
    for lag in range(0, 400):
        art, ok = {}, True
        for t, row in enumerate(blocks):
            s = t+lag
            if s >= len(sched):
                break
            for slot, frame in enumerate(sched[s]):
                if frame is None:
                    continue
                if art.setdefault((slot, frame), row[slot]) != row[slot]:
                    ok = False
                    break
            if not ok:
                break
        if ok and len(art) == 24:
            return lag, art
    raise SystemExit('FAIL: no display latency labels the retail fire tiles consistently')


def build():
    dll = oracle()
    blocks, cam, program = capture(900)
    assert cam[0] < 640 and cam[1] < 352, ('R41A does not start in the fire area', cam)
    sched = schedule(dll, 1400)
    lag, art = label(blocks, sched)
    pack = (ROOT/'assets/generated/tt41A.bin').read_bytes()
    off, size = struct.unpack_from('>II', pack, 4)
    tiles = pack[off:off+size]
    for slot, cell in enumerate(CELLS):
        # The pack's fire cells hold either nothing or one retail fire frame
        # (the VRAM the level art was read from); cg_change overwrites them.
        held = tiles[cell*32:cell*32+512]
        assert held == bytes(512) or any(all(held[i*32:i*32+32] in (bytes(32), art[slot, f][i*32:i*32+32])
                                             for i in range(16)) for f in range(8)), ('pack fire cells hold no fire frame', cell)
    src = SOURCE.read_text()
    scripts = []
    for n in range(3):
        body = re.search(r'static tile_changes tbl_fir%d = \{(.*?)\n\};' % n, src, re.S)[1]
        nums = list(map(int, re.findall(r'-?\d+', re.sub(r'fire\dcg', '', body))))
        count, _, pairs, start = nums[0], nums[1], nums[2:2+2*nums[0]], nums[-1]
        assert start == SLOTS[n] and count == 24, (n, start, count)
        scripts.append(pairs)
    text = ['/* Generated by tools/tt_terrain_assets.py: DEV41A.C fire scripts; art read from retail R41A VRAM. */']
    text.append('static const uint8_t r4_fire_script[3][48] = {' +
                ','.join('{'+','.join(map(str, p))+'}' for p in scripts)+'};  /* (timer, frame) x 24 */')
    text.append('static const uint16_t r4_fire_cell[3] = {'+','.join(map(str, CELLS))+'};  /* retail VRAM cells */')
    text.append('static const uint8_t r4_fire_art[3][8][512] = {' + ','.join(
        '{'+','.join('{'+','.join(map(str, art[slot, f]))+'}' for f in range(8))+'}' for slot in range(3))+'};')
    report = dict(program_sha256=hashlib.sha256(program).hexdigest(), start_camera=cam, display_latency=lag,
                  frames={f'{a}-{b}': hashlib.sha256(v).hexdigest() for (a, b), v in sorted(art.items())}, updates_checked=len(blocks))
    return '\n'.join(text)+'\n', report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    text, report = build()
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD/'assets.json').write_text(json.dumps(report, indent=2)+'\n')
    if args.check:
        if OUT.read_text() != text:
            sys.exit(f'FAIL: {OUT.relative_to(ROOT)} differs from the retail capture')
        print(f'PASS: TT fire tiles: 3 slots x 8 retail frames consistent over {report["updates_checked"]} R41A updates (latency {report["display_latency"]})')
        return
    OUT.write_text(text)
    print('wrote', OUT.relative_to(ROOT), 'latency', report['display_latency'])


if __name__ == '__main__':
    main()
