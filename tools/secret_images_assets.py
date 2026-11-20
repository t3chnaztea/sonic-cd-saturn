#!/usr/bin/env python3
"""Sound test secret pictures (Title Screen/Secrets/Sound Test Image.asm), from the user's disc.

IPX.asm SoundTest exits 2-6 run SCMD_FUNISINF, SCMD_MCSONIC, SCMD_TAILS, SCMD_BATMAN and
SCMD_CUTESONIC; SPX.asm loads NISI.MMD and DUMMY0-3.MMD. Each program loads its Nemesis
art at VRAM 0 (tile 0, blank in all five), draws its 40 x 28 map on plane B ($E000,
DrawTilemapH64, the words as stored) and loads its 64-colour palette. cd/SECRET<n>.BIN,
n = 1..5 in exit order: 'SEC1', u16 tile count, 64 palette words, the tiles (32 bytes
each), the plane B map (40 x 28 Mega Drive words). The disassembly names the data; every
byte and the draw constants must be found in the retail program.
"""
import hashlib, json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from convert_assets import nemesis  # noqa: E402
from extract_mmd import disc_files, ISO  # noqa: E402
from generated_io import write_bytes  # noqa: E402

DATA = ROOT / '.deps/scddisasm/src/Title Screen/Secrets/Data'
# Exit order (IPX.asm SoundTest .Exits 2-6, Sound Test.asm CheckEasterEgg .Codes).
IMAGES = [('NISI.MMD', 'Fun Is Infinite'), ('DUMMY0.MMD', 'M.C. Sonic'), ('DUMMY1.MMD', 'Tails'),
          ('DUMMY2.MMD', 'Batman'), ('DUMMY3.MMD', 'Cute Sonic')]
# Start: VDPCMD $0000 VRAM (art), VDPCMD $E000 VRAM (map), moveq #$28-1,d1, moveq #$1C-1,d2,
# the palette loop moveq #(128)/4-1,d7.
CONSTANTS = ('40000000', '60000003', '7227', '741b', '7e1f')


def main():
    disc = disc_files(ISO.read_bytes())
    summary = []
    for n, (name, label) in enumerate(IMAGES, 1):
        program = disc[name]

        def from_disc(suffix):
            data = (DATA / f'{label} {suffix}').read_bytes()
            assert program.find(data) >= 0, f'{label} {suffix} not in {name}'
            return data
        palette, art, plane = from_disc('Palette.bin'), nemesis(from_disc('Art.nem')), from_disc('Mappings.bin')
        for c in CONSTANTS:
            assert program.hex().find(c) >= 0, f'draw constant {c} not in {name}'
        assert len(palette) == 128 and len(plane) == 40 * 28 * 2 and len(art) % 32 == 0
        tiles = len(art) // 32
        assert not any(art[:32]), f'{name}: tile 0 is not blank (plane A shows it)'
        assert all((w & 0x7ff) < tiles for w in struct.unpack('>1120H', plane)), f'{name}: map past the art'
        blob = b'SEC1' + struct.pack('>H', tiles) + palette + art + plane
        write_bytes(ROOT / f'cd/SECRET{n}.BIN', blob + bytes(-len(blob) % 2048))
        summary.append({'file': f'SECRET{n}.BIN', 'from': name, 'tiles': tiles, 'bytes': len(blob),
                        'sha256': hashlib.sha256(blob).hexdigest()[:12]})
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
