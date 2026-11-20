#!/usr/bin/env python3
"""Verify airborne animation selection against the untouched retail prelude."""
import hashlib,json,struct,subprocess
from pathlib import Path
from test_sonic_animation import Retail
from sonic_animation_assets import ROOT
from extract_mmd import disc_files
from retail_span import disc_span

def main():
    out=ROOT/'build/player-air-animation';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    # ObjSonic_MdAir, through the first BSR boundary. Source labels/offsets
    # agree with Level/_Objects/Sonic/Main.asm and _Definitions.inc.
    prelude=disc_span('R11A__.MMD',0x45f6,26,'da76e09bc43f37f5327a594e4b97b357605c673b02f261f844ad4cd0891d3d9f')
    assert program.count(prelude)==1
    entry=0x200000+program.index(prelude);end=entry+len(prelude)
    assert program[end-0x200000:end-0x200000+2]==bytes.fromhex('6100')
    retail=Retail(entry)
    def original(animation,vy,wind):
        actor=bytearray(64);actor[28]=animation;struct.pack_into('>h',actor,18,vy)
        retail.write(retail.actor,actor);retail.write(0xfff7c6,bytes([0,wind]))
        for reg,value in [(17,0x2700),(15,retail.stack),(8,retail.actor),(16,entry)]:retail.lib.m68k_set_reg(reg,value)
        for step in range(10):
            if retail.lib.m68k_get_reg(16)==end:break
            retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(1)
        assert retail.lib.m68k_get_reg(16)==end,'retail prelude did not reach its original BSR'
        result=retail.read(retail.actor,64)
        assert all(result[i]==actor[i] for i in range(64) if i!=28)
        return result[28]
    for name in ['prepare_probe.py','prepare_player.py']:
        subprocess.run(['python3','tools/'+name],cwd=ROOT,check=True)
    sources=['tools/player_air_animation_test.c','src/player.c','src/sonic_animation.c',
        'src/stage.c','src/objects.c','src/act.c']+[f'build/probe-source/{s}.c' for s in
        ['interaction','player','dircol','fcol','etc','equ','movement']]
    subprocess.run(['clang','-std=gnu11','-O1','-g','-fsigned-char','-fwrapv','-fno-strict-aliasing',
        '-Wno-parentheses','-Wno-unused-value','-Isrc','-Iassets/generated','-Ibuild/probe-source',
        '-DR1','-DR11A','-DSCD_PLAYER_ANIMATION_AUDIT','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all']+sources+['-o',str(out/'test')],cwd=ROOT,check=True)
    with (out/'native.log').open('w') as log:
        subprocess.run([str(out/'test')],cwd=ROOT,stdout=log,check=True)
    count=0;transitions=[];ascent=descent=0
    for line in (out/'native.log').read_text().splitlines():
        tag,*values=line.split();v=list(map(int,values))
        if tag=='selection':
            animation,vy,wind,roll,controlled,selected=v
            expected=animation if roll or controlled else original(animation,vy,wind)
            assert selected==expected,('air selection',v,'retail',expected)
            count+=1
        else:
            assert tag=='spring'
            tick,vy,flags,animation,selected,after,mapping,x,y=v
            expected=original(animation,vy,0) if flags&6==2 else selected
            assert selected==expected,('spring pre-update selection',v,'retail',expected)
            if flags&6==2 and animation==16:
                if vy<0:ascent+=1;assert selected==16
                else:transitions.append(tick);assert selected==0
            if flags&6==2 and vy>=0 and selected==0:descent+=1
    assert count==2400 and ascent>40 and descent>30 and transitions
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    names=['src/player.c','tools/player_air_animation_test.c','tools/test_player_air_animation.py',
        '.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm','.deps/soniccd/src/PLAYER.C']
    report=dict(passed=True,cases=count,spring_ascent=ascent,spring_descent=descent,
        spring_apex_transitions=transitions,retail_entry=entry,retail_boundary=end,
        retail_prelude=prelude.hex(),retail_program_sha256=hashlib.sha256(program).hexdigest(),
        core_sha256=sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        log_sha256=sha(out/'native.log'),source_sha256={n:sha(ROOT/n) for n in names},
        limits='Real host update selection with an isolated unmodified retail air prelude; target pixels and full-route checks remain separate.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Air animation: {count} source-exact selections; spring ascent {ascent}, descent {descent}, transitions {transitions}')
if __name__=='__main__':main()
