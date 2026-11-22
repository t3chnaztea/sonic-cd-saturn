#!/usr/bin/env python3
"""Visual Mode menu screen (Visual Mode/Main.asm, the retail VM____.MMD).

cd/VISMODE.BIN, from the user's disc: the palette (Pal_VisualMode), the background art
(Art_VisModeBG, Nemesis, VRAM $20 = tile 1), the menu text art (Art_VisModeText, VRAM
$8C20 = tile $461), plane A as DrawBackground leaves it (Map_VisModeBG + $4001, 40 x 28)
and the five option sprites as SpawnMenuOptions places them (x 192, y 112 + 16n, base
tile $461; MapSpr_* pieces), laid out as plane cells: every piece is 8-pixel aligned,
so the sprite layer maps one to one onto a second VDP2 plane. Layout: 'VMS1', u16 tile
count (from tile 0), 64 palette words, the tiles (32 bytes each, tile 0 empty, the
text at $461), then plane A and the option layer (40 x 28 Mega Drive words each; 0 in
the option layer is no sprite). The disassembly names the data; every byte, the
mappings and the spawn constants must be found in VM____.MMD.
"""
import hashlib, json, re, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from convert_assets import nemesis  # noqa: E402
from extract_mmd import disc_files, ISO  # noqa: E402
from generated_io import write_bytes  # noqa: E402

SRC = ROOT / '.deps/scddisasm/src/Visual Mode'
TEXT_TILE = 0x461
OPTIONS = ['Exit', 'Opening', 'GoodEnd', 'BadEnd', 'PencilTest']


def number(text):
    """An assembler constant expression such as 2-1 or -$20."""
    expr = re.sub(r'\$([0-9A-Fa-f]+)', r'0x\1', text.strip())
    assert re.fullmatch(r'[-+0-9a-fA-Fx ]+', expr), text
    return eval(expr, {'__builtins__': {}})


def mappings(asm):
    """MapSpr_<name>: the frame's pieces as (size word, tile, x offset, flipped x, y, flipped y)."""
    out = {}
    for name in OPTIONS:
        body = asm.split(f'\nMapSpr_{name}:', 1)[1].split('\nMapSpr_', 1)[0].split('\n; ---', 1)[0]
        words = [number(v) for line in re.findall(r'dc\.w\s+([^;\n]+)', body)
                 for v in line.split(',') if not v.strip().startswith('.Frame')]
        # dc.w 1 (frames); dc.w 1, .Frame-MapSpr (time, offset: the offset is dropped above)
        frames, time, count = words[0], words[1], words[2] + 1
        assert frames == 1 and time == 1 and len(words) == 3 + 6 * count, (name, words)
        out[name] = [tuple(words[3 + 6 * i:9 + 6 * i]) for i in range(count)]
    return out


def mapping_bytes(pieces):
    """The assembled MapSpr data, to find it in the retail program."""
    data = struct.pack('>HHH', 1, 1, 6) + struct.pack('>H', len(pieces) - 1)
    for p in pieces:
        data += struct.pack('>6h', *p)
    return data


def main():
    asm = (SRC / 'Main.asm').read_text()
    disc = disc_files(ISO.read_bytes())['VM____.MMD']

    def from_disc(name):
        data = (SRC / 'Data' / name).read_bytes()
        assert disc.find(data) >= 0, f'{name} not in VM____.MMD'
        return data
    palette = from_disc('Palette.bin')
    bg_art = nemesis(from_disc('Art (Background).nem'))
    text_art = nemesis(from_disc('Art (Text).nem'))
    bg_map = from_disc('Background Mappings.bin')
    assert len(palette) == 128 and len(bg_map) == 40 * 28 * 2 and len(bg_art) % 32 == 0 and len(text_art) % 32 == 0
    assert 1 + len(bg_art) // 32 <= TEXT_TILE, 'background art overlaps the text art'
    # SpawnMenuOptions: x 192, y 112, base tile $461, the highlight tile $2461 (palette line 1),
    # 16 pixels apart; DrawBackground's base $4001 and size 40 x 28 ($28-1, $1C-1).
    for pattern in ('317c00c00004', '317c00700008', '317c0461', '317c2461', '06410010', '3c3c4001', '323c001b', '343c0027'):
        assert disc.hex().find(pattern) >= 0, f'spawn/draw constant {pattern} not in VM____.MMD'
    maps = mappings(asm)
    for name, pieces in maps.items():
        assert disc.find(mapping_bytes(pieces)) >= 0, f'MapSpr_{name} not in VM____.MMD'
    tiles = bytearray(32) + bg_art
    tiles += bytes(TEXT_TILE * 32 - len(tiles)) + text_art
    plane_a = [(w + 0x4001) & 0xffff for w in struct.unpack('>1120H', bg_map)]
    layer = [0] * 1120
    for n, name in enumerate(OPTIONS):
        ox, oy = 192, 112 + 16 * n
        for size, tile, xoff, _, yoff, _ in maps[name]:
            w, h = (size >> 10 & 3) + 1, (size >> 8 & 3) + 1
            x, y = ox - xoff, oy - yoff     # DrawObjects: position minus the piece offset
            assert x % 8 == 0 and y % 8 == 0 and size & 0xff == 0
            for cx in range(w):
                for cy in range(h):        # sprite cells run down each column first
                    at = (y // 8 + cy) * 40 + x // 8 + cx
                    assert layer[at] == 0, ('sprite pieces overlap', name)
                    layer[at] = TEXT_TILE + tile + cx * h + cy
    assert all(not w or 14 <= i // 40 < 24 for i, w in enumerate(layer))   # option n: rows 14+2n, 15+2n
    blob = b'VMS1' + struct.pack('>H', len(tiles) // 32) + palette + bytes(tiles)
    blob += struct.pack('>1120H', *plane_a) + struct.pack('>1120H', *layer)
    write_bytes(ROOT / 'cd/VISMODE.BIN', blob + bytes(-len(blob) % 2048))
    print(json.dumps({'bytes': len(blob), 'tiles': len(tiles) // 32, 'background_tiles': len(bg_art) // 32,
                      'text_tiles': len(text_art) // 32, 'option_cells': sum(1 for w in layer if w),
                      'sha256': hashlib.sha256(blob).hexdigest()[:12]}))


if __name__ == '__main__':
    main()
