#!/usr/bin/env python3
"""Extract a second zone's stage data from its retail R<n>xx MMD programs.

tools/extract_mmd.py does this for Palmtree Panic and additionally carries that
zone's one-off object work (the Act 2 swing and collapsing platforms). This tool
keeps only the part that generalises: locate the stage structures in a template
program, relocate them into the other nine, and cross-check every program
against both the disassembly and the PC reconstruction tables.

Two things had to change to make it zone-generic, both verified against
Palmtree Panic before being relied on for a new zone:

  * PaletteTable is anchored on Sonic's palette, which is identical in every
    zone, instead of on the level palette. Anchoring on the level palette
    assumes the level entry's index, and that index is not the same in every
    zone: it is 5 in Palmtree Panic and 4 in Wacky Workbench. Entry 3 is Sonic
    in both. The real level index is read from LevelDataIndex at run time, as
    extract_mmd.py already does.
  * DebugItemIndex is optional. Its locator is a byte signature of Palmtree
    Panic's own debug item list and finds nothing in R61A. It only supplies a
    count for the report, so a zone without it is not blocked.

Everything else transferred with no change at all.
"""
import argparse, hashlib, json, re, struct
from pathlib import Path

from convert_assets import ROOT, OUT, nemesis, palette, layout
from extract_mmd import (ISO, LEVEL, ORIGIN, GLOBAL_MAPS, disc_files, unique,
                         relocate, pc_table, expand)

ERAS = {'A': 'Present', 'B': 'Past', 'C': 'Good Future', 'D': 'Bad Future'}
SONIC_PALETTE = LEVEL / '_Objects/Sonic/Data/Palette.bin'

ZONES = {
    'wacky-workbench': {
        'round': 6, 'folder': 'Wacky Workbench', 'pc': 'R6', 'prefix': 'ww',
        # The disassembly ships only Act 1 Present for this zone, so that is the
        # template and the only program with a full file-by-file disassembly check.
        'template': 'R61A',
        'programs': ['R61A', 'R61B', 'R61C', 'R61D', 'R62A', 'R62B', 'R62C', 'R62D', 'R63C', 'R63D'],
    },
    # Palmtree Panic is here only so this tool can be proved against a zone whose
    # output is already known. tools/extract_mmd.py remains its real extractor.
    'palmtree-panic': {
        'round': 1, 'folder': 'Palmtree Panic', 'pc': 'R1', 'prefix': 'ppz',
        'template': 'R11A',
        'programs': ['R11A', 'R11B', 'R11C', 'R11D', 'R12A', 'R12B', 'R12C', 'R12D', 'R13C', 'R13D'],
    },
}


def palette_table(target):
    """PaletteTable base, anchored on Sonic's palette in entry 3.

    Rows are (long pointer, word, word count-1). Sonic's palette is byte
    identical in every zone, so this needs no per-zone input and no assumption
    about where the level entry sits.
    """
    sonic = SONIC_PALETTE.read_bytes()
    found = set()
    for hit in re.finditer(re.escape(sonic), target):
        pointer = struct.pack('>I', ORIGIN + hit.start())
        for row in re.finditer(re.escape(pointer) + b'..(..)', target, re.S):
            if row.start() % 2:
                continue
            if (struct.unpack('>H', row[1])[0] + 1) * 4 == len(sonic):
                found.add(ORIGIN + row.start() - 3 * 8)
    if len(found) != 1:
        raise ValueError(f'PaletteTable: {len(found)} candidates {sorted(map(hex, found))}')
    return found.pop()


def template_labels(zone, template):
    data = LEVEL / zone['folder'] / 'Data'
    load = lambda name: (data / name).read_bytes()
    labels = {
        'tiles': ORIGIN + unique(template, load('Tiles (Act 1 Present).nem')),
        'blocks': ORIGIN + unique(template, load('Blocks (Act 1 Present).nem')),
        'chunks': ORIGIN + unique(template, load('Chunks (Act 1 Present).bin')),
        'collision': ORIGIN + unique(template, load('Collision (Act 1 Present).bin')),
        'foreground': ORIGIN + unique(template, load('Foreground (Act 1 Present).bin')),
        'spec_chunks': ORIGIN + 4 + unique(template, load('Start Position (Act 1 Present).bin') + bytes([0x7F] * 4)),
        'objects': ORIGIN + unique(template, load('Objects (Act 1).bin')) - 12,
    }
    index = struct.pack('>III', labels['tiles'] | 0x3000000, labels['blocks'] | 0x2000000, labels['chunks']) + b'\0\x81'
    hits = [m.start() for m in re.finditer(re.escape(index), template)]
    if not hits:
        raise ValueError('LevelDataIndex not found')
    labels['data_index'] = ORIGIN + min(hits)
    labels['layouts'] = labels['foreground'] - 0x48
    if struct.unpack_from('>H', template, labels['layouts'] - ORIGIN)[0] != 0x48:
        raise ValueError('LevelLayouts table does not end at the foreground layout')
    at = unique(template, struct.pack('>I', labels['collision']) * 8)
    labels['collision_head'] = template[at - 12:at]
    return labels


