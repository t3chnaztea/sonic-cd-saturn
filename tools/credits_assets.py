#!/usr/bin/env python3
"""Generate the "Thank You" ending screen tables for src/credits.c (never in git).

Inputs:
  .deps/soniccd/src/TITLE/THANKS   PC reconstruction (DATA_SP.C, IO.C, GAME.C, ETC_M.C, CHRSET.C)
  build/retail/sonic.iso           user-supplied Sega CD disc (tools/extract_mmd.py)

The retail program THANKS_M.MMD is authoritative.  Every PC table that the
Sega CD program also holds (sine table, spawn timers, palette cycle timers,
the three palettes, the name glyph maps) must be found in it, converted to
Mega Drive words, exactly once.  endingcol and the EndingMes message sprites
are PC-only (no copy on the disc); the report says so.

Outputs:
  assets/generated/credits_tables.h        tables included by src/credits.c
  assets/generated/credits/THANKS_*.bin    the three retail files, byte for byte
  cd/THANKS.BIN                            the Sega CD screen's VRAM art and plane maps
                                           (src/credits_saturn.c)
  build/credits/assets-report.json         hashes and the retail cross-check
"""
import hashlib, json, pathlib, re, struct, sys
from extract_mmd import disc_files
from generated_io import write_bytes, write_text

ROOT = pathlib.Path(__file__).resolve().parents[1]
PC = ROOT / '.deps/soniccd/src/TITLE/THANKS'
ISO = ROOT / 'build/retail/sonic.iso'
OUT = ROOT / 'assets/generated'
REPORT = ROOT / 'build/credits/assets-report.json'


def text(name):
    source = (PC / name).read_text()
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def ints(body):
    return [int(v) for v in re.findall(r'-?\d+', body)]


def block(source, pattern):
    match = re.search(pattern + r'\s*=\s*\{(.*?)\n\s*\};', source, re.S)
    if not match:
        raise ValueError(f'missing table {pattern}')
    return match[1]


def palette(source, name):
    values = ints(block(source, re.escape(name) + r'\[\d+\]'))
    return [tuple(values[i:i + 3]) for i in range(0, len(values), 4)]


def parse():
    data = text('DATA_SP.C')
    mappings, patterns = {}, {}
    for name, body in re.findall(r'sprite_pattern_mappings_title (\w+) = \{(.*?)\n\};', data, re.S):
        values = ints(body)
        pieces = [tuple(values[1 + 6 * i:7 + 6 * i]) for i in range(values[0])]
        if len(values) != 1 + 6 * values[0]:
            raise ValueError(name)
        mappings[name] = pieces
    for name, body in re.findall(r'sprite_patterns_title (\w+) = \{(.*?)\n\};', data, re.S):
        count = int(re.match(r'\s*(\d+)', body)[1])
        frames = [(int(t), m) for t, m in re.findall(r'\{\s*(-?\d+),\s*&(\w+)\s*\}', body)]
        if len(frames) != count:
            raise ValueError(name)
        patterns[name] = frames
    good_names = re.findall(r'PALETTEENTRY (lpgood\w)\[24\]', data)
    good = {n: palette(data, n) for n in good_names}
    cycle = re.findall(r'(lpgood\w)', block(data, r'PALETTEENTRY\* lpbs_good\[32\]'))
    glyph_bodies = dict(re.findall(r'static unsigned short (_\w+)\[\d+\] = \{([^}]*)\}', data))
    glyph_order = re.findall(r'\b(0|_\w+)\b', block(data, r'unsigned short\* asc_maptbl\[38\]'))
    game = text('GAME.C')
    return {
        'mappings': mappings, 'patterns': patterns, 'good': good, 'cycle': cycle,
        'asc_col': [palette(data, 'asc_col00'), palette(data, 'asc_col01')],
        'lpbs_timer': ints(block(data, r'unsigned short lpbs_timer\[32\]')),
        'glyphs': [ints(glyph_bodies[g]) if g != '0' else [] for g in glyph_order],
        'colortbl': palette(text('IO.C'), 'colortbl'),
        'endingcol': palette(game, 'endingcol'),
        'sin': ints(block(text('ETC_M.C'), r'short sin_tbl\[128\]')),
        'actset': ints(block(text('CHRSET.C'), r'short actset_tbl\[16\]')),
        'manyact': ints(block(text('CHRSET.C'), r'short manyact_tbl\[16\]')),
    }


