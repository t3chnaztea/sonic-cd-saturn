#!/usr/bin/env python3
"""Extract any round's stage data from its retail MMD programs with no
disassembly input at all.

tools/extract_mmd.py and tools/extract_zone.py both start from a template
program in which every structure is found by searching for a data file of the
pinned disassembly, then relocate those labels into the other nine programs
through the `lea label,aN` code around them. That needs a per-zone disassembly
folder, and only Palmtree Panic and Wacky Workbench have one.

This tool finds every structure in every program on its own, from the shape of
the structure itself. It reads nothing but the retail disc. The PC
reconstruction tables are used only to check the result, never to find it.

How each structure is found
---------------------------
LevelDataIndex
    A 16-byte record `dc.l tiles|$3000000, blocks|$2000000, $210000` followed
    by `dc.w $0081`. The chunk array is at the fixed address $210000 in every
    program, and the two high bytes are the VDP transfer tags, so the record
    matches a fixed 14-byte mask with two free longs. Several byte sequences in
    compressed art match it by accident; the real one is the only candidate
    whose own address appears in the program as an absolute long, because the
    engine loads it with `lea`. Unique in all 70 programs.

PaletteTable
    Rows of `dc.l colors : dc.w destination, count-1`. Entries 0-2 are the
    64-colour level sets staged at $FB00 and entry 3 is Sonic's 8-long palette
    at the same destination, so four consecutive rows match
    `(long, $FB00, $001F) x3, (long, $FB00, $0007)`. That is one hit in all 70
    programs. Sonic is entry 3; the level entry's index is the byte at
    LevelDataIndex+15, which is 5 in Palmtree Panic and 4 in Wacky Workbench.

The shared collision maps and LevelColIndex
    Angles (256 bytes), Height Map (4096) and Width Map (4096) are engine-wide
    data, byte identical in all 70 programs, and are laid out contiguously
    immediately before the level's own collision index. The block is located
    once, bootstrapped from the disc itself: in a program whose LevelColIndex
    is a run of eight identical pointers, that pointer is the end of the block,
    so the 8448 bytes before it are the maps. The block is then required to
    occur exactly once in every program, and the level collision index starts
    where it ends. Round 4 writes its collision pointer as a single immediate
    instead of a pointer table, which is why the block, not the pointer table,
    is the anchor.

LevelLayouts
    A table of word offsets whose first entry is the table's own size, so the
    first plane starts where the table ends. Each plane is `dc.b width-1,
    height-1` then the chunk grid, and the distinct offsets, in order, chain:
    the next one is where the previous plane ends, rounded up to a word. The
    table's address is loaded with `lea`, so it appears in the program as an
    absolute long. Four programs also match this shape on a two-entry decoy
    inside code; the level table is separated from the decoys by sitting at the
    end of the collision index, whose unused tail is zero, so a candidate must
    have zero bytes immediately before it. One hit in all 70 programs.

ObjectLayouts
    `dc.w Layout-ObjectLayouts` (always 12), `dc.w End-ObjectLayouts`, an empty
    8-byte record `$FFFF,0,0,0`, then the layout: 8-byte records ending in one
    whose X is $FFFF and with no $FFFF before it. One hit in all 70 programs.

LevelStartLoc and SpecChunks
    `dc.w x, y` then four chunk ids. Both labels are loaded with `lea`, so both
    addresses appear as absolute longs; the start position must be inside the
    foreground plane; and the `lea SpecChunks,a1` that ends the loader sits
    twelve bytes before the record. One hit in all 70 programs.

UpdateAnimTiles
    Some levels keep numbered placeholder cells in their tile art where the
    engine streams animated art, and draw those cells in the planes (the fires
    on the Tidal Tempest mountains, the Metallic Madness pistons). The engine
    fills them before the first frame is shown: Level/Main.asm:202-208 clears
    aniArtFrames and aniArtTimers with the misc variables, and Main.asm:310-312
    then runs `move.w #$202F,palFadeInfo.w : jsr UpdateAnimTiles`, which is one
    hit in all 70 programs. The routine is `jmp LoadShieldArt` where a level
    has no animated art. Otherwise each slot in it is `lea AniArt,a1 : move.w
    #size/4-1,d6 : bsr.w AnimateTiles : bne.s : LVLDMA aniArtBuffer,dest,size`,
    the shape of Level/Wacky Workbench/Animated Tiles Update (Act 1
    Present).asm. With the timer at zero the first call advances every slot to
    frame 1 (Animate Tiles (Simple).asm:27-38, Animate Tiles (Scripted).asm:
    26-46), and that frame's art is written over the cells the DMA targets. The
    PC port does the same: game_init zeroes cgchgcnt and cgchgtim and calls
    cg_change (R4/GAME4.C:453-454, 674-676), whose cg_chg1 moves each table to
    index 1 on its first call (R4/DEV41A.C:285-300). Slots whose DMA is behind
    a further condition do not have this shape and are reported, not applied.

Everything is found independently in each program: there is no template
program, no relocation, and no per-round table or branch anywhere below.
"""
import argparse
import collections
import difflib
import hashlib
import json
import re
import struct
from pathlib import Path

