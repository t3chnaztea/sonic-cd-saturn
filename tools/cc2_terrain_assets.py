#!/usr/bin/env python3
"""Extract Collision Chaos Act 2 drum tile cycles from the retail R32A-D MMDs.

Each retail UpdateAnimTiles routine (the one call made while the level is set
up, and again from VInt_Level every level vblank, including paused loops) has
this shape in R32A/C/D:

    jsr   LoadShieldArt-like helper
    subq.b #1,timer.w : bpl.w .rts
    move.b #reset,timer.w
    moveq #0,d0 : move.b frame.w,d0 : addq.b #1,d0 : cmpi.b #frames,d0
    bcs.s * : moveq #0,d0 : move.b d0,frame.w : lsl.w #3,d0
    movea.l table(pc,d0.w),a1 : movea.l table+4(pc,d0.w),a2
    bsr copy : LVLDMA buffer,cells0 : movea.l a2,a1 : bsr copy : LVLDMA buffer,cells1

R32B is `jmp` (no animated art). Nothing here is per-round: every value is
read from the routine and validated. The compiled-original DEV32A-D.C oracle
is a separate gate (tools/test_cc_terrain.py).
"""
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

ORIGIN = 0x200000
# Level/_Definitions.inc LVLDMA (same encoding as extract_zone_auto.LVLDMA).
LVLDMA = re.compile(rb'\x4b\xf9\x00\xc0\x00\x04\x2a\xbc\x94(.)\x93(.)\x2a\xbc\x96(.)\x95(.)'
                    rb'\x3a\xbc\x97(.)\x3a\xbc(..)\x31\xfc(..)(..)\x3a\xb8\8', re.S)
HEAD = re.compile(rb'\x4e\xb9(....)\x53\x38(..)\x6a\x00(..)\x11\xfc\x00(.)(..)\x70\x00\x10\x38(..)'
                  rb'\x52\x00\x0c\x00\x00(.)\x65\x02\x70\x00\x11\xc0(..)'
                  rb'\xe7\x48\x22\x7b\x00(.)\x24\x7b\x00(.)\x61(.)', re.S)
COPY = re.compile(rb'\x47\xf9(....)\x30\x3c(..)\x26\xd9\x51\xc8\xff\xfc\x4e\x75', re.S)


