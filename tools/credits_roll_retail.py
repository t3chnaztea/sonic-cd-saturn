#!/usr/bin/env python3
"""Run the retail ending (ENDING.MMD with GOODEND.STM or BADEND.STM; IPX.asm GameDone
RunMMD(SCMD_GOODEND/SCMD_BADEND), IPX.asm:312-326) in the pinned Sega CD core and record
the staff roll and the end screen. 'opening' runs OPEN_M.MMD with OPN.STM (SCMD_OPENING)
for the opening's picture times.

QA oracle only. Patches IPX like tools/fmv_retail.py (Backup RAM call -> RunMMD stub)
and sets endingID ($7F good, 0 bad) before the call. Per emulated frame it records the
picture CRC and that of its right half (x 160-319, where the roll scrolls), the plane B
name table (the roll and the end screen), the plane B V-scroll, the CRAM and the VRAM
tiles the SR packet loads; it stops when the program returns or after --frames.

  credits_roll_retail.py good|bad [--jp] [--frames N] [--png FRAME ...]
Writes build/credits/roll/<good|bad>[-jp].jsonl and -blobs.json (buffers by CRC).

--jp: the Saturn disc carries the Japanese movies (tools/fmv_extract.py takes ENDING.MMD,
GOODEND.STM and BADEND.STM from the Japanese disc; JAPANESE-MUSIC.md), and the core has
only the US Sega CD BIOS. So this builds a local test disc, never shared: the user's US
disc (its system area and every other file, build/retail/sonic.iso) with those three
files from the Japanese disc as tools/fmv_extract.py wrote them to build/fmv/, at
build/credits/roll/jp-disc/. The US IPX then runs the Japanese ending program.
"""
import argparse, hashlib, json, shutil, struct, subprocess, sys, zlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import special_retail as sr
OUT = ROOT / 'build/credits/roll'
JP_FILES = ('ENDING.MMD', 'GOODEND.STM', 'BADEND.STM', 'OPN.STM')
JP_DISC_FILES = ('OPEN_M.MMD', 'OPEN_S.BIN')   # the opening's programs, from the Japanese disc


