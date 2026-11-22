#!/usr/bin/env python3
"""Compare the displayed Metallic Madness BG cells with the original's plane B.

As tools/capture_cc_plane.py: the original player walks to each target, the
level settles, and plane B, VSRAM and the VRAM hscroll table are dumped.  Each
visible BG cell (224 lines x 40 columns) is compared with the tile native
draw_stage shows for the same line scroll: static rows hold world x 0..511,
others world tile sx + ((col - sx) & 63) with sx = scd_background_row_start.

    python3 tools/capture_r8_plane.py 1 A        one program
    python3 tools/capture_r8_plane.py --all      all ten; PASS line on zero mismatches
"""
import argparse
import ctypes as C
import hashlib
import json
import struct
import subprocess
from pathlib import Path

from capture_cc_scroll import boot
from capture_cc_plane import stage, walk
import sys

ROOT = Path(__file__).resolve().parents[1]
# Views across each act's camera range (R8).
TARGETS = {1: [(1200, 1000), (1200, 300), (3000, 800), (5000, 1100), (7000, 900)],
           2: [(1200, 600), (3000, 1100), (5000, 900), (7000, 1000)],
           3: [(800, 900), (1800, 800), (2600, 1000)]}
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']


class Scroll(C.Structure):
    _fields_ = [('ramp', C.c_int32), ('camera_x', C.c_int), ('r3_layers', C.c_int32 * 4)]


def native_lib(out):
    lib_path = out/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Isrc', '-Iassets/generated', '-dynamiclib',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib_path)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib_path))
    native.scd_background_lines_state.argtypes = [C.c_uint, C.POINTER(Scroll), C.c_int, C.c_int, C.c_int, C.c_uint,
                                                  C.POINTER(C.c_int32), C.POINTER(C.c_int32), C.c_uint]
    native.scd_background_row_start.argtypes = [C.c_uint, C.POINTER(Scroll), C.c_int, C.c_int, C.c_uint]
    native.scd_background_static.argtypes = [C.c_uint, C.c_int]
    native.scd_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    native.scd_background_reset.argtypes = [C.POINTER(Scroll), C.c_int]
    native.scd_r7_layers.restype = C.POINTER(C.c_int32)
    native.scd_r7_reset.argtypes = [C.c_uint, C.c_int]
    return native


def capture(act, era, native):
    name = f'R8{act}{era}'
    out = ROOT/f'build/plane-retail/{name}'
    out.mkdir(parents=True, exist_ok=True)
    tile = stage(ROOT/f'assets/generated/mm8{act}{era}.bin')
    bg_id = 72+('ABCD'.index(era) | (act-1) << 2)
    core, e, frame, program = boot(era, act, 8)
    samples, totals = [], dict(cells=0, row_layer=0, line_offsets=0, background_y=0)
    for tx, ty in TARGETS[act]:
        frame = walk(core, e, frame, tx, ty)
        # walk() stops when Sonic arrives; hold him there 65 more updates so
        # the camera (16 px/update at most) settles before plane B is read.
        frame = walk(core, e, frame, tx, ty)
        reg = C.string_at(core.reg, 24)
        plane = core.swapped(core.vram, (reg[4] & 7) << 13, 0x1000)
        hscroll = core.swapped(core.vram, reg[13] << 10, 0x380)
        vs = C.string_at(core.vsram, 4)
        cam = {k: struct.unpack('>i', core.work_read(e[k], 4))[0] for k in
               ('cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg3X')}
        x, cy, by = cam['cameraX'] >> 16, cam['cameraY'] >> 16, cam['cameraBgY'] >> 16
        vsb = [struct.unpack_from(f, vs, 2)[0] & 1023 for f in ('<H', '>H')]
        vsb = next((v for v in vsb if (v & 255) == (by & 255)), None)
        assert vsb is not None, ('plane B vscroll does not match cameraBgY', vs.hex(), by, cam, tx, ty)
        # Native background Y from the camera alone (the program's shifts); the
        # R7 level layer state takes the original's settled layer words.
        totals['background_y'] += native.scd_background_y(bg_id, cy, 0) != by
        native.scd_r7_reset(bg_id-60, x)
        state = native.scd_r7_layers()
        for i, k in enumerate(('cameraBgX', 'cameraBg2X', 'cameraBg3X')):
            state[i] = cam[k]
        sc = Scroll(0, x, (C.c_int32*4)())
        rows = {}
        for row in range(by//8, by//8+30):
            fixed = native.scd_background_static(bg_id, row*8)
            rows[row] = (1 if fixed else 0, 0 if fixed else native.scd_background_row_start(bg_id, C.byref(sc), x, row*8, 0))
        mism = 0
        first = None
        for L in range(224):
            off = (-struct.unpack_from('>h', hscroll, L*4+2)[0]) & 511
            row = (by+L) >> 3
            prow = ((L+vsb) & 255) >> 3
            for col in range(40):
                slot = ((col*8+off) & 511) >> 3
                retail = struct.unpack_from('>H', plane, (prow*64+slot)*2)[0]
                fixed, start = rows[row]
                wx = slot if fixed else start+((slot-start) & 63)
                got = tile((wx*8) & 511 if fixed else wx*8, row*8)
                if got != retail and (got & 2047 or retail & 2047):
                    mism += 1
                    first = first or dict(line=L, col=col, row=row, slot=slot, fixed=fixed, start=start, retail=retail, native=got)
                totals['cells'] += 1
        totals['row_layer'] += mism
        samples.append(dict(target=[tx, ty], frame=frame, camera=cam, mismatches=mism, first=first,
                            plane_sha256=hashlib.sha256(plane).hexdigest()))
        (out/f'{tx}-{ty}-plane.bin').write_bytes(plane)
        (out/f'{tx}-{ty}-hscroll.bin').write_bytes(hscroll)
    report = dict(program=name, program_sha256=hashlib.sha256(program).hexdigest(), samples=samples, totals=totals,
                  limits='Original plane B after a walked camera; compares cell words, one cell per 8 screen columns.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return totals, samples


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('act', nargs='?', type=int, choices=(1, 2, 3))
    ap.add_argument('era', nargs='?', choices=list('ABCD'))
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    out = ROOT/'build/plane-retail'
    out.mkdir(parents=True, exist_ok=True)
    native = native_lib(out)
    todo = PROGRAMS if args.all else [f'{args.act}{args.era}']
    cells = views = bad = 0
    for p in todo:
        totals, samples = capture(int(p[0]), p[1], native)
        cells += totals['cells']
        views += len(samples)
        bad += totals['row_layer']+totals['background_y']
        print(f"R8{p}", totals, [s['first'] for s in samples if s['first']][:1], flush=True)
    if bad:
        raise SystemExit(f'FAIL: MM plane B: {bad} mismatches over {cells} cells')
    print(f'PASS: MM plane B: {cells} retail plane B cells across {views} walked views of {len(todo)} programs match native rows')


if __name__ == '__main__':
    main()
