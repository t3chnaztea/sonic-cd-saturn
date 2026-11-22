#!/usr/bin/env python3
"""Move a "Thank You" screen object into the front-end overlay (src/saturn.x .zone_R0).

  credits_sections.py OBJECT

src/credits.c and src/credits_saturn.c keep their plain names (src/credits.c is also
built on the host for tools/test_credits.py). The Makefile compiles each outside LTO
and then runs this on the object: every allocated section and every defined symbol
gets the overlay prefix (.text.X -> .text.fe_cr_X, _X -> _fe_cr_X), and so do the
references to the src/credits.h API. Names that already start with fe_ stay, so
fe_credits_thanks keeps the name front-end code and src/ending.c call. A .bss or
.data section without a name would stay resident; the object must not have one.
tools/test_zone_code.py checks the result on every link.
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / '.toolchain/bin'
PREFIX = 'fe_cr_'


def main():
    obj = sys.argv[1]
    sections = re.findall(r'^\s*\[\s*\d+\]\s+(\S+)\s+(\S+)', subprocess.check_output(
        [BIN / 'sh-elf-readelf', '-W', '-S', obj], text=True), re.M)
    args = []
    for name, kind in sections:
        m = re.match(r'(\.text|\.rodata|\.data|\.bss)(\..*)?$', name)
        if not m:
            continue
        base, rest = m.group(1), (m.group(2) or '')[1:]
        if rest.startswith('fe_'):
            continue
        if base in ('.bss', '.data') and not rest:
            size = int(re.search(rf'\s{re.escape(name)}\s+\S+\s+\S+\s+\S+\s+([0-9a-f]+)',
                                 subprocess.check_output([BIN / 'sh-elf-readelf', '-W', '-S', obj], text=True))[1], 16)
            if size:
                sys.exit(f'credits_sections: {obj} has {size} B in {name}, which would stay resident')
            continue
        if base == '.bss':
            sys.exit(f'credits_sections: {obj} section {name} is zero-initialised state (.bss stays resident)')
        if base == '.text' and not rest:
            continue
        args.append(f'--rename-section={name}={base}.{PREFIX}{rest}')
    api = set(re.findall(r'\b(scd_credits_\w+)\s*\(', (ROOT / 'src/credits.h').read_text()))
    renamed = set()
    for line in subprocess.check_output([BIN / 'sh-elf-nm', obj], text=True).splitlines():
        p = line.split()
        name = p[-1]
        plain = name[1:] if name.startswith('_') else name
        if plain.startswith('fe_') or name.startswith('.'):
            continue
        defined = len(p) == 3 and p[1] not in 'Uw'
        if defined or plain in api:
            if name not in renamed:
                renamed.add(name)
                args.append(f'--redefine-sym={name}={name[:len(name) - len(plain)]}{PREFIX}{plain}')
    if args:
        subprocess.check_call([BIN / 'sh-elf-objcopy', *args, obj])


if __name__ == '__main__':
    main()
