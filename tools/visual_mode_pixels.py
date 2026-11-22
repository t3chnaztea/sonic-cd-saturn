#!/usr/bin/env python3
"""Visual Mode screens as Mega Drive colour levels: the retail captures
(tools/visual_mode_retail.py), the cd/VISMODE.BIN model (tools/visual_mode_assets.py)
and Saturn screenshots (tools/frontend_emulator_test.c PPM). Each pixel becomes its
(r, g, b) 3-bit DAC level, so a Genesis Plus GX RGB565 frame and a Saturn RGB555
frame compare exactly.

  python3 tools/visual_mode_pixels.py     model against the retail captures, all five selections
"""
import struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RETAIL = ROOT / 'build/visual-mode'
MD_LEVELS = [0, 52, 87, 116, 144, 172, 206, 255]   # Sega CD DAC (tools/fmv_extract.py)


def level(v8):
    return min(range(8), key=lambda i: abs(MD_LEVELS[i] - v8))


def linear(v8):
    """Genesis Plus GX writes the 3-bit levels linearly (level * 255 / 7)."""
    return (v8 * 7 + 127) // 255


def retail(name):
    """retail-<name>.rgb565: 320 x 224 rows of levels."""
    data = (RETAIL / f'retail-{name}.rgb565').read_bytes()
    w, h = struct.unpack_from('>HH', data)
    px = data[4:]
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            v = px[(y * w + x) * 2] | px[(y * w + x) * 2 + 1] << 8
            row.append((linear((v >> 11) * 255 // 31), linear(((v >> 5) & 63) * 255 // 63), linear((v & 31) * 255 // 31)))
        rows.append(row)
    return rows


def saturn(path):
    """A harness PPM as (width, height, rows of levels)."""
    data = Path(path).read_bytes()
    head = data.split(b'\n', 3)
    w, h = map(int, head[1].split())
    body = head[3]
    lut = {}
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            c = body[(y * w + x) * 3:(y * w + x) * 3 + 3]
            if c not in lut:
                lut[c] = tuple(level(v) for v in c)
            row.append(lut[c])
        rows.append(row)
    return w, h, rows


def model(sel, blob=None):
    """The menu with option `sel` highlighted, drawn from cd/VISMODE.BIN as the Mega Drive
    would: sprites (option layer) over plane A, palette line 1 for the selected option."""
    b = blob or (ROOT / 'cd/VISMODE.BIN').read_bytes()
    n = struct.unpack_from('>H', b, 4)[0]
    pal = struct.unpack_from('>64H', b, 6)
    tiles = b[134:134 + n * 32]
    plane = struct.unpack_from('>1120H', b, 134 + n * 32)
    layer = struct.unpack_from('>1120H', b, 134 + n * 32 + 2240)

    def pixel(w, x, y, line):
        tx = 7 - (x & 7) if w & 0x800 else x & 7
        ty = 7 - (y & 7) if w & 0x1000 else y & 7
        t = tiles[(w & 0x7ff) * 32 + ty * 4 + (tx >> 1)]
        i = t & 15 if tx & 1 else t >> 4
        return pal[line * 16 + i] if i else None
    rows = []
    for y in range(224):
        row = []
        for x in range(320):
            at = (y >> 3) * 40 + (x >> 3)
            c = None
            if layer[at]:
                c = pixel(layer[at], x, y, 1 if (y >> 4) - 7 == sel else 0)
            if c is None and plane[at]:
                c = pixel(plane[at], x, y, plane[at] >> 13 & 3)
            if c is None:
                c = pal[0]
            row.append(((c >> 1) & 7, (c >> 5) & 7, (c >> 9) & 7))
        rows.append(row)
    return rows


def origin(shot, want):
    """Offset of the 320 x 224 screen inside a harness frame, or None."""
    w, h, px = shot
    for dy in range(0, h - 223):
        for dx in range(0, w - 319):
            if all(px[dy + y][dx + x] == want[y][x] for y in range(0, 224, 7) for x in range(0, 320, 5)):
                return dx, dy
    return None


def differ(a, b, dx=0, dy=0):
    """Pixels of the 320 x 224 screen b that a (at dx, dy) does not show."""
    return sum(1 for y in range(224) for x in range(320) if a[dy + y][dx + x] != b[y][x])


if __name__ == '__main__':
    if not (RETAIL / 'retail-sel4.rgb565').exists():
        import subprocess
        subprocess.run([sys.executable, str(ROOT / 'tools/visual_mode_retail.py')], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    bad ={s: differ(model(s), retail(f'sel{s}')) for s in range(5)}
    print(('PASS' if not any(bad.values()) else 'FAIL') + f': visual mode model against retail, mismatched pixels {bad}')
    sys.exit(1 if any(bad.values()) else 0)
