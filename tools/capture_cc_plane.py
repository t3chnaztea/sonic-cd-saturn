#!/usr/bin/env python3
"""Compare the displayed Collision Chaos plane A/B cells with native stage tiles.

The scroll fixtures teleport the camera, which leaves the original's
incrementally drawn plane stale. Here the original player walks to each
target (the camera follows at its own speed), the level settles, and the
tool dumps plane B, VSRAM and the CPU hscroll table. Each visible BG cell
(224 lines x 40 columns) is then compared with the tile native draw_stage
shows for the same line scroll: world tile sx + ((col - sx) & 63) of the row.
"""
import argparse
import ctypes as C
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import special_retail as sr
from capture_cc_scroll import boot

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [(2400, 1000), (6000, 1000), (9000, 1100), (11800, 1248)]
# Palmtree Panic is shorter vertically; include the 4096/8192-pixel wraps.
PPZ_TARGETS = [(2400, 300), (4100, 300), (6000, 350), (8200, 350)]
PPZ3_TARGETS = [(800, 300), (1600, 300), (2400, 300)]


def stage(pack, layer=1):
    d = pack.read_bytes()
    parts = [d[o:o + n] for o, n in (struct.unpack_from('>II', d, 4 + 8 * i) for i in range(6))]

    def tile(x, y):
        if x < 0 or y < 0 or x >= 16384 or y >= 2048:
            return 0
        c = parts[3 + layer][(y >> 8) * 64 + (x >> 8)] & 127
        if not c or c * 512 > len(parts[2]):
            return 0
        b = struct.unpack_from('>H', parts[2], (c - 1) * 512 + ((y >> 4) & 15) * 32 + ((x >> 4) & 15) * 2)[0]
        i = b & 1023
        if i * 8 + 8 > len(parts[1]):
            return 0
        tx, ty = (x >> 3) & 1, (y >> 3) & 1
        if b & 0x800:
            tx ^= 1
        if b & 0x1000:
            ty ^= 1
        t = struct.unpack_from('>H', parts[1], i * 8 + ty * 4 + tx * 2)[0] ^ (b & 0x1800)
        return t if (t & 2047) * 32 + 32 <= len(parts[0]) else 0
    return tile


