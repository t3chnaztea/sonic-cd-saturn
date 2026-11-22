#!/usr/bin/env python3
"""Write a backup RAM image whose save holds time stones 1..k (special stage k+1 next).

The record is the src/save.h "SCDS" v2 layout (32 bytes, big endian: magic,
version 2, size 32, generation, zone, act, era, time_stones, good_acts,
good_zones, completed, spec_stage, eight zero bytes, CRC32 of bytes 0-27),
placed in the BIOS-created two-block file of a backup image that
tools/test_save_progression.py wrote (build/save-progression/debug.bin; the
record straddles the block link at 192-195, as that test lays it out).
spec_stage is the original's curSpecStage (IPX.asm svSpecStage): after winning
stages 1..k in order it is k (special_progress.h scd_special_stage_after).

  special_entry_save.py ZONE ACT K OUTPUT [--base IMAGE]
"""
import argparse, struct, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def record(zone, act, stones, spec_stage, generation=1):
    data = b'SCDS' + bytes([2, 32, 0, 0]) + struct.pack('>I', generation)
    data += bytes([zone, act, 0, stones, 0, 0, 0, spec_stage]) + bytes(8)
    return data + struct.pack('>I', zlib.crc32(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('zone', type=int, help='level-select zone index (0 PPZ .. 6 MM)')
    parser.add_argument('act', type=int, help='0-based act')
    parser.add_argument('k', type=int, choices=range(0, 7), help='stones 1..k held (0: none)')
    parser.add_argument('output', type=Path)
    parser.add_argument('--base', type=Path, default=ROOT / 'build/save-progression/debug.bin')
    args = parser.parse_args()
    image = bytearray(args.base.read_bytes())
    assert image[132:143] == b'SCDSATURN00' and image[166:170] == b'SCDS', 'base is not a save-progression backup image'
    stones = (1 << args.k) - 1
    # special_progress.h scd_special_stage_from_stones: stages are won in cyclic
    # order from 0, so with stones 1..k held the next stage index is k.
    spec_stage = args.k % 7
    data = record(args.zone, args.act, stones, spec_stage)
    image[166:192], image[196:202] = data[:26], data[26:]
    args.output.write_bytes(image)
    print(f'save: zone={args.zone} act={args.act} stones={stones:#04x} spec_stage={spec_stage} -> {args.output}')


if __name__ == '__main__':
    main()
