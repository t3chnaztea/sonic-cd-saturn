#!/usr/bin/env python3
"""Prove KAMA/BANPA console semantics where reconstructed PC code differs."""
import hashlib,json,re,struct
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files,ORIGIN
from retail_span import disc_span

def verify():
    files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    animate=disc_span('R31A__.MMD',0x5c6a,44,'8ffd24733ace0988b85bb8acc8a8d326893d1b47f9d99618de911692f2f51051')
    scripts={
        'mantis':disc_span('R31A__.MMD',0xd25a,31,'fec1533c31f365f30c4290f9a67398d975c19c455d0f741ac872c04ea03d672f'),
        'blade':disc_span('R31A__.MMD',0xd3ca,20,'da104fe20b83d1e8055649c6388d10b0e8902f0b3e36b71b842ab56eb96c17e2'),
    }
    instructions={
        'attack_range':disc_span('R31A__.MMD',0xd0d8,12,'f894c1effa95800b55fdeb5b0b86fbd347b2c4baa1d6c503e16acd984d60634a'), # unsigned dy<32, dx<96
        'floor_range':disc_span('R31A__.MMD',0xd16c,16,'ac3f4fc398f30e70fc74ab4822c2bbae25ddf1322ba95e275ec67e65040098d7'), # -7 <= d < 7
        'turn_animation_word':disc_span('R31A__.MMD',0xd180,16,'819df787659c4e03f95293b4d078b9992a0161196e7d10367c440430bb214a24'),
        'blade_parent':disc_span('R31A__.MMD',0xd304,12,'4dcab9d9242d2de6f8f8dfd4495ac46e176094bf334e5da528ee9441e8b19108'),
        'blade_damage_timer':disc_span('R31A__.MMD',0xd352,14,'3233c541a8770d8d61b25327cb9b0f32adaa9b7d78cc138524658cc5c0c1f483'),
        'bumper_tile':disc_span('R31A__.MMD',0xb15c,12,'65e6da3122ec0e5a7375e261178d3ffc8232cda64f6228cea8b27303bff11264'),
        'bumper_init_fallthrough':disc_span('R31A__.MMD',0xb1a0,24,'a42aad433c1dcd0527d03324359422995d4c726d51997c177d6e3a65533a5122'),
        'hurt_tail_no_ring_sound':disc_span('R31A__.MMD',0x73b8,74,'463cd7c9c5c13cd9555500637f248acf54ecfe827b767b0049bd178664b2214a'),
    }
    programs={}
    for act in (1,2,3):
        for era in ('CD' if act==3 else 'ABCD'):
            name=f'R3{act}{era}';p=files[name+'__.MMD'];assert p.count(animate)==1,name
            helper=ORIGIN+p.index(animate)
            record=dict(program_sha256=hashlib.sha256(p).hexdigest(),animate=helper)
            for kind,script in scripts.items():
                assert p.count(script)==1,(name,kind)
                at=p.index(script);calls=[]
                for m in re.finditer(rb'\x43\xfa(..)\x4e[\xb9\xf9]',p,re.S):
                    target=m.start()+2+struct.unpack('>h',m[1])[0]
                    if target==at and p[m.end():m.end()+4]==struct.pack('>I',helper):calls.append(ORIGIN+m.start())
                assert len(calls)==(1 if kind=='mantis' else 2),(name,kind,calls)
                record[kind]=dict(table=ORIGIN+at,calls=calls)
            for kind,code in instructions.items():
                assert p.count(code)==1,(name,kind)
                record[kind]=ORIGIN+p.index(code)
            programs[name]=record
    result=dict(passed=True,programs=programs,scripts={k:v.hex() for k,v in scripts.items()},
                instructions={k:v.hex() for k,v in instructions.items()},animation_bytes=animate.hex(),
                tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limits='Exact original animation calls and console-specific instruction sequences; not a complete original-machine playthrough.')
    out=ROOT/'build/cc1/kama';out.mkdir(parents=True,exist_ok=True)
    (out/'retail.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':print('Verified Kama/Banpa console semantics in',len(verify()['programs']),'programs')
