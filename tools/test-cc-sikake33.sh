#!/bin/bash
# Compiled R3/SIKAKE33.C and its three routines versus src/objects_sikake33.inc.
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/cc3/sikake33
mkdir -p "$out"
python3 - <<'PY'
from pathlib import Path
import json,hashlib,datetime
p=Path('build/cc3/sikake33/report.json')
if p.exists():
 old=p.read_bytes();(p.parent/('previous-'+hashlib.sha256(old).hexdigest()[:16]+'.json')).write_bytes(old)
r=dict(passed=False,status='pending',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
p.write_text(json.dumps(r,indent=2)+'\n')
PY
finish_report() {
    local result=$?
    python3 - "$result" <<'PY'
from pathlib import Path
import json,sys
p=Path('build/cc3/sikake33/report.json');r=json.loads(p.read_text())
code=int(sys.argv[1])
if code:r.update(passed=False,status='interrupted' if code in (130,143) else 'failed',exit_code=code)
p.write_text(json.dumps(r,indent=2)+'\n')
PY
}
trap finish_report EXIT
python3 - <<'PY'
from pathlib import Path
import re
src=Path('build/audit/source/src');out=Path('build/cc3/sikake33')
head='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\nvoid soundset(short);\nvoid actionsub(sprite_status*);\nvoid frameout(sprite_status*);\nint frameout_s(sprite_status*);\nint actwkchk(sprite_status**);\nvoid patchg(sprite_status*,unsigned char**);\n'
def words(t):
    # PC scratch-word casts address the same bytes as the native actfree helpers.
    return re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
                  lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',t)
def strip(t):return re.sub(r'^#include .*\n','',t,flags=re.M)
ride_header=(src/'RIDECHK.H').read_text()
for name in ('SIKAKE33','ROLLPLAT','LIGHT','STOPPER'):
    text=strip((src/'R3'/(name+'.C')).read_text())
    protos=''.join(strip((src/'R3'/(n+'.H')).read_text()) for n in ('SIKAKE33','ROLLPLAT','LIGHT','STOPPER'))
    (out/(name.lower()+'.c')).write_text(head+ride_header+protos+words(text))
playsub=(src/'PLAYSUB.C').read_text()
body=playsub[playsub.index('void patchg('):playsub.index('void playsave0(')]
(out/'patchg.c').write_text(head+body)
ride=strip((src/'RIDECHK.C').read_text())
ride=ride.replace('lXspeed << 8','lXspeed * 256').replace('pActwk->yspeed.w << 8','pActwk->yspeed.w * 256')
(out/'ridechk.c').write_text(head+'short playdieset(sprite_status*);\n'+ride_header+words(ride))
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Wno-incompatible-pointer-types -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_sikake33_test.c "$out"/{sikake33,rollplat,light,stopper,patchg,ridechk}.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >"$out/build.log" 2>&1 || { grep -m 20 'error' "$out/build.log"; exit 1; }
"$out/test" | tee "$out/result.txt"
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_sikake33.inc','src/objects_for3.inc','src/objects.c','src/scd_objects.h','src/scd_actor.h',
       'tools/cc_sikake33_test.c','tools/test-cc-sikake33.sh',
       *[f'build/cc3/sikake33/{n}.c' for n in ('sikake33','rollplat','light','stopper','patchg','ridechk')],
       *[f'build/audit/source/src/R3/{n}.C' for n in ('SIKAKE33','ROLLPLAT','LIGHT','STOPPER')],
       'build/audit/source/src/PLAYSUB.C','build/audit/source/src/RIDECHK.C',
       'assets/generated/cc33C.bin','assets/generated/cc33D.bin']
p=Path('build/cc3/sikake33/report.json')
report=dict(json.loads(p.read_text()),passed=True,status='passed',result=Path('build/cc3/sikake33/result.txt').read_text().strip(),
            inputs={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in paths},
            limits='Compiled original kaitenban/light/stopper, patchg and RIDECHK.C versus the native actor over randomized player contacts in eras C and D. actionsub visibility is copied from the native actor; frameout_s uses the native stream rule. Not an emulator route.')
p.write_text(json.dumps(report,indent=2)+'\n')
PY
