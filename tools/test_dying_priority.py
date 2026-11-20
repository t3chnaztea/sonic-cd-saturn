#!/usr/bin/env python3
"""Dying Sonic in front of high-priority foreground cells (native picture test).

Original: playdieset sets sproffset bit 15 and sprpri 0 (R3/COLI3.C:555-556,
R1/COLI1.C), and actionsub turns sproffset bit 15 into the sprite priority bit
(ACTION.C:322), so the dying Sonic draws in front of high-priority plane cells.
Native: src/main.c gives the Sonic command the PR=1 palette-code LUT
(src/sonic_view.inc SONIC_HIGH_LUT) while actwk[0].sproffset bit 15 is set.

The harness (QA_DEATH_AT) moves Sonic below the map for one update of replay
fixture 2 at tick 380 (Good Future, behind high-priority cells), so the native
bottom check calls the source playdieset; it restores his Y and pictures 48
dying poses. Every opaque Sonic pixel over a high-priority source cell must show
Sonic's colour, every other one too. Rows 56-183 only (HUD).
"""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
from terrain_pixels import foreground_pixel
from check_sonic_pixels import texture,integer,signed
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/dying-priority'
def sym(name):
    out=subprocess.run([str(ROOT/'.toolchain/bin/sh-elf-nm'),str(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')],capture_output=True,text=True,check=True).stdout
    return next(l.split()[0] for l in out.splitlines() if l.split()[-1]==name)
def run():
    OUT.mkdir(parents=True,exist_ok=True)
    subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include',
        'tools/emulator_test.c','-o','build/emulator_test'],cwd=ROOT,check=True)
    env=dict(os.environ,SCD_STAGE_PACKS=sym('_scd_stage_pack_mailbox'),SCD_SONIC_VIEW=sym('_scd_sonic_view_mailbox'),
        SCD_PLAYER_VISUAL_TRACE=sym('_scd_player_visual_trace'),SCD_FLOOR_MAILBOX=sym('_scd_floor_mailbox'),
        QA_ACTWK=sym('_actwk'),QA_DEATH_AT='2:380')
    with (OUT/'results.log').open('w') as log,(OUT/'core.log').open('w') as core:
        subprocess.run([str(ROOT/'build/emulator_test'),str(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),
            str(ROOT/'dist/sonic-cd-saturn-prototype.cue'),str(ROOT/'assets/private'),str(OUT),
            sym('_scd_trace_mailbox'),sym('_scd_audio_mailbox')],cwd=ROOT,env=env,stdout=log,stderr=core,check=True)
def check():
    log=(OUT/'results.log').read_text();assert re.search(r'^Death probe: .* test=2 tick=380 ',log,re.M),'probe did not fire'
    total=dict(pictures=0,high_sonic=0,high_foreground=0,high_other=0,low_sonic=0,low_other=0)
    for name,line in re.findall(r'^Dying Sonic: (\S+) ((?:\d+ ?)+)$',log,re.M):
        v=list(map(int,line.split()));assert v[0]==0x534F4E56 and v[10]>>24==24,('not the dying animation',name)
        mapping,flags=v[3],v[4];wx,wy=integer(v[5]),integer(v[6]);cx,cy=signed(v[7]),signed(v[8]);era=v[11]&255
        raw=(OUT/(name+'.ppm')).read_bytes().split(b'255\n',1)[1];art=texture(mapping)
        for py in range(64):
            for px in range(64):
                sx=63-px if flags&1 else px;sy=63-py if flags&2 else py
                c=int.from_bytes(art[(sy*64+sx)*2:(sy*64+sx)*2+2],'big')
                dx,dy=wx-cx-32+px,wy-cy-32+py
                if not c or not (0<=dx<320 and 56<=dy<184):continue
                rgb=bytes(((c&31)*8,((c>>5)&31)*8,((c>>10)&31)*8))
                tile=foreground_pixel(['Present','Past','Good Future','Bad Future'][era],wx-32+px,wy-32+py,v[12],path=v[17]>>16)
                actual=raw[(dy*330+dx+5)*3:(dy*330+dx+5)*3+3]
                if tile and tile[0]:total['high_sonic' if actual==rgb else 'high_foreground' if actual==tile[1] else 'high_other']+=1
                else:total['low_sonic' if actual==rgb else 'low_other']+=1
        total['pictures']+=1
    passed=total['pictures']==48 and total['high_sonic']>=100 and not total['high_foreground'] and not total['high_other'] and not total['low_other']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=passed,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),**total,
        source_sha256={n:sha(ROOT/n) for n in ['src/main.c','src/sonic_view.inc','src/player.c','src/scd_player.h','tools/emulator_test.c','tools/test_dying_priority.py']},
        limits='One fixture death (Good Future, Palmtree Panic Act 1) forced by a one-update Y move; emulator VDP2 composition, not hardware.')
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(('PASS' if passed else 'FAIL')+': dying Sonic priority',json.dumps(total))
    return passed
if __name__=='__main__':
    if '--check-only' not in sys.argv:run()
    sys.exit(0 if check() else 1)
