#!/usr/bin/env python3
"""Verify all Sonic scripts against retail; prepare data for the native animator.

Scripts feed the native player adapter. The raw DPLC pack feeds the build-time
frame composer; gameplay streams its losslessly precomposed output instead.
"""
import hashlib,json,re,struct
from pathlib import Path
from convert_assets import ROOT,DATA,assembly_frames
from extract_mmd import disc_files,unique
from generated_io import write_text, write_bytes

OUT=ROOT/'assets/generated'
QA=ROOT/'build/sonic-animation'
FOLDER=DATA/'_Objects/Sonic/Data'

def assemble_table(path):
    """Numeric dc.b/dc.w pointer table with explicit source padding/aliases."""
    lines=[line.split(';')[0].strip() for line in path.read_text().splitlines()]
    refs=[m[1] for line in lines if (m:=re.search(r'dc\.w\s+([\w.]+)-[\w.]',line))]
    out=bytearray(len(refs)*2);offsets={}
    for line in lines:
        if re.search(r'dc\.w\s+([\w.]+)-[\w.]',line):continue
        if m:=re.match(r'([\w.]+):',line):offsets[m[1]]=len(out)
        if re.search(r'\beven\b',line) and len(out)&1:out.append(0)
        if m:=re.search(r'dc\.([bw])\s+(.+)',line):
            width=1 if m[1]=='b' else 2
            for value in m[2].split(','):
                value=value.strip();n=int(value[1:],16) if value.startswith('$') else int(value)
                out+=(n&((1<<(8*width))-1)).to_bytes(width,'big')
    for i,label in enumerate(refs):struct.pack_into('>H',out,i*2,offsets[label])
    return bytes(out)

def generate():
    OUT.mkdir(exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    # ObjSonic_Animate: lea Ani_Sonic,a1; moveq #0,d0; move.b oAnim(a0),d0;
    # cmp.b oPrevAnim(a0),d0. Field offsets are Level/_Definitions.inc.
    hits=list(re.finditer(rb'\x43\xf9(....)\x70\x00\x10\x28\x00\x1c\xb0\x28\x00\x1d',program,re.S))
    assert len(hits)==1
    entry=0x200000+hits[0].start();table=struct.unpack('>I',hits[0][1])[0]-0x200000
    scripts=assembly_frames(FOLDER/'Animations.asm')
    assert len(scripts)==60
    addresses=[]
    for i,script in enumerate(scripts):
        at=table+struct.unpack_from('>H',program,table+i*2)[0]
        assert program[at:at+len(script)]==script,('retail animation mismatch',i)
        addresses.append(0x200000+at)
    pc=(ROOT/'.deps/soniccd/src/PLCHG.C').read_text()
    pc_arrays={int(i):bytes(map(int,re.findall(r'\d+',body))) for i,body in re.findall(r'unsigned char plchg(\d+)\[\d+\]\s*=\s*\{([^}]+)\}',pc)}
    pc_order=list(map(int,re.findall(r'plchg(\d+)',pc.split('unsigned char* playchg[60] = {')[1])))
    assert len(pc_order)==60
    for i,j in enumerate(pc_order):assert scripts[i].startswith(pc_arrays[j]),('PC/retail script mismatch',i)
    lines=['/* Verified retail Sonic animation scripts; generated, do not edit. */']
    for i,script in enumerate(scripts):lines.append(f'static const uint8_t sonic_anim_{i}[]={{'+','.join(map(str,script))+'};')
    lines.append('static const uint8_t *const sonic_animations[60]={'+','.join(f'sonic_anim_{i}' for i in range(60))+'};')
    lines.append('static const uint8_t sonic_animation_sizes[60]={'+','.join(str(len(s)) for s in scripts)+'};')
    write_text(OUT/'sonic-animation.inc','\n'.join(lines)+'\n')
    # Preserve original indexed art and per-frame DPLC/mapping tables, rather
    # than expanding 198 poses into permanently resident 64x64 textures.
    art=(FOLDER/'Art.bin').read_bytes();art+=bytes(len(art)&1)
    maps=assemble_table(FOLDER/'Mappings.asm')
    dplcs=assemble_table(FOLDER/'DPLCs.asm')
    pal=(FOLDER/'Palette.bin').read_bytes()
    locations={name:unique(program,blob) for name,blob in [('art',art),('mappings',maps),('dplcs',dplcs)]}
    parts=[art,maps,dplcs,pal];offset=8+8*len(parts);header=b'SON1'+struct.pack('>I',len(parts))
    for part in parts:header+=struct.pack('>II',offset,len(part));offset+=len(part)
    payload=header+b''.join(parts);write_bytes(OUT/'sonic-source.bin',payload)
    report={'retail_program_sha256':hashlib.sha256(program).hexdigest(),'animation_entry':entry,
            'animation_table':table+0x200000,'script_addresses':addresses,'scripts':60,
            'mapping_frames':len(assembly_frames(FOLDER/'Mappings.asm')),
            'dplc_frames':len(assembly_frames(FOLDER/'DPLCs.asm')),
            'retail_data_offsets':locations,'pack_bytes':len(payload),
            'part_bytes':list(map(len,parts)),'pack_sha256':hashlib.sha256(payload).hexdigest(),
            'source_sha256':{n:hashlib.sha256((FOLDER/n).read_bytes()).hexdigest() for n in ['Animations.asm','Mappings.asm','DPLCs.asm','Art.bin','Palette.bin']},
            'scope':'Original script verification and raw DPLC source pack; runtime acceptance is tested separately.'}
    write_text(QA/'source-report.json',json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['scripts','mapping_frames','dplc_frames','pack_bytes','part_bytes']}))
    return report

if __name__=='__main__':generate()
