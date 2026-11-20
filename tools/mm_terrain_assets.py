#!/usr/bin/env python3
"""Metallic Madness animated tiles from the retail R81A-R83D MMDs -> assets/generated/mm_terrain.inc.

    python3 tools/mm_terrain_assets.py           parse the routines, write the include
    python3 tools/mm_terrain_assets.py --check   re-parse and fail if the include differs

Same UpdateAnimTiles shape as Wacky Workbench (tools/ww_terrain_assets.py):
up to five const/script calls per program, no gates; R81B's routine is a bare
jmp (no animated tiles).  Art is retail data (assets/generated, never src/).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import ww_terrain_assets as W  # noqa: E402

OUT = ROOT/'assets/generated/mm_terrain.inc'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    text, report = W.build(8, 'mm', 5)
    assert all(v['gate'] is None for v in report.values()), 'R8 gates'
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            sys.exit(f'FAIL: {OUT.relative_to(ROOT)} differs from the retail routines')
        print(f'PASS: MM animated tiles: {len(report)} retail UpdateAnimTiles routines parsed, include current')
        return
    OUT.write_text(text)
    print('wrote', OUT.relative_to(ROOT))
    for k, v in report.items():
        print(k, [(c['kind'], c['tim'], c['frames'], c['longs'], c['cell']) for c in v['calls']])


if __name__ == '__main__':
    main()