def jp_disc():
    """The hybrid test disc; rebuilt when an input changes."""
    from extract_mmd import disc_files, ISO
    out = OUT / 'jp-disc'
    region = json.loads((ROOT / 'build/fmv/manifest.json').read_text()).get('region')
    if region != 'J':
        raise SystemExit(f'credits_roll_retail: build/fmv holds region {region} movies; '
                         'run tools/fmv_extract.py (the Japanese disc)')
    iso = ISO.read_bytes()
    jp = {name: (ROOT / 'build/fmv' / name).read_bytes() for name in JP_FILES}
    import fmv_extract
    jp_iso = disc_files(fmv_extract.cue_data_track(fmv_extract.JAPAN_CUE))
    jp.update({name: jp_iso[name] for name in JP_DISC_FILES})
    key = hashlib.sha256(hashlib.sha256(iso).digest() + b''.join(hashlib.sha256(d).digest() for d in jp.values())).hexdigest()
    if (out / 'key').exists() and (out / 'key').read_text() == key:
        return out
    shutil.rmtree(out, ignore_errors=True)
    tree = out / 'tree'
    tree.mkdir(parents=True)
    for name, data in disc_files(iso).items():
        (tree / name).write_bytes(jp.get(name, data))
    (out / 'sysarea.bin').write_bytes(iso[:16 * 2048])
    command = ['xorrisofs', '-quiet', '-iso-level', '1', '-V', 'SONIC_CD', '-G', str(out / 'sysarea.bin'),
               '-o', str(out / 'sonic.iso'), str(tree)]
    subprocess.run(command, check=True)
    shutil.rmtree(tree)
    (out / 'sonic.cue').write_text('FILE "sonic.iso" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n')
    shutil.copy(sr.RETAIL / 'IPX___.MMD', out / 'IPX___.MMD')
    (out / 'key').write_text(key)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ending', choices=['good', 'bad', 'opening'],
                    help='opening: OPEN_M.MMD with OPN.STM (IPX.asm SCMD_OPENING), for its picture times')
    ap.add_argument('--jp', action='store_true', help="the Japanese ending files (the Saturn disc's)")
    ap.add_argument('--frames', type=int, default=30000)
    ap.add_argument('--png', type=int, action='append', default=[])
    ap.add_argument('--press', type=int, help='hold Start 4 frames from this program frame')
    ap.add_argument('--card-press', type=int, help='hold Start 4 frames once the "PRESENTED BY SEGA" card has '
                    'held this many V-blanks')
    args = ap.parse_args()
    tag = args.ending + ('-jp' if args.jp else '')
    if args.jp:
        sr.RETAIL = jp_disc()
    main_vars, _, _, commands = sr.layout()
    ipx = (sr.RETAIL / 'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    good = args.ending == 'good'
    # move.b #endingID,endingID; move.w #SCMD,d0; jsr RunMMD; bra *
    stub = struct.pack('>HHI', 0x13fc, 0x7f if good else 0, main_vars['endingID'])
    scmd = 'SCMD_OPENING' if args.ending == 'opening' else 'SCMD_GOODEND' if good else 'SCMD_BADEND'
    stub += struct.pack('>HHHIH', 0x303c, commands[scmd], 0x4eb9, run_mmd, 0x60fe)
    halt = stub_at + len(stub) - 2
    patches = [(bram, code[bram - origin:bram - origin + 8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at - origin:stub_at - origin + len(stub)], stub)]
    core = sr.Core()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, blobs, patched, frame, begun, halted, card_start = [], {}, False, 0, None, 0, None

    def blob(data):
        key = '%08x' % zlib.crc32(data)
        blobs.setdefault(key, data.hex())
        return key
    while frame < args.frames + 3000 and halted < 30:
        t = frame - begun if begun is not None else -1
        if card_start is None and begun is not None and 0xFFC100 <= core.lib.m68k_get_reg(16) < 0xFFD000:
            card_start = t
            # The card routine ($FFC100): 2 V-blanks in, its fade out ends 22 later,
            # 5 more load it, and its fade in takes 24: the hold starts 53 V-blanks after.
            if args.card_press is not None:
                args.press = card_start + 53 + args.card_press
        core.pad = 0x80 if args.press is not None and 0 <= t - args.press < 4 else 0
        core.run()
        frame += 1
        core.host.chunks.clear()
        if not patched:
            if all(core.work_read(at, len(old)) == old for at, old, _ in patches):
                for at, _, new in patches:
                    core.work_write(at, new)
                patched = True
            continue
        if begun is None:
            begun = frame
        t = frame - begun
        if t >= args.frames:
            break
        reg = sr.C.string_at(core.reg, 24)
        cram = [(v >> 6 & 7) << 9 | (v >> 3 & 7) << 5 | (v & 7) << 1 for v in struct.unpack('<64H', sr.C.string_at(core.cram, 128))]
        width, height, pixels = core.frame or (0, 0, b'')
        right = b''.join(pixels[(y * width + 160) * 2:(y * width + 320) * 2] for y in range(height)) if width == 320 else b''
        rows.append({'frame': t, 'width': width, 'height': height, 'pixels': '%08x' % zlib.crc32(pixels),
                     'right': '%08x' % zlib.crc32(right),
                     'reg': reg.hex(), 'vsram': sr.C.string_at(core.vsram, 4).hex(),
                     'plane_a': '%08x' % zlib.crc32(core.swapped(core.vram, (reg[2] & 0x38) << 10, 0x1000)),
                     'plane_b': blob(core.swapped(core.vram, (reg[4] & 7) << 13, 0x1000)),
                     'cram': blob(struct.pack('>64H', *cram)), 'pc': core.lib.m68k_get_reg(16),
                     # Main/Sub flags ($A1200E) and the Sub CPU PC: the stream's end.
                     'comm': core.ga(0xA1200E), 'spc': core.lib.s68k_get_reg(16),
                     # The Main CPU polls the Sub CPU's packet flag (btst #0,$A1200F): its
                     # loop (fades, pictures) waits for the handover.
                     'sub_wait': b'\x08\x39\x00\x00\x00\xa1\x20\x0f' in core.work_read(core.lib.m68k_get_reg(16) - 8, 24)
                     if core.lib.m68k_get_reg(16) >= 0xFF0008 else False,
                     # The SR packet's 720 tiles (the roll text) at VRAM $14C0.
                     'text_tiles': '%08x' % zlib.crc32(core.swapped(core.vram, 0x14C0, 720 * 32)),
                     # The "08" picture shown: its 448 tiles at the buffer plane A's H-scroll
                     # picks (tools/fmv_retail.py), for the opening's picture times.
                     'video_tiles': '%08x' % zlib.crc32(core.swapped(
                         core.vram, 0x3A00 if struct.unpack('>H', core.swapped(core.vram, 0xE400, 2))[0] == 0x200 else 0x0200,
                         14336))})
        if t in args.png and core.frame:
            sr.png(OUT / f'{tag}-{t}.png', core.frame)
        halted = halted + 1 if core.lib.m68k_get_reg(16) == halt else 0
    (OUT / f'{tag}.jsonl').write_text(''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in rows))
    (OUT / f'{tag}-blobs.json').write_text(json.dumps(blobs))
    print(json.dumps({'ending': tag, 'frames': len(rows), 'returned': halted >= 30, 'card_start': card_start,
                      'plane_b_states': len({r['plane_b'] for r in rows})}))


if __name__ == '__main__':
    main()
