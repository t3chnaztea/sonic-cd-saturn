"""Independent original sprite-list compositor: first opaque piece wins.

Unlike the production piece painter, walk destination pixels and search the
original ordered sprite list. Piece-local flips and column-major tile order
come from the five-byte mapping records. Palette/foreground priority does not
reverse sprite-list priority (DrawSprite / make_lut_obj).
"""
import struct

# Pinned from the preserved V0.047 audit, not regenerated from new artwork.
CORRECTED_FRAMES = {24:26,25:15,26:26,27:15,37:8,43:18,44:102,45:84,48:106,
                   49:102,51:102,52:84,55:98,56:100,79:42,80:132,81:350,82:350,
                   83:434,84:434,85:434,98:122,103:639,104:567,105:226,106:138,
                   299:68,300:15,301:68,342:1,351:42,352:42,353:42}


def source_sprite(mapping, art, colors, width=64, y_shift=0, height=64, *, legacy_last=False):
    assert len(mapping) >= 1 + mapping[0] * 5
    assert len(colors) == 32 and width > 0 and height > 0
    palette = struct.unpack('>16H', colors)
    pieces = []
    for n in range(mapping[0]):
        y, size, tile, x = struct.unpack_from('>bBHb', mapping, 1 + n * 5)
        assert size < 16
        w, h = (((size >> 2) & 3) + 1) * 8, ((size & 3) + 1) * 8
        assert ((tile & 0x7ff) + w * h // 64) * 32 <= len(art)
        pieces.append((x + width // 2, y + 32 + y_shift, w, h, tile))
    out = bytearray(width * height * 2)
    for y in range(height):
        for x in range(width):
            for ox, oy, w, h, tile in pieces:
                sx, sy = x - ox, y - oy
                if not (0 <= sx < w and 0 <= sy < h):
                    continue
                if tile & 0x800: sx = w - 1 - sx
                if tile & 0x1000: sy = h - 1 - sy
                tile_id = (tile & 0x7ff) + (sx // 8) * (h // 8) + sy // 8
                packed = art[tile_id * 32 + (sy & 7) * 4 + (sx & 7) // 2]
                index = (packed >> (0 if sx & 1 else 4)) & 15
                if not index: continue
                struct.pack_into('>H', out, (y * width + x) * 2, palette[index])
                if not legacy_last: break
    return bytes(out)
