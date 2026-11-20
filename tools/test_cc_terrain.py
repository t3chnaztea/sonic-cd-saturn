#!/usr/bin/env python3
"""Verify CC2 terrain animation: compiled-original DEV32A-D.C drum tile cycles
against the native retail-extracted cycles, and COL3A-D palette cycles in Act 2."""
import ctypes as C
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
TICKS = 8192
OUT = ROOT / 'build/cc2/terrain'

PRELUDE = '''#include <stdint.h>
typedef struct { char tim; char no; } tile_change_data;
typedef struct { char chgcnt; char dmy; tile_change_data dattbl[25]; int *TileNoTbl[8]; int TileStart; } tile_changes;
unsigned char cgchgtim[6], cgchgcnt[6];
static int writes, write_tile[64], write_bmp[64];
static void record(int tile, int bmp) { write_tile[writes] = tile; write_bmp[writes] = bmp; writes++; }
void (*ChangeTileBmp)(int, int) = record;
'''
EPILOGUE = '''
void reset(void) { for (int i = 0; i < 6; i++) cgchgtim[i] = cgchgcnt[i] = 0; }
int step(int *tiles, int *bmps) { writes = 0; cg_change();
    for (int i = 0; i < writes; i++) { tiles[i] = write_tile[i]; bmps[i] = write_bmp[i]; } return writes; }
'''


