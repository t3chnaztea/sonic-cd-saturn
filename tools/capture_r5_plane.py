#!/usr/bin/env python3
"""Compare the displayed Quartz Quadrant BG cells with the original's plane B.

As tools/capture_r4_plane.py: the original player walks to each target, the
level settles, and plane B, VSRAM and the VRAM hscroll table are dumped.  Each
visible BG cell (224 lines x 40 columns) is compared with the tile native
draw_stage shows for the same line scroll: static rows hold world x 0..511,
others world tile sx + ((col - sx) & 63) with sx = scd_background_row_start.
enkeino is read from the original (tools/capture_r5_scroll.find_enkei) and
given to native.  The gate covers enkeino 0 and 2 views.  enkeino 1 swaps in
another background map and tiles (enkeichg: mapset2, ChangeTileBmp) that the
harvested packs do not hold; those views are reported separately, not gated.

    python3 tools/capture_r5_plane.py 1 A        one program
    python3 tools/capture_r5_plane.py --all      all ten; PASS line on zero mismatches
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
from capture_r5_scroll import find_enkei

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {1: [(1200, 300), (2500, 600), (3000, 100), (5000, 400), (7000, 700), (9500, 300), (10500, 600), (1500, 700)],
           2: [(1200, 300), (3000, 200), (5000, 400), (6800, 100), (9000, 300), (2000, 500)],
           3: [(800, 400), (1800, 700), (3000, 200), (3600, 600)]}
PROGRAMS = ['1A', '1B', '1C', '1D', '2A', '2B', '2C', '2D', '3C', '3D']


def stage_words(pack, native, pid, band):
    """capture_cc_plane.stage without its art bound, through native's enkeino
    layout cells: the plane word the map gives, and whether the pack holds
    that tile's art.  band[0] is the enkeino of the view."""
    d = pack.read_bytes()
    parts = [d[o:o + n] for o, n in (struct.unpack_from('>II', d, 4 + 8 * i) for i in range(6))]
    stage_words.art = parts[0]

    def tile(x, y):
        if x < 0 or y < 0 or x >= 16384 or y >= 2048:
            return 0, True
        c = native.scd_r5_map_cell(pid, band[0], y >> 8, x >> 8, parts[4][(y >> 8) * 64 + (x >> 8)]) & 127
        if not c or c * 512 > len(parts[2]):
            return 0, True
        swap = native.scd_r5_chunk(pid, band[0], c)
        chunk = C.string_at(swap, 512) if swap else parts[2][(c - 1) * 512:c * 512]
        b = struct.unpack_from('>H', chunk, ((y >> 4) & 15) * 32 + ((x >> 4) & 15) * 2)[0]
        i = b & 1023
        if i * 8 + 8 > len(parts[1]):
            return 0, True
        tx, ty = (x >> 3) & 1, (y >> 3) & 1
        if b & 0x800:
            tx ^= 1
        if b & 0x1000:
            ty ^= 1
        t = struct.unpack_from('>H', parts[1], i * 8 + ty * 4 + tx * 2)[0] ^ (b & 0x1800)
        return t, (t & 2047) * 32 + 32 <= len(parts[0])
    return tile


def native_lib(out):
    lib_path = out/'native-r5.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Isrc', '-Iassets/generated', '-dynamiclib',
                    'src/background_r5.c', '-o', str(lib_path)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib_path))
    native.scd_r5_set_enkei.argtypes = [C.c_uint, C.c_int, C.c_int]
    native.scd_r5_row_start.argtypes = [C.c_uint, C.c_int, C.POINTER(C.c_int32), C.c_int]
    native.scd_r5_row_layer.argtypes = [C.c_uint, C.c_int]
    native.scd_r5_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    native.scd_r5_map_cell.argtypes = [C.c_uint, C.c_int, C.c_int, C.c_int, C.c_int]
    native.scd_r5_art.argtypes = [C.c_uint, C.c_int, C.c_uint]
    native.scd_r5_art.restype = C.c_void_p
    native.scd_r5_chunk.argtypes = [C.c_uint, C.c_int, C.c_uint]
    native.scd_r5_chunk.restype = C.c_void_p
    return native


