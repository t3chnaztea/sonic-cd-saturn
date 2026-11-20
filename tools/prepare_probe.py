#!/usr/bin/env python3
"""Prepare only the upstream ACTION code used by the executable arithmetic probe.

The full stage audit remains separate. Fixing these unions is necessary but
not sufficient to port the whole engine: raw actor-word aliases still need work.
"""
import pathlib
import re
from audit_source import ROOT, UPSTREAM
from generated_io import write_text

out=ROOT/'build/probe-source'
out.mkdir(parents=True,exist_ok=True)
for original in (UPSTREAM/'src').glob('*.H'):
    content=original.read_text()
    if original.name=='TYPES.H':
        content=content.replace('  union {\n    sprite_data spra[20];\n    sprite_data spr[];\n  };','  sprite_data spra[20];')
        for base in ('char','short','unsigned char','unsigned short'):
            old=f'  {base} l;\n  {base} h;'
            content=content.replace(old,f'#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__\n  {base} h;\n  {base} l;\n#else\n{old}\n#endif')
        for base in ('char','unsigned char'):
            old='\n'.join(f'  {base} b{i};' for i in (4,3,2,1))
            new='\n'.join(f'  {base} b{i};' for i in (1,2,3,4))
            content=content.replace(old,f'#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__\n{new}\n#else\n{old}\n#endif')
    write_text(out/original.name,content)
content=(UPSTREAM/'src/ACTION.C').read_text()
# Signed shifts of negative velocities are undefined in C. Multiplication has
# identical intended fixed-point behavior here and is well-defined in range.
content=content.replace('spd.w << 8','(int)spd.w * 256').replace('spd << 8','spd * 256')
write_text(out/'action.c',content)