def routine(data):
    import extract_zone_auto as Z
    entry = Z.only('UpdateAnimTiles', [struct.unpack('>I', m[1])[0] for m in Z.ANIM_INIT_CALL.finditer(data)
                                       if m.start() % 2 == 0])
    start = entry - ORIGIN
    if data[start:start + 2] == b'\x4e\xf9':
        return entry, None
    head = HEAD.match(data, start)
    if not head:
        raise ValueError(f'UpdateAnimTiles at {entry:#x} is not the two-slot drum cycle shape')
    timer, frame_var = head[2], head[6]
    if head[5] != timer or head[8] != frame_var:
        raise ValueError('timer/frame variables disagree')
    reset, frames = head[4][0], head[7][0]
    # movea.l (d8,pc,d0.w): PC is the extension word's address.
    ext1 = head.start(9) - 1
    table = ORIGIN + ext1 + head[9][0]
    ext2 = head.start(10) - 1
    if ORIGIN + ext2 + head[10][0] != table + 4:
        raise ValueError('second art pointer is not table+4')
    copy_at = head.end() + struct.unpack('>b', head[11])[0]
    copy = COPY.match(data, copy_at)
    if not copy:
        raise ValueError('copy helper shape changed')
    buffer = struct.unpack('>I', copy[1])[0] & 0xFFFFFF
    copied = (struct.unpack('>H', copy[2])[0] + 1) * 4
    slots, at = [], head.end()
    for n in range(2):
        dma = LVLDMA.match(data, at)
        if not dma:
            raise ValueError(f'slot {n} DMA shape changed')
        size = (dma[1][0] << 8 | dma[2][0]) * 2
        source = (((dma[5][0] & 0x7F) << 16) | (dma[3][0] << 8) | dma[4][0]) * 2
        high, low = struct.unpack('>H', dma[6])[0], struct.unpack('>H', dma[7])[0]
        dest = (high & 0x3FFF) | ((low & 3) << 14)
        if high >> 14 != 1 or not low & 0x80 or source != buffer or dest % 32 or size % 32 or size > copied:
            raise ValueError(f'slot {n} is not a VRAM copy of the art buffer')
        slots.append((dest // 32, size // 32))
        at = dma.end()
        if n == 0:
            if data[at:at + 2] != b'\x22\x4a' or data[at + 2] != 0x61:
                raise ValueError('second slot does not copy from a2')
            if at + 4 + struct.unpack('>b', data[at + 3:at + 4])[0] != copy_at:
                raise ValueError('second slot calls another helper')
            at += 4
    if data[at:at + 2] != b'\x4e\x75':
        raise ValueError('routine does not end after two slots')
    art = []
    for f in range(frames):
        pointers = struct.unpack_from('>II', data, table - ORIGIN + f * 8)
        row = []
        for (cell, cells), pointer in zip(slots, pointers):
            if not ORIGIN <= pointer <= ORIGIN + len(data) - cells * 32:
                raise ValueError('art pointer outside the program')
            row.append((pointer, data[pointer - ORIGIN:pointer - ORIGIN + cells * 32]))
        art.append(row)
    return entry, dict(timer=0xFF0000 | struct.unpack('>H', timer)[0], frame_var=0xFF0000 | struct.unpack('>H', frame_var)[0],
                       reset=reset, period=reset + 1, frames=frames, table=table, buffer=buffer, slots=slots, art=art)


def main():
    import extract_zone_auto as Z
    from extract_mmd import disc_files
    iso = ROOT / 'build/retail/sonic.iso'
    disc = disc_files(Z.read_iso(iso))
    blob, rows, report = bytearray(), [], {'source': str(iso.relative_to(ROOT)), 'programs': {}}
    for letter in 'ABCD':
        data = disc[f'R32{letter}__.MMD']
        entry, r = routine(data)
        entry_report = {'mmd_sha256': hashlib.sha256(data).hexdigest(), 'UpdateAnimTiles': f'{entry:#x}'}
        if r is None:
            rows.append('{0,0,0,{0,0},{0,0},{{0,0},{0,0}}}')
            entry_report['cycle'] = None
        else:
            offsets = []
            for row in r['art']:
                offsets.append([len(blob) + sum(len(a) for _, a in row[:i]) for i in range(len(row))])
                for _, a in row:
                    blob += a
            rows.append('{%d,%d,%d,{%s},{%s},{%s}}' % (
                r['period'], r['frames'], len(r['slots']),
                ','.join(str(c) for c, _ in r['slots']), ','.join(str(n) for _, n in r['slots']),
                ','.join('{%s}' % ','.join(map(str, o)) for o in offsets)))
            entry_report['cycle'] = dict(
                timer=f"{r['timer']:#x}", frame=f"{r['frame_var']:#x}", period=r['period'], frames=r['frames'],
                table=f"{r['table']:#x}", buffer=f"{r['buffer']:#x}",
                slots=[{'cell': c, 'cells': n} for c, n in r['slots']],
                art=[[{'address': f'{p:#x}', 'sha256': hashlib.sha256(a).hexdigest()} for p, a in row] for row in r['art']])
        report['programs'][f'R32{letter}'] = entry_report
    text = ('/* Generated by tools/cc2_terrain_assets.py from the retail R32A-D UpdateAnimTiles routines. */\n'
            'typedef struct { uint8_t period, frames, slots; uint16_t cell[2], cells[2]; uint16_t art[2][2]; } cc2_tile_cycle;\n'
            f'static const uint8_t cc2_tile_art[{max(len(blob), 1)}] = {{' + ','.join(str(b) for b in blob or b'\0') + '};\n'
            'static const cc2_tile_cycle cc2_tile_cycles[4] = {' + ','.join(rows) + '};\n')
    target = ROOT / 'assets/generated/cc2_terrain.inc'
    target.parent.mkdir(parents=True, exist_ok=True)
    changed = not target.exists() or target.read_text() != text
    if changed:
        target.write_text(text)
    report['output_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    out = ROOT / 'build/cc2/terrain';out.mkdir(parents=True, exist_ok=True)
    (out / 'assets.json').write_text(json.dumps(report, indent=2) + '\n')
    cycles = sum(1 for p in report['programs'].values() if p['cycle'])
    print(f'CC2 drum tile cycles: {cycles} retail programs, {len(blob)} art bytes ({"updated" if changed else "unchanged"})')


if __name__ == '__main__':
    main()
