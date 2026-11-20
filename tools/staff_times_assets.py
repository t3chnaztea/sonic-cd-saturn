#!/usr/bin/env python3
"""Private STF1 pack from local DUMMY4.MMD and its pinned source. Import is inert.

No raw retail program enters the pack. CLI needs an authorized extraction window.
Text positions, strings and font mappings come from source, then join disc bytes.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = 'Title Screen/Secrets'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode_text(text):
    out, i = [], 0
    punctuation = {' ': 0, '-': 37, ',': 38, '.': 39, "'": 40,
                   '"': 41, '!': 42, '?': 43, 'x': 44}
    while i < len(text):
        c = text[i]
        if text[i:i+2] == "''":
            out.append(41); i += 2; continue
        if '0' <= c <= '9': v = ord(c)-ord('0')+1
        elif 'A' <= c <= 'Z': v = ord(c)-ord('A')+11
        elif c in punctuation: v = punctuation[c]
        else: raise ValueError(f'unsupported source character {c!r}')
        out.append(v); i += 1
    return bytes(out)+b'\xff'


def parse_source(source):
    def font(label):
        block = source.split(label+':', 1)[1].split('; -------------------------------------------------------------------------', 1)[0]
        block = block.split('.TilesLower:', 1)[0]
        values = [int(v, 16) for v in re.findall(r'^\s*dc\.b\s+\$([0-9A-Fa-f]+)', block, re.M)]
        if len(values) != 45: raise ValueError(f'{label}: expected45 glyphs')
        return bytes(values)
    strings = dict(re.findall(r'(TextDat_\w+):\s*TEXTSTR\s+"([^"\n]*)"', source))
    groups = []
    for label, count in [('Text_BestTimes', 1), ('Text_BestTimesList', 28)]:
        block = source.split(label+':', 1)[1].split('TEXTEND', 1)[0]
        entries = [(name, int(x), int(y)) for name, x, y in re.findall(r'TEXTPTR\s+(\w+),\s*(\d+),\s*(\d+)', block)]
        if len(entries) != count or any(name not in strings for name, _, _ in entries):
            raise ValueError(f'{label}: incorrect source records')
        groups.append(entries)
    if groups[0][0][1:] != (3, 1) or [e[1:] for e in groups[1]] != [(4, 4+3*n) for n in range(28)]:
        raise ValueError('unexpected source layout')
    return {'upper': font('.TilesUpper'), 'lower': font('.TilesLower'),
            'strings': {k: encode_text(v) for k, v in strings.items()}, 'groups': groups}


def text_plane(spec):
    plane = [0]*(32*128)
    for group, base in zip(spec['groups'], (0, 0x6000)):
        for name, x, y in group:
            text = spec['strings'][name][:-1]
            if x+len(text) > 32 or y+1 >= 128: raise ValueError('text outside source plane')
            for n, code in enumerate(text):
                plane[y*32+x+n] = base+spec['upper'][code]
                plane[(y+1)*32+x+n] = base+spec['lower'][code]
    return struct.pack('>4096H', *plane)


def vdp_command(address):
    return 0x40000000 | ((address & 0x3fff) << 16) | (address >> 14)


def bind_program(program, spec):
    if len(program) < 0x100: raise ValueError('short MMD')
    origin = struct.unpack_from('>I', program, 2)[0]
    addresses = {}
    for name, text in spec['strings'].items():
        at = program.find(text, 0x100)
        if at < 0 or program.find(text, at+1) >= 0: raise ValueError(f'nonunique or absent string {name}')
        addresses[name] = origin+at-0x100
    for font in ('upper', 'lower'):
        if spec[font] not in program[0x100:]: raise ValueError('font table not in DUMMY4')
    for group in spec['groups']:
        table = struct.pack('>H', len(group)-1)
        for name, x, y in group:
            table += struct.pack('>III', addresses[name], vdp_command(0xc000+x*2+y*64), vdp_command(0xc000+x*2+(y+1)*64))
        if table not in program[0x100:]: raise ValueError('text pointer/position table differs from disc')
    # Source VDP registers, including H32 and32x128. No runtime extraction guess.
    regs = bytes([4, 0x34, 0x30, 0, 7, 0x58, 0, 0, 0, 0, 0, 0, 0, 0x2d, 0, 2, 0x30, 0, 0])
    if regs not in program[0x100:]: raise ValueError('source VDP register table not in DUMMY4')
    for word in ('40000000', '60000003', '721f', '741b', '303c6000', '7e1f'):
        if bytes.fromhex(word) not in program[0x100:]:
            raise ValueError(f'source draw constant {word} absent from DUMMY4')
    return origin


def make_pack(palette, art, background, text):
    if len(palette) != 128 or not art or len(art)%32 or len(art)//32 > 2048 or any(art[:32]):
        raise ValueError('invalid palette/art dimensions or blank tile')
    if len(background) != 1792 or len(text) != 8192: raise ValueError('invalid map dimensions')
    if any(v & ~0xeee for v in struct.unpack('>64H', palette)): raise ValueError('invalid MD palette')
    if any((v & 2047) >= len(art)//32 for v in struct.unpack('>4992H', background+text)):
        raise ValueError('map references absent art')
    payload = palette+art+background+text
    logical = 32+len(payload)
    blob = b'STF1'+struct.pack('>7I', logical, len(art)//32, 896, 4096, 28, zlib.crc32(payload), 64)+payload
    blob += bytes(-len(blob)%2048)
    if len(blob) > 0x14000: raise ValueError('pack exceeds reserved low RAM')
    return blob


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'cd/STAFFTIM.BIN')
    p.add_argument('--report', type=Path, default=ROOT/'build/staff-times-assets/report.json')
    a = p.parse_args()
    # Heavy/private reads are deferred until explicit CLI invocation.
    from extract_mmd import disc_files, ISO
    from convert_assets import nemesis
    from scd_source import SRC
    source = SRC/REL/'Best Staff Times.asm'
    paths = [source, SRC/REL/'_Macros.inc', SRC/REL/'_Variables.inc', SRC/REL/'Functions.asm',
             SRC/'_Include/MMD.inc', Path(__file__),
             ROOT/'tools/convert_assets.py', ROOT/'tools/extract_mmd.py']
    pins = {str(x): sha(x.read_bytes()) for x in paths}
    report = {'status': 'pending', 'inputs': pins, 'python': sys.version, 'zlib': zlib.ZLIB_VERSION, 'scope': 'private source-derived STF1; viewport unaccepted'}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    def save(): a.report.write_text(json.dumps(report, indent=2)+'\n')
    save()
    try:
        spec = parse_source(source.read_text())
        disc = ISO.read_bytes(); report['disc_sha256'] = sha(disc)
        program = disc_files(disc)['DUMMY4.MMD']; report['program_sha256'] = sha(program)
        report['origin'] = bind_program(program, spec)
        parts = []
        for name in ('Palette.bin', 'Art.nem', 'Background Mappings (H32).bin'):
            path = SRC/REL/'Data'/name; data = path.read_bytes(); pins[str(path)] = sha(data)
            if not data or data not in program[0x100:]: raise ValueError(f'{name}: absent from DUMMY4')
            parts.append(data)
        blob = make_pack(parts[0], nemesis(parts[1]), parts[2], text_plane(spec))
        if any(sha(Path(path).read_bytes()) != expected for path, expected in pins.items()):
            raise ValueError('source changed during conversion')
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_bytes(blob)
        report.update(status='passed', output=str(a.output), output_sha256=sha(blob), bytes=len(blob), records=28)
        save(); print('PASS: StaffTimes private source/disc pack')
    except BaseException as e:
        report.update(status='interrupted' if isinstance(e, KeyboardInterrupt) else 'failed', error=repr(e)); save(); raise


if __name__ == '__main__': main()