def extract(template, target, labels):
    long = lambda a: struct.unpack_from('>I', target, a - ORIGIN)[0]
    word = lambda a: struct.unpack_from('>H', target, a - ORIGIN)[0]
    at = lambda a, n: target[a - ORIGIN:a - ORIGIN + n]
    index = relocate(template, target, labels['data_index'])
    tiles, blocks, chunks = long(index) & 0x3FFFFF, long(index + 4) & 0x3FFFFF, long(index + 8)
    if word(index + 12) != 0x81 or chunks != ORIGIN + 0x10000:
        raise ValueError('LevelDataIndex layout changed')
    layouts = relocate(template, target, labels['layouts'])
    if word(layouts) != 0x48:
        raise ValueError('LevelLayouts table size changed')
    plane = lambda a: at(a, 2 + (target[a - ORIGIN] + 1) * (target[a - ORIGIN + 1] + 1))
    fg, bg = plane(layouts + word(layouts)), plane(layouts + word(layouts + 2))
    heads = [m.start() for m in re.finditer(re.escape(labels['collision_head']) + rb'(....)\1\1\1\1\1\1\1', target, re.S)]
    if len(heads) != 1:
        raise ValueError(f'LevelColIndex: {len(heads)} matches')
    collision = long(ORIGIN + heads[0] + 12)
    start = relocate(template, target, labels['spec_chunks']) - 4
    objects = relocate(template, target, labels['objects'])
    palettes = palette_table(target)
    palette_id = target[index - ORIGIN + 15]
    color_table = lambda i: at(long(palettes + i * 8), (word(palettes + i * 8 + 6) + 1) * 4)
    used = max(c & 127 for c in fg[2:] + bg[2:])
    return {
        'addresses': {k: f'{v:#08x}' for k, v in dict(
            data_index=index, tiles=tiles, blocks=blocks, chunks=chunks, layouts=layouts,
            collision=collision, start=start, objects=objects, palettes=palettes).items()},
        'tiles_raw': target[tiles - ORIGIN:], 'blocks_raw': target[blocks - ORIGIN:],
        'chunks': at(chunks, used * 512), 'foreground': fg, 'background': bg,
        'collision': at(collision, layouts - collision).rstrip(b'\0'),
        'start': at(start, 4), 'spec_chunks': at(start + 4, 4),
        'objects': at(objects + word(objects), word(objects + 2) - word(objects)),
        'sonic_palette': color_table(3), 'level_palette': color_table(palette_id), 'palette_id': palette_id,
        'maps': {n: target[unique(target, (LEVEL / f'_Data/Collision {n}.bin').read_bytes()):][
                    :len((LEVEL / f'_Data/Collision {n}.bin').read_bytes())] for n in GLOBAL_MAPS},
    }