from convert_assets import ROOT, nemesis, palette, layout
from extract_mmd import ORIGIN, disc_files

SIZE = 0x40000                     # the MMD programs are 256 KiB at ORIGIN
CHUNKS = ORIGIN + 0x10000          # the chunk array is always at $210000
ANGLES, HEIGHT_MAP, WIDTH_MAP = 256, 4096, 4096
MAPS = ANGLES + HEIGHT_MAP + WIDTH_MAP
# zone1scd is dc.b[1000] in every PC round but R7, where it is dc.b[1100].
MAX_COLLISION = 1100
# The collision index's unused tail is zero, so LevelLayouts always follows a
# run of zero bytes. Decoys elsewhere in the program have at most one.
MIN_TAIL_ZEROS = 4
# `lea SpecChunks,a1 : move.l (a1),($F7AC).w : rts` ends at LevelStartLoc.
MAX_START_LEA = 16
ROUNDS = [1, 3, 4, 5, 6, 7, 8]
# Level/_Definitions.inc:353 LVLDMA: VDP DMA length, source, then the command
# words, the low one through dmaCmdLow.w.
LVLDMA = (rb'\x4b\xf9\x00\xc0\x00\x04\x2a\xbc\x94(.)\x93(.)\x2a\xbc\x96(.)\x95(.)'
          rb'\x3a\xbc\x97(.)\x3a\xbc(..)\x31\xfc(..)(..)\x3a\xb8\8')
# Level/Main.asm:310-312, the one call made while the level is set up.
ANIM_INIT_CALL = re.compile(rb'\x31\xfc\x20\x2f..\x4e\xb9(....)', re.S)
# lea AniArt,a1 : move.w #n,d6 : bsr.w AnimateTiles, then bne.s : LVLDMA.
ANIM_CALL = re.compile(rb'\x43\xf9(....)\x3c\x3c(..)\x61\x00(..)', re.S)
ANIM_SLOT = re.compile(rb'\x66.' + LVLDMA, re.S)
# The two frame helpers, from their first instructions up to the frame compare.
ANIM_SIMPLE = re.compile(rb'\x53\x12\x6a\x00..\x14\x91\x70\x00\x10\x14\x52\x00\xb0\x29\x00\x01', re.S)
ANIM_SCRIPT = re.compile(rb'\x53\x12\x6a[^\x00]\x70\x00\x10\x14\x52\x00\xb0\x11', re.S)
# lea aniArtBuffer,a3 inside a helper, which is where the frame is staged.
ANIM_BUFFER = re.compile(rb'\x47\xf9(....)', re.S)
MANIFEST = ROOT / 'build/all-zones-extract.json'
ACTS = [(1, 'A'), (1, 'B'), (1, 'C'), (1, 'D'),
        (2, 'A'), (2, 'B'), (2, 'C'), (2, 'D'), (3, 'C'), (3, 'D')]


# The extractor and the helpers whose code shapes the packs. Each round's
# report.json records their digests; tools/install_zone_packs.py re-extracts a
# round whose recorded digests or retail programs differ from the current ones.
TOOLS = ('tools/extract_zone_auto.py', 'tools/convert_assets.py', 'tools/extract_mmd.py')


def tool_hashes():
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in TOOLS}


def programs_of(round_number):
    return [f'R{round_number}{act}{era}' for act, era in ACTS]


def word(data, address):
    return struct.unpack_from('>H', data, address - ORIGIN)[0]


def long(data, address):
    return struct.unpack_from('>I', data, address - ORIGIN)[0]


def at(data, address, size):
    return data[address - ORIGIN:address - ORIGIN + size]


def only(name, candidates, log=None):
    """The one address a locator resolved to, or a loud failure.

    Every locator goes through here, so a structure that is not unique stops
    the extraction instead of being guessed at. The candidate count is recorded
    for the report.
    """
    values = sorted(set(candidates))
    if log is not None:
        log[name] = len(values)
    if len(values) != 1:
        raise ValueError(f'{name}: {len(values)} candidates {[hex(v) for v in values]}')
    return values[0]