WHITE = None   # PC (240, 240, 240)


def md(colors):
    """PC PALETTEENTRY (3-bit channel * 32) -> Mega Drive 0000BBB0GGG0RRR0.
    The PC's (240, 240, 240) stands for a retail word with every colour bit
    set: $FFFF in colortbl, $0FFF in the cycle palettes.  CRAM keeps only
    $0EEE (224 per channel); src/credits.c keeps the PC value."""
    return [WHITE if (r, g, b) == (240, 240, 240) else
            ((b // 32 * 2) << 8) | ((g // 32 * 2) << 4) | (r // 32 * 2) for r, g, b in colors]


def words(values):
    """Byte pattern for big-endian words; WHITE matches $0FFF or $FFFF."""
    return b''.join(b'(?:\x0f\xff|\xff\xff)' if v is None else re.escape(struct.pack('>H', v & 0xFFFF))
                    for v in values)


def retail_checks(t, program):
    checks = {'sin_tbl': words(t['sin']), 'actset_tbl': words(t['actset']),
              'manyact_tbl': words(t['manyact']), 'lpbs_timer': words(t['lpbs_timer']),
              'colortbl': words(md(t['colortbl'])), 'endingcol (PC only)': words(md(t['endingcol'])),
              # lpgoodA..Q, 24 entries each, stored back to back.
              'lpgood A-Q': words(sum((md(c) for c in t['good'].values()), []))}
    for i, colors in enumerate(t['asc_col']):
        checks[f'asc_col0{i}'] = words(md(colors[:4]))
    # Identical glyphs (0/O) and the two ASCII colour rows share data, so
    # these only need to be present; every other table must be unique.
    shared = {'asc_col00', 'asc_col01'}
    for i, glyph in enumerate(t['glyphs'][1:], 1):
        checks[f'glyph{i}'] = words(glyph)
        shared.add(f'glyph{i}')
    result = {}
    for name, pattern in checks.items():
        hits = [m.start() for m in re.finditer(pattern, program, re.S)]
        count = len(hits)
        ok = count == 0 if 'PC only' in name else count >= 1 if name in shared else count == 1
        result[name] = {'offset': hits[0] if hits else None, 'copies': count, 'ok': ok}
    return result


def be16(data, at):
    return struct.unpack_from('>H', data, at)[0]


def bes16(data, at):
    return struct.unpack_from('>h', data, at)[0]


def enigma(data, base):
    """Enigma map decoder (the retail program's $FF415E): 00 incrementing, 01 common,
    100/101/110 inline value repeated/incremented/decremented, 111 inline values, 1111111 end."""
    plen, mask = data[0], data[1]
    inc, com = be16(data, 2), be16(data, 4)
    pos = [48]

    def bits(n):
        v = 0
        for _ in range(n):
            v = v << 1 | data[pos[0] >> 3] >> (7 - (pos[0] & 7)) & 1
            pos[0] += 1
        return v

    def inline():
        flags = 0
        for bit, shift in ((0x10, 15), (0x08, 14), (0x04, 13), (0x02, 12), (0x01, 11)):
            if mask & bit and bits(1):
                flags |= 1 << shift
        return (flags | bits(plen)) & 0xFFFF
    out = []
    while True:
        if not bits(1):
            if not bits(1):
                for _ in range(bits(4) + 1):
                    out.append(inc)
                    inc = (inc + 1) & 0xFFFF
            else:
                out += [com] * (bits(4) + 1)
            continue
        mode, n = bits(2), bits(4)
        if mode == 3 and n == 15:
            break
        if mode == 3:
            out += [inline() for _ in range(n + 1)]
            continue
        v = inline()
        for _ in range(n + 1):
            out.append(v)
            v = (v + (1 if mode == 1 else -1 if mode == 2 else 0)) & 0xFFFF
    return [(w + base) & 0xFFFF for w in out]


def retail_program(t, program, data):
    """The Sega CD presentation from THANKS_M.MMD ($FF2000) and THANKS_D.BIN (Word RAM
    $210000): the sprite pattern tables and their Mega Drive mappings, the art the
    program decompresses into VRAM and the two plane maps."""
    from convert_assets import nemesis
    code = program[0x100:]
    org, word_ram = 0xFF2000, 0x210000

    def find(signature):
        hits = [m.start() for m in re.finditer(re.escape(bytes.fromhex(signature)), code)]
        if len(hits) != 1:
            raise SystemExit(f'credits_assets: THANKS_M.MMD signature {signature} found {len(hits)} times')
        return hits[0]
    # Pattern tables: count, then (timer, offset from the table) per frame; the PC tables
    # in DATA_SP.C order. Retail m_furi_map has count 1 (the PC has 2): it never animates.
    names, at, tables = list(t['patterns']), None, {}
    for start in range(0, len(code) - 2, 2):
        found, cursor = {}, start
        for name in names:
            frames = t['patterns'][name]
            limit = cursor + 0x200
            while cursor < min(limit, len(code) - 4 * len(frames) - 2):
                count = be16(code, cursor)
                if count in (len(frames), 1) and all(be16(code, cursor + 2 + 4 * i) == f[0] for i, f in enumerate(frames)):
                    break
                cursor += 2
            else:
                break
            found[name] = cursor
            cursor += 2 + 4 * len(frames)
        if len(found) == len(names):
            tables, at = found, start
            break
    if not tables:
        raise SystemExit('credits_assets: retail pattern tables not found in THANKS_M.MMD')
    retail_counts, frame_maps, md_maps = [], [], {}
    for name in names:
        table, frames = tables[name], t['patterns'][name]
        retail_counts.append(be16(code, table))
        for i, (timer, mapping) in enumerate(frames):
            offset = table + be16(code, table + 4 + 4 * i)
            if mapping in md_maps and md_maps[mapping][0] != offset:
                raise SystemExit(f'credits_assets: {mapping} has two retail mappings')
            pieces = []
            for j in range(be16(code, offset) + 1):
                p = offset + 2 + 12 * j
                pieces.append((code[p], code[p + 1], be16(code, p + 2), bes16(code, p + 4), bes16(code, p + 6),
                               bes16(code, p + 8), bes16(code, p + 10)))
            md_maps[mapping] = (offset, pieces)
            frame_maps.append(mapping)
    # Art: the PLC list read by $FF3F5E (VDP command, Word RAM source) and the two Enigma
    # maps of $FF40F6 (source, base, width-1, height-1, VDP command).
    plc = find('41fa00162ab010f8207010fc') + 2 + 0x16
    vram = bytearray(0xC000)
    loads = []
    # $FF2312 and $FF2368 (move.l #command,$C00004; lea source,a0; bsr NemDec) first.
    direct = [struct.unpack('>II', m.group(1) + m.group(2)) for m in
              re.finditer(rb'\x23\xfc(.{4})\x00\xc0\x00\x04\x41\xf9(.{4})\x61\x00', code, re.S)]
    if len(direct) != 2:
        raise SystemExit('credits_assets: THANKS_M.MMD direct art loads')
    for command, source in direct + [struct.unpack_from('>II', code, plc + 8 * i) for i in range(5)]:
        address = (command >> 16 & 0x3FFF) | (command & 3) << 14
        art = nemesis(data[source - word_ram:])
        vram[address:address + len(art)] = art
        loads.append((source - word_ram, address, len(art)))
    eni = struct.unpack_from('>I', code, find('c0fc000e43f9') + 6)[0] - org
    planes = []
    for i in range(2):
        source, base, width, height, command = struct.unpack_from('>IHHHI', code, eni + 14 * i)
        words = enigma(data[source - word_ram:], base)
        if len(words) != (width + 1) * (height + 1):
            raise SystemExit('credits_assets: plane map size')
        plane = [0] * 2048
        for y in range(height + 1):
            for x in range(width + 1):
                plane[y * 64 + x] = words[y * (width + 1) + x]
        planes.append(plane)
        loads.append((source - word_ram, (command >> 16 & 0x3FFF) | (command & 3) << 14, len(words) * 2))
    # Palettes as the program stores them (the PC's (240, 240, 240) is $FFFF or $0FFF):
    # colortbl copied to the fade target $FFB680 at start ($FF20B0), and the V-int cycles
    # ($FF3AFC: lpbs_good offsets, 24 colours to $FFB620; $FF3B4E: asc_coltbl, 8 to $FFB650).
    colortbl = None
    for m in re.finditer(rb'\x41\xfa(..)\x43\xf8\xb6\x80\x7e\x1f', code, re.S):
        colortbl = m.start() + 2 + struct.unpack('>h', m.group(1))[0]
    def cycle_table(dest):
        hits = [m for m in re.finditer(rb'\x43\xf9(.{4})\x45\xf1\x00\x00\xd2\xd2\x41\xf8' + dest, code, re.S)]
        if len(hits) != 1:
            raise SystemExit('credits_assets: palette cycle table')
        return struct.unpack('>I', hits[0].group(1))[0] - org
    good_at, asc_at = cycle_table(b'\xb6\x20'), cycle_table(b'\xb6\x50')
    if colortbl is None:
        raise SystemExit('credits_assets: colortbl copy')
    md_colortbl = [be16(code, colortbl + 2 * i) for i in range(64)]
    good_words = [[be16(code, good_at + be16(code, good_at + 2 * i) + 2 * k) for k in range(24)] for i in range(31)]
    asc_words = [[be16(code, asc_at + be16(code, asc_at + 2 * i) + 2 * k) for k in range(8)] for i in range(2)]
    def same(pc, retail):
        return all(r in (0x0FFF, 0xFFFF) if v is None else r == v for v, r in zip(md(pc), retail))
    if not same(t['colortbl'], md_colortbl):
        raise SystemExit('credits_assets: retail colortbl differs from the PC')
    for i in range(31):
        if not same(t['good'][t['cycle'][i]], good_words[i]):
            raise SystemExit(f'credits_assets: retail palette cycle {i} differs from the PC')
    for i in range(2):
        if not same(t['asc_col'][i], asc_words[i]):
            raise SystemExit(f'credits_assets: retail asc_coltbl {i} differs from the PC')
    # Name glyph base: dsp_usrname ($FF21BC: lea $C00004,a2; move.w #base,d5) adds it to
    # the glyph words in plane A ($C149 on the Sega CD; the PC adds 32767+330).
    glyph_base = be16(code, find('45f900c000043a3c') + 8)
    return {'md_colortbl': md_colortbl, 'good_words': good_words, 'asc_words': asc_words,
            'pattern_tables': at, 'retail_counts': retail_counts, 'frame_maps': frame_maps, 'md_maps': md_maps,
            'vram': bytes(vram), 'planes': planes, 'loads': loads, 'glyph_base': glyph_base}


def emit_md(t, r):
    """Tables for scd_credits_md (src/credits.c): per PC pattern frame, its retail mapping."""
    lines = ['/* Sega CD presentation (THANKS_M.MMD): Mega Drive pieces per pattern frame. */']
    if r is None:
        return '\n'.join(lines + ['#define SCD_CREDITS_MD_TABLES 0', ''])
    order = list(dict.fromkeys(r['frame_maps']))
    pieces, first = [], {}
    for name in order:
        first[name] = len(pieces)
        pieces += r['md_maps'][name][1]
    lines.append('#define SCD_CREDITS_MD_TABLES 1')
    lines.append('/* size, etc, tile, hoffs, hrevoffs, voffs, vrevoffs */')
    lines.append('static const scd_credits_md_piece scd_credits_md_pieces[] = {')
    lines += ['    {%d, %d, %d, %d, %d, %d, %d},' % p for p in pieces]
    lines.append('};')
    lines.append('static const scd_credits_mapping scd_credits_md_maps[] = {')
    lines += [f'    {{{len(r["md_maps"][n][1])}, {first[n]}}}, /* {n} at THANKS_M+${r["md_maps"][n][0] + 0x100:X} */'
              for n in order]
    lines.append('};')
    lines.append('/* Retail mapping of each scd_credits_frames entry. */')
    lines.append('static const uint8_t scd_credits_md_frame_map[] = {' +
                 ', '.join(str(order.index(n)) for n in r['frame_maps']) + '};')
    lines.append('/* Retail frame counts (m_furi_map: 1, the PC 2). */')
    lines.append('static const uint8_t scd_credits_md_count[] = {' + ', '.join(map(str, r['retail_counts'])) + '};')
    lines.append(f'#define SCD_CREDITS_MD_GLYPH_BASE 0x{r["glyph_base"]:04X}')
    words16 = lambda ws: ', '.join(f'0x{w:04X}' for w in ws)
    lines.append('/* The fade target (colortbl) and the cycle palettes as THANKS_M.MMD stores them. */')
    lines.append('static const uint16_t scd_credits_md_colortbl[64] = {' + words16(r['md_colortbl']) + '};')
    lines.append('static const uint16_t scd_credits_md_good[31][24] = {' +
                 ', '.join('{' + words16(g) + '}' for g in r['good_words']) + '};')
    lines.append('static const uint16_t scd_credits_md_asc[2][8] = {' +
                 ', '.join('{' + words16(g) + '}' for g in r['asc_words']) + '};')
    lines.append('')
    return '\n'.join(lines)


def thanks_pack(r):
    """cd/THANKS.BIN: 'THK1', VRAM bytes (u32), the VRAM image from 0, then planes A and B
    (64x32 Mega Drive words each)."""
    vram = r['vram'].rstrip(b'\0')
    vram += bytes(-len(vram) % 32)
    blob = b'THK1' + struct.pack('>I', len(vram)) + vram
    for plane in r['planes']:
        blob += struct.pack('>2048H', *plane)
    return blob + bytes(-len(blob) % 2048)


def emit(t):
    names = list(t['patterns'])
    mapping_names = list(t['mappings'])
    lines = ['/* Generated by tools/credits_assets.py from the PC reconstruction (TITLE/THANKS);',
             '   cross-checked against the retail THANKS_M.MMD.  Never commit. */',
             '#ifndef SCD_CREDITS_TABLES_H', '#define SCD_CREDITS_TABLES_H', '']
    lines.append('#define SCD_CREDITS_PATTERN_NAMES \\')
    lines += [f'    X({n}) \\' for n in names]
    lines.append('')
    lines += [f'#define SCD_CREDITS_PAT_{n} {i}' for i, n in enumerate(names)]
    lines.append(f'#define SCD_CREDITS_PATTERN_COUNT {len(names)}')
    pieces, first = [], {}
    for n in mapping_names:
        first[n] = len(pieces)
        pieces += t['mappings'][n]
    lines.append('static const scd_credits_piece scd_credits_pieces[] = {')
    lines += ['    {%d, %d, %d, %d, %d, %d},' % p for p in pieces]
    lines.append('};')
    lines.append('static const scd_credits_mapping scd_credits_mappings[] = {')
    lines += [f'    {{{len(t["mappings"][n])}, {first[n]}}}, /* {n} */' for n in mapping_names]
    lines.append('};')
    frames, frame_first = [], {}
    for n in names:
        frame_first[n] = len(frames)
        frames += [(timer, mapping_names.index(m)) for timer, m in t['patterns'][n]]
    lines.append('static const scd_credits_pattern_frame scd_credits_frames[] = {')
    lines += [f'    {{{timer}, {m}}},' for timer, m in frames]
    lines.append('};')
    lines.append('static const scd_credits_pattern scd_credits_patterns[] = {')
    lines += [f'    {{{len(t["patterns"][n])}, {frame_first[n]}}}, /* {n} */' for n in names]
    lines.append('};')

    def rgb(name, colors):
        body = ', '.join('{%d, %d, %d}' % c for c in colors)
        return f'static const uint8_t {name}[{len(colors)}][3] = {{{body}}};'
    lines.append(rgb('scd_credits_colortbl', t['colortbl']))
    lines.append(rgb('scd_credits_endingcol', t['endingcol']))
    good = list(t['good'])
    lines.append(f'static const uint8_t scd_credits_good[{len(good)}][24][3] = {{')
    lines += ['    {' + ', '.join('{%d, %d, %d}' % c for c in t['good'][n]) + f'}}, /* {n} */' for n in good]
    lines.append('};')
    lines.append('static const uint8_t scd_credits_good_cycle[32] = {' + ', '.join(str(good.index(n)) for n in t['cycle']) + '};')
    lines.append('static const uint8_t scd_credits_asc_col[2][8][3] = {' + ', '.join(
        '{' + ', '.join('{%d, %d, %d}' % c for c in pal) + '}' for pal in t['asc_col']) + '};')
    lines.append('static const uint16_t scd_credits_lpbs_timer[32] = {' + ', '.join(map(str, t['lpbs_timer'])) + '};')
    lines.append('static const int16_t scd_credits_sin[128] = {' + ', '.join(map(str, t['sin'])) + '};')
    glyph_words, glyph_first = [], []
    for g in t['glyphs']:
        glyph_first.append(len(glyph_words))
        glyph_words += g
    lines.append('static const uint16_t scd_credits_glyph_words[] = {' + ', '.join(map(str, glyph_words)) + '};')
    lines.append('static const uint16_t scd_credits_glyph_first[38] = {' + ', '.join(map(str, glyph_first)) + '};')
    lines += ['']
    return '\n'.join(lines)


def main():
    t = parse()
    if len(t['glyphs']) != 38 or len(t['cycle']) != 32 or len(t['sin']) != 128 or len(t['colortbl']) != 64:
        raise SystemExit('credits_assets: unexpected table sizes')
    report = {'pc_source': str(PC.relative_to(ROOT)), 'patterns': len(t['patterns']),
              'mappings': len(t['mappings'])}
    retail = None
    if ISO.exists():
        files = disc_files(ISO.read_bytes())
        (OUT / 'credits').mkdir(parents=True, exist_ok=True)
        for name in ('THANKS_M.MMD', 'THANKS_D.BIN', 'THANKS_S.BIN'):
            data = files[name]
            write_bytes(OUT / 'credits' / (name.replace('.', '_') + '.bin'), data)
            report[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        report['retail'] = retail_checks(t, files['THANKS_M.MMD'])
        missing = [n for n, r in report['retail'].items() if not r['ok']]
        report['retail_match'] = not missing
        report['retail_missing'] = missing
        retail = retail_program(t, files['THANKS_M.MMD'], files['THANKS_D.BIN'])
        pack = thanks_pack(retail)
        (ROOT / 'cd').mkdir(exist_ok=True)
        write_bytes(ROOT / 'cd/THANKS.BIN', pack)
        report['md'] = {'pattern_tables': f"THANKS_M+${retail['pattern_tables'] + 0x100:X}",
                        'retail_counts_differ': [n for n, c in zip(t['patterns'], retail['retail_counts'])
                                                 if c != len(t['patterns'][n])],
                        'mappings': len(retail['md_maps']),
                        'pieces': sum(len(p) for _, p in retail['md_maps'].values()),
                        'loads': [f'D+${s:04X} -> VRAM ${a:04X} ({n} B)' for s, a, n in retail['loads']],
                        'pack_bytes': len(pack), 'pack_sha256': hashlib.sha256(pack).hexdigest()}
    else:
        report['retail_match'] = None
        print(f'credits_assets: {ISO.relative_to(ROOT)} missing; retail cross-check skipped', file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    write_text(OUT / 'credits_tables.h', emit(t) + emit_md(t, retail) + '#endif\n')
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    checked = report.get('retail', {})
    print(f"credits tables: {len(t['patterns'])} patterns, {len(t['mappings'])} mappings; "
          f"retail tables matched {sum(r['ok'] for r in checked.values())}/{len(checked)}; "
          f"retail_match={report['retail_match']}")
    if report['retail_match'] is False:
        print('missing in THANKS_M.MMD:', report['retail_missing'], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
