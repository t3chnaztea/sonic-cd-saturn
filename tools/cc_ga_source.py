#!/usr/bin/env python3
"""Verify GA's unterminated timed scripts and console animation call sites."""
import hashlib
import json
import re
import struct
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files, ORIGIN
from retail_span import disc_span


def verify():
    programs={}
    files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    animate=disc_span('R31A__.MMD',0x5c6a,44,'8ffd24733ace0988b85bb8acc8a8d326893d1b47f9d99618de911692f2f51051')
    main=disc_span('R31A__.MMD',0xb49c,19,'bafadabc4592a6b0dd7728dc37d4c8b955b5db02e60dcba9922e51c930a2d8cb')
    child=disc_span('R31A__.MMD',0xb5c0,8,'9e1a182a96f146ef3e54a4e37e2230e859b5255e21879f2742da4a7af4bc4f13')
    for act in (1,2,3):
        for era in ('CD' if act==3 else 'ABCD'):
            name=f'R3{act}{era}';p=files[name+'__.MMD']
            assert p.count(animate)==p.count(main)==1,name
            helper=ORIGIN+p.index(animate);table=ORIGIN+p.index(main)
            calls=list(re.finditer(re.escape(b'\x43\xf9'+struct.pack('>I',table)+b'\x4e\xb9'+struct.pack('>I',helper)),p))
            assert len(calls)==1,(name,'main call')
            children=[]
            for m in re.finditer(rb'\x43\xfa(..)\x4e\xf9'+re.escape(struct.pack('>I',helper)),p,re.S):
                at=m.start()+2+struct.unpack('>h',m[1])[0]
                if p[at:at+len(child)]==child:children.append((ORIGIN+m.start(),ORIGIN+at))
            assert len(children)==1,(name,'particle call')
            programs[name]=dict(program_sha256=hashlib.sha256(p).hexdigest(),main_table=table,
                main_call=ORIGIN+calls[0].start(),particle_call=children[0][0],particle_table=children[0][1],animate=helper)
    result=dict(passed=True,programs=programs,main_scripts=main.hex(),particle_script=child.hex(),
                animation_bytes=animate.hex(),tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limits='Original Sega CD script bytes and animation helper call sites, not a full original-machine playthrough.')
    out=ROOT/'build/cc1/ga';out.mkdir(exist_ok=True,parents=True)
    (out/'retail-animation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print('Verified GA animation in',len(verify()['programs']),'Sega CD programs')
