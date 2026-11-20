#!/usr/bin/env python3
"""Zone placement streaming (tools/zone_stream_test.c) for the zones whose
actors stream through the ACTSET camera window (scd_zone_ops stream_windowed):
Tidal Tempest, Quartz Quadrant, Wacky Workbench and Stardust Speedway. No zone placement may
reload more than 3 times in a right-then-left sweep of each act and era.
Builds an instrumented host copy of src/objects.c (tools/ww_host_objects.py
wires ww_zone_ops until objects_zone_ops.inc lists it) that counts spawns per
placement in tt_spawn_record() and stream(), then runs each zone case.

usage: test_zone_stream.py [tt|qq|ww|ss ...]   (default: tt qq ww)"""
import os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cases=sys.argv[1:] or ['tt','qq','ww']
out=ROOT/'build/zone-stream';out.mkdir(parents=True,exist_ok=True)
# ZONE_STREAM_SRC: a directory with patched objects.c / *.inc to test instead.
alt=os.environ.get('ZONE_STREAM_SRC')
for f in (Path(alt).glob('*.inc') if alt else []):shutil.copy(f,out/f.name)
for f in ([] if alt else out.glob('*.inc')):f.unlink()
# ww_host_objects.py writes objects.c and objects_zone_ops.inc (ww wired in).
subprocess.run([sys.executable,'tools/ww_host_objects.py',str(out)],cwd=ROOT,check=True)
if alt:shutil.copy(Path(alt)/'objects.c',out/'objects.c')
text=(out/'objects.c').read_text()
a="        if(index<0)break;pool[index].origin=j;"
assert text.count(a)==1,'objects.c stream spawn anchor moved'
text='unsigned stream_spawns[1024];\n'+text.replace(a,"        if(index<0)break;stream_spawns[j]++;pool[index].origin=j;")
b="    pool[index].origin=j;tt_alive_add(j);actwk[index+1].userflag.b.l=e->secondary;"
assert text.count(b)==1,'objects.c tt_spawn_record anchor moved'
text=text.replace(b,"    stream_spawns[j]++;pool[index].origin=j;tt_alive_add(j);actwk[index+1].userflag.b.l=e->secondary;")
(out/'objects.c').write_text(text)
orig=[f'build/probe-source/{n}.c' for n in ('interaction','player','dircol','fcol','etc','equ','movement')]
subprocess.run(['clang','-std=gnu11','-O2','-fsigned-char','-fwrapv','-fno-strict-aliasing','-Wno-parentheses','-Wno-unused-value',
                f'-I{out}','-Isrc','-Iassets/generated','-Ibuild/probe-source','-DR1','-DR11A','tools/zone_stream_test.c',str(out/'objects.c'),
                'src/title_card.c','src/player_replay.c','src/world.c','src/act.c','src/player.c','src/sonic_animation.c','src/stage.c','src/water.c',*orig,
                '-o',str(out/'test')],cwd=ROOT,check=True)
sys.exit(max([subprocess.run([str(out/'test'),c],cwd=ROOT).returncode for c in cases]))