def absolute_longs(data):
    """Every in-program address the program stores as an aligned long."""
    counts = collections.Counter()
    for i in range(0, len(data) - 4, 2):
        value = struct.unpack_from('>I', data, i)[0]
        if ORIGIN <= value < ORIGIN + SIZE:
            counts[value] += 1
    return counts


def lea_sites(data):
    """address -> the `lea <abs>.l,An` instructions that load it."""
    sites = collections.defaultdict(list)
    for i in range(0, len(data) - 6, 2):
        if (struct.unpack_from('>H', data, i)[0] & 0xF1FF) == 0x41F9:
            value = struct.unpack_from('>I', data, i + 2)[0]
            if ORIGIN <= value < ORIGIN + SIZE:
                sites[value].append(ORIGIN + i)
    return sites


def data_index(data, longs, log=None):
    """LevelDataIndex: the record shape, kept to the one the engine loads."""
    found = [ORIGIN + m.start()
             for m in re.finditer(rb'\x03(...)\x02(...)\x00\x21\x00\x00\x00\x81', data, re.S)
             if m.start() % 2 == 0]
    if log is not None:
        log['LevelDataIndex shape'] = len(set(found))
    return only('LevelDataIndex', [a for a in found if longs[a]], log)


def palette_table(data, log=None):
    """PaletteTable: level entries 0-2 then Sonic in entry 3, all at $FB00."""
    rows = rb'(....)\xfb\x00\x00\x1f(....)\xfb\x00\x00\x1f(....)\xfb\x00\x00\x1f(....)\xfb\x00\x00\x07'
    return only('PaletteTable', [ORIGIN + m.start() for m in re.finditer(rows, data, re.S)
                                 if m.start() % 2 == 0], log)


