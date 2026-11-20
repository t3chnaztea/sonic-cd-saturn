#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/traps
python3 - <<'PY'
from pathlib import Path
import re,sys
sys.path.insert(0,'tools')
from cc_gandair_source import verify
verify()
src=Path('build/audit/source/src')
source=(src/'R3/TRAP_R3.C').read_text()
k=source[source.index('void harir3('):source.index('static sprite_pattern fo00')]
k+=source[source.index('void getdair3('):source.index('static unsigned char',source.index('void getdair3('))]
k+=source[source.index('static unsigned char pchg1'):source.index('static sprite_pattern drm00')]
p=(src/'PLAYSUB.C').read_text().split('void patchg(sprite_status* patchgwk')[1]
k+='\nvoid patchg(sprite_status* patchgwk'+p[:p.index('\n}')+2]+'\n'
# Match the verified Sega CD AnimateObject reload, which preserves zero.
# This is an explicit platform difference in the reconstructed PC helper.
k=k.replace('sprpat_adr[search_end - 1] != 252 && *sprpat_adr <= 0 ? 1 : *sprpat_adr', '*sprpat_adr')
k=re.sub(r'^static sprite_pattern .*?;\n|^sprite_pattern\* .*?;\n','',k,flags=re.M)
k=re.sub(r'\w+->patbase = \w+;', '(void)0;',k)
k=k.replace('new_actwk->actno = 32','new_actwk->actno = 73').replace('new_actwk->actno == 32','new_actwk->actno == 73').replace('new_actwk->actno = 39','new_actwk->actno = 77')
ride=re.sub(r'^#include .*\n','',(src/'RIDECHK.C').read_text(),flags=re.M)
col=(src/'R3/COLI3.C').read_text()
col=col[col.index('static unsigned char bCarry;'):col.index('short pcolitem(')]
col=col.replace('  CollitblDataYchk(pActwk, pColliAct, iYposi, iColiNo, iD5);','  return CollitblDataYchk(pActwk, pColliAct, iYposi, iColiNo, iD5);')
# The reconstructed tail call lacks its return; restore it for defined C.
prototypes=';\n'.join(re.findall(r'^(?:void|short) \w+\([^\n{]+\)',k+col,re.M))+';\n'
header='''#include "EQU.H"
#include "DIRCOL.H"
#include "ETC.H"
void actionsub(sprite_status*);
void tr3_fout(sprite_status*);
void frameout(sprite_status*);
void soundset(short);
int actwkchk2(sprite_status*,sprite_status**);
int actwkchk(sprite_status**);
int frameout_s(sprite_status*);
short playdamageset(sprite_status*,sprite_status*);
short pcolplay(sprite_status*,sprite_status*);
short pcolnomal(sprite_status*,sprite_status*);
short pcolspecial(sprite_status*,sprite_status*);
short pcolitem(sprite_status*,sprite_status*);
unsigned char CCset(unsigned short,unsigned short);
unsigned char CSset(unsigned short,unsigned short);
'''
k=header+(src/'RIDECHK.H').read_text()+prototypes+k+ride+col
k=re.sub(r'\(\((unsigned short|short)\*\)(\w+|&actwk\[0\])\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',k)
k=k.replace('lXspeed << 8','lXspeed * 256').replace('pActwk->yspeed.w << 8','pActwk->yspeed.w * 256').replace('floorwk->xspeed.w << 8','floorwk->xspeed.w * 256').replace('actwk[0].yspeed.w << 8','actwk[0].yspeed.w * 256').replace('bulletwk->xspeed.w << 8','bulletwk->xspeed.w * 256')
Path('build/cc1/traps/original.c').write_text(k)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_traps_test.c build/cc1/traps/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/traps/test >build/cc1/traps/build.log 2>&1
build/cc1/traps/test | tee build/cc1/traps/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_cc_traps.inc','src/objects_for3.inc','src/objects_bobin.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h',
       'tools/cc_traps_test.c','tools/test-cc-traps.sh','build/cc1/traps/original.c',
       'build/audit/source/src/R3/TRAP_R3.C','build/audit/source/src/RIDECHK.C','build/audit/source/src/R3/COLI3.C',
       'build/audit/source/src/PLAYSUB.C','tools/cc_gandair_source.py','build/cc1/gandair/retail-animation.json']
report=dict(passed=True,result=Path('build/cc1/traps/result.txt').read_text().strip(),
            inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
            limits='Compiled original trap and full-solid routines, contact/motion/child fixtures; not full controller routes.')
Path('build/cc1/traps/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
