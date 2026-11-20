#!/usr/bin/env python3
"""Extract Palmtree Panic stage data from the retail R1xx MMD programs.

R11A__.MMD is the template. Every Act 1 Present data file of the pinned
disassembly is found in it byte for byte; each label is then located in the
other nine programs through the absolute `lea label,aN` code that uses it.
The four Act 1 programs are compared with the disassembly data files and all
ten with the PC reconstruction tables (collision, layouts, object layouts).
Outputs keep the PPZ1 stage pack format read by `stage_open`.
"""
import hashlib, json, pathlib, re, struct
from convert_assets import ROOT, OUT, nemesis, palette, layout, assembly_frames

from scd_source import SRC as SCD_SRC
LEVEL = SCD_SRC / 'Level'
DATA = LEVEL / 'Palmtree Panic/Data'
PC = ROOT / '.deps/soniccd/src/R1'
ISO = ROOT / 'build/retail/sonic.iso'
ORIGIN = 0x200000
PROGRAMS = ['R11A', 'R11B', 'R11C', 'R11D', 'R12A', 'R12B', 'R12C', 'R12D', 'R13C', 'R13D']
ERAS = {'A': 'Present', 'B': 'Past', 'C': 'Good Future', 'D': 'Bad Future'}
GLOBAL_MAPS = ['Height Map', 'Width Map', 'Angles']
# Z12ACT.C (PC/PS2 reconstruction) places record 168 in time zones 0x60; the
# Sega CD retail program uses 0x40. The retail disc is authoritative.
KNOWN_PC_OBJECT_DIFFERENCES = {'R11': [], 'R12': [168], 'R13': []}


def disc_files(iso):
    def walk(lba, size):
        data = iso[lba*2048:lba*2048+size]; i = 0
        while i < len(data):
            n = data[i]
            if not n:
                i = (i//2048+1)*2048; continue
            r = data[i:i+n]; i += n; name = r[33:33+r[32]]
            if name in (b'\0', b'\1'):
                continue
            start, length = struct.unpack_from('<I', r, 2)[0], struct.unpack_from('<I', r, 10)[0]
            if r[25] & 2:
                yield from walk(start, length)
            else:
                yield name.split(b';')[0].decode(), iso[start*2048:start*2048+length]
    root = iso[16*2048+156:]
    return dict(walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]))


def unique(data, blob):
    i = data.find(blob)
    if i < 0 or data.find(blob, i+1) >= 0:
        raise ValueError(f'expected one copy of {len(blob)} bytes, found {data.count(blob)}')
    return i


def signatures(template, address, before, after):
    """Code bytes around absolute `lea address,aN` in the template."""
    word = struct.pack('>I', address)
    for i in range(max(2, before), len(template)-after-4, 2):
        if template[i:i+4] == word and template[i-1] == 0xF9 and (template[i-2] & 0xF1) == 0x41:
            yield template[i-before:i], template[i+4:i+4+after]


def relocate(template, target, address):
    found = set()
    for before, after in [(12, 8), (8, 4), (4, 4), (2, 8), (2, 4)]:
        for head, tail in signatures(template, address, before, after):
            hits = [m for m in re.finditer(re.escape(head) + b'(....)' + re.escape(tail), target, re.S) if m.start() % 2 == 0]
            if len(hits) == 1:
                found.add(struct.unpack('>I', hits[0][1])[0])
    if len(found) != 1:
        raise ValueError(f'label {address:#x}: {len(found)} relocations {sorted(map(hex, found))}')
    return found.pop()


def template_labels(r11a):
    load = lambda name: (DATA / name).read_bytes()
    labels = {
        'tiles': ORIGIN + unique(r11a, load('Tiles (Act 1 Present).nem')),
        'blocks': ORIGIN + unique(r11a, load('Blocks (Act 1 Present).nem')),
        'chunks': ORIGIN + unique(r11a, load('Chunks (Act 1 Present).bin')),
        'collision': ORIGIN + unique(r11a, load('Collision (Act 1 Present).bin')),
        'foreground': ORIGIN + unique(r11a, load('Foreground (Act 1 Present).bin')),
        # LevelStartLoc directly precedes SpecChunks, which every scroll variant loads with lea.
        'spec_chunks': ORIGIN + 4 + unique(r11a, load('Start Position (Act 1 Present).bin') + bytes([0x7F]*4)),
        # ObjectLayouts: two offset words and one 8-byte null record before the layout.
        'objects': ORIGIN + unique(r11a, load('Objects (Act 1).bin')) - 12,
    }
    index = struct.pack('>III', labels['tiles'] | 0x3000000, labels['blocks'] | 0x2000000, labels['chunks']) + b'\0\x81'
    labels['data_index'] = ORIGIN + min(m.start() for m in re.finditer(re.escape(index), r11a))
    labels['layouts'] = labels['foreground'] - 0x48
    if struct.unpack_from('>H', r11a, labels['layouts'] - ORIGIN)[0] != 0x48:
        raise ValueError('LevelLayouts table does not end at the foreground layout')
    # PaletteTable entry 5 (Pal_Level: 24 longs) is the first copy of the Present palette.
    level = struct.pack('>I', ORIGIN + r11a.find(load('Palette (Present).bin')))
    rows = [m.start() for m in re.finditer(re.escape(level) + b'..\x00\x17', r11a, re.S)]
    if len(rows) != 1:
        raise ValueError('PaletteTable not found')
    labels['palettes'] = ORIGIN + rows[0] - 40
    debug = [m.start() for m in re.finditer(rb'\x34\x00\x35\x01....\x03\x28\x00\x00\x00\x00\x2f\x01....\x23\x70\x00\x00\x00\x0f', r11a, re.S)]
    if len(debug) != 1:
        raise ValueError('DebugItemIndex not found')
    labels['debug'] = ORIGIN + debug[0]
    at = unique(r11a, struct.pack('>I', labels['collision']) * 8)
    labels['collision_head'] = r11a[at-12:at]
    return labels


def extract(template, target, labels):
    long = lambda a: struct.unpack_from('>I', target, a - ORIGIN)[0]
    word = lambda a: struct.unpack_from('>H', target, a - ORIGIN)[0]
    at = lambda a, n: target[a-ORIGIN:a-ORIGIN+n]
    index = relocate(template, target, labels['data_index'])
    tiles, blocks, chunks = long(index) & 0x3FFFFF, long(index+4) & 0x3FFFFF, long(index+8)
    if word(index+12) != 0x81 or chunks != ORIGIN + 0x10000:
        raise ValueError('LevelDataIndex layout changed')
    layouts = relocate(template, target, labels['layouts'])
    if word(layouts) != 0x48:
        raise ValueError('LevelLayouts table size changed')
    plane = lambda a: at(a, 2 + (target[a-ORIGIN]+1) * (target[a-ORIGIN+1]+1))
    fg, bg = plane(layouts + word(layouts)), plane(layouts + word(layouts+2))
    heads = [m.start() for m in re.finditer(re.escape(labels['collision_head']) + rb'(....)\1\1\1\1\1\1\1', target, re.S)]
    if len(heads) != 1:
        raise ValueError(f'LevelColIndex: {len(heads)} matches')
    collision = long(ORIGIN + heads[0] + 12)
    start = relocate(template, target, labels['spec_chunks']) - 4
    objects = relocate(template, target, labels['objects'])
    palettes = relocate(template, target, labels['palettes'])
    palette_id = target[index-ORIGIN+15]
    color_table = lambda i: at(long(palettes+i*8), (word(palettes+i*8+6)+1)*4)
    debug = relocate(template, target, labels['debug'])
    used = max(c & 127 for c in fg[2:] + bg[2:])
    return {
        'addresses': {k: f'{v:#08x}' for k, v in dict(data_index=index, tiles=tiles, blocks=blocks, chunks=chunks, layouts=layouts,
                      collision=collision, start=start, objects=objects, palettes=palettes, debug=debug).items()},
        'tiles_raw': target[tiles-ORIGIN:], 'blocks_raw': target[blocks-ORIGIN:], 'chunks': at(chunks, used*512),
        'foreground': fg, 'background': bg, 'collision': at(collision, layouts-collision).rstrip(b'\0'),
        'start': at(start, 4), 'spec_chunks': at(start+4, 4),
        'objects': at(objects + word(objects), word(objects+2) - word(objects)),
        'sonic_palette': color_table(3), 'level_palette': color_table(palette_id), 'palette_id': palette_id,
        'debug_count': target[debug-ORIGIN],
        'maps': {n: target[unique(target, (LEVEL/f'_Data/Collision {n}.bin').read_bytes()):][:len((LEVEL/f'_Data/Collision {n}.bin').read_bytes())] for n in GLOBAL_MAPS},
    }


def object_index(program):
    """ObjectIndex: 64 absolute routine longs; IDs 1 and 2 both dispatch to ObjSonic."""
    for i in range(0, 0x10000, 2):
        v = struct.unpack_from('>64I', program, i)
        if v[0] == v[1] and all(ORIGIN <= a < ORIGIN + 0x40000 for a in v) and len(set(v)) > 20:
            return i
    raise ValueError('ObjectIndex not found')


