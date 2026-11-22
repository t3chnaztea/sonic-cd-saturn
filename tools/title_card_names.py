#!/usr/bin/env python3
"""Per-zone title card name art from the retail programs (cd/TCN<round>.BIN).

_Objects/Title Card/Main.asm draws nine MapSpr_TitleCard frames from tiles $360
(common art, PLC 1 entry at VRAM $6C00) and $3D0 (the zone's text art, the next
PLC 1 entry at $7A00). Frames 0-6 are the same in every round; frames 7 and 8
are the two words of the zone name, and ObjTitleCard_Data moves pieces 1-4 in
R6 and piece 4 in R8. tools/convert_objects.py builds the resident card from the
Palmtree Panic disassembly; this tool reads each round's own frames 7/8 and
ObjTitleCard_Data from all of its programs (they must agree) and writes, per
round: the 8x4 data words, then for frames 7 and 8 width, height, left, top,
then both textures (4-bit indices + 16-colour CLUT, as convert_objects.py).
src/main.c title_card_name_load() reads the file on a zone change.
"""
import re
import struct
import sys

from convert_assets import ROOT, OUT, DATA, nemesis, palette
from convert_objects import draw
from extract_mmd import disc_files
from test_objects import unpack_texture

ORIGIN = 0x200000
ROUNDS = (1, 3, 4, 5, 6, 7, 8)  # native zone index -> retail round
SLOTS = (2944, 3168)  # VDP1 bytes reserved for frames 7 and 8 (tools/convert_objects.py)


def plc1_text(p):
    tables = {struct.unpack_from('>I', p, m.start() + 6)[0] - ORIGIN
              for m in re.finditer(bytes.fromhex('48e7006043f9'), p)}  # LoadPLC: lea PLCLists,a1
    assert len(tables) == 1
    t = tables.pop()
    plc = t + struct.unpack_from('>H', p, t + 2)[0]
    ents = [struct.unpack_from('>IH', p, plc + 2 + 6 * i) for i in range(struct.unpack_from('>h', p, plc)[0] + 1)]
    pairs = [(ents[i - 1][0] - ORIGIN, a - ORIGIN) for i, (a, v) in enumerate(ents) if v == 0x7a00 and i and ents[i - 1][1] == 0x6c00]
    assert len(pairs) == 1, pairs
    return pairs[0]


def card_code(p):
    """ObjTitleCard_Init's move.l #MapSpr_TitleCard,oMap(a1) and the lea ObjTitleCard_Data before it."""
    hits = []
    for m in re.finditer(b'\x23\x7c', p):
        s = m.start()
        if s % 2 or s + 8 > len(p) or p[s + 6:s + 8] != b'\x00\x04':
            continue
        a = struct.unpack_from('>I', p, s + 2)[0] - ORIGIN
        if 0 <= a < len(p) - 0x14 and struct.unpack_from('>H', p, a)[0] == 0x12 and p[a + 0x12:a + 0x14] == b'\x06\x90':
            k = p.find(bytes.fromhex('72007c0745f9'), s - 100, s)  # moveq #0,d1; moveq #7,d6; lea ObjTitleCard_Data,a2
            if k >= 0:
                hits.append((a, struct.unpack_from('>I', p, k + 6)[0] - ORIGIN))
    assert len(set(hits)) == 1, hits
    return hits[0]


def frame(p, sheet, maps, k, colors):
    o = maps + struct.unpack_from('>H', p, maps + 2 * k)[0]
    mapping = bytes(p[o:o + 1 + 5 * p[o]])
    xs = []; ys = []
    for j in range(mapping[0]):
        y, size, hi, lo, x = mapping[1 + j * 5:6 + j * 5]
        x = x - 256 if x > 127 else x; y = y - 256 if y > 127 else y
        xs += [x, x + (((size >> 2) & 3) + 1) * 8]; ys += [y, y + ((size & 3) + 1) * 8]
    left, top = min(xs), min(ys); width, height = max(xs) - left, max(ys) - top
    width = (width + 7) & ~7  # VDP1 character widths are multiples of 8 (pad on the right)
    shifted = bytearray(mapping)
    for j in range(mapping[0]):
        shifted[5 + j * 5] = (shifted[5 + j * 5] - left - width // 2) & 255
    pixels = draw(bytes(shifted), sheet, colors, width, -top - 32, height)
    clut = [0]; indices = []
    for value, in struct.iter_unpack('>H', pixels):
        if value not in clut:
            clut.append(value)
        indices.append(clut.index(value))
    assert len(clut) <= 16
    data = bytes((indices[i] << 4) | indices[i + 1] for i in range(0, len(indices), 2)) + struct.pack('>16H', *(clut + [0] * (16 - len(clut))))
    assert len(data) <= SLOTS[k - 7], (k, width, height)
    return (width, height, left, top), data


def program_card(p, colors):
    common, text = plc1_text(p)
    maps, table = card_code(p)
    sheet = nemesis(p[common:]).ljust(0x70 * 32, b'\0') + nemesis(p[text:])
    names = [frame(p, sheet, maps, k, colors) for k in (7, 8)]
    return bytes(p[table:table + 64]), names


def main():
    files = disc_files((ROOT / 'build/retail/sonic.iso').read_bytes())
    colors = palette((DATA / '_Objects/Sonic/Data/Palette.bin').read_bytes())
    meta = (OUT / 'title-card.inc').read_text().split('title_card_frames', 1)[1]
    layout = [tuple(map(int, row.split(','))) for row in re.findall(r'\{([\d,-]+)\}', meta)]
    resident = unpack_texture((OUT / 'title-card-art.bin').read_bytes())
    rows = []
    for zone, r in enumerate(ROUNDS):
        seen = {}
        for n in sorted(files):
            if re.fullmatch(rf'R{r}[123][ABCD]__\.MMD', n):
                table, names = program_card(files[n], colors)
                seen.setdefault((table, tuple((d, x) for d, x in names)), []).append(n)
        assert len(seen) == 1, (r, [v for v in seen.values()])
        (table, names), programs = next(iter(seen.items()))
        if r == 1:
            # The retail R1 names must equal the disassembly frames the resident card carries.
            for k, (dims, data) in zip((7, 8), names):
                off, w, h, left, top = layout[k]
                assert (w, h, left, top) == dims and resident[off:off + len(data)] == data, ('R1 frame', k)
        out = table + b''.join(struct.pack('>HHhh', *dims) for dims, _ in names) + b''.join(data for _, data in names)
        (OUT / f'title-card-name-{r}.bin').write_bytes(out)
        rows.append(f'    STAGE_ZONE_PACK(PACK_CARD_NAME,{zone},0,"TCN{r}.BIN","assets/generated/title-card-name-{r}.bin")')
        print(f'R{r}: {len(programs)} programs agree; name frames {names[0][0][:2]} {names[1][0][:2]}; {len(out)} bytes')
    # Read by tools/stage_packs.py only: src/main.c stage_pack_file() names TCN<round>.BIN itself.
    (OUT / 'title-card-names.h').write_text('/* Generated by tools/title_card_names.py. */\n#define TITLE_CARD_NAME_PACKS \\\n' + ' \\\n'.join(rows) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