def read_iso():
    if ISO.exists():
        return ISO.read_bytes()
    raw = (ISO.parent / 'sonic.bin').read_bytes()
    return b''.join(raw[i + 16:i + 2064] for i in range(0, len(raw), 2352))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zone', choices=sorted(ZONES))
    parser.add_argument('--write', action='store_true', help='write stage packs into assets/generated')
    args = parser.parse_args()
    zone = ZONES[args.zone]
    data = LEVEL / zone['folder'] / 'Data'
    pc_dir = ROOT / '.deps/soniccd/src' / zone['pc']

    disc = disc_files(read_iso())
    template = disc[f"{zone['template']}__.MMD"]
    labels = template_labels(zone, template)
    report = {'zone': args.zone, 'round': zone['round'], 'template': zone['template'],
              'source': 'build/retail/sonic.iso', 'wrote_packs': bool(args.write), 'programs': {}}

    for program in zone['programs']:
        mmd = disc[f'{program}__.MMD']
        x = extract(template, mmd, labels)
        tiles, blocks = nemesis(x['tiles_raw']), nemesis(x['blocks_raw'])
        entry = {'mmd_sha256': hashlib.sha256(mmd).hexdigest(), 'addresses': x['addresses'],
                 'palette_id': x['palette_id'], 'chunks': len(x['chunks']) // 512,
                 'tiles': len(tiles) // 32, 'blocks': len(blocks) // 8,
                 'foreground': [x['foreground'][0] + 1, x['foreground'][1] + 1],
                 'background': [x['background'][0] + 1, x['background'][1] + 1],
                 'start': list(struct.unpack('>HH', x['start'])),
                 'spec_chunks': x['spec_chunks'].hex(),
                 'object_records': len(x['objects']) // 8 - 1}

        # The disassembly only covers this zone's Act 1 Present program.
        if program == zone['template']:
            load = lambda name: (data / name).read_bytes()
            checks = {
                'tiles': x['tiles_raw'].startswith(load('Tiles (Act 1 Present).nem')),
                'blocks': x['blocks_raw'].startswith(load('Blocks (Act 1 Present).nem')),
                'chunks': x['chunks'] == load('Chunks (Act 1 Present).bin'),
                'foreground': x['foreground'] == load('Foreground (Act 1 Present).bin'),
                'background': x['background'] == load('Background (Act 1 Present).bin'),
                'collision': x['collision'] == load('Collision (Act 1 Present).bin').rstrip(b'\0'),
                'start': x['start'] == load('Start Position (Act 1 Present).bin'),
                'objects': x['objects'] == load('Objects (Act 1).bin'),
                'level_palette': x['level_palette'] == load('Palette (Present).bin'),
                'sonic_palette': x['sonic_palette'] == SONIC_PALETTE.read_bytes(),
            }
            if not all(checks.values()):
                raise SystemExit(f'{program} differs from the disassembly: {[k for k, v in checks.items() if not v]}')
            entry['disassembly_match'] = sorted(checks)

        pc = (pc_dir / f'Z{program[1:]}TBL.C').read_text(encoding='latin1')
        checks = {
            'collision': (lambda z: z[:len(x['collision'])] == x['collision'] and not any(z[len(x['collision']):]))(pc_table(pc, 'zone1scd')),
            'foreground': expand(x['foreground']) == pc_table(pc, 'mapwka'),
            'background': expand(x['background']) == pc_table(pc, 'mapwkb'),
            'angles': pc_table(pc, 'scddirtbl') == x['maps']['Angles'],
            'height': pc_table(pc, 'scdtblwk')[:4096] == x['maps']['Height Map'],
            'width': pc_table(pc, 'scdtblwk2')[:4096] == x['maps']['Width Map'],
        }
        rows = [tuple(map(int, m.groups())) for m in re.finditer(
            r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}',
            (pc_dir / f'Z{program[1:3]}ACT.C').read_text(encoding='latin1'))]
        records = [struct.unpack_from('>HHBBBB', x['objects'], i) for i in range(0, len(x['objects']), 8)]
        differences = [i for i, (a, b) in enumerate(zip(rows[:-1], records[:-1])) if a != b]
        # The retail disc is authoritative where the PC reconstruction differs;
        # differences are recorded per program rather than asserted away.
        checks['objects_terminated'] = (len(rows) == len(records)
                                        and rows[-1][0] == records[-1][0] == 0xFFFF)
        failed = [k for k, v in checks.items() if not v]
        if failed:
            raise SystemExit(f'{program} differs from the PC tables: {failed}')
        entry['pc_match'] = sorted(checks)
        entry['pc_object_differences'] = [{'record': i, 'pc': rows[i], 'retail': records[i]} for i in differences]

        colors = palette(x['sonic_palette'] + x['level_palette'])
        if len(colors) != 128:
            raise SystemExit(f'{program}: expected 64 palette entries')
        parts = [tiles, blocks, x['chunks'], expand(x['foreground']), expand(x['background']), colors]
        header, offset = b'PPZ1', 56
        for part in parts:
            header += struct.pack('>II', offset, len(part))
            offset += len(part)
        pack = header + x['start'] + b''.join(parts)
        collision = x['collision'].ljust(1024, b'\0') + x['maps']['Height Map'] + x['maps']['Width Map'] + x['maps']['Angles']
        key = program[1:]
        entry['pack_sha256'] = hashlib.sha256(pack).hexdigest()
        entry['collision_sha256'] = hashlib.sha256(collision).hexdigest()
        entry['objects_sha256'] = hashlib.sha256(x['objects']).hexdigest()
        entry['pack_bytes'] = len(pack)
        if args.write:
            prefix = zone['prefix']
            (OUT / f'{prefix}{key}.bin').write_bytes(pack)
            (OUT / f'{prefix}collision{key}.bin').write_bytes(collision)
            (OUT / f'{prefix}objects{key}.bin').write_bytes(x['objects'])
        report['programs'][program] = entry

    out = ROOT / 'build' / f'zone-{args.zone}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')
    total = sum(e['pack_bytes'] for e in report['programs'].values())
    print(f"{args.zone}: {len(report['programs'])} programs extracted and cross-checked; "
          f"{total} stage-pack bytes; report {out.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
