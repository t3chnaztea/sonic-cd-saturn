#!/usr/bin/env python3
"""Run the retail FMV programs in the Sega CD core and match them to fmv_stm.c.

Like level_title_retail.py, the IPX Backup RAM call is patched to a stub that
calls RunMMD with SCMD_OPENING, SCMD_GOODEND or SCMD_BADEND. The FMV Main and
Sub CPU programs, the CD file engine and the VDP are untouched. Every emulated
frame, the displayed VRAM tile buffer (picked from the plane A H-scroll word)
is looked up among the decoded STM frames, and the screen's picture area is
compared pixel for pixel with the host decoder's render of that frame, under
the core's RGB565 color mapping. Needs build/fmv/ from fmv_extract.py.

  python3 tools/fmv_retail.py ptest [--start-at N]   the pencil test (SCMD_PENCILTEST):
writes build/fmv/retail-ptest.json (every bank shown, its first frame, the
fade steps, whole-screen checks) and retail-ptest-timeline.json, the retail
reference tools/test_fmv_emulator.py compares the Saturn player with.
--start-at holds Start for 30 frames to show it does not end the movie.
"""
import argparse
import ctypes as C
import hashlib
import json
import struct
import subprocess

import special_retail as sr

OUT = sr.ROOT / 'build/fmv'
STREAMS = {'opening': ('OPN.STM', 'SCMD_OPENING', 'opening'),
           'goodend': ('GOODEND.STM', 'SCMD_GOODEND', 'ending'),
           'badend': ('BADEND.STM', 'SCMD_BADEND', 'ending')}
VIDEO_TILES, ANIM_TILES = 14336, 4800


def rgb565_to_md(p):
    """Invert the core's 3-bit to RGB565 expansion (normal intensity)."""
    return (((p >> 13) & 7) << 1) | (((p >> 8) & 7) << 5) | (((p >> 2) & 7) << 9)


