#!/usr/bin/env python3
"""Pack only the current era's zone-object sprites into the gameplay UFO arena."""
import hashlib
import itertools
import json
import struct
import subprocess
import sys
from pathlib import Path

from convert_assets import ROOT, OUT
from convert_objects import pack_texture
from extract_mmd import disc_files
from zone_object_source import dependencies
import zone_art_lz

ARENA_BYTES = 0x80000-0x71000
# src/stage_packs.h PACK_ZONE_ART capacity (120,832 B since the PPZ1-3 regions
# gave it 16 KB for the TT exit2 splash and flowers).
PACK_ZONE_ART_BYTES = 0x1D800
SOURCE = ROOT/'build/zone-object-source'
# Families stored per original mapping piece: consecutive part records with the
# same kind and pose, drawn back to front (src/zone_object_view.inc). As
# composited poses funsui4 needs 47,136 B of the arena, et4 14,304 B and kuzure4
# (nine poses of a growing ledge) 9,632 B; a few distinct pieces each. The
# water-surface wave is six 32 px pieces per 192 px pose: 768 B instead of 6,144.
# Quartz Quadrant Act 3: egg5 (kind 244, 16 poses) stored per piece keeps R53C/D's zone
# art and boss (70,816 B composited) inside the 61,440 B VDP1 arena (52,608 B).
# TT also stores the PLAYSUB flower (31, priority 287) and exit2 splash (132)
# per piece: R42A's era holds both only so (composited, 62,560 of 61,440 B).
PIECES = {4: {119: 'funsui4', 127: 'et4', 108: 'kuzure4', 103: 'rblk4', 133: 'wave', 31: 'flower', 132: 'exit2'},
          # KDAI6 per piece (+12 records) frees 2,560 B of R61B's VDP1 era for the flower.
          5: {244: 'egg5'}, 6: {240: 'egg6boss', 139: 'kdai6'}, 7: {145: 'slight7'},
          # Metallic Madness: nokogiri's 18 saw poses composite to 112,896 B.
          8: {159: 'nokogiri', 166: 'okusieso', 71: 'piston', 169: 'et8', 240: 'egg8', 247: 'egg8meca'}}
DEFERRED = {}
# (round, kind & 255): per-piece families whose pieces share one CLUT per palette
# line (TT's flower and splash: one CLUT per piece put R42A 64 B past the region).
SHARED_CLUT = {(4, 31), (4, 132), (6, 139)}


def source_paths(name):
    paths=[SOURCE/name]
    if name=='R31A':paths.append(SOURCE/(name+'-mecasnc'))
    if name in ('R33C','R33D'):paths.append(SOURCE/(name+'-sikake'))
    # R51D/R52D have no friend5 fixture, as in the original: SUICIDE.C
    # friend_suicide frames out every animal whose subtype lacks bit 7 once
    # time_flag >= 2 without generate_flag (the Bad Future), the R5 layouts
    # place friend5 only with subtypes 0/1, the bit-7 projector animals need
    # a projector the future has not got, and FRIEND5.C set_sproffset gives
    # the Bad Future tile base 0 (tbl0sproffset[3], [7]).
    if name.startswith(('R31','R32','R4')) or (name.startswith(('R51','R52')) and not name.endswith('D')):
        paths.append(SOURCE/(name+'-friend'))
        if name.endswith('B') and name.startswith('R3'):paths.append(SOURCE/(name+'-movie'))
    if name.startswith(('R71','R72')) and not name.endswith('D'):
        paths.append(SOURCE/(name+'-friend'))
    # R4 families whose original PLC bank loads after the capture frame
    # (tools/zone_object_source.py plc_overlay), written with the main fixture.
    if name.startswith(('R4','R5','R7','R8')) and (SOURCE/(name+'-plc')/'source.json').exists():
        paths.append(SOURCE/(name+'-plc'))
    # The Act 3 boss (BOSS_3.C, GATE.C), written by tools/extract_mmd.py.
    if name.startswith('R33'):paths.append(SOURCE/(name+'-boss'))
    # Tidal Tempest's (BOSS_4.C/WALL4.C with PLC 2, BOSS_4_2.C with PLC 4), the same tool.
    if name.startswith('R43'):paths+=[SOURCE/(name+'-boss'),SOURCE/(name+'-boss2')]
    # Quartz Quadrant's (BOSS_5.C, PLC 4 over PLC 2 as in every retail fight phase).
    if name.startswith('R53'):paths.append(SOURCE/(name+'-boss'))
    if name.startswith('R73'):paths.append(SOURCE/(name+'-boss'))
    # PLAYSUB flowers (tools/ss_flower_source.py): a badnik explosion grows one
    # in these acts, which have no capsule-flower art of their own. R61B fits
    # with KDAI6 stored per piece (PIECES).
    # R41 and R42A/B fit since PACK_ZONE_ART grew to 120,832 B (flower and
    # splash stored per piece in TT, PIECES).
    # R31's four eras share a 62,240 B arena: ZAR5 (zar5_layout).
    if name.startswith(('R7','R8','R31','R32','R41','R42','R5','R61','R62')):paths.append(SOURCE/(name+'-flower'))
    if name.startswith('R63'):
        paths.append(SOURCE/(name+'-boss'))
        paths.append(SOURCE/(name+'-boss-entry'))
        paths += [SOURCE/(name+f'-boss-beam{i}') for i in range(3)]
    # Acts 1-2: BOBINB.C break frames for PLAYSP3.C's bumper blocks (tools/extract_mmd.py).
    if name.startswith(('R31','R32')):paths.append(SOURCE/(name+'-bumper'))
    return paths


