#!/usr/bin/env python3
"""Generate nine original effect scripts only after matching retail bytes."""
import hashlib,json,struct
from convert_assets import ROOT,DATA
from sonic_animation_assets import assemble_table
from extract_mmd import disc_files,unique
from generated_io import write_text

def generate():
    path=DATA/'_Objects/Powerup/Data/Animations.asm'
    blob=assemble_table(path)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    at=unique(program,blob);offsets=list(struct.unpack_from('>9H',blob))
    assert offsets==sorted(offsets) and offsets[0]==18
    scripts=[blob[a:b] for a,b in zip(offsets,offsets[1:]+[len(blob)])]
    assert len(scripts)==9
    for n,script in enumerate(scripts):
        start=at+struct.unpack_from('>H',program,at+2*n)[0]
        assert program[start:start+len(script)]==script
        assert 255 in script and all(b<128 for b in script[:script.index(255)])
    lines=['/* Original power-up scripts, independently matched to retail. */']
    for n,script in enumerate(scripts):lines.append(f'static const uint8_t powerup_anim_{n}[]={{'+','.join(map(str,script))+'};')
    lines.append('static const uint8_t *const powerup_animations[9]={'+','.join(f'powerup_anim_{n}' for n in range(9))+'};')
    lines.append('static const uint8_t powerup_animation_sizes[9]={'+','.join(str(len(s)) for s in scripts)+'};')
    write_text(ROOT/'assets/generated/powerup-animation.inc','\n'.join(lines)+'\n')
    return dict(retail_table=at+0x200000,retail_program_sha256=hashlib.sha256(program).hexdigest(),
        script_sha256=hashlib.sha256(blob).hexdigest(),scripts=len(scripts))
if __name__=='__main__':print(json.dumps(generate(),indent=2))
