#!/usr/bin/env python3
"""Correct the generated PC PISTON6.C fixture to the retail 68k behavior.

The PC scratch source differs from ObjPiston_Init and ObjPiston_Move in the
scddisasm reference. The actor gate compiles the corrected generated copy;
the audited source file remains untouched.
"""
from pathlib import Path
import sys


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"PISTON6 fixture changed: expected one {old!r}")
    return text.replace(old, new)


asm = Path('.deps/scddisasm/src/Level/Wacky Workbench/Objects/Piston/Main.asm').read_text()
for required in (
    'move.w\t#-32,d0\n\tbsr.w\tObjPiston_SetupSolidSide',
    'move.w\t#32,d0\n\tbsr.w\tObjPiston_SetupSolidSide',
    'subq.b\t#1,oPistonOff(a0)\n\tbcc.s\t.End',
):
    if required not in asm:
        raise SystemExit(f"retail PISTON6 reference changed: {required!r}")

path = Path(sys.argv[1])
source = path.read_text()
source = replace_once(source,
                      'pis6_setdata(actionwk, a1, 32); \n  if (actwkchk(&a1) == 0) pis6_setdata(actionwk, a1, -32);',
                      'pis6_setdata(actionwk, a1, -32); \n  if (actwkchk(&a1) == 0) pis6_setdata(actionwk, a1, 32);')
source = replace_once(source,
                      '--actionwk->actfree[17]; \n    if ((char)actionwk->actfree[17] > 0) return;',
                      'if (actionwk->actfree[17]-- != 0) return;')
path.write_text(source)
