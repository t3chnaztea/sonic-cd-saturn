#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/platform
python3 - <<'PY'
from pathlib import Path
import re
src=Path('build/audit/source/src')
k=(src/'R3/TRAP_R3.C').read_text();k=k[k.index('void for3('):k.index('static sprite_pattern gtd00')]
k=k.replace('floorwk->patbase = for3pat;', '(void)floorwk;')
ride=(src/'RIDECHK.C').read_text();ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
header=(src/'RIDECHK.H').read_text()
prototypes='\n'.join(re.findall(r'^(?:void|short) \w+\([^\n{]+\)',k,re.M))
prototypes=';\n'.join(prototypes.splitlines())+';\n'
k='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\nvoid actionsub(sprite_status*);\nvoid tr3_fout(sprite_status*);\nvoid soundset(short);\n'+header+prototypes+k+ride
# Retail R32A $20CFB6 (the shipped binary, which src/objects_for3.inc follows)
# moves the rising platform by the whole speed word, not the masked yspeed.
old='floorwk->yposi.l += floorwk->yspeed.w << 8; /* Line 776'
assert k.count(old)==1
k=k.replace(old,'floorwk->yposi.l += ((short*)floorwk)[28] << 8; /* Line 776')
k=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',k)
# Reconstructed signed left shifts represent multiplication in the original
# CPU. Express them without C undefined behavior for the sanitizer oracle.
k=k.replace('tmp_sin << 10','tmp_sin * 1024').replace('lXspeed << 8','lXspeed * 256')
k=re.sub(r'(\(\*\(short\*\).*?\)\)|\(floorwk->xspeed.w = .*?\)\)|floorwk->yspeed.w|pActwk->yspeed.w) << 8',r'\1 * 256',k)
Path('build/cc1/platform/original.c').write_text(k)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_platform_test.c build/cc1/platform/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/platform/test >build/cc1/platform/build.log 2>&1
build/cc1/platform/test | tee build/cc1/platform/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_for3.inc','src/objects_bobin.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h',
       'tools/cc_platform_test.c','tools/test-cc-platform.sh','build/cc1/platform/original.c',
       'build/audit/source/src/R3/TRAP_R3.C','build/audit/source/src/RIDECHK.C']
report=dict(passed=True,result=Path('build/cc1/platform/result.txt').read_text().strip(),
            inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
            limits='Independent compiled original platform and ride routines; contact and motion fixtures, not a complete route.')
Path('build/cc1/platform/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
