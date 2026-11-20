#!/usr/bin/env python3
"""Verify CC1's static terrain and compiled-original COL3A-D palette animation."""
import ctypes as C
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from convert_assets import ROOT


def function(source,name):
    m=re.search(r'void '+name+r'\([^)]*\)\s*\{',source);assert m,name
    depth=1;end=m.end()
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[m.start():end]


def main(run):
    out=ROOT/'build/cc1/palette';out.mkdir(parents=True,exist_ok=True)
    harvest_path=ROOT/'build/auto-extract/3/report.json'
    harvest=json.loads(harvest_path.read_text())
    terrain={}
    for letter in 'ABCD':
        program=f'R31{letter}';row=harvest['programs'][program]
        dev_path=ROOT/f'.deps/soniccd/src/R3/DEV31{letter}.C'
        dev=dev_path.read_text()
        functions=re.findall(r'\b[A-Za-z_]\w*\s*\([^;{}]*\)\s*\{',dev)
        assert not functions,(program,'unexpected Act 1 DEV function',functions)
        assert not re.search(r'\b(?:cg_change|cg_chg1|ChangeTileBmp|tile_changes)\b',dev),program
        assert row['animated_tiles']==[] and row['animated_skipped']==[],program
        assert row['pack_sha256']==row['raw_pack_sha256'],program
        pack=ROOT/f'assets/generated/cc31{letter}.bin'
        assert hashlib.sha256(pack.read_bytes()).hexdigest()==row['pack_sha256'],program
        terrain[letter]={'mmd_sha256':row['mmd_sha256'],'pack_sha256':row['pack_sha256'],
                         'animated_tile_slots':0,'conditional_tile_slots':0,
                         'dev_functions':0,'tile_or_block_updates_per_frame':0}
    subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-Isrc','-Iassets/generated',
                    'src/background.c','src/background_r3.c','-o',str(out/'native.dylib')],cwd=ROOT,check=True)
    native=C.CDLL(str(out/'native.dylib'))
    native.scd_background_palette.argtypes=[C.c_uint,C.c_uint,C.c_void_p,C.c_void_p]
    cases=paused=0;traces={};changes={}
    for era,letter in enumerate('ABCD'):
        source=(ROOT/f'.deps/soniccd/src/R3/COL3{letter}.C').read_text()
        arrays='\n'.join(m[0] for m in re.finditer(r'(?:unsigned char|PALETTEENTRY) col3\w+\[\d+\] = \{.*?\};',source,re.S))
        text='''#include <stdint.h>
typedef struct {uint8_t peRed,peGreen,peBlue,peFlags;} PALETTEENTRY;
PALETTEENTRY colors[64],*lpcolorwk=colors;
unsigned char clchgtim[8],clchgcnt[8];
void clchg_sub0(unsigned char*,unsigned char*,unsigned char*,PALETTEENTRY*);
'''+arrays+'\n'+function(source,'clchg_sub0')
        if letter!='B':text+='\n'+function(source,'colchg3'+letter.lower())
        text+='\n'+function(source,'clchgctr')
        text+='''
void init(void){
    for(unsigned i=0;i<8;i++)clchgtim[i]=clchgcnt[i]=0;
    for(unsigned i=0;i<64;i++)colors[i]=(PALETTEENTRY){(i%8)*32,((i/8)%8)*32,((i*3)%8)*32,1};
}
void read_colors(uint16_t *out){for(unsigned i=0;i<64;i++){
    PALETTEENTRY c=colors[i];out[i]=0x8000|((c.peRed/32)*31/7)|(((c.peGreen/32)*31/7)<<5)|(((c.peBlue/32)*31/7)<<10);
}}
'''
        path=out/f'original-{letter}.c';path.write_text(text)
        subprocess.run(['clang','-std=c11','-fsigned-char','-Wall','-Wextra','-Werror','-shared','-fPIC',str(path),
                        '-o',str(path.with_suffix('.dylib'))],check=True)
        original=C.CDLL(str(path.with_suffix('.dylib')));original.init()
        expected=(C.c_uint16*64)();actual=(C.c_uint16*64)();original.read_colors(expected)
        base=C.create_string_buffer(b''.join(int(v).to_bytes(2,'big') for v in expected))
        trace=hashlib.sha256();previous=None;changed=0
        for frame in range(8193):
            if frame:original.clchgctr()
            original.read_colors(expected)
            native.scd_background_palette(12+era,frame,base,actual)
            assert list(actual)==list(expected),(letter,frame,[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b])
            values=bytes(expected);trace.update(values)
            changed+=previous is not None and values!=previous;previous=values
            # Repeated rendering while paused must preserve the exact palette.
            native.scd_background_palette(12+era,frame,base,actual)
            assert list(actual)==list(expected)
            cases+=1;paused+=1
        traces[letter]=trace.hexdigest();changes[letter]=changed
        assert hashlib.sha256((ROOT/f'assets/generated/cc31{letter}.bin').read_bytes()).hexdigest()==terrain[letter]['pack_sha256']
    assert len(set(traces.values()))==4,'era palette traces must differ'
    paths=['src/background.c','src/background_r3.c','src/background_r3_tables.inc','tools/cc_palette_source.py',
           'tools/test_cc_palette.py','tools/prepare_background.py','tools/extract_zone_auto.py','build/auto-extract/3/report.json']
    paths += [f'.deps/soniccd/src/R3/DEV31{letter}.C' for letter in 'ABCD']
    paths += [f'.deps/soniccd/src/R3/COL3{letter}.C' for letter in 'ABCD']
    paths += [f'assets/generated/cc31{letter}.bin' for letter in 'ABCD']
    report=dict(run,passed=True,status='passed',contract='CC1 terrain tiles and blocks are static; COL3A-D palette cycles are the terrain animation',
                eras=terrain,frames_per_era=8193,frames=cases,colors=cases*64,
                repeated_paused_frames=paused,palette_changed_frames=changes,palette_trace_sha256=traces,
                boundary_frames_tested=[0,1,255,256,8191,8192],tile_block_boundary_and_wrap_updates=0,
                inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                limits='Compiled original COL3A-D palette routines plus retail MMD/DEV31A-D proof that Act 1 has no tile or block animation. Target rendered scenes and hardware remain separate gates.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'CC1 terrain animation: four static tile/block eras; {cases} original/native palette frames, {cases*64} colors, {paused} pause repeats pass')


if __name__=='__main__':
    out=ROOT/'build/cc1/palette';out.mkdir(parents=True,exist_ok=True)
    report_path=out/'report.json'
    RUN=dict(passed=False,status='pending',started_utc=datetime.now(timezone.utc).isoformat())
    report_path.write_text(json.dumps(RUN,indent=2)+'\n')
    try:
        paths=['tools/test_cc_palette.py','src/background.c','src/background.h',
               'src/background_r3.c','src/background_r3.h','src/background_r3_tables.inc',
               'assets/generated/background.inc','build/auto-extract/3/report.json']
        paths += [f'.deps/soniccd/src/R3/{prefix}{letter}.C'
                  for prefix in ('COL3','DEV31') for letter in 'ABCD']
        paths += [f'assets/generated/cc31{letter}.bin' for letter in 'ABCD']
        RUN.update(disc_sha256=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
                   compiler=subprocess.check_output(['clang','--version'],text=True).strip(),
                   run_inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                   build_scope='Host comparison; disc hash identifies the accompanying development image, not target execution.')
        report_path.write_text(json.dumps(RUN,indent=2)+'\n')
        main(RUN)
    except BaseException as error:
        RUN.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',
                   error=f'{type(error).__name__}: {error}')
        report_path.write_text(json.dumps(RUN,indent=2)+'\n')
        raise
