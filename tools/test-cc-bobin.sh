#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/bobin
# Compile the pinned original routine independently. Only PC actor-offset
# accesses and includes are adapted for the host's pointer size.
python3 - <<'PY'
from pathlib import Path
import re, sys
sys.path.insert(0,"tools")
from extract_mmd import disc_files
src=Path('build/audit/source/src')
k=(src/'R3/BOBIN.C').read_text()
# Original binary tables define the otherwise undefined C index-64 reads.
files=disc_files(Path('build/retail/sonic.iso').read_bytes())
for name,tail in [('frip_posi',18),('frip_posi_r',0)]:
    pattern=r'char '+name+r'\[64\] = \{(.*?)\};'
    match=re.search(pattern,k,re.S)
    values=bytes(int(v)&255 for v in re.findall(r'-?\d+',match[1]))
    for act in (1,2,3):
        for era in ('CD' if act==3 else 'ABCD'):
            data=files[f'R3{act}{era}__.MMD']; at=data.find(values)
            assert at>=0 and data[at+64]==tail,(act,era,name)
    k=re.sub(pattern,lambda m:'char '+name+'[65] = {'+m[1]+','+str(tail)+'};',k,flags=re.S)
k=re.sub(r'^#include .*\n','',k,flags=re.M)
k='#include "EQU.H"\n#include "ETC.H"\nvoid frip_init(sprite_status*);\nvoid frip_move(sprite_status*);\nvoid frip_chk(sprite_status*);\nshort ride_on_set(sprite_status*,sprite_status*);\nshort ride_on_clr(sprite_status*,sprite_status*);\nint frameout_s(sprite_status*);\nvoid soundset(short);\nvoid bobininit(sprite_status*);\nvoid bobinmove(sprite_status*);\nvoid scoreup(unsigned int);\nvoid tensuu0(sprite_status*,unsigned char);\nvoid sub_sync(short);\nvoid patchg(sprite_status*,unsigned char**);\nvoid actionsub(sprite_status*);\nint frameout_s00(sprite_status*,short);\n'+k
ride=(src/'RIDECHK.C').read_text()
ride=ride[ride.index('short ride_on_clr('):ride.index('short ride_on_set(')]+ride[ride.index('short ride_on_set('):]
ride=ride[:ride.index('} /* Line 185')]+ '}\n'
k+='\n'+ride
k=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',k)
p=(src/'PLAYSUB.C').read_text().split('void patchg(sprite_status* patchgwk')[1]
k+='\nvoid patchg(sprite_status* patchgwk'+p[:p.index('\n}')+2]+'\n'
Path('build/cc1/bobin/original.c').write_text(k)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_bobin_test.c build/cc1/bobin/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/bobin/test >build/cc1/bobin/build.log 2>&1
build/cc1/bobin/test | tee build/cc1/bobin/result.txt
python3 - <<'PY'
import hashlib,json,re
from pathlib import Path
out=Path('build/cc1/bobin')
m=re.fullmatch(r'PASS: (\d+) assertions; (\d+) bumper updates, (\d+) hitbox cases, (\d+) flipper contact cases\n', (out/'result.txt').read_text())
assert m
paths=['src/objects_bobin.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h',
       'tools/test-cc-bobin.sh','tools/cc_bobin_test.c','build/cc1/bobin/original.c',
       'build/audit/source/src/R3/BOBIN.C','build/audit/source/src/RIDECHK.C','build/audit/source/src/PLAYSUB.C']
report=dict(passed=True,assertions=int(m[1]),bumper_updates=int(m[2]),hitbox_cases=int(m[3]),flipper_cases=int(m[4]),
            inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
            limits='Compiled original behavior and bounded contact fixtures; target artwork and full controller routes are separate gates.')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
