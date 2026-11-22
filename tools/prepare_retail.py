#!/usr/bin/env python3
"""Write the retail files later steps read from build/retail.

tools/prepare_audio.py extracts the user's CHD to build/retail/sonic.bin/.cue.
This writes build/retail/sonic.iso (the data track's Mode 1 user data) and
copies the programs that tools read by path (the boot program IPX___.MMD that
the emulator captures load, and the special-stage and backup-RAM programs)
out of that ISO. A file already present must be byte identical.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from background_tables import retail_iso  # noqa: E402
from extract_mmd import disc_files  # noqa: E402

RETAIL = ROOT/'build/retail'
FILES = ('IPX___.MMD', 'SPMM__.MMD', 'SPSS__.BIN', 'SPX___.BIN', 'BRAMINIT.MMD', 'MDINIT.MMD')


def main():
    retail_iso()
    disc = disc_files((RETAIL/'sonic.iso').read_bytes())
    written = 0
    for name in FILES:
        path = RETAIL/name
        if path.exists():
            if path.read_bytes() != disc[name]:
                raise SystemExit(f'{path} differs from {name} on the disc; remove it to re-extract')
            continue
        path.write_bytes(disc[name])
        written += 1
    print(f'Retail files: sonic.iso and {len(FILES)} programs in build/retail ({written} written)')


if __name__ == '__main__':
    main()