def ipx_patches(scmd):
    """IPX Backup RAM call -> stub: RunMMD(scmd), then bra * (back in IPX)."""
    main_vars, _, _, commands = sr.layout()
    ipx = (sr.RETAIL / 'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    stub = struct.pack('>HHHIH', 0x303c, commands[scmd], 0x4eb9, run_mmd, 0x60fe)
    patches = [(bram, code[bram - origin:bram - origin + 8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at - origin:stub_at - origin + len(stub)], stub)]
    return patches, stub_at + len(stub) - 2


def md_pixel(md):
    """Mega Drive color word to the core's RGB565 pixel (normal intensity)."""
    r, g, b = ((md >> 1) & 7) << 1, ((md >> 5) & 7) << 1, ((md >> 9) & 7) << 1
    return r << 12 | (r >> 3) << 11 | g << 7 | (g >> 2) << 5 | b << 1 | b >> 3


def ptest(args):
    """PTEST.MMD (SCMD_PENCILTEST) in the core. Every frame: the bank on screen
    (plane A H-scroll flips once per bank, so shown = flips - 2; its VRAM buffer
    and CRAM line 0 are checked against PTEST.STM), CRAM line 1 (the border fade),
    and, the first time each bank shows, the whole screen against the decoded
    picture over PTEST.MMD's border (tools/fmv_convert.py ptest_program)."""
    import fmv_convert as fc
    stm = (OUT / 'PTEST.STM').read_bytes()
    prog = fc.ptest_program((OUT / 'PTEST.MMD').read_bytes())
    bank_bytes = 5 * 2048
    banks = len(stm) // bank_bytes
    pal = [struct.unpack_from('>16H', stm, k * bank_bytes + 16) for k in range(banks)]
    tiles = [stm[k * bank_bytes + 48:k * bank_bytes + 48 + 9408] for k in range(banks)]
    by_tiles = {}
    for k in range(banks):
        by_tiles.setdefault(tiles[k], []).append(k)
    skipped, repeats = [], []
    fade = [struct.unpack_from('>16H', prog['fade'], i * 32) for i in range(8)]
    border_map = struct.unpack('>1120H', prog['border_map'])
    art = prog['border_tiles']
    # Plane B as palette indices (40 x 28 names with flips), colored per CRAM line 1.
    border_idx = bytearray(320 * 224)
    for y in range(224):
        for x in range(320):
            w = border_map[(y >> 3) * 40 + (x >> 3)]
            tx = 7 - (x & 7) if w & 0x800 else x & 7
            ty = 7 - (y & 7) if w & 0x1000 else y & 7
            byte = art[((w & 0x7FF) - 0x3E8) * 32 + ty * 4 + (tx >> 1)]
            border_idx[y * 320 + x] = byte & 15 if tx & 1 else byte >> 4
    patches, halt = ipx_patches('SCMD_PENCILTEST')
    core = sr.Core()
    patched, after, end = False, 0, None
    flips, last_h, shown = 0, 0, -2
    timeline, bad_vram, bad_screen = [], [], []
    border_cache, checked = {}, set()
    pending = None   # (bank shown, CRAM line 1) that the next frame renders
    for frame in range(args.frames + 6000):
        start = args.start_at is not None and patched and args.start_at <= after < args.start_at + 30
        core.pad = 128 if start else 0
        core.run()
        core.host.chunks.clear()
        if not patched:
            if all(core.work_read(at, len(old)) == old for at, old, _ in patches):
                for at, _, new in patches:
                    core.work_write(at, new)
                patched = True
            continue
        after += 1
        if after > args.frames:
            break
        # The frame just rendered shows the state the previous frame's V-blank left.
        if pending and core.frame is not None and 0 <= pending[0] < banks and pending[0] not in checked:
            k, line1 = pending
            checked.add(k)
            width, height, data = core.frame
            if line1 not in border_cache:
                border_cache[line1] = [md_pixel(line1[i]) for i in border_idx]
            want = list(border_cache[line1])
            for y in range(112):
                row = (56 + y) * 320 + 72
                for x in range(168):
                    byte = tiles[k][((y >> 3) * 21 + (x >> 3)) * 32 + (y & 7) * 4 + ((x & 7) >> 1)]
                    i = byte & 15 if x & 1 else byte >> 4
                    if i:
                        want[row + x] = md_pixel(pal[k][i])
            ox, oy = (width - 320) // 2, (height - 224) // 2
            got = b''.join(data[((oy + y) * width + ox) * 2:((oy + y) * width + ox + 320) * 2] for y in range(224))
            if got != struct.pack('<71680H', *want):
                bad_screen.append(k)
        h = struct.unpack('>H', core.swapped(core.vram, 0xE400, 2))[0]
        buf = core.swapped(core.vram, 0x26C0 if h == 0x200 else 0x0200, 9408)
        cram = [(v & 7) << 1 | (v >> 3 & 7) << 5 | (v >> 6 & 7) << 9
                for v in struct.unpack('<64H', C.string_at(core.cram, 128))]
        line0, line1 = tuple(cram[0:16]), tuple(cram[16:32])
        if h != last_h:
            # A flip shows the next bank (tiles and line 0 both its own). When the
            # Sub CPU is late, PTEST.MMD reloads the bank it has into the other
            # buffer and shows it again; a bank the flip does not reach is skipped.
            flips += 1
            last_h = h
            if flips >= 2:
                same = lambda k: 0 <= k < banks and tiles[k] == buf and pal[k] == line0
                if same(shown + 1):
                    shown += 1
                elif same(shown):
                    repeats.append([after, shown])
                else:
                    hits = [k for k in by_tiles.get(buf, ()) if k > shown and pal[k] == line0]
                    if hits:
                        skipped.append([after, shown, hits[0]])
                        shown = hits[0]
                    else:
                        bad_vram.append([after, shown + 1])
                        shown += 1
            else:
                shown = -1
        if 0 <= shown < banks and buf != tiles[shown]:
            bad_vram.append([after, shown])
        step1 = [i for i in range(8) if fade[i][:5] + fade[i][6:] == line1[:5] + line1[6:]]
        step0 = [i for i in range(8) if fade[i] == line0]
        timeline.append({'f': after, 'shown': shown, 'line0_bank': 0 <= shown < banks and line0 == pal[shown],
                         'line0_step': step0[0] if step0 else None, 'line1_step': step1[0] if step1 else None,
                         'line1_c5': '%04x' % line1[5], 'pc': '%06x' % core.lib.m68k_get_reg(16)})
        pending = (shown, line1)
        if end is None and core.lib.m68k_get_reg(16) == halt:
            end = after
        if end is not None and after > end + 4:
            break
    first = {}
    for row in timeline:
        if row['shown'] >= 0 and row['shown'] not in first:
            first[row['shown']] = row['f']
    order = sorted(first)
    gaps = {}
    for a, b in zip(order, order[1:]):
        gaps[first[b] - first[a]] = gaps.get(first[b] - first[a], 0) + 1
    changes, prev = [], None
    for row in timeline:
        key = (row['line1_step'], row['line0_step'], row['line1_c5'])
        if key != prev:
            changes.append([row['f'], row['line1_step'], row['line0_step'], row['line1_c5']])
            prev = key
    bad_pal = [r['f'] for r in timeline if r['shown'] >= 0 and not r['line0_bank'] and r['line0_step'] is None]
    last = order[-1] if order else None
    report = {'stream': 'PTEST.STM', 'banks_in_file': banks, 'emulated_frames': after, 'end_frame': end,
              'pictures_shown': len(order), 'last_index': last,
              'first_shown_frame': first.get(0), 'last_shown_frame': first.get(last),
              'frames_between_pictures': {str(k): v for k, v in sorted(gaps.items())},
              'palette_changes': [c for c in changes if order and not (first[order[0]] + 8 < c[0] < first[last])],
              'vram_mismatch': bad_vram[:10], 'palette_mismatch_frames': bad_pal[:10],
              'screens_checked': len(checked), 'screen_mismatch': bad_screen[:10], 'start_at': args.start_at, 'banks_skipped': skipped, 'banks_repeated': repeats}
    # Fade step 1 shows 8 V-blanks after step 0; fade-out step 7 is line 0's first fade step.
    step1 = next((c[0] for c in changes if c[1] == 1), None)
    report['fade_step0_frame'] = step1 - 8 if step1 else None
    report['fade_out_step7_frame'] = next((r['f'] for r in timeline if r['line0_step'] == 7 and r['f'] > first.get(last, 0)), None)
    report['picture_frames'] = [first[k] for k in order]
    report['inputs'] = {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in
                        (('PTEST.STM', OUT / 'PTEST.STM'), ('PTEST.MMD', OUT / 'PTEST.MMD'),
                         ('fmv_retail.py', sr.ROOT / 'tools/fmv_retail.py'))}
    tag = '-start' if args.start_at is not None else ''
    (OUT / f'retail-ptest{tag}.json').write_text(json.dumps(report, indent=1) + '\n')
    (OUT / f'retail-ptest{tag}-timeline.json').write_text(json.dumps(timeline) + '\n')
    print(json.dumps(report))
    ok = (len(order) > 0 and not bad_vram and not bad_screen
          and not bad_pal and end is not None and checked == set(order))
    print(f'{"PASS" if ok else "FAIL"}: fmv_retail ptest')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stream', choices=list(STREAMS) + ['ptest'])
    ap.add_argument('--frames', type=int, default=1800, help='emulated frames after the stub runs')
    ap.add_argument('--start-at', type=int, help='ptest: hold Start for 30 frames from this frame after the stub')
    args = ap.parse_args()
    if args.stream == 'ptest':
        return ptest(args)
    name, scmd, kind = STREAMS[args.stream]
    exe = OUT / 'fmv_stm_host'
    stm = (OUT / name).read_bytes()
    import fmv_extract as fx
    model = fx.packets(stm, kind)
    by_tiles = {}
    for c, (k, gfx, n) in enumerate(model):
        for i in range(n):
            if k == 'video':
                at = gfx + i * fx.FRAME
                by_tiles.setdefault(stm[at + 32:at + 32 + VIDEO_TILES], (c, i, k))
            elif k == 'anim':
                at = gfx + i * fx.ANIM_FRAME
                by_tiles.setdefault(stm[at + 32:at + 32 + ANIM_TILES], (c, i, k))

    patches, _ = ipx_patches(scmd)

    core = sr.Core()
    patched, after = False, 0
    seen, screen_ok, screen_bad, unmatched = {}, 0, 0, 0
    renders = {}
    for frame in range(args.frames + 6000):
        core.pad = 0
        core.run()
        core.host.chunks.clear()
        if not patched:
            if all(core.work_read(at, len(old)) == old for at, old, _ in patches):
                for at, _, new in patches:
                    core.work_write(at, new)
                patched = True
            continue
        after += 1
        if after > args.frames:
            break
        hscroll = struct.unpack('>H', core.swapped(core.vram, 0xE400, 2))[0]
        buf = 0x3A00 if hscroll == 0x200 else 0x0200
        hit = by_tiles.get(core.swapped(core.vram, buf, VIDEO_TILES))
        if hit is None:
            hit = by_tiles.get(core.swapped(core.vram, 0x0200, ANIM_TILES))
            if hit and hit[2] != 'anim':
                hit = None
        if hit is None:
            unmatched += 1
            continue
        c, i, k = hit
        seen[(c, i)] = seen.get((c, i), 0) + 1
        if core.frame is None or (c, i) in renders:
            continue
        ppm = OUT / 'retail.ppm'
        subprocess.run([str(exe), 'ppm', str(OUT / name), kind, str(c), str(i), str(ppm)], check=True)
        head, body = ppm.read_bytes().split(b'\n', 3)[1:3], ppm.read_bytes().split(b'\n', 3)[3]
        w, h = map(int, head[0].split())
        width, height, data = core.frame
        # Picture origin: plane A column 4, row 6 (DrawFMVTilemaps, ENDING.MMD map).
        ox, oy = 32 + (width - 320) // 2, 48 + (height - 224) // 2
        good = True
        levels = fx.MD_LEVELS
        for y in range(h):
            for x in range(w):
                p = struct.unpack_from('<H', data, ((oy + y) * width + ox + x) * 2)[0]
                md = rgb565_to_md(p)
                r, g, b = body[(y * w + x) * 3:(y * w + x) * 3 + 3]
                if (levels[(md >> 1) & 7], levels[(md >> 5) & 7], levels[(md >> 9) & 7]) != (r, g, b):
                    good = False
                    break
            if not good:
                break
        renders[(c, i)] = good
        screen_ok += good
        screen_bad += not good
    (OUT / 'retail.ppm').unlink(missing_ok=True)
    kinds = {}
    for (c, i) in seen:
        kinds[model[c][0]] = kinds.get(model[c][0], 0) + 1
    report = {'stream': name, 'emulated_frames': after, 'distinct_frames_matched': len(seen),
              'by_packet_type': kinds, 'frames_without_match': unmatched,
              'screen_exact': screen_ok, 'screen_mismatch': screen_bad,
              'first': min(seen) if seen else None, 'last': max(seen) if seen else None,
              'mismatched_frames': [list(k) for k, v in renders.items() if not v][:10]}
    (OUT / f'retail-{args.stream}.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report))
    ok = seen and screen_bad == 0
    print(f'{"PASS" if ok else "FAIL"}: fmv_retail {args.stream}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