def original(letter):
    source = (ROOT / f'.deps/soniccd/src/R3/DEV32{letter}.C').read_text()
    body = re.sub(r'^\s*#include.*$', '', source, flags=re.M)
    body = re.sub(r'^\s*map_init_data mapinittbl = .*?;', '', body, flags=re.M)
    path = OUT / f'original-DEV32{letter}.c'
    path.write_text(PRELUDE + body + EPILOGUE)
    subprocess.run(['clang', '-std=c11', '-fsigned-char', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-shared', '-fPIC', str(path), '-o', str(path.with_suffix('.dylib'))], check=True)
    lib = C.CDLL(str(path.with_suffix('.dylib')))
    lib.step.argtypes = [C.POINTER(C.c_int), C.POINTER(C.c_int)]
    return lib


class Write(C.Structure):
    _fields_ = [('cell', C.c_uint16), ('cells', C.c_uint16), ('art', C.POINTER(C.c_uint8)), ('frame', C.c_uint)]


def main(run):
    import extract_zone_auto as Z
    from extract_mmd import disc_files
    import cc2_terrain_assets as A
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-Isrc', '-Iassets/generated',
                    'src/background.c', 'src/background_r3.c', '-o', str(OUT / 'native.dylib')], cwd=ROOT, check=True)
    native = C.CDLL(str(OUT / 'native.dylib'))
    native.scd_background_tile_cycle.argtypes = [C.c_uint, C.c_uint, C.POINTER(Write)]
    native.scd_background_tile_cycle.restype = C.c_uint
    native.scd_background_palette.argtypes = [C.c_uint, C.c_uint, C.c_void_p, C.c_void_p]
    disc = disc_files(Z.read_iso(ROOT / 'build/retail/sonic.iso'))
    out = (Write * 4)()
    eras, tile_checks, cell_bytes, fires = {}, 0, 0, 0
    for era, letter in enumerate('ABCD'):
        data = disc[f'R32{letter}__.MMD']
        _, retail = A.routine(data)
        dev = (ROOT / f'.deps/soniccd/src/R3/DEV32{letter}.C').read_text()
        has_cycles = bool(re.search(r'\bcg_change\s*\(', dev))
        if retail is None:
            assert not has_cycles, (letter, 'DEV has tile cycles but the retail routine is jmp')
            for tick in range(TICKS + 1):
                assert native.scd_background_tile_cycle(16 + era, tick, out) == 0
            eras[letter] = {'tile_cycles': 0, 'ticks': TICKS + 1}
            continue
        assert has_cycles, (letter, 'retail cycles but no DEV32 cg_change')
        # The PC bitmap bank is contiguous retail art: frame 1 (dattbl index 1,
        # the "re" tables 0..n-1) then frame 0 (the "no" tables n..2n-1).
        base = retail['art'][1][0][0]
        order = [p for f in (1, 0) for p, _ in retail['art'][f]]
        cells = [n for _, n in retail['slots']]
        expect = [base + 32 * sum(cells[:i]) for i in range(len(cells))]
        expect += [base + 32 * sum(cells) + 32 * sum(cells[:i]) for i in range(len(cells))]
        assert order == expect, (letter, 'retail art is not one contiguous bitmap bank', order, expect)
        lib = original(letter)
        lib.reset()
        tiles, bmps = (C.c_int * 64)(), (C.c_int * 64)()
        state, written_ticks, prev_frame = {}, [], None
        for tick in range(TICKS + 1):
            n = lib.step(tiles, bmps)
            for i in range(n):
                state[tiles[i]] = bmps[i]
            if n:
                written_ticks.append(tick)
            slots = native.scd_background_tile_cycle(16 + era, tick, out)
            assert slots == len(retail['slots']), (letter, tick, slots)
            live = {}
            for s in range(slots):
                w = out[s]
                assert (w.cell, w.cells) == retail['slots'][s], (letter, tick, s)
                art = bytes(w.art[:w.cells * 32])
                assert art == retail['art'][w.frame][s][1], (letter, tick, s, 'native art is not retail frame art')
                for c in range(w.cells):
                    live[w.cell + c] = art[c * 32:c * 32 + 32]
            assert set(live) == set(state), (letter, tick, sorted(set(live) ^ set(state)))
            for tile, bmp in state.items():
                source = base + bmp * 32 - A.ORIGIN
                assert live[tile] == data[source:source + 32], (letter, tick, tile, bmp)
                tile_checks += 1
                cell_bytes += 32
            if prev_frame is not None and out[0].frame != prev_frame:
                assert written_ticks and written_ticks[-1] == tick, (letter, tick, 'native frame changed without an original write')
            if n and tick:
                assert out[0].frame != prev_frame, (letter, tick, 'original wrote but native frame held')
            prev_frame = out[0].frame
        assert written_ticks[0] == 0 and all(b - a == retail['period'] for a, b in zip(written_ticks, written_ticks[1:])), letter
        fires += len(written_ticks)
        eras[letter] = {'tile_cycles': len(retail['slots']), 'cells': [dict(cell=c, cells=n) for c, n in retail['slots']],
                        'period': retail['period'], 'frames': retail['frames'], 'original_fires': len(written_ticks),
                        'ticks': TICKS + 1}
    # COL3A-D are round-wide; tools/test_cc_palette.py proves the Act 1 ids
    # against the compiled originals. Act 2 must run the same cycles.
    palette_frames = 0
    base_colors = C.create_string_buffer(bytes(range(128)))
    a, b = (C.c_uint16 * 64)(), (C.c_uint16 * 64)()
    for era in range(4):
        changed = 0
        for frame in range(TICKS + 1):
            native.scd_background_palette(12 + era, frame, base_colors, a)
            native.scd_background_palette(16 + era, frame, base_colors, b)
            assert list(a) == list(b), ('ABCD'[era], frame)
            palette_frames += 1
            changed += frame > 0 and list(a) != list(prev)
            prev = list(a)
        # COL3B.C has no colchg3b: the Past palette is static in every act.
        assert bool(changed) == (era != 1), ('ABCD'[era], changed)
        if era >= 2:
            # Act 3 Good/Bad Future (ids 22/23) run the same round-wide cycles.
            for frame in range(TICKS + 1):
                native.scd_background_palette(12 + era, frame, base_colors, a)
                native.scd_background_palette(20 + era, frame, base_colors, b)
                assert list(a) == list(b), ('Act 3', 'ABCD'[era], frame)
                palette_frames += 1
    # Act 3: DEV33C/D.C hold only mapinittbl and retail UpdateAnimTiles is jmp.
    for letter in 'CD':
        dev = (ROOT / f'.deps/soniccd/src/R3/DEV33{letter}.C').read_text()
        assert not re.search(r'\b(?:cg_change|cg_chg1|ChangeTileBmp|tile_changes)\b', dev), letter
        assert A.routine(disc[f'R33{letter}__.MMD'])[1] is None, (letter, 'Act 3 retail has animated tiles')
        for tick in range(TICKS + 1):
            assert native.scd_background_tile_cycle(20 + 'ABCD'.index(letter), tick, out) == 0
        eras['R33' + letter] = {'tile_cycles': 0, 'ticks': TICKS + 1}
    paths = ['tools/test_cc_terrain.py', 'tools/cc2_terrain_assets.py', 'src/background.c', 'src/background.h',
             'assets/generated/cc2_terrain.inc'] + [f'.deps/soniccd/src/R3/DEV32{l}.C' for l in 'ABCD'] + [f'.deps/soniccd/src/R3/DEV33{l}.C' for l in 'CD']
    report = dict(run, passed=True, status='passed', eras=eras, tile_checks=tile_checks, cell_bytes=cell_bytes,
                  original_fires=fires, palette_frames=palette_frames,
                  inputs={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                  limits='Host comparison of compiled DEV32A-D.C cg_change with the native retail-extracted art; '
                         'Act 2 palette equals the Act 1 ids verified by test_cc_palette.py. Target VRAM and hardware are separate gates.')
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'CC2 terrain animation: {fires} original drum fires, {tile_checks} tile states ({cell_bytes} bytes) over '
          f'{TICKS + 1} ticks x 4 eras, {palette_frames} Act 2/3 palette frames pass; Act 3 C/D have no tile cycles')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / 'report.json'
    RUN = dict(passed=False, status='pending', started_utc=datetime.now(timezone.utc).isoformat())
    report_path.write_text(json.dumps(RUN, indent=2) + '\n')
    try:
        main(RUN)
    except BaseException as error:
        RUN.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                   error=f'{type(error).__name__}: {error}')
        report_path.write_text(json.dumps(RUN, indent=2) + '\n')
        raise
