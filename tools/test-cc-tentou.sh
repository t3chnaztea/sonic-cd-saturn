#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ga build/cc1/tentou
python3 tools/cc_enemy_reference.py
python3 tools/cc_tentou_source.py
python3 - <<'PY'
from pathlib import Path
import re
src=Path('build/audit/source/src')
text=(src/'R3/TENTOU.C').read_text()
text=text[text.index('static unsigned char bCarry;'):]
# The PC drawing structs are replaced by separate original-machine art captures.
text=re.sub(r'sprite_pattern\s*\*?\s+\w+(?:\[\d+\])?\s*=\s*\{.*?\n\};','',text,flags=re.S)
text=re.sub(r'\w+->patbase = \w+;', '(void)0;',text)
text=re.sub(r'\bpchg(\w*)',r'ten_pchg\1',text)
text=re.sub(r'\babs\(', 'ten_abs(',text)
# Include the original bomb explosion through its removal, with no score or
# flower allocation: TENTOU sets r_no1=1 before changing the actor id.
p=(src/'PLAYSUB.C').read_text();explosion=p[p.index('void bakuha('):p.index('void baku_die(')]
start=p.index('void baku_die(');explosion+=p[start:p.index('\n}',start)+2]
explosion=re.sub(r'\w+->patbase = \w+;', '(void)0;',explosion)
t=(src/'TBL1.C').read_text();scripts=t[t.index('static unsigned char baku_chg0'):t.index('static sprite_pattern bak00')]
text=scripts+text+explosion
header='''#include "EQU.H"
#include "DIRCOL.H"
typedef struct __attribute__((packed)) { int value; } ref_unaligned_int;
void actionsub(sprite_status*); int frameout_s(sprite_status*); int actwkchk(sprite_status**);
void tensuu_set(sprite_status*); void frameout(sprite_status*);
void patchg(sprite_status*,unsigned char**); short enemy_suicide(sprite_status*); void soundset(short);
unsigned char CCset(unsigned short,unsigned short);
'''
prototypes=';\n'.join(re.findall(r'^(?:void|int) \w+\([^\n{]+\)',text,re.M))+';\n'
text=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',text)
# actfree starts at an even but not necessarily 4-byte-aligned host offset.
# Preserve the original four-byte values without undefined aligned int loads.
text=re.sub(r'\*\(int\*\)&(\w+)->actfree\[(\d+)\]',r'((ref_unaligned_int*)(void*)&\1->actfree[\2])->value',text)
Path('build/cc1/tentou/original.c').write_text(header+prototypes+text)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_tentou_test.c build/cc1/tentou/original.c build/cc1/ga/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/tentou/test >build/cc1/tentou/build.log 2>&1
build/cc1/tentou/test | tee build/cc1/tentou/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_tentou.inc','src/objects_cc_enemy.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h','src/sprite_order.h',
       'tools/cc_tentou_test.c','tools/cc_enemy_test_fixture.h','tools/cc_enemy_reference.py','tools/cc_tentou_source.py','tools/test-cc-tentou.sh','build/cc1/tentou/retail.json',
       'build/cc1/tentou/original.c','build/cc1/ga/original.c','build/audit/source/src/R3/TENTOU.C',
       'build/audit/source/src/PLAYSUB.C','build/audit/source/src/TBL1.C','build/audit/source/src/R3/GA3.C','build/audit/source/src/R3/COLI3.C','build/audit/source/src/SUICIDE.C',
       'build/probe-source/dircol.c','build/probe-source/fcol.c']
report=dict(passed=True,result=Path('build/cc1/tentou/result.txt').read_text().strip(),
 inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
 limits='Compiled original Tentou motion/terrain/bomb states, non-enemy bomb explosions through removal, and COLI3 contacts, using real era collision maps. Original offscreen streaming and enemy explosion/flower/score effects remain separate.')
Path('build/cc1/tentou/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