def walk(core, e, frame, tx, ty):
    player = bytearray(core.work_read(e['objPlayerSlot'], 64))
    x = struct.unpack_from('>I', player, e['oX'])[0] >> 16
    y = struct.unpack_from('>I', player, e['oY'])[0] >> 16
    for n in range(4000):
        dx, dy = tx + 160 - x, ty + 96 - y
        if not dx and not dy and n > 64:
            break
        x += max(-6, min(6, dx)); y += max(-6, min(6, dy))
        player = bytearray(core.work_read(e['objPlayerSlot'], 64))
        struct.pack_into('>I', player, e['oX'], x * 65536); struct.pack_into('>I', player, e['oY'], y * 65536)
        player[e['oXVel']:e['oXVel'] + 6] = bytes(6); player[e['oFlags']] = 2; player[e['oRoutine']] = 2
        player[0x2c] = 0; player[0x30:0x32] = struct.pack('>H', 120)
        core.work_write(e['objPlayerSlot'], player)
        core.pad = 0; core.run(); frame += 1; core.host.chunks.clear()
    return frame


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('era', choices=list('ABCD')); ap.add_argument('--act', type=int, default=2, choices=(1, 2, 3)); ap.add_argument('--round', type=int, default=3, choices=(1, 3))
    args = ap.parse_args()
    name = f'R{args.round}{args.act}{args.era}'
    out = ROOT / f'build/plane-retail/{name}'; out.mkdir(parents=True, exist_ok=True)
    lib_path = out / 'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Isrc', '-Iassets/generated', '-dynamiclib',
                    'src/background.c', 'src/background_r3.c', '-o', str(lib_path)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib_path))

    class Scroll(C.Structure):
        _fields_ = [('ramp', C.c_int32), ('camera_x', C.c_int), ('r3_layers', C.c_int32 * 4)]
    native.scd_background_lines_state.argtypes = [C.c_uint, C.POINTER(Scroll), C.c_int, C.c_int, C.c_int, C.c_uint,
                                                  C.POINTER(C.c_int32), C.POINTER(C.c_int32), C.c_uint]
    native.scd_background_row_start.argtypes = [C.c_uint, C.POINTER(Scroll), C.c_int, C.c_int, C.c_uint]
    native.scd_background_static.argtypes = [C.c_uint, C.c_int]
    pack = f'cc3{args.act}{args.era}' if args.round == 3 else f'ppz{"ABCD".index(args.era)}' if args.act == 1 else f'ppz1{args.act}{args.era}'
    tile = stage(ROOT / f'assets/generated/{pack}.bin')
    foreground_tile = stage(ROOT / f'assets/generated/{pack}.bin', 0)
    bg_id = (12 if args.round == 3 else 0) + ('ABCD'.index(args.era) | (args.act - 1) << 2)
    core, e, frame, program = boot(args.era, args.act, args.round)
    foreground_cache = [0] * 4096
    previous_foreground = [-10000, -10000]

    def track_foreground():
        cx = struct.unpack('>i', core.work_read(e['cameraX'], 4))[0] >> 16
        cy = struct.unpack('>i', core.work_read(e['cameraY'], 4))[0] >> 16
        camera_tx, camera_ty = cx // 8, cy // 8
        if (camera_tx, camera_ty) == tuple(previous_foreground):
            return
        old_x, old_y = previous_foreground
        for wy in range(camera_ty, camera_ty + 30):
            for wx in range(camera_tx, camera_tx + 42):
                if old_x <= wx < old_x + 42 and old_y <= wy < old_y + 30:
                    continue
                foreground_cache[(wy & 63) * 64 + (wx & 63)] = foreground_tile(wx * 8, wy * 8)
        previous_foreground[:] = [camera_tx, camera_ty]

    track_foreground()
    original_run = core.run

    def tracked_run():
        original_run()
        track_foreground()

    core.run = tracked_run
    speed = 32768 if args.era == 'B' else 49152
    samples, totals = [], dict(cells=0, row_cells=0, row_layer=0,
                               foreground_cells=0, foreground_stale_visible=0,
                               foreground_active=0,
                               foreground_mismatches=0)
    for tx, ty in ((PPZ3_TARGETS if args.act == 3 else PPZ_TARGETS) if args.round == 1 else TARGETS):
        frame = walk(core, e, frame, tx, ty)
        reg = C.string_at(core.reg, 24)
        plane = core.swapped(core.vram, (reg[4] & 7) << 13, 0x1000)
        foreground_plane = core.swapped(core.vram, (reg[2] & 0x38) << 10, 0x1000)
        hscroll = core.swapped(core.vram, reg[13] << 10, 0x380)
        vs = C.string_at(core.vsram, 4)
        cam = {k: struct.unpack('>i', core.work_read(e[k], 4))[0] for k in
               ('cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg3X')}
        dx = struct.unpack('>h', core.work_read(e['scrollXDiff'], 2))[0]
        acc = struct.unpack('>I', core.work_read(e['deformBuffer'], 4))[0]
        x, cy, by = cam['cameraX'] >> 16, cam['cameraY'] >> 16, cam['cameraBgY'] >> 16
        vsa = struct.unpack_from('<H', vs, 0)[0] & 511
        assert vsa == (cy & 511), ('plane A vscroll does not match cameraY', vs.hex(), cy)
        vsb = [struct.unpack_from(f, vs, 2)[0] & 1023 for f in ('<H', '>H')]
        vsb = next((v for v in vsb if (v & 255) == (by & 255)), None)
        assert vsb is not None, ('plane B vscroll does not match cameraBgY', vs.hex(), by)
        sc = Scroll(0, x, (C.c_int32 * 4)(cam['cameraBgX'], cam['cameraBg2X'], cam['cameraBg3X'], 65535 if dx < 0 else 0))
        bg = (C.c_int32 * 224)(); fg = (C.c_int32 * 224)()
        f = acc // speed
        native.scd_background_lines_state(bg_id, C.byref(sc), x, cy, by, f, bg, fg, 224)
        rows = {}
        for row in range(by // 8, by // 8 + 30):
            fixed = native.scd_background_static(bg_id, row * 8)
            rows[row] = (1 if fixed else 0, 0 if fixed else native.scd_background_row_start(bg_id, C.byref(sc), x, row * 8, f))
        mism = {'row_layer': 0, 'line_offsets': 0, 'foreground': 0,
                'foreground_stale_visible': 0}; first = {}
        for L in range(224):
            off = (-struct.unpack_from('>h', hscroll, L * 4 + 2)[0]) & 511
            foreground_off = (-struct.unpack_from('>h', hscroll, L * 4)[0]) & 511
            # VRAM hscroll was DMAed one vblank before the work-RAM state.
            lagged = off != (bg[L] >> 16) & 511
            mism['line_offsets'] += lagged
            row = (by + L) >> 3
            prow = ((L + vsb) & 255) >> 3
            for col in range(40):
                foreground_slot = ((col * 8 + foreground_off) & 511) >> 3
                foreground_row = (cy + L) >> 3
                foreground_plane_row = ((L + vsa) & 255) >> 3
                foreground_retail = struct.unpack_from('>H', foreground_plane,
                    (foreground_plane_row * 64 + foreground_slot) * 2)[0]
                foreground_tx = x // 8
                foreground_world_x = foreground_tx + ((foreground_slot - foreground_tx) & 63)
                foreground_native = foreground_cache[(foreground_row & 63) * 64 + foreground_slot]
                totals['foreground_cells'] += 1
                totals['foreground_active'] += bool(foreground_retail & 2047)
                # Line deformation can display a stale slot outside the 42
                # freshly drawn columns. Keep that count, then compare it too.
                if foreground_world_x - foreground_tx >= 42:
                    mism['foreground_stale_visible'] += 1
                    totals['foreground_stale_visible'] += 1
                if (foreground_retail != foreground_native and
                        (foreground_retail & 2047 or foreground_native & 2047)):
                    mism['foreground'] += 1
                    first.setdefault('foreground', dict(line=L, col=col, row=foreground_row,
                        slot=foreground_slot, world_x=foreground_world_x,
                        retail=foreground_retail, native=foreground_native))
                slot = ((col * 8 + off) & 511) >> 3
                retail = struct.unpack_from('>H', plane, (prow * 64 + slot) * 2)[0]
                # Shipped draw_stage rule: static rows hold x 0..511, others sx..sx+63.
                fixed, start = rows[row]
                wx = slot if fixed else start + ((slot - start) & 63)
                got = tile((wx * 8) & 511 if fixed else wx * 8, row * 8)
                if got != retail and (got & 2047 or retail & 2047):
                    mism['row_layer'] += 1
                    first.setdefault('row_layer', dict(line=L, col=col, row=row, slot=slot, fixed=fixed, start=start,
                                                       retail=retail, native=got))
                totals['row_cells'] += 1
                totals['cells'] += 1
        totals['row_layer'] += mism['row_layer']
        totals['foreground_mismatches'] += mism['foreground']
        samples.append(dict(target=[tx, ty], frame=frame, camera=cam, scroll_x_diff=dx, deform_frame=f,
                            mismatches=mism, first=first, plane_sha256=hashlib.sha256(plane).hexdigest(),
                            foreground_plane_sha256=hashlib.sha256(foreground_plane).hexdigest()))
        (out / f'{tx}-{ty}-plane.bin').write_bytes(plane); (out / f'{tx}-{ty}-hscroll.bin').write_bytes(hscroll)
        (out / f'{tx}-{ty}-foreground-plane.bin').write_bytes(foreground_plane)
        print(name, (tx, ty), 'camera', x, cy, 'by', by, 'mismatched cells', mism, flush=True)
    report = dict(program=name, program_sha256=hashlib.sha256(program).hexdigest(), samples=samples, totals=totals,
                  limits='Original planes A/B after a walked camera; compares cell words, including tile priority, one cell per 8 screen columns. Plane A uses a replayed 42x30 camera cache so stale visible cells are compared too.')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(name, 'totals', totals)


if __name__ == '__main__':
    main()