def object_mappings(program, object_id):
    """First `move.l #mappings,oMap(a0)` in an object's routine and its frames."""
    routine = struct.unpack_from('>I', program, object_index(program) + (object_id - 1) * 4)[0] - ORIGIN
    code = program[routine:routine + 0x800]
    found = [m for m in re.finditer(rb'\x21\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
    if not found:
        raise ValueError(f'object {object_id:#x}: no mappings')
    at = struct.unpack('>I', found[0][1])[0] - ORIGIN
    count = struct.unpack_from('>H', program, at)[0] // 2
    frames = []
    for k in range(count):
        frame = at + struct.unpack_from('>H', program, at + 2 * k)[0]
        frames.append(program[frame:frame + 1 + 5 * program[frame]])
    return code, frames


def pc_table(text, name):
    m = re.search(re.escape(name) + r'\[[^\]]*\](?:\[[^\]]*\])?\s*=\s*\{(.*?)\};', text, re.S)
    return bytes(int(v) & 255 for v in re.findall(r'-?\d+', m[1]))


def expand(plane):
    return layout(plane) if (plane[0]+1) <= 64 and (plane[1]+1) <= 8 else None


# Collision Chaos Act 3 boss (R3/BOSS_3.C, R3/GATE.C) in R33C/R33D. Each actor
# routine's first `move.l #map,oMap(a0)` names its mappings and its
# `move.w #tile,oTile(a0)` words equal the PC sproffset values; the art comes from
# the program's own PLC lists. Written as zone art sources (CC_BOSS_KIND) that
# tools/zone_object_assets.py packs with the round's other Act 3 objects.
CC_BOSS = [  # actno, PC pattern count, tile words (BOSS_3.C sproffset) the routine sets
    (48, 2, (0x31E,)), (49, 7, (0x31E,)), (50, 3, (0x31E,)), (51, 10, (0x31E, 0x3FC)),
    (61, 5, (0x47C,)), (62, 2, (0x47C,)), (63, 8, (0x474,))]
# Zone art kinds (below 256: the art probe's object view keeps an 8-bit type, and
# scd_zone_art_kind maps these to themselves): actor -> kind.
CC_BOSS_KIND = {48: 240, 49: 241, 50: 244, 51: 245, 61: 246, 62: 247, 63: 248}
CC_BOSS_ART = {1: (0x6D7, 0x568), 2: (0x31E, 0x474, 0x47C), 4: (0x3FC,)}  # PLC list: destinations used


def split_cc_boss(program, record):
    """Shared parts of the egg3dai_l and gate poses become separate zone art frames.

    egg3dai_l (241) mixes line 0 and line 1 pieces (over 16 colours per pose). Its
    line 1 pieces lie behind the platform or clear of every line 0 piece, so a
    pose draws as line 1 layer 242[p/2] (poses 0-5), platform 241[p&1], then top
    243[0] (poses 0-1): the same pixels as the original piece order (src/boss.c
    scd_boss_views). The gate poses stay whole (one sprite command per gate);
    this only checks that pose k is k+1 copies of one piece (GATE.C pat00-07)."""
    frames = [bytes.fromhex(f) for f in record['frames']]
    pieces = lambda f: [f[1 + 5 * i:6 + 5 * i] for i in range(f[0])]
    pack = lambda ps: (bytes([len(ps)]) + b''.join(ps)).hex()
    line1 = lambda q: struct.unpack_from('>H', q, 2)[0] & 0x6000 == 0x2000
    if record['kind'] == 241:
        layer, platform, top = [], [], []
        for n, f in enumerate(frames):
            ps = pieces(f)
            if any(struct.unpack_from('>H', q, 2)[0] & 0x6000 not in (0, 0x2000) for q in ps):
                raise SystemExit(f'{program}: egg3dai_l pose {n} palette lines')
            layer.append([q for q in ps if line1(q)])
            platform.append([q for q in ps if not line1(q) and struct.unpack('b', q[:1])[0] == -16])
            top.append([q for q in ps if not line1(q) and struct.unpack('b', q[:1])[0] != -16])
        if (any(layer[n] != layer[n & ~1] for n in range(6)) or layer[6] or any(platform[n] != platform[n & 1] for n in range(7))
                or top[0] != top[1] or any(top[n] for n in range(2, 7)) or len(platform[0]) != 4):
            raise SystemExit(f'{program}: egg3dai_l poses no longer share their parts')
        return [dict(record, frames=[pack(platform[0]), pack(platform[1])]),
                dict(record, kind=242, frames=[pack(layer[0]), pack(layer[2]), pack(layer[4])]),
                dict(record, kind=243, frames=[pack(top[0])])]
    if record['kind'] == 248:
        piece = pieces(frames[0])
        if len(piece) != 1 or any(pieces(f) != [piece[0][:4] + struct.pack('b', 48 - 16 * j) for j in range(n, -1, -1)] for n, f in enumerate(frames)):
            raise SystemExit(f'{program}: gate poses changed')
    return [record]


def cc_bumper_break(mmd, program, index, table, vram, loaded):
    """R3/BOBINB.C bobinbreak (actor 41): the break frames of PLAYSP3.C's breakable
    bumper blocks, as zone art kind 249. Its tile word $A421 (line 1, priority)
    points into the bank most of the program's PLC lists load at or below $421."""
    routine = lambda oid: struct.unpack_from('>I', mmd, index + (oid - 1) * 4)[0] - ORIGIN
    code = mmd[routine(41):routine(41) + 0x300]
    tile = [m for m in re.finditer(rb'[\x31\x33]\x7c\xa4\x21\x00\x02', code, re.S) if m.start() % 2 == 0]
    if len(tile) != 1:
        raise SystemExit(f'{program}: bobinbreak tile word')
    maps = [(m.start(), struct.unpack('>I', m[1])[0]) for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
    # The pair of break poses; in R32A the routine also sets an unrelated table first.
    maps = [a for at, a in sorted(maps, key=lambda m: (m[0] < tile[0].start(), m[0]))
            if ORIGIN <= a < ORIGIN + len(mmd) and struct.unpack_from('>H', mmd, a - ORIGIN)[0] == 4]
    if not maps:
        raise SystemExit(f'{program}: bobinbreak mappings')
    at = maps[0] - ORIGIN
    frames = [mmd[at + o:at + o + 1 + 5 * mmd[at + o]].hex() for o in (struct.unpack_from('>H', mmd, at + 2 * k)[0] for k in range(2))]
    counts = {}
    for plc in range(struct.unpack_from('>H', mmd, table)[0] // 2):
        entry = table + struct.unpack_from('>H', mmd, table + 2 * plc)[0]
        for e in range(struct.unpack_from('>h', mmd, entry)[0] + 1):
            address, dest = struct.unpack_from('>IH', mmd, entry + 2 + 6 * e)
            if dest // 32 <= 0x421:
                counts.setdefault((address, dest), set()).add(plc)
    candidates = [(len(v), k) for k, v in counts.items()]
    art = None
    for _, (address, dest) in sorted(candidates, reverse=True):
        data = nemesis(mmd[address - ORIGIN:])
        if dest // 32 + len(data) // 32 > 0x421 + 3:
            art = (address, dest, data); break
    address, dest, data = art
    vram[dest:dest + len(data)] = data
    loaded[f'{dest // 32:#x}'] = dict(plc=sorted(counts[(address, dest)]), address=f'{address:#08x}', tiles=len(data) // 32,
                                      sha256=hashlib.sha256(data).hexdigest())
    return dict(kind=249, retail_id=41, tile=0xA421, address=maps[0], frames=frames)


def cc_object_index(mmd):
    return next(i for i in range(0, 0x10000, 2) if (lambda v: v[0] == v[1] and len(set(v)) > 20 and
                all(ORIGIN <= a < ORIGIN + len(mmd) for a in v))(struct.unpack_from('>40I', mmd, i)))


def cc_plc_table(mmd, program):
    tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
    if len(tables) != 1:
        raise SystemExit(f'{program}: PLC table {tables}')
    return tables.pop() - ORIGIN


def cc_bumper_sources(disc, report):
    """Acts 1 and 2 of Collision Chaos: kind 249 in a '-bumper' zone art source."""
    from zone_object_source import dependencies
    out = {}
    for program in [f'R3{a}{e}' for a in (1, 2) for e in 'ABCD']:
        mmd = disc[f'{program}__.MMD']
        vram = bytearray(65536); loaded = {}
        record = cc_bumper_break(mmd, program, cc_object_index(mmd), cc_plc_table(mmd, program), vram, loaded)
        path = ROOT / f'build/zone-object-source/{program}-bumper'
        path.mkdir(parents=True, exist_ok=True)
        (path / 'vram.bin').write_bytes(bytes(vram))
        source = dict(program=program, objects=[record], art=loaded, generator='tools/extract_mmd.py',
                      dependencies=dependencies(), program_sha256=hashlib.sha256(mmd).hexdigest(),
                      vram_sha256=hashlib.sha256(vram).hexdigest(),
                      tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (path / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
        out[program] = loaded
    report['cc_bumper_break'] = out


def collision_chaos_boss(disc, report):
    from zone_object_source import dependencies
    pc_word = lambda rgb: struct.pack('>H', (rgb[2] // 16) << 8 | (rgb[1] // 16) << 4 | rgb[0] // 16)
    out = {}
    for program in ('R33C', 'R33D'):
        mmd = disc[f'{program}__.MMD']
        # ObjectIndex: R3 has 63 actor routines (ACT33C.C act_tbl); IDs 1 and 2 are Sonic.
        index = next(i for i in range(0, 0x10000, 2) if (lambda v: v[0] == v[1] and len(set(v)) > 20 and
                     all(ORIGIN <= a < ORIGIN + len(mmd) for a in v))(struct.unpack_from('>63I', mmd, i)))
        routine = lambda oid: struct.unpack_from('>I', mmd, index + (oid - 1) * 4)[0] - ORIGIN
        tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
        if len(tables) != 1:
            raise SystemExit(f'{program}: PLC table {tables}')
        table = tables.pop() - ORIGIN
        vram = bytearray(65536); loaded = {}
        for plc, destinations in CC_BOSS_ART.items():
            at = table + struct.unpack_from('>H', mmd, table + 2 * plc)[0]
            entries = [struct.unpack_from('>IH', mmd, at + 2 + 6 * e) for e in range(struct.unpack_from('>h', mmd, at)[0] + 1)]
            for tile in destinations:
                found = [a for a, d in entries if d == tile * 32]
                if len(found) != 1:
                    raise SystemExit(f'{program}: PLC {plc} has no single entry for tile {tile:#x}')
                art = nemesis(mmd[found[0] - ORIGIN:])
                vram[tile * 32:tile * 32 + len(art)] = art
                loaded[f'{tile:#x}'] = dict(plc=plc, address=f'{found[0]:#08x}', tiles=len(art) // 32,
                                           sha256=hashlib.sha256(art).hexdigest())
        records = []
        for actno, count, tiles in CC_BOSS:
            code = mmd[routine(actno):routine(actno) + 0x400]
            words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
            if list(tiles) != sorted(set(words[:len(tiles) + 1]) & set(tiles)) or words[0] != tiles[0]:
                raise SystemExit(f'{program}: actor {actno} tiles {[hex(w) for w in words[:4]]}')
            maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
            at = maps[0] - ORIGIN
            if struct.unpack_from('>H', mmd, at)[0] // 2 != count:
                raise SystemExit(f'{program}: actor {actno} has {struct.unpack_from(">H", mmd, at)[0] // 2} mappings, BOSS_3.C {count}')
            frames = []
            for k in range(count):
                frame = bytearray(mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0]:][:1])
                frame += mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0] + 1:][:5 * frame[0]]
                # egg3 poses 7-9 (pchg3/pchg4) draw from tile $3FC (sproffset 1020, the
                # PLC 4 bank); their pieces are rebased onto the record's $31E.
                if actno == 51 and k >= 7:
                    for piece in range(frame[0]):
                        word = struct.unpack_from('>H', frame, 3 + 5 * piece)[0]
                        struct.pack_into('>H', frame, 3 + 5 * piece, (word & 0xF800) | ((word & 2047) + 0x3FC - 0x31E))
                frames.append(bytes(frame).hex())
            record = dict(kind=CC_BOSS_KIND[actno], retail_id=actno, tile=tiles[0], address=maps[0], frames=frames)
            records += split_cc_boss(program, record)
        # The capsule's flowers (actor 31, GOAL.C flower) use Collision Chaos's own art at
        # $6D7, not Palmtree Panic's: kind 31 in the zone art. Poses 0-3 (seeds) are on
        # line 0 ($6D7) and 4-7 (growing, grown) on line 1 ($26D7), as the native atlas.
        code = mmd[routine(31):routine(31) + 0x300]
        words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
        maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
        if words[:3] != [0xA6D7, 0x6D7, 0x26D7]:
            raise SystemExit(f'{program}: flower tiles {[hex(w) for w in words[:3]]}')
        at = maps[0] - ORIGIN; flowers = []
        for k in range(struct.unpack_from('>H', mmd, at)[0] // 2):
            frame = bytearray(mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0]:][:1])
            frame += mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0] + 1:][:5 * frame[0]]
            for piece in range(frame[0] if k >= 4 else 0):
                struct.pack_into('>H', frame, 3 + 5 * piece, struct.unpack_from('>H', frame, 3 + 5 * piece)[0] | 0x2000)
            flowers.append(bytes(frame).hex())
        if len(flowers) != 8:
            raise SystemExit(f'{program}: {len(flowers)} flower poses')
        records.append(dict(kind=31, retail_id=31, tile=0x6D7, address=maps[0], frames=flowers))
        # PLAYSP3.C breakable bumpers: their break frames (actor 41) and BOBINB.C's
        # tensuu0 points (actor 28, the native SCD_OBJ_CC_POINTS, tile $8568, PLC 1 $568).
        records.append(cc_bumper_break(mmd, program, index, table, vram, loaded))
        code = mmd[routine(28):routine(28) + 0x300]
        words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
        maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
        if words[:1] != [0x8568]:
            raise SystemExit(f'{program}: points tile {[hex(w) for w in words[:2]]}')
        at = maps[0] - ORIGIN
        points = [mmd[at + o:at + o + 1 + 5 * mmd[at + o]].hex() for o in (struct.unpack_from('>H', mmd, at + 2 * k)[0] for k in range(struct.unpack_from('>H', mmd, at)[0] // 2))]
        records.append(dict(kind=85, retail_id=28, tile=0x8568, address=maps[0], frames=points))
        pc = (PC.parent / f'R3/COL3{program[3]}.C').read_text(encoding='latin1')
        palettes = {}
        for name in ('zone3colboss1', 'zone3colboss0'):
            body = re.search(re.escape(name) + r'\[16\]\s*=\s*\{(.*?)\};', pc, re.S)[1]
            words = b''.join(pc_word(tuple(map(int, m))) for m in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\}', body))
            if mmd.count(words) < 1:
                raise SystemExit(f'{program}: {name} not in the retail program')
            palettes[name] = words
        path = ROOT / f'build/zone-object-source/{program}-boss'
        path.mkdir(parents=True, exist_ok=True)
        (path / 'vram.bin').write_bytes(bytes(vram))
        source = dict(program=program, objects=records, art=loaded, generator='tools/extract_mmd.py',
                      dependencies=dependencies(), program_sha256=hashlib.sha256(mmd).hexdigest(),
                      vram_sha256=hashlib.sha256(vram).hexdigest(),
                      tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (path / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
        (OUT / f'boss3{program[3]}.pal').write_bytes(palettes['zone3colboss1'] + palettes['zone3colboss0'])
        out[program] = dict(art=loaded, frames={r['kind']: len(r['frames']) for r in records})
    report['boss3'] = dict(out, checks=['ObjectIndex routines set BOSS_3.C tile words', 'mapping counts equal BOSS_3.C/GATE.C patterns',
                                        'art from the program PLC lists 2 and 4', 'zone3colboss0/1 found in the program'])


# Tidal Tempest Act 3 boss (R4/BOSS_4.C, BOSS_4_2.C, WALL4.C) in R43C/R43D. As for
# Collision Chaos: each routine's first mappings and tile word, art from the
# program's PLC list. Two sets share tile $31E: PLC 2 holds egg4air/egg4airhead
# (the submarine chase) and PLC 4 the egg4 bubble machine, so each set is its own
# zone art source (-boss, -boss2) over its own VRAM image.
TT_BOSS = [  # actno, PC pattern count, tile word (sproffset), PLC set
    (71, 1, 0x446A, 2), (74, 9, 0x31E, 2), (75, 4, 0x31E, 2),
    (76, 7, 0x31E, 4), (77, 2, 0x31E, 4), (78, 2, 0x31E, 4), (79, 9, 0x31E, 4)]
# Zone art kinds (below 256, as CC_BOSS_KIND): actor -> kind (src/boss.c kinds4).
TT_BOSS_KIND = {74: 240, 75: 241, 76: 242, 77: 243, 78: 244, 79: 245, 71: 246}


def tidal_tempest_boss(disc, report):
    from zone_object_source import dependencies
    pc_word = lambda rgb: struct.pack('>H', (rgb[2] // 16) << 8 | (rgb[1] // 16) << 4 | rgb[0] // 16)
    out = {}
    for program in ('R43C', 'R43D'):
        mmd = disc[f'{program}__.MMD']
        # ObjectIndex: R4 has 80 actor routines (ACT43C.C act_tbl); IDs 1 and 2 are Sonic.
        index = next(i for i in range(0, 0x10000, 2) if (lambda v: v[0] == v[1] and len(set(v)) > 20 and
                     all(ORIGIN <= a < ORIGIN + len(mmd) for a in v))(struct.unpack_from('>80I', mmd, i)))
        routine = lambda oid: struct.unpack_from('>I', mmd, index + (oid - 1) * 4)[0] - ORIGIN
        tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
        if len(tables) != 1:
            raise SystemExit(f'{program}: PLC table {tables}')
        table = tables.pop() - ORIGIN
        entries = lambda plc: [struct.unpack_from('>IH', mmd, table + struct.unpack_from('>H', mmd, table + 2 * plc)[0] + 2 + 6 * e)
                               for e in range(struct.unpack_from('>h', mmd, table + struct.unpack_from('>H', mmd, table + 2 * plc)[0])[0] + 1)]
        sets = {}
        for plc in (2, 4):
            vram = bytearray(65536); loaded = {}
            # PLC 1 (the capsule's flowers at $6D7), then the set's own list over it.
            for source, destination in entries(1) + entries(plc):
                art = nemesis(mmd[source - ORIGIN:])
                vram[destination:destination + len(art)] = art
                loaded[f'{destination // 32:#x}'] = dict(plc=1 if (source, destination) in entries(1) else plc, address=f'{source:#08x}',
                                                        tiles=len(art) // 32, sha256=hashlib.sha256(art).hexdigest())
            sets[plc] = dict(vram=vram, loaded=loaded, records=[])
        if entries(4) != [e for e in entries(4) if e[1] == 0x31E * 32] or not entries(4):
            raise SystemExit(f'{program}: PLC 4 is not the single $31E boss bank')
        for actno, count, tile, plc in TT_BOSS:
            # A routine's window ends where the next routine in memory starts.
            start = routine(actno)
            end = min([routine(o) for o in range(3, 81) if routine(o) > start] + [start + 0x600])
            code = mmd[start:end]
            words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
            if not words or words[0] != tile:
                raise SystemExit(f'{program}: actor {actno} tiles {[hex(w) for w in words[:4]]}')
            maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
            at = maps[0] - ORIGIN
            if struct.unpack_from('>H', mmd, at)[0] // 2 != count:
                raise SystemExit(f'{program}: actor {actno} has {struct.unpack_from(">H", mmd, at)[0] // 2} mappings, BOSS_4 {count}')
            frames = [mmd[at + o:at + o + 1 + 5 * mmd[at + o]].hex() for o in (struct.unpack_from('>H', mmd, at + 2 * k)[0] for k in range(count))]
            sets[plc]['records'].append(dict(kind=TT_BOSS_KIND[actno], retail_id=actno, tile=tile, address=maps[0], frames=frames))
        # The capsule's flowers (actor 31, GOAL.C flower) at $6D7, as Collision Chaos (kind 31).
        code = mmd[routine(31):routine(31) + 0x300]
        words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
        maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
        if words[:3] != [0x26D7, 0x6D7, 0x26D7]:
            raise SystemExit(f'{program}: flower tiles {[hex(w) for w in words[:3]]}')
        at = maps[0] - ORIGIN; flowers = []
        for k in range(struct.unpack_from('>H', mmd, at)[0] // 2):
            frame = bytearray(mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0]:][:1])
            frame += mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0] + 1:][:5 * frame[0]]
            for piece in range(frame[0] if k >= 4 else 0):
                struct.pack_into('>H', frame, 3 + 5 * piece, struct.unpack_from('>H', frame, 3 + 5 * piece)[0] | 0x2000)
            flowers.append(bytes(frame).hex())
        if len(flowers) != 8:
            raise SystemExit(f'{program}: {len(flowers)} flower poses')
        sets[2]['records'].append(dict(kind=31, retail_id=31, tile=0x6D7, address=maps[0], frames=flowers))
        # COL4C/D.C colortbl[5] (colorset2(5), egg4air_ini): boss4color into line 1.
        pc = (PC.parent / f'R4/COL4{program[3]}.C').read_text(encoding='latin1')
        body = re.search(r'boss4color\[16\]\s*=\s*\{(.*?)\};', pc, re.S)[1]
        colors = b''.join(pc_word(tuple(map(int, m))) for m in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\}', body))
        if len(colors) != 32 or mmd.count(colors) < 1:
            raise SystemExit(f'{program}: boss4color not in the retail program')
        for plc, suffix in ((2, 'boss'), (4, 'boss2')):
            s = sets[plc]
            path = ROOT / f'build/zone-object-source/{program}-{suffix}'
            path.mkdir(parents=True, exist_ok=True)
            (path / 'vram.bin').write_bytes(bytes(s['vram']))
            source = dict(program=program, objects=s['records'], art=s['loaded'], generator='tools/extract_mmd.py',
                          dependencies=dependencies(), program_sha256=hashlib.sha256(mmd).hexdigest(),
                          vram_sha256=hashlib.sha256(s['vram']).hexdigest(),
                          tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
            (path / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
        (OUT / f'boss4{program[3]}.pal').write_bytes(colors)
        out[program] = dict(frames={r['kind']: len(r['frames']) for s in sets.values() for r in s['records']})
    report['boss4'] = dict(out, checks=['ObjectIndex routines set BOSS_4.C/BOSS_4_2.C/WALL4.C tile words',
                                        'mapping counts equal the PC patterns', 'art from the program PLC lists 1, 2 and 4',
                                        'boss4color (COL4C/D.C) found in the program'])


# Quartz Quadrant Act 3 boss (R5/BOSS_5.C) in R53C/R53D. As for Tidal Tempest:
# each routine's first mappings and tile word. The art is PLC 1 (the capsule's flowers
# at $6D7), PLC 2 (the boss bank at $2BC) and PLC 4 ($373-$4E9) over it: the retail
# fight capture (tools/boss_retail_capture.py) finds VRAM $2BC-$4E9 in that layout in
# every phase. egg5bomb2 (57) shares egg5bomb's mappings; egg5bakuha (35) is the common
# explosion ($680) and egg5belt (34) draws nothing.
QQ_BOSS = [  # actno, PC pattern count, tile word (sproffset)
    (32, 5, 0x22BC), (33, 1, 0x42BC), (50, 16, 0x2BC), (51, 1, 0x22BC), (52, 6, 0x22BC),
    (53, 1, 0x22BC), (54, 4, 0x22BC), (55, 3, 0x2BC), (56, 2, 0x22BC)]
# Zone art kinds (below 256, as CC_BOSS_KIND): actor -> kind (src/boss.c kinds5).
QQ_BOSS_KIND = {51: 240, 52: 241, 53: 242, 54: 243, 50: 244, 55: 245, 56: 246, 32: 247, 33: 248}


def quartz_quadrant_boss(disc, report):
    from zone_object_source import dependencies
    pc_word = lambda rgb: struct.pack('>H', (rgb[2] // 16) << 8 | (rgb[1] // 16) << 4 | rgb[0] // 16)
    out = {}
    for program in ('R53C', 'R53D'):
        mmd = disc[f'{program}__.MMD']
        # ObjectIndex: R5 has 60 actor routines (ACT53.C act_tbl); IDs 1 and 2 are Sonic.
        index = next(i for i in range(0, 0x10000, 2) if (lambda v: v[0] == v[1] and len(set(v)) > 20 and
                     all(ORIGIN <= a < ORIGIN + len(mmd) for a in v))(struct.unpack_from('>60I', mmd, i)))
        routine = lambda oid: struct.unpack_from('>I', mmd, index + (oid - 1) * 4)[0] - ORIGIN
        tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
        if len(tables) != 1:
            raise SystemExit(f'{program}: PLC table {tables}')
        table = tables.pop() - ORIGIN
        entries = lambda plc: [struct.unpack_from('>IH', mmd, table + struct.unpack_from('>H', mmd, table + 2 * plc)[0] + 2 + 6 * e)
                               for e in range(struct.unpack_from('>h', mmd, table + struct.unpack_from('>H', mmd, table + 2 * plc)[0])[0] + 1)]
        if not any(d == 0x2BC * 32 for _, d in entries(2)):
            raise SystemExit(f'{program}: PLC 2 has no $2BC boss bank')
        if [d // 32 for _, d in entries(4)] != [0x373, 0x481]:
            raise SystemExit(f'{program}: PLC 4 is not the $373/$481 boss bank')
        sets = {}
        vram = bytearray(65536); loaded = {}
        for n in (1, 2, 4):
            for source, destination in entries(n):
                art = nemesis(mmd[source - ORIGIN:])
                vram[destination:destination + len(art)] = art
                loaded[f'{destination // 32:#x}'] = dict(plc=n, address=f'{source:#08x}',
                                                        tiles=len(art) // 32, sha256=hashlib.sha256(art).hexdigest())
        records = []
        for actno, count, tile in QQ_BOSS:
            start = routine(actno)
            end = min([routine(o) for o in range(3, 61) if routine(o) > start] + [start + 0x600])
            code = mmd[start:end]
            words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
            if not words or words[0] != tile:
                raise SystemExit(f'{program}: actor {actno} tiles {[hex(w) for w in words[:4]]}')
            maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
            at = maps[0] - ORIGIN
            if struct.unpack_from('>H', mmd, at)[0] // 2 != count:
                raise SystemExit(f'{program}: actor {actno} has {struct.unpack_from(">H", mmd, at)[0] // 2} mappings, BOSS_5 {count}')
            frames = [mmd[at + o:at + o + 1 + 5 * mmd[at + o]].hex() for o in (struct.unpack_from('>H', mmd, at + 2 * k)[0] for k in range(count))]
            records.append(dict(kind=QQ_BOSS_KIND[actno], retail_id=actno, tile=tile, address=maps[0], frames=frames))
        # The capsule's flowers (actor 31, GOAL.C flower) at $6D7, as Tidal Tempest (kind 31).
        code = mmd[routine(31):routine(31) + 0x300]
        words = [struct.unpack('>H', m[1])[0] for m in re.finditer(rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
        maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
        # R5 sets the first word with the priority bit ($A6D7); the poses are Tidal Tempest's.
        if [words[0] & 0x7FFF] + words[1:3] != [0x26D7, 0x6D7, 0x26D7]:
            raise SystemExit(f'{program}: flower tiles {[hex(w) for w in words[:3]]}')
        at = maps[0] - ORIGIN; flowers = []
        for k in range(struct.unpack_from('>H', mmd, at)[0] // 2):
            frame = bytearray(mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0]:][:1])
            frame += mmd[at + struct.unpack_from('>H', mmd, at + 2 * k)[0] + 1:][:5 * frame[0]]
            for piece in range(frame[0] if k >= 4 else 0):
                struct.pack_into('>H', frame, 3 + 5 * piece, struct.unpack_from('>H', frame, 3 + 5 * piece)[0] | 0x2000)
            flowers.append(bytes(frame).hex())
        if len(flowers) != 8:
            raise SystemExit(f'{program}: {len(flowers)} flower poses')
        records.append(dict(kind=31, retail_id=31, tile=0x6D7, address=maps[0], frames=flowers))
        # COL5C/D.C colortbl[6] (colorset2(6), egg5meca1_ini): zone5colboss0 into line 1.
        pc = (PC.parent / f'R5/COL5{program[3]}.C').read_text(encoding='latin1')
        body = re.search(r'zone5colboss0\[16\]\s*=\s*\{(.*?)\};', pc, re.S)[1]
        colors = b''.join(pc_word(tuple(map(int, m))) for m in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\}', body))
        if len(colors) != 32 or mmd.count(colors) < 1:
            raise SystemExit(f'{program}: zone5colboss0 not in the retail program')
        path = ROOT / f'build/zone-object-source/{program}-boss'
        path.mkdir(parents=True, exist_ok=True)
        (path / 'vram.bin').write_bytes(bytes(vram))
        source = dict(program=program, objects=records, art=loaded, generator='tools/extract_mmd.py',
                      dependencies=dependencies(), program_sha256=hashlib.sha256(mmd).hexdigest(),
                      vram_sha256=hashlib.sha256(vram).hexdigest(),
                      tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (path / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
        (OUT / f'boss5{program[3]}.pal').write_bytes(colors)
        out[program] = dict(frames={r['kind']: len(r['frames']) for r in records})
    report['boss5'] = dict(out, checks=['ObjectIndex routines set BOSS_5.C tile words', 'mapping counts equal the PC patterns',
                                        'art from the program PLC lists 1, 2 and 4', 'zone5colboss0 (COL5C/D.C) found in the program'])


# R63C/D: ACT63.C IDs 52-64 and BOSS_6.C's first patbase assignments.
# PLC 1 supplies stage art, PLC 2 installs entry art, and PLC 19 installs
# fight art over tiles $300-$457. The native pack currently uses fight art.
# Retail R63C/D actor traces confirm gareki4 and beamer at the adjacent
# mapping tables. The beam's three VRAM art states are uncompressed MMD data.
WW_BOSS = [  # actno, poses, sproffset, Saturn kind
    (52, 17, 0x03ec, 240), (53, 2, 0x2300, 241), (54, 4, 0x2300, 242),
    (55, 4, 0x2300, 243), (56, 1, 0x2300, 244), (57, 2, 0x4440, 245),
    (61, 1, 0x0440, 247), (62, 2, 0x4458, 248), (63, 8, 0x2300, 250),
    (64, 5, 0x4470, 251),
]


def wacky_workbench_boss(disc, report):
    from zone_object_source import dependencies
    out = {}
    for name in ('R63C', 'R63D'):
        mmd = disc[f'{name}__.MMD']
        indexes = [i for i in range(0, 0x10000, 2)
                   if (lambda v: v[0] == v[1] and len(set(v)) > 20 and
                       all(ORIGIN <= a < ORIGIN + len(mmd) for a in v))(
                           struct.unpack_from('>64I', mmd, i))]
        if len(indexes) != 1:
            raise SystemExit(f'{name}: ObjectIndex candidates {indexes}')
        index = indexes[0]
        routine = lambda oid: struct.unpack_from('>I', mmd, index + 4 * (oid - 1))[0] - ORIGIN
        tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(
            rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
        if len(tables) != 1:
            raise SystemExit(f'{name}: PLC table {tables}')
        table = tables.pop() - ORIGIN
        def entries(plc):
            at = table + struct.unpack_from('>H', mmd, table + 2 * plc)[0]
            return [struct.unpack_from('>IH', mmd, at + 2 + 6 * j)
                    for j in range(struct.unpack_from('>h', mmd, at)[0] + 1)]
        if not any(dest == 0x330 * 32 for _, dest in entries(2)):
            raise SystemExit(f'{name}: PLC 2 has no $330 boss bank')
        if [dest // 32 for _, dest in entries(19)] != [0x300, 0x3ec, 0x440]:
            raise SystemExit(f'{name}: PLC 19 boss banks differ')
        vram = bytearray(65536); loaded = {}
        entry_vram = None
        entry_loaded = None
        for plc in (1, 2, 19):
            for source, dest in entries(plc):
                art = nemesis(mmd[source - ORIGIN:])
                if dest + len(art) > len(vram):
                    raise SystemExit(f'{name}: PLC {plc} art exceeds VRAM')
                vram[dest:dest + len(art)] = art
                loaded[f'{dest // 32:#x}'] = dict(plc=plc, address=f'{source:#08x}',
                                                  tiles=len(art) // 32,
                                                  sha256=hashlib.sha256(art).hexdigest())
            if plc == 2:
                entry_vram = bytes(vram)
                entry_loaded = dict(loaded)
        records = []
        for oid, count, tile, kind in WW_BOSS:
            start = routine(oid)
            end = min([routine(k) for k in range(3, 65) if routine(k) > start] + [start + 0x600])
            code = mmd[start:end]
            words = [struct.unpack('>H', m[1])[0] for m in re.finditer(
                rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start() % 2 == 0]
            maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(
                rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start() % 2 == 0]
            if not words or words[0] != tile or not maps:
                raise SystemExit(f'{name}: actor {oid} tile/map {words[:2]} {maps[:2]}')
            at = maps[0] - ORIGIN
            actual = struct.unpack_from('>H', mmd, at)[0] // 2
            if actual != count:
                raise SystemExit(f'{name}: actor {oid} mappings {actual}, expected {count}')
            frames = [mmd[at + off:at + off + 1 + 5 * mmd[at + off]].hex()
                      for off in (struct.unpack_from('>H', mmd, at + 2 * k)[0]
                                  for k in range(count))]
            records.append(dict(kind=kind, retail_id=oid, tile=tile,
                                address=maps[0], frames=frames))
        # The same actor IDs switch patbase. Retail fight traces observed
        # actor 57 at primary+0x10 (falling debris split into four pieces)
        # and actor 62 at primary-0x10 (the door's beam emitter) in both eras.
        for oid, kind, count, delta in ((57, 246, 4, 0x10),
                                        (62, 249, 2, -0x10)):
            primary = next(r for r in records if r['retail_id'] == oid)
            address = primary['address'] + delta; at = address - ORIGIN
            actual = struct.unpack_from('>H', mmd, at)[0] // 2
            if actual != count:
                raise SystemExit(f'{name}: actor {oid} alternate mappings {actual}, expected {count}')
            frames = [mmd[at + off:at + off + 1 + 5 * mmd[at + off]].hex()
                      for off in (struct.unpack_from('>H', mmd, at + 2 * k)[0]
                                  for k in range(count))]
            records.append(dict(kind=kind, retail_id=oid, tile=primary['tile'],
                                address=address, frames=frames))
        pc = (PC.parent / f'R6/COL6{name[3]}.C').read_text(encoding='latin1')
        body = re.search(r'boss6col\[16\]\s*=\s*\{(.*?)\};', pc, re.S)[1]
        colors = b''.join(struct.pack('>H', (int(b) // 16) << 8 |
                                      (int(g) // 16) << 4 | int(r) // 16)
                          for r, g, b in re.findall(
                              r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\}', body))
        if len(colors) != 32 or colors not in mmd:
            raise SystemExit(f'{name}: boss6col differs from retail')
        path = ROOT / f'build/zone-object-source/{name}-boss'
        path.mkdir(parents=True, exist_ok=True)
        (path / 'vram.bin').write_bytes(bytes(vram))
        source = dict(program=name, objects=[r for r in records if r['kind'] != 251], art=loaded,
                      generator='tools/extract_mmd.py', dependencies=dependencies(),
                      program_sha256=hashlib.sha256(mmd).hexdigest(),
                      vram_sha256=hashlib.sha256(vram).hexdigest(),
                      tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (path / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
        # Before PLC 19 completes, the four entry actors use PLC 1/2 art.
        # Live C/D captures through the load show these mapping poses.
        entry_poses = {52: (0, 1, 2, 3), 53: (0,), 54: (0,), 55: (0, 1, 2, 3)}
        entry_records = [dict(r, kind=r['kind'] | 0x100,
                              frame_ids=list(entry_poses[r['retail_id']]),
                              frames=[r['frames'][i] for i in entry_poses[r['retail_id']]])
                         for r in records if r['retail_id'] in entry_poses]
        entry_path = ROOT / f'build/zone-object-source/{name}-boss-entry'
        entry_path.mkdir(parents=True, exist_ok=True)
        (entry_path / 'vram.bin').write_bytes(entry_vram)
        entry_source = dict(source, objects=entry_records, art=entry_loaded,
                            vram_sha256=hashlib.sha256(entry_vram).hexdigest())
        (entry_path / 'source.json').write_text(json.dumps(entry_source, indent=2) + '\n')
        # Retail actor 64 retains one mapping address while its $470-$477
        # sprite tiles cycle through three 256-byte blocks. C and D live
        # captures locate those blocks at $233C0C/$233D0C/$233E0C; the
        # host BOSS_6.C patbase cycle supplies kinds 251/252/253 natively.
        beam_at = 0x233c0c - ORIGIN
        beam_art = mmd[beam_at:beam_at + 3 * 256]
        if hashlib.sha256(beam_art).hexdigest() != 'c905a527ec0937a9bbdceee6c8bfa6da50bf8198c451a5e886e65165795edd36':
            raise SystemExit(f'{name}: beam animation art differs from retail capture')
        beam = next(r for r in records if r['kind'] == 251)
        for phase in range(3):
            art = beam_art[phase * 256:(phase + 1) * 256]
            beam_vram = bytearray(vram)
            beam_vram[0x470 * 32:0x478 * 32] = art
            beam_path = ROOT / f'build/zone-object-source/{name}-boss-beam{phase}'
            beam_path.mkdir(parents=True, exist_ok=True)
            (beam_path / 'vram.bin').write_bytes(beam_vram)
            beam_source = dict(source, objects=[dict(beam, kind=251 + phase)],
                               art=dict(loaded, beam=dict(address=f'{ORIGIN + beam_at + phase * 256:#08x}',
                                                           tiles=8, sha256=hashlib.sha256(art).hexdigest())),
                               vram_sha256=hashlib.sha256(beam_vram).hexdigest())
            (beam_path / 'source.json').write_text(json.dumps(beam_source, indent=2) + '\n')
        (OUT / f'boss6{name[3]}.pal').write_bytes(colors)
        out[name] = dict(frames={r['kind']: len(r['frames']) for r in records} |
                                {252: len(beam['frames']), 253: len(beam['frames'])})
    report['boss6'] = dict(out, checks=['ObjectIndex routines set BOSS_6.C tile words',
                                        'mapping counts equal BOSS_6.C patterns',
                                        'retail C/D actor traces identify gareki4 and beamer tables',
                                        'fight art from retail PLC lists 1, 2 and 19',
                                        'three beam art states equal retail VRAM and MMD bytes',
                                        'boss6col found in each retail program'])


# R73C/D ACT73.C and BOSS_7.C. The complete race bank is installed by PLC 2;
# PLC 1 supplies hahen73. All seven mapping tables are the initializers' own.
SS_BOSS_KIND = {44: 240, 45: 241, 46: 242, 47: 243, 48: 244, 49: 245, 55: 246}
SS_BOSS = [(44, 2, 0x300), (45, 6, 0x2300), (46, 2, 0x2300),
           (47, 24, 0x37c), (48, 2, 0x37c), (49, 5, 0x37c), (55, 4, 0x451c)]


def stardust_speedway_boss(disc, report):
    from zone_object_source import dependencies, read_tiles
    result = {}
    for name in ('R73C', 'R73D'):
        mmd = disc[name+'__.MMD']
        indexes = [i for i in range(0, 0x10000, 2)
                   if (lambda v: v[0] == v[1] and len(set(v)) > 20 and
                       all(ORIGIN <= a < ORIGIN+len(mmd) for a in v))(
                           struct.unpack_from('>60I', mmd, i))]
        assert len(indexes) == 1, (name, 'ACT73 ObjectIndex', indexes)
        routines = struct.unpack_from('>60I', mmd, indexes[0])
        tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(
            rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
        assert len(tables) == 1, (name, 'PLC table', tables)
        table = tables.pop()-ORIGIN
        vram = bytearray(65536); loaded = []; resident = set()
        for plc in (1, 2):
            at = table+struct.unpack_from('>H', mmd, table+2*plc)[0]
            entries = [struct.unpack_from('>IH', mmd, at+2+6*j)
                       for j in range(struct.unpack_from('>h', mmd, at)[0]+1)]
            if plc == 2:
                assert [dest//32 for _,dest in entries] == [0x300,0x37c], (name, 'race banks')
            for address,dest in entries:
                art = nemesis(mmd[address-ORIGIN:])
                assert dest+len(art) <= len(vram)
                vram[dest:dest+len(art)] = art
                resident.update(range(dest,dest+len(art),32))
                loaded.append(dict(plc=plc,address=address,destination=dest,tiles=len(art)//32,
                                   sha256=hashlib.sha256(art).hexdigest()))
        records = []
        for oid,count,tile in SS_BOSS:
            start = routines[oid-1]-ORIGIN
            end = min([a-ORIGIN for a in routines if a-ORIGIN > start]+[start+0x2000])
            code = mmd[start:end]
            words = [struct.unpack('>H', m[1])[0] for m in re.finditer(
                rb'[\x31\x33]\x7c(..)\x00\x02', code, re.S) if m.start()%2 == 0]
            maps = [struct.unpack('>I', m[1])[0] for m in re.finditer(
                rb'[\x21\x23]\x7c(....)\x00\x04', code, re.S) if m.start()%2 == 0]
            assert words and words[0] == tile and maps, (name, oid, words, maps)
            at = maps[0]-ORIGIN
            assert struct.unpack_from('>H',mmd,at)[0] == count*2, (name,oid,'mapping count')
            frames = [mmd[at+off:at+off+1+5*mmd[at+off]].hex()
                      for off in struct.unpack_from(f'>{count}H',mmd,at)]
            record = dict(kind=SS_BOSS_KIND[oid],retail_id=oid,tile=tile,address=maps[0],frames=frames)
            assert read_tiles(record) <= resident, (name,oid,'mapping reads unloaded PLC tiles')
            records.append(record)
        pc = (PC.parent/f'R7/COL7{name[-1]}.C').read_text(encoding='latin1')
        body = re.search(r'bosscolor\[6\]\s*=\s*\{(.*?)\};',pc,re.S)[1]
        colors = b''.join(struct.pack('>H',(int(b)//16)<<8|(int(g)//16)<<4|int(r)//16)
                          for r,g,b in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\}',body))
        assert len(colors) == 12 and colors in mmd, (name,'six-color boss palette')
        assert re.search(r'\{\s*bosscolor,\s*16,\s*6\s*\}',pc), (name,'palette destination')
        path = ROOT/f'build/zone-object-source/{name}-boss';path.mkdir(parents=True,exist_ok=True)
        (path/'vram.bin').write_bytes(vram)
        source = dict(program=name,objects=records,art=loaded,generator='tools/extract_mmd.py',
                      dependencies=dependencies(),program_sha256=hashlib.sha256(mmd).hexdigest(),
                      vram_sha256=hashlib.sha256(vram).hexdigest(),
                      tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                      palette_patch=dict(offset=16,count=6,words=colors.hex()))
        (path/'source.json').write_text(json.dumps(source,indent=2)+'\n')
        (OUT/f'boss7{name[-1]}.pal').write_bytes(colors)
        result[name] = dict(kinds=[r['kind'] for r in records],poses=sum(len(r['frames']) for r in records),
                            program_sha256=source['program_sha256'],vram_sha256=source['vram_sha256'])
    report['boss7'] = dict(programs=result,checks=['ACT73 60-entry ObjectIndex',
        'initializer mapping/tile words and BOSS_7 pose counts','every mapped tile belongs to PLC 1/2',
        'COL7C/D six-entry bosscolor found in retail; entries 16-21 only'])


# R83C/D BOSS_8.C (ACT83.C ids 63-66). PLC 4 installs the fight bank: egg8,
# egg8meca and egg8hibana at $3DE, egg8hane at $220 over PLC 1/2's stage art.
# Kinds follow src/boss_r8.c scd_boss8_kind: 240 egg8, 241-246 the six
# hane_base_tbl tables (egg8hane0_pat1/2/3, egg8hane1_pat, egg8hane2_pat1/2),
# 247 egg8meca, 248 egg8hibana. Tables are the initializers' own immediates.
MM_BOSS = [(240, 63, 990, 9), (247, 65, 9182, 4), (248, 66, 990, 2)]


def metallic_madness_boss(disc, report):
    from zone_object_source import dependencies, read_tiles
    result = {}
    for name in ('R83C', 'R83D'):
        mmd = disc[name+'__.MMD']
        tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(
            rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', mmd, re.S)}
        assert len(tables) == 1, (name, 'PLC table', tables)
        table = tables.pop()-ORIGIN
        vram = bytearray(65536); loaded = []; fight = set(); ending = set()
        for plc in (1, 2, 4, 5):
            if plc == 5:fight_vram = bytes(vram)
            at = table+struct.unpack_from('>H', mmd, table+2*plc)[0]
            entries = [struct.unpack_from('>IH', mmd, at+2+6*j)
                       for j in range(struct.unpack_from('>h', mmd, at)[0]+1)]
            for address, dest in entries:
                art = nemesis(mmd[address-ORIGIN:])
                assert dest+len(art) <= len(vram)
                vram[dest:dest+len(art)] = art
                if plc == 4:fight.update(range(dest, dest+len(art), 32))
                if plc == 5:ending.update(range(dest, dest+len(art), 32))
                loaded.append(dict(plc=plc, address=address, destination=dest, tiles=len(art)//32,
                                   sha256=hashlib.sha256(art).hexdigest()))
        def frames_at(address, count):
            at = address-ORIGIN
            assert struct.unpack_from('>H', mmd, at)[0] == count*2, (name, hex(address), 'mapping count')
            return [mmd[at+off:at+off+1+5*mmd[at+off]].hex() for off in struct.unpack_from(f'>{count}H', mmd, at)]
        records = []
        for kind, oid, tile, count in MM_BOSS:
            # move.w #tile,2(a0); move.l #table,4(a0) (BOSS_8.C sproffset, patbase).
            hits = [struct.unpack('>I', m[1])[0] for m in re.finditer(
                re.escape(b'\x31\x7c'+struct.pack('>H', tile)+b'\x00\x02\x21\x7c')+rb'(....)\x00\x04', mmd, re.S)]
            hits = [a for a in hits if ORIGIN <= a < ORIGIN+len(mmd) and struct.unpack_from('>H', mmd, a-ORIGIN)[0] == count*2]
            assert len(hits) == 1, (name, kind, [hex(a) for a in hits])
            records.append(dict(kind=kind, retail_id=oid, tile=tile, address=hits[0], frames=frames_at(hits[0], count)))
        # egg8hane's six 16-pose tables: every move.l/cmpi.l #table,4(a0) whose
        # target holds 16 poses. They lie in BOSS_8.C declaration order
        # (hane_base_tbl): egg8hane0_pat1/2/3, egg8hane1_pat, egg8hane2_pat1/2.
        hane = sorted({struct.unpack('>I', m[1])[0] for m in re.finditer(rb'(?:\x21\x7c|\x0c\xa8)(....)\x00\x04', mmd, re.S)
                       if m.start() % 2 == 0 and ORIGIN <= struct.unpack('>I', m[1])[0] < ORIGIN+len(mmd)-2
                       and struct.unpack_from('>H', mmd, struct.unpack('>I', m[1])[0]-ORIGIN)[0] == 32})
        assert len(hane) == 6, (name, 'egg8hane tables', [hex(a) for a in hane])
        # egg8hane_ini: move.w #8736,2(a0); move.l #egg8hane0_pat1,4(a0).
        assert re.search(re.escape(b'\x31\x7c\x22\x20\x00\x02\x21\x7c'+struct.pack('>I', hane[0])+b'\x00\x04'), mmd), (name, 'egg8hane0_pat1')
        # Line 3430: patbase != egg8hane1_pat ? egg8hane0_pat3 : egg8hane2_pat1.
        assert re.search(re.escape(b'\x0c\xa8'+struct.pack('>I', hane[3])+b'\x00\x04')+rb'\x67.\x21\x7c'
                         +re.escape(struct.pack('>I', hane[2])+b'\x00\x04')+rb'\x60.\x21\x7c'+re.escape(struct.pack('>I', hane[4])), mmd, re.S), (name, 'egg8hane1 selector')
        for n, address in enumerate(hane):
            records.append(dict(kind=241+n, retail_id=64, tile=8736, address=address, frames=frames_at(address, 16)))
        for record in records:
            assert read_tiles(record) <= fight, (name, record['kind'], 'mapping reads tiles PLC 4 does not load')
        # egg8's third hit loads PLC 5 (retail case 1 of the hit count; R83C
        # $20B36A) over hane's tiles: Amy's (EMIE8.C emie8_ini: tile 8736,
        # emie8_pat, 8 poses; kind 249) with egg8, egg8meca and egg8hibana.
        amy = [struct.unpack('>I', m[1])[0] for m in re.finditer(
            rb'\x31\x7c\x22\x20\x00\x02\x21\x7c(....)\x00\x04\x54\x28', mmd, re.S)]
        assert len(amy) == 1, (name, 'emie8_ini', amy)
        late = [r for r in records if r['kind'] in (240, 247, 248)]
        late.append(dict(kind=249, retail_id=67, tile=8736, address=amy[0], frames=frames_at(amy[0], 8)))
        assert read_tiles(late[-1]) <= ending, (name, 'emie8 reads tiles PLC 5 does not load')
        assert not any(read_tiles(r) & ending for r in late[:-1]), (name, 'PLC 5 overwrote boss tiles')
        for suffix, objects, image in (('-boss', records, fight_vram), ('-boss-ending', late, bytes(vram))):
            path = ROOT/f'build/zone-object-source/{name}{suffix}';path.mkdir(parents=True,exist_ok=True)
            (path/'vram.bin').write_bytes(image)
            source = dict(program=name,objects=objects,art=[a for a in loaded if suffix == '-boss-ending' or a['plc'] != 5],
                          generator='tools/extract_mmd.py',
                          dependencies=dependencies(),program_sha256=hashlib.sha256(mmd).hexdigest(),
                          vram_sha256=hashlib.sha256(image).hexdigest(),
                          tool_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
            (path/'source.json').write_text(json.dumps(source,indent=2)+'\n')
        result[name] = dict(kinds=[r['kind'] for r in records],poses=sum(len(r['frames']) for r in records),
                            program_sha256=source['program_sha256'],vram_sha256=source['vram_sha256'])
    report['boss8'] = dict(programs=result,checks=['initializer tile/mapping immediates and BOSS_8 pose counts',
        'hane_base_tbl six 16-pose tables','every mapped tile belongs to PLC 4',
        'emie8_ini table read from PLC 5 (-boss-ending), boss tiles untouched by it'])


def main():
    if ISO.exists():
        iso = ISO.read_bytes()
    else:
        # tools/prepare_audio.py extracts the private disc as MODE1/2352 sectors.
        raw = (ISO.parent / 'sonic.bin').read_bytes()
        iso = b''.join(raw[i+16:i+2064] for i in range(0, len(raw), 2352))
    disc = disc_files(iso)
    template = disc['R11A__.MMD']
    labels = template_labels(template)
    report = {'source': 'build/retail/sonic.iso', 'template': 'R11A__.MMD', 'programs': {}}
    for program in PROGRAMS:
        mmd = disc[f'{program}__.MMD']
        x = extract(template, mmd, labels)
        tiles, blocks = nemesis(x['tiles_raw']), nemesis(x['blocks_raw'])
        entry = {'mmd_sha256': hashlib.sha256(mmd).hexdigest(), 'addresses': x['addresses'], 'palette_id': x['palette_id'],
                 'debug_items': x['debug_count'], 'chunks': len(x['chunks'])//512, 'tiles': len(tiles)//32, 'blocks': len(blocks)//8,
                 'foreground': [x['foreground'][0]+1, x['foreground'][1]+1], 'background': [x['background'][0]+1, x['background'][1]+1],
                 'start': list(struct.unpack('>HH', x['start'])), 'spec_chunks': x['spec_chunks'].hex(), 'object_records': len(x['objects'])//8 - 1}
        if program.startswith('R11'):
            era = ERAS[program[3]]; load = lambda name: (DATA / name).read_bytes()
            start = 'Present' if era == 'Present' else 'Past'
            checks = {
                'tiles': x['tiles_raw'].startswith(load(f'Tiles (Act 1 {era}).nem')),
                'blocks': x['blocks_raw'].startswith(load(f'Blocks (Act 1 {era}).nem')),
                'chunks': x['chunks'] == load(f'Chunks (Act 1 {era}).bin'),
                'foreground': x['foreground'] == load(f'Foreground (Act 1 {era}).bin'),
                'background': x['background'] == load(f'Background (Act 1 {era}).bin'),
                'collision': x['collision'] == load(f'Collision (Act 1 {era}).bin').rstrip(b'\0'),
                'start': x['start'] == load(f'Start Position (Act 1 {start}).bin'),
                'objects': x['objects'] == load('Objects (Act 1).bin'),
                'level_palette': x['level_palette'] == load(f'Palette ({era}).bin'),
                'sonic_palette': x['sonic_palette'] == (LEVEL/'_Objects/Sonic/Data/Palette.bin').read_bytes(),
            }
            if not all(checks.values()):
                raise SystemExit(f'{program} differs from the disassembly: {[k for k, v in checks.items() if not v]}')
            entry['disassembly_match'] = sorted(checks)
        pc = (PC / f'Z{program[1:]}TBL.C').read_text(encoding='latin1')
        zone = pc_table(pc, 'zone1scd')
        checks = {
            'collision': zone[:len(x['collision'])] == x['collision'] and not any(zone[len(x['collision']):]),
            'foreground': expand(x['foreground']) == pc_table(pc, 'mapwka'),
            'background': expand(x['background']) == pc_table(pc, 'mapwkb'),
            'angles': pc_table(pc, 'scddirtbl') == x['maps']['Angles'],
            'height': pc_table(pc, 'scdtblwk')[:4096] == x['maps']['Height Map'],
            'width': pc_table(pc, 'scdtblwk2')[:4096] == x['maps']['Width Map'],
        }
        rows = [tuple(map(int, m.groups())) for m in re.finditer(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}',
                (PC / f'Z{program[1:3]}ACT.C').read_text(encoding='latin1'))]
        records = [struct.unpack_from('>HHBBBB', x['objects'], i) for i in range(0, len(x['objects']), 8)]
        # Both tables end with an X=0xFFFF record; Z11ACT.C fills its other fields with 0xFF.
        differences = [i for i, (a, b) in enumerate(zip(rows[:-1], records[:-1])) if a != b]
        checks['objects'] = (len(rows) == len(records) and rows[-1][0] == records[-1][0] == 0xFFFF
                             and differences == KNOWN_PC_OBJECT_DIFFERENCES[program[:3]])
        if not all(checks.values()):
            raise SystemExit(f'{program} differs from the PC tables: {[k for k, v in checks.items() if not v]} {differences}')
        entry['pc_match'] = sorted(checks)
        entry['pc_object_differences'] = [{'record': i, 'pc': rows[i], 'retail': records[i]} for i in differences]
        if not program.startswith('R11'):
            key = program[1:]
            colors = palette(x['sonic_palette'] + x['level_palette'])
            parts = [tiles, blocks, x['chunks'], expand(x['foreground']), expand(x['background']), colors]
            if len(colors) != 128:
                raise SystemExit(f'{program}: expected 64 palette entries')
            header, offset = b'PPZ1', 56
            for part in parts:
                header += struct.pack('>II', offset, len(part)); offset += len(part)
            pack = header + x['start'] + b''.join(parts)
            collision = x['collision'].ljust(1024, b'\0') + x['maps']['Height Map'] + x['maps']['Width Map'] + x['maps']['Angles']
            (OUT / f'ppz{key}.bin').write_bytes(pack)
            (OUT / f'collision{key}.bin').write_bytes(collision)
            (OUT / f'objects{key}.bin').write_bytes(x['objects'])
            entry['outputs'] = {f'ppz{key}.bin': hashlib.sha256(pack).hexdigest(), f'collision{key}.bin': hashlib.sha256(collision).hexdigest(),
                                f'objects{key}.bin': hashlib.sha256(x['objects']).hexdigest()}
        report['programs'][program] = entry
    # Act 2 swing (object 0x29, BRANKO1.C): mappings from the R12A routine,
    # art = the platform sheet at tile $44BE. Validate the locator on R11A's
    # springboard (0x28) and spinning disc (0x09) against the disassembly first.
    for object_id, folder in [(0x28, 'Springboard'), (0x09, 'Spinning Disc')]:
        _, found = object_mappings(template, object_id)
        expected = [bytes(f[:1 + 5 * f[0]]) for f in assembly_frames(LEVEL / f'Palmtree Panic/Objects/{folder}/Data/Mappings.asm')]
        if found[:len(expected)] != expected:
            raise SystemExit(f'R11A {folder} mappings differ from the disassembly')
    code, swing = object_mappings(disc['R12A__.MMD'], 0x29)
    if [f[0] for f in swing[:3]] != [1, 2, 1] or code.find(b'\x31\x7c\x44\xbe\x00\x02') < 0:
        raise SystemExit('R12A swing mappings not found')
    platform_art = (LEVEL / 'Palmtree Panic/Objects/Platform/Data/Art.nem').read_bytes()
    if platform_art not in disc['R12A__.MMD']:
        raise SystemExit('R12A platform art differs from the disassembly')
    (OUT / 'swing12A.map').write_bytes(b''.join(swing[:3]))
    report['swing'] = {'object': '0x29', 'frames': [f.hex() for f in swing[:3]], 'tile': '0x44BE', 'art': 'Palmtree Panic/Objects/Platform/Data/Art.nem'}
    # Act 2 collapsing platform (object 0x20): the debug item mappings (ledge, one
    # frame; single-row platform, two frames) and the piece mappings the break-up
    # code loads with move.l #map,oMap(a1). All four Act 2 eras are identical, and
    # the two single-row size tables (7,2 and 7,1 in KUZUR12A-D.C) are on the disc.
    sets = []
    for program in ['R12A', 'R12B', 'R12C', 'R12D']:
        mmd = disc[f'{program}__.MMD']; x = extract(template, mmd, labels)
        debug = int(x['addresses']['debug'], 16) - ORIGIN
        maps = sorted({struct.unpack_from('>I', mmd, debug + 4 + i*12)[0] for i in range(mmd[debug]) if mmd[debug + 2 + i*12] == 0x20})
        routine = struct.unpack_from('>I', mmd, object_index(mmd) + (0x20 - 1) * 4)[0] - ORIGIN
        pieces = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'\x23\x7c(....)\x00\x04', mmd[routine:routine + 0x600], re.S) if m.start() % 2 == 0]
        def frames_at(address):
            at = address - ORIGIN; count = struct.unpack_from('>H', mmd, at)[0] // 2
            return [bytes(mmd[at + o:at + o + 1 + 5 * mmd[at + o]]) for o in (struct.unpack_from('>H', mmd, at + 2 * k)[0] for k in range(count))]
        families = sorted((frames_at(a) for a in maps), key=len) + [frames_at(a) for a in pieces]
        if [len(f) for f in families] != [1, 2, 7, 2]:
            raise SystemExit(f'{program}: unexpected collapse mappings {[len(f) for f in families]}')
        for table in (bytes([7, 2] + [0] * 8), bytes([7, 1] + [1] * 8)):
            if table not in mmd:
                raise SystemExit(f'{program}: collapse size table {table.hex()} not found')
        sets.append(families)
    if any(s != sets[0] for s in sets):
        raise SystemExit('Act 2 collapse mappings differ between eras')
    (OUT / 'collapse12.map').write_bytes(b''.join(bytes([len(f)]) + b''.join(f) for f in sets[0]))
    report['collapse_act2'] = {'families': [len(f) for f in sets[0]], 'shapes': [[7, 2], [7, 1]]}
    # Act 3 boss (objects 0x2A-0x32, BOSS_1.C). The PLC list that loads the flower capsule
    # art (tile $481, equal to the disassembly) also loads the boss parts ($359) and
    # Robotnik ($3FD). Each part routine sets its own mappings; the two arm 3 tables are
    # set by the parent's part builder (move.l #map,oMap(a1)). PaletteTable entry 5 is the
    # boss palette of COL1C.C/COL1D.C.
    capsule_art = (LEVEL / '_Objects/Level End/Data/Art (Flower Capsule).nem').read_bytes()
    capsule_palette = (LEVEL / '_Objects/Level End/Data/Palette (Flower Capsule).bin').read_bytes()
    pc_word = lambda rgb: struct.pack('>H', (rgb[2] // 16) << 8 | (rgb[1] // 16) << 4 | rgb[0] // 16)
    pc_colors = lambda text, name: b''.join(pc_word(tuple(map(int, m))) for m in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\}',
                                            re.search(re.escape(name) + r'\[16\]\s*=\s*\{(.*?)\};', text, re.S)[1]))
    if pc_colors((PC.parent / 'GOAL.C').read_text(encoding='latin1'), 'colortbl') != capsule_palette:
        raise SystemExit('Flower capsule palette differs from GOAL.C genecolor')
    boss = {}
    for program in ['R13C', 'R13D']:
        mmd = disc[f'{program}__.MMD']
        entry = unique(mmd, struct.pack('>IH', ORIGIN + unique(mmd, capsule_art), 0x481 * 32))
        plc = [struct.unpack_from('>IH', mmd, entry + 6 * i) for i in range(struct.unpack_from('>H', mmd, entry - 2)[0] + 1)]
        if [v // 32 for _, v in plc] != [0x481, 0x359, 0x3FD]:
            raise SystemExit(f'{program}: boss PLC list {[hex(v // 32) for _, v in plc]}')
        index = object_index(mmd)
        routine = lambda oid: struct.unpack_from('>I', mmd, index + (oid - 1) * 4)[0] - ORIGIN
        def frames_at(address):
            at = address - ORIGIN; count = struct.unpack_from('>H', mmd, at)[0] // 2
            return [bytes(mmd[at + o:at + o + 1 + 5 * mmd[at + o]]) for o in (struct.unpack_from('>H', mmd, at + 2 * k)[0] for k in range(count))]
        tables = [object_mappings(mmd, oid)[1] for oid in (0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30)]
        builder = mmd[routine(0x2A):routine(0x2B)]
        arm3 = [struct.unpack('>I', m[1])[0] for m in re.finditer(rb'\x23\x7c(....)\x00\x04', builder, re.S) if m.start() % 2 == 0]
        if len(arm3) != 2:
            raise SystemExit(f'{program}: arm 3 mappings {arm3}')
        tables += [frames_at(a) for a in arm3] + [object_mappings(mmd, 0x32)[1]]
        # BOSS_1.C pattern tables: egg1 11, body/legs/arms 1 each, arm 3 two sets of 3.
        if [len(t) for t in tables] != [11, 1, 1, 1, 1, 1, 1, 3, 3, 1]:
            raise SystemExit(f'{program}: boss mapping counts {[len(t) for t in tables]}')
        tiles = {0x2A: b'\x31\x7c\x03\xfd\x00\x02', 0x2B: b'\x31\x7c\x03\x59\x00\x02', 0x2C: b'\x31\x7c\x23\x59\x00\x02'}
        if any(mmd[routine(oid):routine(oid) + 0x600].find(word) < 0 for oid, word in tiles.items()):
            raise SystemExit(f'{program}: boss base tiles changed')
        # egg1_pchg animation scripts (BOSS_1.C) in the retail program.
        if not re.search(rb'\x3b\x00\xff\x00?\x07\x02\x03\xff\x03\x01\x05\x04\x06\xff\x00?\x03\x07\x08\xff\x03\x09\x0a\xff', mmd):
            raise SystemExit(f'{program}: egg1 animation scripts not found')
        x = extract(template, mmd, labels); palettes = int(x['addresses']['palettes'], 16) - ORIGIN
        pointer, destination, longs = struct.unpack_from('>IHH', mmd, palettes + 5 * 8)
        colors = mmd[pointer - ORIGIN:pointer - ORIGIN + (longs + 1) * 4]
        if destination != 0xFB20 or colors != pc_colors((PC / f'COL1{program[3]}.C').read_text(encoding='latin1'), 'zone1colboss1'):
            raise SystemExit(f'{program}: boss palette differs from COL1{program[3]}.C')
        boss[program] = {'tables': b''.join(bytes([len(t)]) + b''.join(t) for t in tables),
                         'parts': nemesis(mmd[plc[1][0] - ORIGIN:]), 'robotnik': nemesis(mmd[plc[2][0] - ORIGIN:]), 'palette': colors,
                         'plc': f'{entry - 2 + ORIGIN:#08x}', 'arm3': [f'{a:#08x}' for a in arm3]}
    for key in ('tables', 'parts', 'robotnik'):
        if boss['R13C'][key] != boss['R13D'][key]:
            raise SystemExit(f'Act 3 boss {key} differ between futures')
    # The native Act 2 and Act 3 futures reuse the Act 1 palette cycles (background.c era & 3):
    # each future program holds the disassembly's cycle data exactly once.
    cycles = {}
    for era, programs in [('Good Future', ['R12C', 'R13C']), ('Bad Future', ['R12D', 'R13D'])]:
        text = (LEVEL / f'Palmtree Panic/Palette Cycle ({era}).asm').read_text()
        for name, body in re.findall(r'(PalCycle\w+):\s*\n((?:\s*dc\.[wb].*\n)+)', text):
            size = 2 if 'dc.w' in body else 1
            values = [int(v.strip().replace('$', '0x'), 0) for line in re.findall(r'dc\.[wb]\s+([^;\n]+)', body) for v in line.split(',') if v.strip()]
            blob = b''.join((v & (1 << 8 * size) - 1).to_bytes(size, 'big') for v in values)
            for program in programs:
                if disc[f'{program}__.MMD'].count(blob) != 1:
                    raise SystemExit(f'{program}: palette cycle {name} differs from Act 1')
            cycles[f'{era}/{name}'] = len(blob)
    report['future_palette_cycles'] = {'programs': ['R12C', 'R12D', 'R13C', 'R13D'], 'blocks': cycles}
    (OUT / 'boss13.map').write_bytes(boss['R13C']['tables'])
    (OUT / 'boss-parts.tiles').write_bytes(boss['R13C']['parts'])
    (OUT / 'boss-robotnik.tiles').write_bytes(boss['R13C']['robotnik'])
    for program in boss:
        (OUT / f'boss{program[1:]}.pal').write_bytes(boss[program]['palette'])
    report['boss'] = {'plc': {p: boss[p]['plc'] for p in boss}, 'arm3_tables': {p: boss[p]['arm3'] for p in boss},
                      'tables': [11, 1, 1, 1, 1, 1, 1, 3, 3, 1], 'parts_tiles': len(boss['R13C']['parts']) // 32,
                      'robotnik_tiles': len(boss['R13C']['robotnik']) // 32, 'palettes': {p: boss[p]['palette'].hex() for p in boss},
                      'checks': ['capsule art equals disassembly', 'PLC tiles $481/$359/$3FD', 'mapping counts equal BOSS_1.C patterns',
                                 'base tiles $3FD/$359/$2359', 'egg1_pchg scripts', 'palettes equal COL1C/COL1D zone1colboss1',
                                 'capsule palette equals GOAL.C genecolor', 'futures share mappings and art']}
    collision_chaos_boss(disc, report)
    tidal_tempest_boss(disc, report)
    quartz_quadrant_boss(disc, report)
    wacky_workbench_boss(disc, report)
    stardust_speedway_boss(disc, report)
    metallic_madness_boss(disc, report)
    cc_bumper_sources(disc, report)
    (ROOT / 'build/mmd-extract.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f"MMD extraction: {len(PROGRAMS)} programs located; R11A-D equal the disassembly; all equal the PC tables "
          f"(known object differences {sum(len(v) for v in KNOWN_PC_OBJECT_DIFFERENCES.values())})")


if __name__ == '__main__':
    main()
