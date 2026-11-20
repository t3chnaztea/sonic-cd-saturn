#!/usr/bin/env python3
"""Independent STF1 decoder, pixel/control model. No extraction or emulator import.

H32 source content is256x224. Saturn uses the title grid205/256 across320.
Full actual original/Saturn captures remain required. A pack model is not its own
text-layout oracle. The comparator accepts already normalized 3-bit DAC levels.
"""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

SOURCE_STEP = 205
UP, DOWN, START = 1, 2, 128


def decode(blob):
    if len(blob) < 32 or len(blob) > 0x14000 or len(blob)%2048 or blob[:4] != b'STF1':
        raise ValueError('invalid STF1 file')
    size, tiles, bg, text, records, crc, colours = struct.unpack_from('>7I', blob, 4)
    if not 1 <= tiles <= 2048 or (bg, text, records, colours) != (896, 4096, 28, 64):
        raise ValueError('invalid counts')
    expected = 32+128+tiles*32+2*(bg+text)
    if size != expected or not 0 <= len(blob)-size < 2048 or any(blob[size:]):
        raise ValueError('invalid length/padding')
    if zlib.crc32(blob[32:size]) != crc: raise ValueError('CRC mismatch')
    palette = struct.unpack_from('>64H', blob, 32)
    if any(v & ~0xeee for v in palette): raise ValueError('invalid palette')
    art = blob[160:160+tiles*32]
    if any(art[:32]): raise ValueError('nonblank source tile0')
    maps = struct.unpack_from('>4992H', blob, 160+tiles*32)
    if any((v & 2047) >= tiles for v in maps): raise ValueError('absent tile')
    return palette, art, maps[:896], maps[896:]


def ui_step(scroll, prior_hold, newly_read_hold):
    """MainLoop uses last VInterrupt hold; Start uses this VSync's hold."""
    if type(scroll) is not int or not 0 <= scroll <= 511: raise ValueError('invalid scroll')
    if prior_hold & DOWN: scroll = min(scroll+2, 511)
    if prior_hold & UP: scroll = max(scroll-2, 0)
    return scroll, bool(newly_read_hold & START)


def fade_palettes(target, outward=False):
    if len(target) != 64 or any(v & ~0xeee for v in target): raise ValueError('invalid target')
    current = list(target) if outward else [0]*64
    for shift in ((0, 4, 8) if outward else (8, 4, 0)):
        mask = 14 << shift
        for k in range(8):
            for i in range(64):
                v = current[i] & mask if outward else target[i] & mask
                v = max(0, v-(2*k << shift)) if outward else min(v, 2*k << shift)
                current[i] = (current[i] & ~mask) | v
            yield tuple(current)


def render(blob, scroll, *, port=False, palette=None):
    if type(scroll) is not int or not 0 <= scroll <= 511: raise ValueError('invalid scroll')
    colours, art, bg, text = decode(blob)
    if palette is not None:
        if len(palette) != 64 or any(v & ~0xeee for v in palette): raise ValueError('invalid palette')
        colours = palette
    def rgb(word): return bytes(((word >> n) & 14)*255//14 for n in (0, 4, 8))
    def pixel(word, x, y):
        if word & 0x800: x = 7-x
        if word & 0x1000: y = 7-y
        value = art[(word & 2047)*32+y*4+x//2]
        index = (value >> (0 if x & 1 else 4)) & 15
        return (colours[((word >> 13)&3)*16+index], index, bool(word & 0x8000))
    width = 256
    result = bytearray(rgb(colours[0])*(width*224))
    for y in range(224):
        ty = (y+scroll)%1024
        for x in range(256):
            a = pixel(text[(ty//8)*32+x//8], x%8, ty%8)
            b = pixel(bg[(y//8)*32+x//8], x%8, y%8)
            # MD priority: A-high, B-high, A-low, B-low; colour0 transparent.
            candidates = [a] if a[1] and a[2] else []
            if b[1] and b[2]: candidates.append(b)
            if a[1] and not a[2]: candidates.append(a)
            if b[1] and not b[2]: candidates.append(b)
            colour = candidates[0][0] if candidates else colours[0]
            at = (y*width+x)*3
            result[at:at+3] = rgb(colour)
    return (320,224,expand_h32(bytes(result))) if port else (256,224,bytes(result))


def expand_h32(source):
    """Pure presentation model; exact same source phase as title reduction."""
    if len(source) != 256*224*3: raise ValueError('source must be complete256x224 RGB')
    out = bytearray()
    for y in range(224):
        for x in range(320):
            at = (y*256+(x*SOURCE_STEP//256))*3
            out.extend(source[at:at+3])
    return bytes(out)


def compare_full_levels(reference, actual):
    """Actual captured source256x224 vs port320x224, normalized DAC levels.

    Caller binds fixed active rectangles/frame phase and source/core receipts.
    No per-image crop search, phase search, neighbour tolerance or layout model.
    """
    if len(reference) != 256*224*3 or len(actual) != 320*224*3:
        raise ValueError('need full reference256x224 and actual320x224 captures')
    if any(v > 7 for v in reference+actual): raise ValueError('expected normalized 3-bit DAC levels')
    if len(set(reference[i:i+3] for i in range(0,len(reference),3))) < 2:
        raise ValueError('flat frame cannot establish display geometry')
    mismatches = edges = 0
    for y in range(224):
        for x in range(320):
            r = (y*256+(x*205//256))*3; a = (y*320+x)*3
            if reference[r:r+3] != actual[a:a+3]:
                mismatches += 1; edges += x < 32 or x >= 288
    if mismatches: raise ValueError(f'full-frame mismatches={mismatches}, edge mismatches={edges}')
    return {'matched_pixels':320*224,'matched_edge_pixels':64*224,'source_step':[205,256]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pack', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--scroll', type=int, required=True); p.add_argument('--port', action='store_true')
    a = p.parse_args(); blob = a.pack.read_bytes()
    w, h, data = render(blob, a.scroll, port=a.port)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(f'P6\n{w} {h}\n255\n'.encode()+data)
    print(json.dumps({'status': 'rendered', 'pack_sha256': hashlib.sha256(blob).hexdigest(),
                      'scroll': a.scroll, 'width': w, 'height': h,
                      'viewport': 'title-grid205/256' if a.port else 'source-H32',
                      'acceptance': False}))


if __name__ == '__main__': main()
