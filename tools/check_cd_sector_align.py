#!/usr/bin/env python3
"""Fail the build unless libyaul cdfs.c's sector buffer is 4-aligned.

_sector is a __packed union (alignment 1) that the CD block transfer fills
with word stores; at an odd address the boot stops with a CPU address error
(commit aec6431). src/saturn.x places *(.bss._sector) first in .bss, which only
works while libyaul is built with -fdata-sections. This reads the linked
address from the ELF with sh-elf-nm.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
NM = ROOT / '.toolchain/bin/sh-elf-nm'


def main():
    out = subprocess.run([str(NM), str(ELF)], capture_output=True, text=True, check=True).stdout
    hits = [line.split() for line in out.splitlines() if line.split()[-1:] == ['__sector']]
    if len(hits) != 1:
        sys.exit(f'FAIL: cdfs sector buffer: {len(hits)} __sector symbols in {ELF.name}')
    address = int(hits[0][0], 16)
    if address & 3:
        sys.exit(f'FAIL: cdfs sector buffer __sector at {address:#010x} is not 4-aligned')
    print(f'PASS: cdfs sector buffer __sector at {address:#010x} (4-aligned)')


if __name__ == '__main__':
    main()