def capture(act, era, native):
    name = f'R5{act}{era}'
    out = ROOT/f'build/plane-retail/{name}'
    out.mkdir(parents=True, exist_ok=True)
    pid = 'ABCD'.index(era) | (act-1) << 2
    band = [0]
    tile = stage_words(ROOT/f'assets/generated/qq5{act}{era}.bin', native, pid, band)
    no_art = set()
    pid = 'ABCD'.index(era) | (act-1) << 2
    core, e, frame, program = boot(era, act, 5)
    enkei_at = find_enkei(core, e, act) if act < 3 else None
    samples = []
    totals = dict(cells=0, undrawn=0, row_layer=0, background_y=0, art=0, enkeino1_cells=0, tiles_without_art=0)
    for tx, ty in TARGETS[act]:
        frame = walk(core, e, frame, tx, ty)
        # Hold the player until the camera has not moved for 8 frames, so
        # VSRAM/hscroll (written in vblank) show the recorded camera.
        still, last = 0, None
        while still < 8 and frame < 1 << 30:
            p = bytearray(core.work_read(e['objPlayerSlot'], 64))
            p[e['oXVel']:e['oXVel']+6] = bytes(6)
            core.work_write(e['objPlayerSlot'], p)
            core.pad = 0
            core.run()
            core.host.chunks.clear()
            frame += 1
            now = core.work_read(e['cameraX'], 8)
            still = still+1 if now == last else 0
            last = now
        reg = C.string_at(core.reg, 24)
        plane = core.swapped(core.vram, (reg[4] & 7) << 13, 0x1000)
        hscroll = core.swapped(core.vram, reg[13] << 10, 0x380)
        vs = C.string_at(core.vsram, 4)
        cam = {k: struct.unpack('>i', core.work_read(e[k], 4))[0] for k in
               ('cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg3X')}
        px = struct.unpack('>I', core.work_read(e['objPlayerSlot']+e['oX'], 4))[0] >> 16
        enkei = core.work_read(enkei_at, 1)[0] if enkei_at else 0
        band[0] = enkei
        vram = core.swapped(core.vram, 0, 0x10000)
        x, cy, by = cam['cameraX'] >> 16, cam['cameraY'] >> 16, cam['cameraBgY'] >> 16
        vsb = [struct.unpack_from(f, vs, 2)[0] & 1023 for f in ('<H', '>H')]
        vsb = next((v for v in vsb if (v & 255) == (by & 255)), None)
        assert vsb is not None, ('plane B vscroll does not match cameraBgY', vs.hex(), by)
        native.scd_r5_set_enkei(pid, enkei, x)
        bad_y = native.scd_r5_background_y(pid, cy, px) != by and not cam['cameraY'] & 0xffff
        lay = (C.c_int32*3)(cam['cameraBgX'], cam['cameraBg2X'], cam['cameraBg3X'])
        rows = {}
        for row in range(by//8, by//8+30):
            fixed = native.scd_r5_row_layer(pid, row*8) == 0
            rows[row] = (1 if fixed else 0, 0 if fixed else native.scd_r5_row_start(pid, x, lay, row*8))
        mism = cells = undrawn = art_bad = 0
        art_first = None
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
                got, art = tile((wx*8) & 511 if fixed else wx*8, row*8)
                t = got & 2047
                over = native.scd_r5_art(pid, enkei, t)
                if over:
                    mine = C.string_at(over, 32)
                elif art:
                    mine = stage_words.art[t*32:t*32+32]
                else:
                    no_art.add(t)
                    mine = None
                if mine != vram[t*32:t*32+32]:
                    art_bad += 1
                    art_first = art_first or dict(line=L, col=col, tile=t, enkeino=enkei)
                if got != retail and (got & 2047 or retail & 2047):
                    # Layer rows: scrollwrtb/hblockwrt draw 21 blocks (42 cells)
                    # from the layer's position - 16; retail leaves the rest blank.
                    if not fixed and not retail & 2047 and (slot-(start+9)) % 64 >= 42:
                        undrawn += 1
                        continue
                    mism += 1
                    first = first or dict(line=L, col=col, row=row, slot=slot, fixed=fixed, start=start, retail=retail, native=got)
                cells += 1
        gated = True
        totals['art'] += art_bad
        totals['enkeino1_cells'] += cells if enkei & 1 else 0
        if gated:
            totals['undrawn'] += undrawn
            totals['cells'] += cells
            totals['row_layer'] += mism
            totals['background_y'] += bad_y
        else:
            totals['open_cells'] += cells
            totals['open_mismatches'] += mism
        samples.append(dict(target=[tx, ty], frame=frame, camera=cam, player_x=px, enkeino=enkei, gated=gated,
                            mismatches=mism, background_y_ok=not bad_y, first=first, art_mismatches=art_bad, art_first=art_first,
                            plane_sha256=hashlib.sha256(plane).hexdigest()))
        (out/f'{tx}-{ty}-plane.bin').write_bytes(plane)
        (out/f'{tx}-{ty}-hscroll.bin').write_bytes(hscroll)
    totals['tiles_without_art'] = len(no_art)
    report = dict(program=name, tiles_without_art=sorted(no_art), program_sha256=hashlib.sha256(program).hexdigest(), samples=samples, totals=totals,
                  limits='Original plane B after a walked camera; compares cell words, one cell per 8 screen columns. '
                         'enkeino 1 views (alternate map/tiles not in the pack) are reported, not gated.')
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
    t = dict(cells=0, views=0, bad=0, art=0, enkei1=0, undrawn=0, no_art=0)
    for p in todo:
        totals, samples = capture(int(p[0]), p[1], native)
        t['cells'] += totals['cells']
        t['views'] += len(samples)
        t['bad'] += totals['row_layer']+totals['background_y']
        t['art'] += totals['art']
        t['enkei1'] += totals['enkeino1_cells']
        t['undrawn'] += totals['undrawn']
        t['no_art'] += totals['tiles_without_art']
        print(f'R5{p}', totals, [s['first'] or s['art_first'] for s in samples if s['first'] or s['art_first']][:1], flush=True)
    if t['bad'] or t['art']:
        raise SystemExit(f"FAIL: QQ plane B: {t['bad']} cell and {t['art']} art mismatches over {t['cells']} cells")
    print(f"PASS: QQ plane B: {t['cells']} retail plane B cells ({t['enkei1']} in enkeino 1 views) across {t['views']} walked views "
          f"of {len(todo)} programs match native rows and tile art ({t['undrawn']} cells native fills where retail leaves "
          f"layer rows undrawn; {t['no_art']} shown tiles without native art)")


if __name__ == '__main__':
    main()
