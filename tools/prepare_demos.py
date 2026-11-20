#!/usr/bin/env python3
"""Extract the retail attract demo input from the user's disc into cd/DEMOS.BIN.

Level/Functions (General).asm ReadControllers plays 0x800 words of pad state
(hold << 8 | tap, Mega Drive bits) from demoDataPtr while demoMode is set; the
level restarts once demoDataIndex reaches $800 (Level/Main.asm:405). The data
sits inside the level's chunk data (Level/_Definitions.inc DemoData =
LevelChunks + DemoDataRel). DEMO11A uses DemoDataRel $6C00; DEMO43C and DEMO82A,
whose chunk data is smaller, carry it at $3600 and $4000. Each offset holds the
only 0x800-word window in its file that is valid pad input (every tap bit held,
no Start), which this tool checks on every build.

Output: three 0x1000-byte blocks in the attract order R11A, R43C, R82A. The disc
image stays private; nothing extracted is committed (cd/ is ignored by Git).
"""
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
ISO = ROOT / 'build/retail/sonic.iso'
OUT = ROOT / 'cd/DEMOS.BIN'
CHUNKS = 0x210000          # LevelDataIndex chunk pointer in all three DEMO programs
DEMOS = [('DEMO11A.MMD', 0x6C00), ('DEMO43C.MMD', 0x3600), ('DEMO82A.MMD', 0x4000)]


def disc():
    src = (ROOT / 'tools/extract_mmd.py').read_text()
    ns = {}
    exec(compile(src.split('def main():')[0], 'extract_mmd', 'exec'), ns)
    if ISO.exists():
        iso = ISO.read_bytes()
    else:
        raw = (ISO.parent / 'sonic.bin').read_bytes()
        sectors = min(len(raw) // 2352, 330000)
        iso = b''.join(raw[i * 2352 + 16:i * 2352 + 2064] for i in range(sectors))
    return ns['disc_files'](iso)


def valid(words):
    return all(((w & 0xFF) & ~(w >> 8)) == 0 and not w & 0x8080 for w in words)


def main():
    files = disc()
    out = bytearray()
    for name, rel in DEMOS:
        data = files[name]
        # LevelDataIndex: $03 tiles, $02 blocks, then the chunk pointer.
        if not re.search(rb'\x03[\x20-\x23]..\x02[\x20-\x23]..\x00\x21\x00\x00', data, re.S):
            sys.exit(f'FAIL: demos: {name} has no LevelDataIndex with chunks at {CHUNKS:#x}')
        at = CHUNKS - 0x200000 + rel
        block = data[at:at + 0x1000]
        words = struct.unpack('>2048H', block)
        if not valid(words) or sum(1 for w in words if w) < 300:
            sys.exit(f'FAIL: demos: {name} +{at:#x} is not pad input')
        out += block
    OUT.write_bytes(out)
    print(f'Demos: {", ".join(n for n, _ in DEMOS)} -> {OUT.relative_to(ROOT)} ({len(out)} B)')


if __name__ == '__main__':
    main()