def source_frames(record, vram):
    """Flatten retail mapping pieces in source draw order to CRAM indices.

    Zero means transparent; visible values are CRAM index + 1 so opaque index
    zero cannot become transparent. Global flips are applied by the Saturn.
    """
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        if not mapping[0]:
            # Represent an original zero-piece pose with a transparent cell.
            yield 0, 0, 8, 8, bytes(64)
            continue
        pieces = []
        for i in range(mapping[0]):
            y, size, word, x = struct.unpack_from('>bBHb', mapping, 1+5*i)
            pieces.append((x, y, ((size>>2)&3)*8+8, (size&3)*8+8, (word+record['tile'])&65535))
        left = min(p[0] for p in pieces); top = min(p[1] for p in pieces)
        width = (max(p[0]+p[2] for p in pieces)-left+7)//8*8
        height = max(p[1]+p[3] for p in pieces)-top
        while width*height % 64: height += 1
        assert width <= 504 and height <= 255
        pixels = bytearray(width*height)
        for x, y, w, h, word in reversed(pieces):
            for dy in range(h):
                for dx in range(w):
                    sx = w-1-dx if word&0x800 else dx
                    sy = h-1-dy if word&0x1000 else dy
                    tile = ((word&2047)+(sx//8)*(h//8)+sy//8)&2047
                    byte = vram[tile*32+sy%8*4+sx%8//2]
                    color = byte&15 if sx&1 else byte>>4
                    if color: pixels[(y-top+dy)*width+x-left+dx] = ((word>>13)&3)*16+color+1+(128 if word&0x8000 else 0)
        yield left, top, width, height, bytes(pixels)


def per_piece(rnd, obj):
    """Stored per mapping piece: the listed families, and any R4 family whose
    pose mixes palette lines (harid4), which one 16-color CLUT cannot hold
    exactly as the source compositor checks it."""
    if obj['kind']&255 in PIECES.get(rnd, {}) or obj['kind'] in PIECES.get(rnd, {}):return True
    if rnd not in (4, 5, 6, 7, 8):return False
    for encoded in obj['frames']:
        mapping = bytes.fromhex(encoded)
        lines = {((struct.unpack_from('>H', mapping, 3+5*i)[0]+obj['tile'])>>13)&3 for i in range(mapping[0])}
        if len(lines) > 1:return True
    return False


# Per-piece families whose pieces are stored in groups: kind -> function of the
# pose's piece count giving the composited groups (mapping piece indices).
# NOKOGIRI.C: the last eight pieces are the 64x64 saw (two poses alternate);
# the earlier ones are its diagonal chain of 16x16 links. Composited whole, the
# 18 poses take 112,896 B; one record per piece takes 270 records.
GROUPS = {8: {159: lambda n: [[i] for i in range(n-8)]+[list(range(n-8, n))]}}


def part_pieces(rnd, record, count):
    """The mapping piece indices of each part, back to front (the last piece
    is drawn first): one piece per part unless GROUPS composites some."""
    group = GROUPS.get(rnd, {}).get(record['kind'] & 255)
    groups = group(count) if group and count > 8 else [[i] for i in range(count)]
    return sorted(groups, key=lambda g: -max(g))


def source_parts(record, vram, rnd=None):
    """One (left, top, width, height, pixels) list per pose: each mapping piece
    (or GROUPS group) on its own, back to front, with its own flips applied."""
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        if not mapping[0]:
            yield [(0, 0, 8, 8, bytes(64))]
            continue
        parts = []
        for pieces in part_pieces(rnd, record, mapping[0]):
            one = dict(record, frames=[(bytes([len(pieces)])+b''.join(mapping[1+5*i:6+5*i] for i in pieces)).hex()])
            parts.append(next(source_frames(one, vram)))
        yield parts


def packed_objects(name):
    """(kind, object, vram, source) for every family this era packs, in pack order.

    R4 and R5 (ZAR3) kinds are type | subtype<<8 (tools/zone_object_source.py
    r4_specs, r5_specs; R5 view subtypes from src/objects_qq.inc qq_view). A
    subtype whose original table, tile base and poses equal the plain type's is
    left to the runtime fallback (src/zone_object_view.inc zone_art_find), and
    R4_ALIASES repeat a captured variant under the view subtype that uses it."""
    from zone_object_source import R4_ALIASES
    rnd = int(name[1]); out = []; kinds = {}
    for path in source_paths(name):
        source = json.loads((path/'source.json').read_text())
        vram = (path/'vram.bin').read_bytes()
        assert hashlib.sha256(vram).hexdigest() == source['vram_sha256']
        for obj in source['objects']:
            # R4: a family whose tiles no resident PLC bank holds is not packed
            # from this VRAM (a -plc sibling source carries it when it can).
            # A family whose tiles hold no PLC bank's bytes is packed only with
            # retail runtime evidence that the capture's VRAM is what retail draws.
            if obj['kind'] in source.get('plc_unverified', ()) and (path.name, obj['kind']) not in RETAIL_VRAM_EVIDENCE:continue
            if obj['kind']&255 in DEFERRED.get(rnd, {}):continue
            kinds[obj['kind']] = (obj, vram, source)
    same = lambda a, b: (a['tile'], a['address'], a['frames']) == (b['tile'], b['address'], b['frames'])
    for kind, (obj, vram, source) in kinds.items():
        # Identical mappings can still draw different art from a later PLC
        # state (R63 actor 55's entry subtype versus its fight base kind).
        if kind > 255 and kind&255 in kinds and same(obj, kinds[kind&255][0]) and vram==kinds[kind&255][1]:continue
        out.append((kind, obj, vram, source))
    if rnd == 4:
        for (kind, sub), (ckind, csub) in sorted(R4_ALIASES.items()):
            captured = kinds.get(ckind | csub << 8) or (kinds.get(ckind) if csub == 0 else None)
            if captured:out.append((kind | sub << 8, captured[0], captured[1], captured[2]))
    return out


def boss6_patch_stream(name, dynamics, raw):
    """VDP1 word writes for retail PLC 19's three-tile-per-update queue.

    The entry sprites remain mutable until the last tile they read is loaded.
    Each age's offsets are relative to the decompressed zone-art arena.
    """
    entry = bytearray((SOURCE/(name+'-boss-entry')/'vram.bin').read_bytes())
    fight = (SOURCE/(name+'-boss')/'vram.bin').read_bytes()
    first = 22 if name.endswith('C') else 21
    end_age = first + 84  # $300-$3eb, then six updates through $3fd
    current = bytearray(raw)
    body = bytearray(); ends = [0]
    written = [0, 0]
    for age in range(1, end_age+1):
        for bank, (tile, count, begin) in enumerate(((0x300, 236, first), (0x3ec, 84, first+79))):
            n = max(0, min(count, (age-begin+1)*3))
            if n > written[bank]:
                lo = (tile+written[bank])*32; hi = (tile+n)*32
                entry[lo:hi] = fight[lo:hi]
                written[bank] = n
        changed = []
        for offset, obj, pose, part, colors in dynamics:
            one = dict(obj, frames=[obj['frames'][pose]])
            pieces = next(source_parts(one, entry)) if per_piece(6, obj) else [next(source_frames(one, entry))]
            left, top, width, height, pixels = pieces[part]
            indices = [colors.index(c) for c in pixels]
            bitmap = bytes((indices[i]<<4)|indices[i+1] for i in range(0, len(indices), 2))
            assert len(bitmap) == width*height//2
            for i in range(0, len(bitmap), 2):
                at = offset+i
                if current[at:at+2] != bitmap[i:i+2]:
                    current[at:at+2] = bitmap[i:i+2]
                    changed.append(at//2)
        changed.sort()
        assert all(at < 65536 for at in changed)
        for _, group in itertools.groupby(enumerate(changed), lambda x: x[1]-x[0]):
            words = [v for _, v in group]
            body.extend(struct.pack('>HH', words[0], len(words)))
            for word in words:body.extend(current[word*2:word*2+2])
        ends.append(len(body))
    assert written == [236, 18]
    return b'W6PT'+struct.pack('>HH', end_age, 0)+struct.pack(f'>{len(ends)}I', *ends)+body


# Metallic Madness Act 3 fight art. Retail egg8 calls colorset2(7), (8), (9)
# and then LoadPLC(4) (R83C $20B524), whose fight bank overwrites stage tiles
# $220-$510; its third hit loads PLC 5 (Amy over hane's tiles, $20B36A). Each
# bank (tools/extract_mmd.py -boss, -boss-ending) with the actors left in the
# room (tobira's door view 2, shut, kaiten, flowers) uses an era slot Act 3
# has no use for: A the fight, B the ending, the same in both futures.
# src/zone_object_view.inc loads them at those PLC requests (src/boss.c).
# (source, kind): retail VRAM, read while the actor is on screen, equals the
# capture's VRAM at every tile its mappings read.
RETAIL_VRAM_EVIDENCE = {
    # MM1A ET8 (generator, tile $423): retail row 6246 (on screen at 291,113) holds
    # the R81A capture's bytes on all 23 tiles $8460-$8740; only $8460-$8640 is a
    # PLC bank (2/4-8/15/17), so verify_tile_bytes leaves it unverified.
    ('R81A', 169): 'retail MM1A row 6246 VRAM',
    # MM2A ET8 (tile $2FE), packed from R82A-plc (PLC 4/8's own bank over the fixture
    # VRAM): retail R82A with the generator on screen at (1352,1408) holds those bytes
    # on all 23 tiles $5FC0-$629F; $6280 is zero and no PLC writes it
    # (tools/check_mm2a_et8_vram.py).
    ('R82A-plc', 169): 'tools/check_mm2a_et8_vram.py retail MM2A VRAM',
}
FIGHT_KINDS = {688, 185, 178, 31, 31 | 1 << 8}  # + PLAYSUB flowers (tiles $6D7, outside PLC 4)


def fight_objects(name, bank='-boss'):
    """(kind, object, vram, source) of the R83C/D fight (-boss) or ending
    (-boss-ending) slot."""
    out = []
    for kind, obj, vram, source in packed_objects(name):
        if kind in FIGHT_KINDS:out.append((kind, obj, vram, source))
    path = SOURCE/(name+bank)
    source = json.loads((path/'source.json').read_text())
    vram = (path/'vram.bin').read_bytes()
    assert hashlib.sha256(vram).hexdigest() == source['vram_sha256']
    out += [(obj['kind'], obj, vram, source) for obj in source['objects']]
    if bank == '-boss-ending':
        # PLC 5 (Amy) overwrites only $4400-$56E0: fight parts whose every tile the
        # ending VRAM still holds byte for byte (egg8hane 241-243) keep drawing in
        # retail after the swap (MM3D update 7574: hane 241 pose 8 under the pod).
        from zone_object_source import read_tiles
        fight = SOURCE/(name+'-boss'); fvram = (fight/'vram.bin').read_bytes()
        have = {kind for kind, *_ in out}
        for obj in json.loads((fight/'source.json').read_text())['objects']:
            if obj['kind'] not in have and all(fvram[t%65536:t%65536+32] == vram[t%65536:t%65536+32] for t in read_tiles(obj)):
                out.append((obj['kind'], obj, vram, source))
    return out


def pack_era(name, arena=None, lz=False, objects=None, base=None, out_state=None):
    """base: {'raw', 'shared'} of a bank resident in VDP1 when this one streams
    (R83's Amy bank over its fight bank): identical textures keep their offsets,
    new ones reuse the space of base textures this bank does not use, and the
    LZ stream keeps (distance 0) every word the base already holds."""
    raw = bytearray() if arena is None else arena['raw']
    records = bytearray(); frames = []
    shared = {} if arena is None else arena['textures']
    free = []
    if base is not None:
        probe = {}
        pack_era(name, None, lz, objects, out_state=probe)
        raw = bytearray(base['raw']); shared = dict(base['shared'])
        need = set(probe['shared'])
        for key, at in base['shared'].items():
            if key not in need:
                size = len(key[3]) if key[0] == 'bitmap' else 32
                free.append([at, at+size]); del shared[key]
        free.sort()
        merged = []
        for a, b in free:
            if merged and merged[-1][1] == a:merged[-1][1] = b
            else:merged.append([a, b])
        free = merged

    def alloc(key, data):
        if key in shared:return
        for span in free:
            if span[1]-span[0] >= len(data):
                shared[key] = span[0]; raw[span[0]:span[0]+len(data)] = data; span[0] += len(data); return
        shared[key] = len(raw); raw.extend(data)
    sources=[]; dynamics=[]
    fight_vram = (SOURCE/(name+'-boss')/'vram.bin').read_bytes() if name in ('R63C','R63D') else None
    for kind, obj, vram, source in (objects if objects is not None else packed_objects(name)):
        if source not in sources:sources.append(source)
        if True:
            # A capture of listed poses (frame_ids) keeps the original pose numbers.
            ids = obj.get('frame_ids') or list(range(len(obj['frames'])))
            dynamic = fight_vram is not None and 496 <= kind <= 499
            if per_piece(int(name[1]), obj):
                # A fully transparent piece draws nothing: keep it only when a pose has
                # no other, so the pose still resolves (egg5's pose 2 has one).
                poses = [(ids[n], n, i, part) for n, parts in enumerate(source_parts(obj, vram, int(name[1])))
                         for i, part in (list(enumerate(parts)) if dynamic else
                                         ([(i,q) for i,q in enumerate(parts) if any(q[4])] or [(0,parts[0])]))]
            else:
                poses = [(ids[n], n, 0, f) for n, f in enumerate(source_frames(obj, vram))]
            # SHARED_CLUT families: the pieces on one palette line share one CLUT
            # (the union of their colours) instead of one CLUT per piece.
            line_colors = {}
            if (int(name[1]), obj['kind']&255) in SHARED_CLUT and not dynamic:
                for *_, (_, _, _, _, px) in poses:
                    used = set(px)-{0}
                    if used and len({(c-1)//16 for c in used}) == 1:
                        line_colors.setdefault((min(used)-1)//16, set()).update(used)
            for frame, pose, part, (left, top, width, height, pixels) in poses:
                if dynamic:
                    one = dict(obj, frames=[obj['frames'][pose]])
                    final = next(source_parts(one, fight_vram))[part] if per_piece(6, obj) else next(source_frames(one, fight_vram))
                    assert (left, top, width, height) == final[:4]
                    colors = [0]+sorted((set(pixels)|set(final[4]))-{0})
                else:
                    used = set(pixels)-{0}
                    shared_line = line_colors.get((min(used)-1)//16) if used else None
                    colors = [0]+sorted(shared_line if shared_line and used <= shared_line and len(shared_line) <= 15 else used)
                assert len(colors) <= 16
                indices = [colors.index(c) for c in pixels]
                bitmap = bytes((indices[i]<<4)|indices[i+1] for i in range(0, len(indices), 2))
                refs = [0]+[c-1 for c in colors[1:]]+[0]*(16-len(colors))
                clut = struct.pack('>16H', *[0 if i==0 else 0x8000+c for i,c in enumerate(refs)])
                if arena is None and not lz:
                    texture=bitmap+clut;key=(width,height,texture)
                    if key not in shared:shared[key]=len(raw);raw.extend(texture)
                    offset=shared[key]
                else:
                    # The high/low halves hold separate CLUT/bitmap offsets.
                    # This lets identical indexed pixels share storage even
                    # when another era needs different live CRAM references.
                    # ZAR3 (R4) splits them too: per-piece families repeat one
                    # indexed piece under several palette lines. The first
                    # entry is always a bitmap, so a CLUT offset is never 0.
                    bitmap_key=('dynamic-bitmap',kind,frame,part) if dynamic else ('bitmap',width,height,bitmap)
                    alloc(bitmap_key, bitmap)
                    clut_key=('clut',clut)
                    alloc(clut_key, clut)
                    assert shared[bitmap_key]<65536 and shared[clut_key]<65536
                    offset=shared[bitmap_key]|shared[clut_key]<<16
                if dynamic:dynamics.append((offset&65535,obj,pose,part,colors))
                records.extend(struct.pack('>HHIHHhh16H', kind, frame, offset, width, height, left, top, *refs))
                frames.append(dict(kind=kind, frame=frame, left=left, top=top, width=width,
                                   height=height, offset=offset, pixel_sha256=hashlib.sha256(pixels).hexdigest()))
    # A ZAR2 arena past the VDP1 region becomes ZAR5 (zar5_layout): checked per era there.
    assert len(raw) <= ARENA_BYTES or (arena is not None and not lz), (name, len(raw), ARENA_BYTES)
    assert len(frames) <= 512, (name, len(frames), 'records (src/zone_object_art.h SCD_ZONE_ART_MAX_FRAMES)')
    assert len({(f['kind'],f['frame']) for f in frames}) <= 256, (name, 'poses exceed src/zone_object_view.inc lookup')
    if arena is not None:
        return struct.pack('>I',len(frames))+records, dict(frames=frames,sources=sources)
    if out_state is not None:out_state.update(raw=bytes(raw), shared=dict(shared))
    if base is not None:
        # Byte-exact: the stream over the resident base rebuilds this bank's raw,
        # and every record's bitmap and CLUT sit where its texture key says.
        packed = zone_art_lz.pack(bytes(raw), base=base['raw'])
        assert zone_art_lz.unpack(packed, len(raw)//2, base['raw']) == bytes(raw), (name, 'patched bank')
        for key, at in shared.items():
            data = key[3] if key[0] == 'bitmap' else key[1] if key[0] == 'clut' else None
            if data is not None:assert raw[at:at+len(data)] == data, (name, 'texture moved', key[:3] if key[0]=='bitmap' else 'clut')
    else:packed = zone_art_lz.pack(bytes(raw)) if lz else pack_texture(raw)
    patches = boss6_patch_stream(name,dynamics,raw) if dynamics else b''
    return struct.pack('>III', len(frames), len(raw), len(packed))+records+packed+patches, dict(
        frames=frames, raw_bytes=len(raw), packed_bytes=len(packed), sources=sources)


def zar5_layout(data, raw_bytes, packed):
    """ZAR2 -> ZAR5 when the shared arena is larger than the VDP1 region.

    Each era keeps the arena textures its records use, in arena order, at
    compact offsets: era blob = count, era raw bytes, span count, records
    (offsets rewritten), spans (u16 arena word, u16 words). The packed arena
    stream stays shared; src/zone_object_view.inc decodes it once and keeps
    only the era's spans. Header words 20/24/28 stay the arena's raw/packed
    size and packed offset."""
    eras, blobs, sizes = [struct.unpack_from('>I', data, 4+i*4)[0] for i in range(4)], {}, {}
    out = bytearray(b'ZAR5' + bytes(28))
    for i, at in enumerate(eras):
        if not at:continue
        if at not in blobs:
            count = struct.unpack_from('>I', data, at)[0]
            records = bytearray(data[at+4:at+4+count*48])
            units, cluts = set(), set()  # 32-byte units used; units that start a CLUT
            for r in range(count):
                offset, w, h = struct.unpack_from('>IHH', records, r*48+4)
                bitmap, clut = offset & 65535, offset >> 16
                assert clut and not bitmap % 32 and not clut % 32 and not w*h//2 % 32
                units.update(range(bitmap//32, (bitmap+w*h//2)//32)); units.add(clut//32); cluts.add(clut//32)
            order = sorted(units)
            # A CLUT offset of 0 means 'after the bitmap': keep offset 0 a bitmap unit
            # (the loader starts the spans at era raw - span bytes).
            base = 1 if order[0] in cluts else 0
            remap = {u: (base+n)*32 for n, u in enumerate(order)}
            for r in range(count):
                offset = struct.unpack_from('>I', records, r*48+4)[0]
                struct.pack_into('>I', records, r*48+4, remap[(offset & 65535)//32] | remap[(offset >> 16)//32] << 16)
            spans = []
            for u in order:
                if spans and spans[-1][0]+spans[-1][1] == u*16 and spans[-1][1] < 65535-16:spans[-1][1] += 16
                else:spans.append([u*16, 16])
            era_raw = (base+len(order))*32
            assert era_raw <= ARENA_BYTES, (f'era {i}', era_raw, ARENA_BYTES)
            assert len(spans) < 65536 and raw_bytes//2 < 65536
            blobs[at] = len(out); sizes[at] = era_raw
            out += struct.pack('>III', count, era_raw, len(spans)) + records + b''.join(struct.pack('>HH', *s) for s in spans)
        struct.pack_into('>I', out, 4+i*4, blobs[at])
    struct.pack_into('>III', out, 20, raw_bytes, len(packed), len(out))
    return out + packed, {i: sizes[at] for i, at in enumerate(eras) if at}


def zar5_era(pack, start, unpack):
    """A ZAR5 era as the loader sees it: (count, records offset, era raw bytes,
    packed bytes, packed offset, era VRAM image). unpack decodes the arena stream."""
    count, era_raw, spans = struct.unpack_from('>III', pack, start)
    arena_bytes, packed_size, packed_at = struct.unpack_from('>III', pack, 20)
    arena = unpack(pack[packed_at:packed_at+packed_size])
    assert len(arena) == arena_bytes
    rows = [struct.unpack_from('>HH', pack, start+12+48*count+4*i) for i in range(spans)]
    words = sum(n for _, n in rows)
    image = bytearray(era_raw - 2*words)
    for at, n in rows:image += arena[2*at:2*(at+n)]
    assert len(image) == era_raw
    return count, start+12, era_raw, packed_size, packed_at, bytes(image)


def main():
    disc = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    tool = hashlib.sha256((ROOT/'tools/zone_object_source.py').read_bytes()).hexdigest()
    inputs = dependencies()
    report = {}; rows = []
    OUT.mkdir(exist_ok=True)
    (OUT/'zone-art-none.bin').write_bytes(b'ZART'+bytes(16))
    for rnd, zone in ((3,1), (4,2), (5,3), (6,4), (7,5), (8,6)):
        for act in (1,2,3):
            # CC's small era differences previously duplicated nearly every
            # texture four times in low RAM. A shared texture arena keeps each
            # era's exact records, while storing identical bitmaps/CLUTs once.
            # Metallic Madness (ZAR4): the four eras' records over one shared arena
            # packed with the ZAR3 codec; per-era ZAR3 files exceed the 104,448 B
            # PACK_ZONE_ART region (R81: about 145 KB).
            arena = dict(raw=bytearray(),textures={}) if (rnd == 3 and act < 3) or (rnd == 8 and act < 3) else None
            # Tidal Tempest: four eras of composited poses overflow the 104,448 B
            # staging region with run-length packing (R42: 196,194 B) and share
            # too little to use ZAR2. ZAR3 is ZART with the word-LZ codec
            # (tools/zone_art_lz.py): repeated piece rows cost a back reference.
            # Quartz Quadrant (R5) uses ZAR3 as well: kinds are type|subtype<<8.
            # Wacky Workbench (R6) too (tools/zone_object_source.py r6_specs).
            zar3 = rnd in (4, 5, 6, 7, 8)
            data = bytearray(b'ZAR4'+bytes(28) if zar3 and arena is not None else b'ZAR3'+bytes(16) if zar3 else b'ZAR2'+bytes(28) if arena is not None else b'ZART'+bytes(16))
            era_blobs = {}
            for era in ('CD' if act==3 else 'ABCD'):
                name = f'R{rnd}{act}{era}'; path = SOURCE/name/'source.json'
                for source_path in source_paths(name):
                    fixture=source_path.name[len(name)+1:] if source_path.name!=name else 'main'
                    if fixture=='flower':
                        subprocess.run([sys.executable,str(ROOT/'tools/ss_flower_source.py'),'--program',name],check=True)
                        continue
                    if fixture in ('boss','boss2','boss-entry','bumper','plc') or fixture.startswith('boss-beam'):continue
                    path=source_path/'source.json'
                    old=json.loads(path.read_text()) if path.exists() else {}
                    if old.get('tool_sha256') != tool or old.get('dependencies') != inputs or old.get('program_sha256') != hashlib.sha256(disc[name+'__.MMD']).hexdigest():
                        subprocess.run([sys.executable,str(ROOT/'tools/zone_object_source.py'),name,'--fixture',fixture],check=True)
                blob, report[name] = pack_era(name,arena,lz=zar3)
                # Some eras use byte-identical mappings and indexed textures;
                # live stage CRAM supplies their different colors. Share only
                # identical complete records/texture streams in low work RAM.
                if blob not in era_blobs:
                    era_blobs[blob] = len(data); data.extend(blob)
                struct.pack_into('>I', data, 4+'ABCD'.index(era)*4, era_blobs[blob])
                report[name]['file_offset'] = era_blobs[blob]
                if rnd == 8 and act == 3:
                    fight_state = {}
                    for slot, (label, bank) in enumerate((('-fight', '-boss'), ('-ending', '-boss-ending'))):
                        # The Amy bank streams over the resident fight bank (PLC 5 after 4).
                        blob, report[name+label] = pack_era(name, None, lz=True, objects=fight_objects(name, bank),
                                                            base=fight_state if slot else None, out_state=None if slot else fight_state)
                        if blob not in era_blobs:
                            # Both futures share each bank's records: one slot holds them.
                            assert era == 'C', (name, label, 'futures differ in the shared bank')
                            era_blobs[blob] = len(data); data.extend(blob)
                        struct.pack_into('>I', data, 4+slot*4, era_blobs[blob])
                        report[name+label]['file_offset'] = era_blobs[blob]
            if arena is not None:
                packed = zone_art_lz.pack(bytes(arena['raw'])) if zar3 else pack_texture(arena['raw'])
                era_raw = None
                if not zar3 and len(arena['raw']) > ARENA_BYTES:
                    data, era_raw = zar5_layout(data, len(arena['raw']), packed)
                else:
                    assert len(arena['raw']) <= ARENA_BYTES, (f'R{rnd}{act}', len(arena['raw']), ARENA_BYTES)
                    struct.pack_into('>III',data,20,len(arena['raw']),len(packed),len(data))
                    data.extend(packed)
                for era in ('CD' if act==3 else 'ABCD'):
                    report[f'R{rnd}{act}{era}'].update(raw_bytes=len(arena['raw']),packed_bytes=len(packed),format='ZAR4' if zar3 else 'ZAR5' if era_raw else 'ZAR2')
                    if era_raw:report[f'R{rnd}{act}{era}'].update(era_raw_bytes=era_raw['ABCD'.index(era)])
            assert len(data) <= PACK_ZONE_ART_BYTES, (f'R{rnd}{act}', len(data), 'src/stage_packs.h PACK_ZONE_ART region')
            file = f'ZART{rnd}{act}.BIN'; source = f'assets/generated/zone-art-{rnd}{act}.bin'
            (ROOT/source).write_bytes(data)
            rows.append(f'    STAGE_ZONE_PACK(PACK_ZONE_ART,{zone},{act-1},"{file}","{source}")')
    (OUT/'zone-object-packs.h').write_text('/* Generated original zone object art. */\n#define ZONE_OBJECT_PACKS \\\n'+' \\\n'.join(rows)+'\n')
    (ROOT/'build/zone-object-art.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Zone art: {len(report)} variants, peak {max(r["raw_bytes"] for r in report.values())}/{ARENA_BYTES} VDP1 bytes')


if __name__ == '__main__':
    main()
