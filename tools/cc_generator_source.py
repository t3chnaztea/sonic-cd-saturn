#!/usr/bin/env python3
"""Verify the complete console CC generator routine, mappings and event table."""
import hashlib
import json
import re
import struct
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files, ORIGIN
from retail_span import disc_span


def sha(data):return hashlib.sha256(data).hexdigest()


def verify():
    files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    programs={}
    source=ROOT/'build/audit/source/src/R3/ET3.C'
    text=source.read_text()
    events=bytes(int(v)&255 for v in re.findall(r'-?\d+',re.search(r'static char tbl0\[64\] =\s*\{(.*?)\};',text,re.S)[1]))
    assert len(events)==64 and events[-1]==255
    baseline=None
    for name in ['R11A']+[f'R3{act}{era}' for act in (1,2,3) for era in ('CD' if act==3 else 'ABCD')]:
        p=files[name+'__.MMD']
        signature=disc_span('R31A__.MMD',0xea28,12,'010195209f548374415b5c5224acc388578ad6a1af8aef2d01fd56321a7dad83')
        assert p.count(signature)==1
        base=p.rfind(disc_span('R31A__.MMD',0xb93c,14,'f0ec1106b3e0357d46642ff791abd5db0004ad145772b6e59cdd0940fc9fb8aa'),0,p.index(signature))
        assert base>=0
        block=bytearray(p[base:base+468])
        offsets=[16,30,108,116,254,264,272,284,294,332,376,416]
        targets=[struct.unpack_from('>I',block,at)[0] for at in offsets]
        assert all(ORIGIN<=v<ORIGIN+len(p) for v in targets)
        for at in offsets:block[at:at+4]=bytes(4)
        assert sha(block)=='6dfcaf41d07356412be11f2acfc3a7b269fa1dd4b07448147f85f7ca4eb96553'
        draw,despawn,maps,explosions,points,solid,unride,solid2,animate,allocate,sound,sound2=targets
        assert solid==solid2 and sound==sound2
        assert maps==ORIGIN+base+468 and explosions==ORIGIN+base+1042
        assert p[explosions-ORIGIN:explosions-ORIGIN+64]==events
        assert p[allocate-ORIGIN:allocate-ORIGIN+22]==disc_span('R31A__.MMD',0x7afc,22,'6667fa7be16cecae589929eb06827cf21a34ca97c4d48375f8fa5fb36d0018f7')
        art=p[base+468:base+1042]
        if baseline is None:baseline=art
        assert art==baseline, (name,'mappings differ from the shared original generator')
        tile_at=base+80+struct.unpack_from('>h',p,base+80)[0]
        tiles=struct.unpack_from('>11H',p,tile_at)
        assert tiles==((1087,1033,0,0,1108,1024,0,0,0,0,0) if name=='R11A' else (830,830,0,0,874,874,0,0,0,0,0))
        # Full-block equality includes CLR.W collision, integer child positions,
        # and no immediate explosion initializer; these differ from PC ET3.C.
        programs[name]=dict(program_sha256=sha(p),base=ORIGIN+base,normalized_code_sha256=sha(block),
            mapping_sha256=sha(art),tile_table=list(tiles),calls=dict(draw=draw,despawn=despawn,points=points,
            solid=solid,unride=unride,animate=animate,allocate=allocate,sound=sound))
    report=dict(passed=True,programs=programs,events=[list(struct.unpack('>Bbb',events[i:i+3])) for i in range(0,63,3)],
        inputs={str(source.relative_to(ROOT)):sha(source.read_bytes()),'tools/cc_generator_source.py':sha(Path(__file__).read_bytes())},
        limits='Complete normalized generator routine, mappings, tile bases, allocation search and explosion schedule. Shared helper behavior, loaded art, native implementation and ordinary gameplay require separate checks.')
    out=ROOT/'build/cc1/generator';out.mkdir(parents=True,exist_ok=True)
    (out/'retail.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':print('Verified generator in',len(verify()['programs']),'console programs (ten CC and PPZ baseline)')
