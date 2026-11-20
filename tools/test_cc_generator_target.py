#!/usr/bin/env python3
"""Render every used generator pose with the actual gameplay sprite builder."""
import hashlib,json,os,re,struct,subprocess
from pathlib import Path
from convert_assets import ROOT,OUT
from sprite_composition import source_sprite
from test_objects import unpack_texture


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def check(name,folder):
    source=json.loads((ROOT/'build/cc1/generator/art-placement'/name/'source.json').read_text())
    vram=(ROOT/'build/cc1/generator/art-placement'/name/'vram.bin').read_bytes()
    meta=(OUT/'object-frames.inc').read_text()
    def array(n):return list(map(int,re.search(n+r'\[\]=\{([^}]+)',meta)[1].split(',')))
    offsets,widths,heights,tops=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops']]
    normal=int(re.search(r'#define OBJECT_BASE_45 (\d+)',meta)[1]);withered=int(re.search(r'#define OBJECT_BASE_86 (\d+)',meta)[1])
    raw=unpack_texture((OUT/'object-art.bin').read_bytes());target=(folder/'zone-art-vdp1.bin').read_bytes()
    stage=(OUT/f'cc{name[1:]}.bin').read_bytes();at,size=struct.unpack_from('>II',stage,44);assert size==128
    palette=stage[at:at+32];obj=source['objects'][0]
    log=(folder/'results.log').read_text();records={int(n):list(map(int,words.split())) for n,words in re.findall(r'^Zone art sprite: (\d+) ([\d ]+)$',log,re.M)}
    assert set(records)==set(range(4*len(obj['frame_ids'])))
    captures={};pixels=0
    for ordinal,(pose,encoded) in enumerate(zip(obj['frame_ids'],obj['frames'])):
        mapping=bytearray.fromhex(encoded)
        for i in range(mapping[0]):
            at=3+5*i;struct.pack_into('>H',mapping,at,(struct.unpack_from('>H',mapping,at)[0]+obj['tile'])&65535)
        original=struct.unpack('>5120H',source_sprite(mapping,vram,palette,80,0,64))
        n=normal+pose if name[-1]=='B' else withered+(pose==2)
        w,h,top,off=widths[n],heights[n],tops[n],offsets[n];assert w==80
        assert target[0x1aac0+off:0x1aac0+off+w*h//2+32]==raw[off:off+w*h//2+32],(name,pose,'uploaded texture/CLUT')
        for flags in range(4):
            case=4*ordinal+flags;left=120;ytop=80+(64-top-h if flags&2 else top)
            assert records[case]==[86,pose,left,ytop,flags,w<<16|h,0x1aac0+off,2],(name,case,records[case])
            path=folder/f'zone-art-{case:03}.ppm';header,rgb=path.read_bytes().split(b'255\n',1);assert header==b'P6\n330 224\n'
            background=rgb[5*3:6*3]
            for y in range(64):
                for x in range(80):
                    color=original[(63-y if flags&2 else y)*80+(79-x if flags&1 else x)]
                    expected=bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8)) if color else background
                    at=((80+y)*330+125+x)*3
                    assert rgb[at:at+3]==expected,(name,pose,flags,x,y,'pixel')
                    pixels+=1
            captures[path.name]=sha(path)
    return dict(passed=True,poses=obj['frame_ids'],captures=captures,pixels=pixels,
        vdp1_sha256=sha(folder/'zone-art-vdp1.bin'),log_sha256=sha(folder/'results.log'),source_sha256=sha(ROOT/'build/cc1/generator/art-placement'/name/'source.json'))


def main():
    out=ROOT/'build/cc1/generator/target';out.mkdir(exist_ok=True)
    exe=out/'emulator'
    subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include','tools/emulator_test.c','-o',exe],cwd=ROOT,check=True)
    nm=subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'],text=True)
    symbols={r.split()[2]:r.split()[0] for r in nm.splitlines() if len(r.split())==3}
    disc=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin');report=dict(passed=False,disc_sha256=disc,variants={})
    for name in ['R31A','R31B','R32A','R32B']:
        folder=out/name;folder.mkdir(exist_ok=True)
        env={k:v for k,v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='1',SCD_ZONE_ACT=str(int(name[2])-1),SCD_ZONE_ERA=str('AB'.index(name[3])),SCD_CC_GENERATOR_ART='1',
            SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],SCD_ZONE_ART_MAILBOX=symbols['_scd_zone_art_mailbox'])
        command=[exe,ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',ROOT/'dist/sonic-cd-saturn-prototype.cue',ROOT/'assets/private',folder,symbols['_scd_trace_mailbox'],symbols['_scd_audio_mailbox'],'zones']
        with (folder/'results.log').open('w') as stdout,(folder/'core.log').open('w') as stderr:
            subprocess.run(list(map(str,command)),cwd=ROOT,env=env,stdout=stdout,stderr=stderr,check=True,timeout=240)
        report['variants'][name]=check(name,folder);print(name,'PASS',flush=True)
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    assert sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')==disc
    report.update(passed=True,hardware_tested=False,inputs={p:sha(ROOT/p) for p in ['src/main.c','src/zone_object_view.inc','tools/emulator_test.c','tools/test_cc_generator_target.py','assets/generated/object-frames.inc','assets/generated/object-art.bin']},limits='Visual fixture uses the same generator sprite builder as ordinary gameplay. Covers every reachable pose/flip, transparent pixels and uploaded texture/CLUT bytes; ordinary gameplay behavior is separate.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Generator target:',sum(len(v['captures']) for v in report['variants'].values()),'pictures,',sum(v['pixels'] for v in report['variants'].values()),'exact pixels')
if __name__=='__main__':main()
