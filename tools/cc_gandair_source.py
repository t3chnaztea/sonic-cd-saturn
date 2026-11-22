#!/usr/bin/env python3
"""Verify the launcher's animation scripts and zero-delay reload in Sega CD code."""
import hashlib
import json
import re
import struct
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files, ORIGIN
from retail_span import disc_span


def verify():
    files = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    # Original AnimateObject through move.b (a1),oAnimTime(a0). Unlike the PC
    # reconstruction's patchg, no expression clamps a zero script delay to one.
    animate = disc_span('R31A__.MMD',0x5c6a,44,'8ffd24733ace0988b85bb8acc8a8d326893d1b47f9d99618de911692f2f51051')
    scripts = disc_span('R31A__.MMD',0xcc66,34,'ef47c2fc2ea6ecefe0947e9e15204fc975c6d5c6e359c70b542b136e1c34242b')
    programs = {}
    for act in (1,2,3):
        for era in ('CD' if act==3 else 'ABCD'):
            name=f'R3{act}{era}';program=files[name+'__.MMD']
            assert program.count(animate)==program.count(scripts)==1, name
            target=ORIGIN+program.index(animate);table=ORIGIN+program.index(scripts)
            calls=[]
            for match in re.finditer(rb'\x43\xfa(..)\x4e\xb9(....)', program, re.S):
                address=ORIGIN+match.start()+2+struct.unpack('>h',match[1])[0]
                if address==table:
                    assert struct.unpack('>I',match[2])[0]==target, name
                    calls.append(ORIGIN+match.start())
            assert len(calls)==3, (name,calls)
            programs[name]=dict(program_sha256=hashlib.sha256(program).hexdigest(),
                                animate=target, scripts=table, calls=calls)
    report=dict(passed=True,programs=programs,animation_bytes=animate.hex(),script_bytes=scripts.hex(),
                tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limits='Sega CD animation scripts, call targets and timer reload; not a complete gameplay comparison.')
    out=ROOT/'build/cc1/gandair';out.mkdir(parents=True,exist_ok=True)
    (out/'retail-animation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    print('Verified original launcher animation in',len(verify()['programs']),'Sega CD programs')
