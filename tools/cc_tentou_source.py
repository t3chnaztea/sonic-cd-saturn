#!/usr/bin/env python3
"""Verify Tentou animation calls and terrain corrections in original CC programs."""
import hashlib
import json
import re
import struct
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files, ORIGIN
from retail_span import disc_span


def verify():
    files = disc_files((ROOT / 'build/retail/sonic.iso').read_bytes())
    animate = disc_span('R31A__.MMD',0x5c6a,44,'8ffd24733ace0988b85bb8acc8a8d326893d1b47f9d99618de911692f2f51051')
    scripts = {'fly': bytes.fromhex('000203000102ff'),
               'bomb': bytes.fromhex('0002010001ff')}
    corrections = {
        # subq.w #8,d1; bgt; SUB.w d1,Y; save base Y; hover speed; timer.
        'fall_subtract': disc_span('R31A__.MMD',0xb9b8,28,'d55c4e46d81652068f932d9aab19beff3ace5b07d6b0daed5a74a282b9a50db5'),
        # subq.w #8,d1; ADD.w d1,Y; save base Y.
        'lateral_add': disc_span('R31A__.MMD',0xba6c,12,'68e6d85eb318fc2a94f67b02b1185c72aa6419f7426c150e27e946a267c8d2d2'),
    }
    programs = {}
    for act in (1, 2, 3):
        for era in ('CD' if act == 3 else 'ABCD'):
            name = f'R3{act}{era}'
            p = files[name + '__.MMD']
            assert p.count(animate) == 1, (name, 'animation helper')
            helper = ORIGIN + p.index(animate)
            record = dict(program_sha256=hashlib.sha256(p).hexdigest(), animate=helper)
            for kind, script in scripts.items():
                calls = []
                for m in re.finditer(rb'\x43\xfa(..)\x4e[\xb9\xf9]' +
                                     re.escape(struct.pack('>I', helper)), p, re.S):
                    at = m.start() + 2 + struct.unpack('>h', m[1])[0]
                    if p[at:at + len(script)] == script:
                        calls.append(dict(call=ORIGIN + m.start(), table=ORIGIN + at))
                assert len(calls) == 1, (name, kind, calls)
                record[kind] = calls[0]
            for kind, instructions in corrections.items():
                assert p.count(instructions) == 1, (name, kind)
                record[kind] = ORIGIN + p.index(instructions)
            programs[name] = record
    result = dict(passed=True, programs=programs,
                  scripts={k: v.hex() for k, v in scripts.items()},
                  corrections={k: v.hex() for k, v in corrections.items()},
                  animation_bytes=animate.hex(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  limits='Original script/helper calls and signed terrain-correction instructions; not a complete original-machine playthrough.')
    out = ROOT / 'build/cc1/tentou'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'retail.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print('Verified Tentou animation and terrain corrections in', len(verify()['programs']), 'Sega CD programs')