def plane_fits(data, offset, allocated):
    """A level plane is `width-1, height-1` then the grid the table makes room
    for; short rows are how a few levels store a trailing unused row."""
    if offset + 2 > len(data):
        return None
    width, height = data[offset] + 1, data[offset + 1] + 1
    if width > 64 or height > 8 or allocated < 3:
        return None
    rows = min(height, (allocated - 2) // width)
    if rows < 1 or (allocated - 2) - rows * width > 1:
        return None
    return width, rows


def layout_entries(data, address):
    """The LevelLayouts offset table at `address`, or None."""
    i = address - ORIGIN
    if i < 0 or i + 4 > len(data):
        return None
    size = struct.unpack_from('>H', data, i)[0]
    if size < 4 or size > 0x200 or size % 2 or i + size > len(data):
        return None
    entries = struct.unpack_from(f'>{size // 2}H', data, i)
    if entries[0] != size or any(e < size or e > 0x4000 for e in entries):
        return None
    offsets = sorted(set(entries))
    if len(offsets) < 2:
        return None
    for a, b in zip(offsets, offsets[1:]):
        if plane_fits(data, i + a, b - a) is None:
            return None
    # The background is entry 1, which in a two-entry table is also the last
    # offset and so has no following entry to size it; check its header alone.
    background = i + entries[1]
    if background + 2 > len(data) or data[background] + 1 > 64 or data[background + 1] + 1 > 8:
        return None
    return entries


def level_layouts(data, longs, log=None):
    """LevelLayouts: the table shape, loaded with lea, after the zero tail of
    the collision index."""
    found = [a for a in sorted(longs) if a % 2 == 0 and layout_entries(data, a)]
    if log is not None:
        log['LevelLayouts shape'] = len(set(found))
    if len(found) > 1:
        found = [a for a in found
                 if data[a - ORIGIN - MIN_TAIL_ZEROS:a - ORIGIN] == bytes(MIN_TAIL_ZEROS)]
    return only('LevelLayouts', found, log)


def planes(data, layouts):
    """The foreground and background planes, each clipped to the space the
    layout table gives it."""
    entries = layout_entries(data, layouts)
    offsets = sorted(set(entries))

    def plane(offset):
        base = layouts - ORIGIN + offset
        width, height = data[base] + 1, data[base + 1] + 1
        after = next((o for o in offsets if o > offset), None)
        allocated = (after - offset) if after is not None else 2 + width * height
        rows = max(1, min(height, (allocated - 2) // width))
        return bytes([width - 1, rows - 1]) + data[base + 2:base + 2 + width * rows]

    return plane(entries[0]), plane(entries[1])


def object_layouts(data, log=None):
    """ObjectLayouts: two offsets, an empty record, then 8-byte records."""
    found = []
    for i in range(0, len(data) - 32, 2):
        if data[i] or data[i + 1] != 12 or data[i + 4:i + 12] != b'\xff\xff' + bytes(6):
            continue
        end = struct.unpack_from('>H', data, i + 2)[0]
        if end <= 12 or (end - 12) % 8 or i + end > len(data):
            continue
        body = data[i + 12:i + end]
        x = [struct.unpack_from('>H', body, k)[0] for k in range(0, len(body), 8)]
        if x[-1] != 0xFFFF or any(v == 0xFFFF for v in x[:-1]):
            continue
        found.append(ORIGIN + i)
    return only('ObjectLayouts', found, log)


def start_location(data, sites, foreground, log=None):
    """LevelStartLoc: the record before SpecChunks, both loaded with lea, with
    a start position inside the foreground plane."""
    width, height = foreground[0] + 1, foreground[1] + 1
    found = []
    for spec in sorted(sites):
        if spec % 2 or (spec - 4) not in sites:
            continue
        x, y = struct.unpack_from('>HH', data, spec - 4 - ORIGIN)
        if not (0 < x < width * 256 and 0 < y < height * 256):
            continue
        near = [(spec - 4) - s for s in sites[spec] if 0 <= (spec - 4) - s <= MAX_START_LEA]
        if near:
            found.append(spec - 4)
    return only('LevelStartLoc', found, log)


def animated_tiles(data, log=None):
    """UpdateAnimTiles: the art each slot writes into the level's cells when the
    level is set up, as (first cell, art bytes, report record)."""
    entry = only('UpdateAnimTiles', [struct.unpack('>I', m[1])[0] for m in ANIM_INIT_CALL.finditer(data)
                                     if m.start() % 2 == 0], log)
    start = entry - ORIGIN
    if data[start:start + 2] == b'\x4e\xf9':
        return [], []                      # jmp LoadShieldArt: no animated art
    end = data.find(b'\x4e\x75', start)    # the routine's rts
    if end < 0:
        raise ValueError('UpdateAnimTiles has no rts')
    slots, skipped = [], []
    for m in ANIM_CALL.finditer(data, start, end):
        if m.start() % 2:
            continue
        table, words = struct.unpack('>I', m[1])[0], struct.unpack('>H', m[2])[0] + 1
        helper = m.start() + 12 + struct.unpack('>h', m[3])[0]
        dma = ANIM_SLOT.match(data, m.end())
        if not dma or dma.end() > end:
            skipped.append({'at': f'{ORIGIN + m.start():#08x}', 'table': f'{table:#08x}'})
            continue
        size = (dma[1][0] << 8 | dma[2][0]) * 2
        source = (((dma[5][0] & 0x7F) << 16) | (dma[3][0] << 8) | dma[4][0]) * 2
        high, low = struct.unpack('>H', dma[6])[0], struct.unpack('>H', dma[7])[0]
        buffer = ANIM_BUFFER.search(data, helper, helper + 64)
        if high >> 14 != 1 or not low & 0x80 or size != words * 4 or not buffer \
                or source != struct.unpack('>I', buffer[1])[0] & 0xFFFFFF:
            raise ValueError(f'UpdateAnimTiles slot at {ORIGIN + m.start():#x} is not a VRAM copy of its frame')
        dest = (high & 0x3FFF) | ((low & 3) << 14)
        # Timers and frames start at zero, so the first call moves to frame 1
        # unless the slot has only one frame.
        if ANIM_SIMPLE.match(data, helper):
            kind, frames = 'simple', data[table - ORIGIN + 1]
            frame = 1 if frames > 1 else 0
            art = long(data, table + 2 + frame * 4)
        elif ANIM_SCRIPT.match(data, helper):
            kind, frames = 'script', data[table - ORIGIN]
            frame = 1 if frames > 1 else 0
            art = long(data, table + 2 + frames * 2 + data[table - ORIGIN + 3 + frame * 2] * 4)
        else:
            raise ValueError(f'UpdateAnimTiles slot at {ORIGIN + m.start():#x} calls an unknown helper')
        if dest % 32 or not ORIGIN <= art <= ORIGIN + SIZE - size:
            raise ValueError(f'UpdateAnimTiles slot at {ORIGIN + m.start():#x} has a bad frame')
        slots.append((dest // 32, at(data, art, size),
                      {'cell': dest // 32, 'cells': size // 32, 'helper': kind, 'frames': frames,
                       'frame': frame, 'table': f'{table:#08x}', 'art': f'{art:#08x}'}))
    if log is not None:
        log['UpdateAnimTiles slots'] = len(slots)
    return slots, skipped


def with_animated_tiles(tiles, slots):
    """The level art as VRAM holds it when the level is first shown."""
    out = bytearray(tiles)
    for cell, art, _ in slots:
        if cell * 32 + len(art) > len(out):
            raise ValueError(f'animated cells {cell}+{len(art) // 32} run past {len(out) // 32} level cells')
        out[cell * 32:cell * 32 + len(art)] = art
    return bytes(out)


def collision_maps(disc):
    """The shared Angles/Height Map/Width Map block, bootstrapped from the disc.

    In a program whose LevelColIndex is the usual run of eight identical
    pointers, that pointer is where the block ends. The block is engine data,
    identical everywhere, so one program is enough to learn it; every program
    is then required to contain it exactly once.
    """
    for name in sorted(disc):
        data = disc[name]
        if len(data) != SIZE:
            continue
        try:
            layouts = level_layouts(data, absolute_longs(data))
        except ValueError:
            continue
        runs = set()
        i = 0
        while i + 32 <= len(data):
            value = struct.unpack_from('>I', data, i)[0]
            if (ORIGIN + MAPS <= value < ORIGIN + SIZE
                    and all(struct.unpack_from('>I', data, i + 4 * k)[0] == value for k in range(1, 8))):
                runs.add(value)
                i += 4
            else:
                i += 2
        ends = [v for v in runs if 0 < layouts - v <= MAX_COLLISION]
        if len(ends) == 1:
            return data[ends[0] - ORIGIN - MAPS:ends[0] - ORIGIN], name
    raise ValueError('no program on the disc resolves the shared collision maps')


def locate(data, maps, min_chunks=0):
    """Every stage structure of one program, found independently."""
    log = {}
    longs = absolute_longs(data)
    sites = lea_sites(data)
    index = data_index(data, longs, log)
    tiles, blocks, chunks = long(data, index) & 0x3FFFFF, long(data, index + 4) & 0x3FFFFF, long(data, index + 8)
    if word(data, index + 12) != 0x81 or chunks != CHUNKS:
        raise ValueError('LevelDataIndex layout changed')
    layouts = level_layouts(data, longs, log)
    hits = [m.start() for m in re.finditer(re.escape(maps), data)]
    if len(hits) != 1:
        raise ValueError(f'shared collision maps: {len(hits)} copies')
    collision = ORIGIN + hits[0] + MAPS
    if not 0 < layouts - collision <= MAX_COLLISION:
        raise ValueError(f'collision index {layouts - collision} bytes before LevelLayouts')
    foreground, background = planes(data, layouts)
    start = start_location(data, sites, foreground, log)
    objects = object_layouts(data, log)
    palettes = palette_table(data, log)
    animated, skipped = animated_tiles(data, log)
    palette_id = data[index - ORIGIN + 15]
    colors = lambda i: at(data, long(data, palettes + i * 8), (word(data, palettes + i * 8 + 6) + 1) * 4)
    used = max(min_chunks, *(c & 127 for c in foreground[2:] + background[2:]))
    log['shared collision maps'] = len(hits)
    return {
        'candidates': log,
        'addresses': {k: f'{v:#08x}' for k, v in dict(
            data_index=index, tiles=tiles, blocks=blocks, chunks=chunks, layouts=layouts,
            collision=collision, start=start, objects=objects, palettes=palettes).items()},
        'tiles_raw': data[tiles - ORIGIN:], 'blocks_raw': data[blocks - ORIGIN:],
        'chunks': at(data, chunks, used * 512),
        'foreground': foreground, 'background': background,
        'collision': at(data, collision, layouts - collision).rstrip(b'\0'),
        'start': at(data, start, 4), 'spec_chunks': at(data, start + 4, 4),
        'objects': at(data, objects + word(data, objects),
                      word(data, objects + 2) - word(data, objects)),
        'sonic_palette': colors(3), 'level_palette': colors(palette_id), 'palette_id': palette_id,
        'animated': animated, 'animated_skipped': skipped,
        'maps': {'Angles': maps[:ANGLES],
                 'Height Map': maps[ANGLES:ANGLES + HEIGHT_MAP],
                 'Width Map': maps[ANGLES + HEIGHT_MAP:]},
    }


def pc_table(text, name):
    m = re.search(re.escape(name) + r'\[[^\]]*\](?:\[[^\]]*\])?\s*=\s*\{(.*?)\};', text, re.S)
    return bytes(int(v) & 255 for v in re.findall(r'-?\d+', m[1]))


def expand(plane):
    return layout(plane) if (plane[0] + 1) <= 64 and (plane[1] + 1) <= 8 else None


def cross_check(x, pc_dir, program):
    """The six PC reconstruction tables, the correctness oracle for every round."""
    text = (pc_dir / f'Z{program[1:]}TBL.C').read_text(encoding='latin1')
    zone = pc_table(text, 'zone1scd')
    return {
        'collision': zone[:len(x['collision'])] == x['collision'] and not any(zone[len(x['collision']):]),
        'foreground': expand(x['foreground']) == pc_table(text, 'mapwka'),
        'background': expand(x['background']) == pc_table(text, 'mapwkb'),
        'angles': pc_table(text, 'scddirtbl') == x['maps']['Angles'],
        'height': pc_table(text, 'scdtblwk')[:4096] == x['maps']['Height Map'],
        'width': pc_table(text, 'scdtblwk2')[:4096] == x['maps']['Width Map'],
    }


def object_check(x, pc_dir, program):
    """The object layout against the PC asettbl.

    The retail disc is authoritative where the two differ, so the difference is
    described rather than asserted away: a few acts hold one record the PC
    reconstruction does not (or the other way round). What is asserted is that
    the retail list is self-consistent: 8-byte records, one $FFFF terminator,
    and no $FFFF before it.
    """
    rows = [tuple(map(int, m.groups())) for m in re.finditer(
        r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}',
        (pc_dir / f'Z{program[1:3]}ACT.C').read_text(encoding='latin1'))]
    records = [struct.unpack_from('>HHBBBB', x['objects'], i) for i in range(0, len(x['objects']), 8)]
    # Both tables end with an X=$FFFF record; some PC files fill that record's
    # other fields with $FF, so the terminators are compared on X alone.
    body, pc_body = records[:-1], rows[:-1]
    ops = [{'kind': tag, 'at': i1, 'pc': pc_body[i1:i2], 'retail': body[j1:j2]}
           for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=pc_body, b=body, autojunk=False).get_opcodes()
           if tag != 'equal']
    xs = [r[0] for r in body]
    return {
        'pc_records': len(rows), 'retail_records': len(records),
        'terminated': records[-1][0] == 0xFFFF and all(r[0] != 0xFFFF for r in body),
        'pc_terminated': bool(rows) and rows[-1][0] == 0xFFFF,
        'x_sorted': all(a <= b for a, b in zip(xs, xs[1:])),
        'equals_pc': not ops,
        'differences': ops,
    }


def stage_pack(x, tiles, blocks):
    colors = palette(x['sonic_palette'] + x['level_palette'])
    if len(colors) != 128:
        raise ValueError('expected 64 palette entries')
    parts = [tiles, blocks, x['chunks'], expand(x['foreground']), expand(x['background']), colors]
    header, offset = b'PPZ1', 56
    for part in parts:
        header += struct.pack('>II', offset, len(part))
        offset += len(part)
    return header + x['start'] + b''.join(parts)


def read_iso(path):
    if path.exists():
        return path.read_bytes()
    raw = (path.parent / 'sonic.bin').read_bytes()
    return b''.join(raw[i + 16:i + 2064] for i in range(0, len(raw), 2352))


def template_sha(entry, kind):
    """The template-based tools never apply the animated cells, so a pack is
    compared with them as it was before those cells were written."""
    return entry.get('raw_pack_sha256', entry['pack_sha256']) if kind == 'pack' else entry[f'{kind}_sha256']


def verify(round_number, report, out):
    """Compare this run against what the template-based tools already produced."""
    results = {}
    generated = ROOT / 'assets/generated'
    for program, entry in report['programs'].items():
        key = program[1:]
        for kind, name in [('pack', f'ppz{key}.bin'), ('collision', f'collision{key}.bin'),
                           ('objects', f'objects{key}.bin')]:
            path = generated / name
            if path.exists():
                results[name] = hashlib.sha256(path.read_bytes()).hexdigest() == template_sha(entry, kind)
    for known in sorted((ROOT / 'build').glob('zone-*.json')):
        other = json.loads(known.read_text())
        if other.get('round') == round_number:
            for program, entry in other['programs'].items():
                mine = report['programs'].get(program, {})
                for kind in ('pack', 'collision', 'objects'):
                    results[f'{program}:{kind}'] = bool(mine) and template_sha(mine, kind) == entry[f'{kind}_sha256']
    return results


# src/stage_packs.h: each era pack slot and collision slot in the stage RAM map.
STAGE_PACKS_H = ROOT / 'src/stage_packs.h'
STAGE_PACK_ROW = re.compile(r'STAGE_PACK\(PACK_(PPZ|COL)([0-3]),"[^"]*",(0x[0-9A-Fa-f]+),(0x[0-9A-Fa-f]+),')


def slot_bytes():
    """{'PPZ0': size, ..., 'COL3': size}: every era pack and collision slot's
    capacity, read from the STAGE_PACK rows in src/stage_packs.h. The slots
    differ in size, so a pack's headroom depends on its era."""
    slots = {kind + index: int(size, 16)
             for kind, index, _, size in STAGE_PACK_ROW.findall(STAGE_PACKS_H.read_text())}
    want = {f'{kind}{index}' for kind in ('PPZ', 'COL') for index in range(4)}
    if set(slots) != want:
        raise SystemExit(f'{STAGE_PACKS_H}: STAGE_PACK rows give slots {sorted(slots)}, want {sorted(want)}')
    return slots


def era_slot(program):
    """The PPZn slot an era's pack loads into: era A-D is slot 0-3."""
    return f"PPZ{'ABCD'.index(program[-1])}"


def manifest_row(program, entry, slots):
    """A new manifest row for one program, from its report entry."""
    return {'mmd_sha256': entry['mmd_sha256'], 'chunks': entry['chunks'], 'pack_bytes': entry['pack_bytes'],
            'pack_headroom_bytes': slots[era_slot(program)] - entry['pack_bytes'], 'pack_sha256': entry['pack_sha256'],
            'collision_bytes': entry['collision_bytes'], 'collision_sha256': entry['collision_sha256'],
            'objects_sha256': entry['objects_sha256'], 'animated_tiles': entry['animated_tiles'],
            'pc_checks_passed': not entry['pc_failed']}


def update_manifest(report):
    """Refresh this round's pack rows in the harvest manifest.

    A missing manifest, round or program row is created from the report (a
    fresh checkout has no harvest); main() only gets here when every PC
    cross-check passed.

    tools/install_zone_packs.py checks every copy against the manifest, so a
    re-harvest that changes pack bytes has to land there too. Only the animated
    cells may differ from the recorded run: they are written in place, so the
    pack size and everything else in a row must be unchanged, except a chunk
    array that grew (R8 keeps st_metalDataChk's chunks through 111): the pack
    then grows by exactly 512 bytes per chunk, inside the era region.
    """
    slots = slot_bytes()
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {
        'tool': 'tools/extract_zone_auto.py', 'source': report['source'], 'rounds': {}}
    # Older manifests carried one era size for every slot.
    manifest.pop('era_region_bytes', None)
    manifest['era_slot_bytes'] = {f'PPZ{index}': slots[f'PPZ{index}'] for index in range(4)}
    manifest['collision_slot_bytes'] = {f'COL{index}': slots[f'COL{index}'] for index in range(4)}
    manifest.pop('collision_region_bytes', None)
    round_entry = manifest['rounds'].setdefault(f"R{report['round']}", {
        'round': report['round'], 'programs': len(report['programs']), 'all_pc_checks_passed': True,
        'program_data': {}})
    rows = round_entry['program_data']
    for program, entry in report['programs'].items():
        if program not in rows:
            rows[program] = manifest_row(program, entry, slots)
            continue
        row = rows[program]
        row['pack_headroom_bytes'] = slots[era_slot(program)] - row['pack_bytes']
        grown = (entry['chunks'] - row['chunks']) * 512
        if grown > 0 and entry['pack_bytes'] - row['pack_bytes'] == grown and grown <= row['pack_headroom_bytes']:
            row['chunks'], row['pack_bytes'] = entry['chunks'], entry['pack_bytes']
            row['pack_headroom_bytes'] -= grown
        if (row['pack_bytes'], row['collision_sha256'], row['objects_sha256']) != (
                entry['pack_bytes'], entry['collision_sha256'], entry['objects_sha256']):
            raise SystemExit(f'{program}: the manifest row differs by more than the animated cells')
        row['pack_sha256'] = entry['pack_sha256']
        row['animated_tiles'] = entry['animated_tiles']
    manifest['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('round', type=int, choices=ROUNDS)
    parser.add_argument('--iso', type=Path, default=ROOT / 'build/retail/sonic.iso')
    parser.add_argument('--out', type=Path, default=None,
                        help='where to write packs (default build/auto-extract/<round>)')
    parser.add_argument('--pc-dir', type=Path, default=None)
    parser.add_argument('--verify', action='store_true',
                        help='compare the packs with the template-based tools\' output')
    parser.add_argument('--no-write', action='store_true')
    parser.add_argument('--manifest', action='store_true',
                        help=f'refresh this round\'s pack rows in {MANIFEST.relative_to(ROOT)}')
    args = parser.parse_args()

    out = args.out or ROOT / 'build/auto-extract' / str(args.round)
    pc_dir = args.pc_dir or ROOT / '.deps/soniccd/src' / f'R{args.round}'
    disc = disc_files(read_iso(args.iso))
    maps, bootstrap = collision_maps(disc)

    report = {'round': args.round, 'source': str(args.iso),
              'disassembly_input': 'none: every structure is found from its own shape',
              'oracle': str(pc_dir), 'collision_maps_bootstrap': bootstrap,
              'collision_maps_sha256': hashlib.sha256(maps).hexdigest(),
              'tools': tool_hashes(), 'programs': {}}
    failures = []
    for program in programs_of(args.round):
        data = disc[f'{program}__.MMD']
        # FCOL.C:1070-1100 st_metalDataChk reads MM's upper-layer chunks 106-111,
        # which no layout cell names: keep the chunk array through 111 for R8.
        x = locate(data, maps, 111 if args.round == 8 else 0)
        tiles, blocks = nemesis(x['tiles_raw']), nemesis(x['blocks_raw'])
        checks = cross_check(x, pc_dir, program)
        objects = object_check(x, pc_dir, program)
        raw_pack = stage_pack(x, tiles, blocks)
        pack = stage_pack(x, with_animated_tiles(tiles, x['animated']), blocks)
        collision = (x['collision'].ljust(1024, b'\0') + x['maps']['Height Map']
                     + x['maps']['Width Map'] + x['maps']['Angles'])
        entry = {
            'mmd_sha256': hashlib.sha256(data).hexdigest(), 'addresses': x['addresses'],
            'palette_id': x['palette_id'], 'chunks': len(x['chunks']) // 512,
            'tiles': len(tiles) // 32, 'blocks': len(blocks) // 8,
            'foreground': [x['foreground'][0] + 1, x['foreground'][1] + 1],
            'background': [x['background'][0] + 1, x['background'][1] + 1],
            'start': list(struct.unpack('>HH', x['start'])), 'spec_chunks': x['spec_chunks'].hex(),
            'object_records': len(x['objects']) // 8 - 1,
            'candidates': x['candidates'],
            'pc_match': sorted(k for k, v in checks.items() if v),
            'pc_failed': sorted(k for k, v in checks.items() if not v),
            'objects': objects,
            'animated_tiles': [slot for _, _, slot in x['animated']],
            'animated_skipped': x['animated_skipped'],
            'pack_sha256': hashlib.sha256(pack).hexdigest(),
            'raw_pack_sha256': hashlib.sha256(raw_pack).hexdigest(),
            'collision_sha256': hashlib.sha256(collision).hexdigest(),
            'collision_bytes': len(collision),
            'objects_sha256': hashlib.sha256(x['objects']).hexdigest(),
            'pack_bytes': len(pack),
        }
        if entry['pc_failed']:
            failures.append(f"{program}: {entry['pc_failed']}")
        if not (objects['terminated']):
            failures.append(f'{program}: object layout is not terminated')
        if not args.no_write:
            out.mkdir(parents=True, exist_ok=True)
            key = program[1:]
            (out / f'ppz{key}.bin').write_bytes(pack)
            (out / f'collision{key}.bin').write_bytes(collision)
            (out / f'objects{key}.bin').write_bytes(x['objects'])
        report['programs'][program] = entry

    if args.verify:
        report['verify'] = verify(args.round, report, out)
    if not args.no_write:
        out.mkdir(parents=True, exist_ok=True)
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    total = len(report['programs'])
    passed = sum(1 for e in report['programs'].values() if not e['pc_failed'])
    same_objects = sum(1 for e in report['programs'].values() if e['objects']['equals_pc'])
    print(f"round {args.round}: {total} programs located without any disassembly input; "
          f"{passed}/{total} pass all six PC cross-checks; "
          f"{same_objects}/{total} object layouts equal the PC asettbl; "
          f"collision maps bootstrapped from {bootstrap}")
    for program, entry in report['programs'].items():
        for op in entry['objects']['differences']:
            print(f"  {program} objects {op['kind']}: pc {op['pc']} retail {op['retail']}")
    if 'verify' in report:
        bad = sorted(k for k, v in report['verify'].items() if not v)
        print(f"verify: {len(report['verify']) - len(bad)}/{len(report['verify'])} byte identical"
              + (f"; differs: {bad}" if bad else ''))
    for program, entry in report['programs'].items():
        if entry['animated_tiles'] or entry['animated_skipped']:
            print(f"  {program} animated cells: "
                  + ' '.join(f"{s['cell']}+{s['cells']} frame {s['frame']}/{s['frames']}" for s in entry['animated_tiles'])
                  + ''.join(f"; skipped the conditional slot at {s['at']}" for s in entry['animated_skipped']))
    for line in failures:
        print('  PC cross-check failed', line)
    if failures:
        raise SystemExit(1)
    if args.manifest and not args.no_write:
        update_manifest(report)


if __name__ == '__main__':
    main()
