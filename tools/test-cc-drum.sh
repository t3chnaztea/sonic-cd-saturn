#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc2/drum
python3 - <<'PY'
from pathlib import Path
import json,hashlib,datetime
p=Path('build/cc2/drum/report.json')
if p.exists():
 old=p.read_bytes();(p.parent/('previous-'+hashlib.sha256(old).hexdigest()[:16]+'.json')).write_bytes(old)
paths=['src/objects_drumr3.inc','src/objects_for3.inc','src/objects.c','tools/cc_drum_test.c','tools/test-cc-drum.sh',
       'build/audit/source/src/R3/TRAP_R3.C','build/audit/source/src/RIDECHK.C']
r=dict(passed=False,status='pending',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
       disc_sha256=hashlib.sha256(Path('dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
       inputs={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in paths})
p.write_text(json.dumps(r,indent=2)+'\n')
PY
finish_drum_report() {
    local result=$?
    python3 - "$result" <<'PY'
from pathlib import Path
import json,sys
p=Path('build/cc2/drum/report.json');r=json.loads(p.read_text())
code=int(sys.argv[1])
if code:r.update(passed=False,status='interrupted' if code in (130,143) else 'failed',exit_code=code)
p.write_text(json.dumps(r,indent=2)+'\n')
PY
}
trap finish_drum_report EXIT
python3 - <<'PY'
from pathlib import Path
import re
source=Path('build/audit/source/src/R3/TRAP_R3.C').read_text()
body=source[source.index('void drumr3('):source.index('void tr3_fout(')]
body=body.replace('drumwk->patbase = drumr3pat;', 'drumwk->patbase = 0;')
body=body.replace('drumwk->yspeed.w << 8', 'drumwk->yspeed.w * 256')
header=Path('build/audit/source/src/R3/TRAP_R3.H').read_text()
prototypes='\n'.join(line for line in header.splitlines() if line.startswith('void drumr3'))
ride=Path('build/audit/source/src/RIDECHK.C').read_text()
ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
ride=ride.replace('lXspeed << 8','lXspeed * 256').replace('pActwk->yspeed.w << 8','pActwk->yspeed.w * 256')
text='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\nvoid soundset(short);\n'+Path('build/audit/source/src/RIDECHK.H').read_text()+prototypes+'\nvoid actionsub(sprite_status*);\nvoid tr3_fout(sprite_status*);\n'+body+ride
text=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',text)
Path('build/cc2/drum/original.c').write_text(text)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_drum_test.c build/cc2/drum/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc2/drum/test >build/cc2/drum/build.log 2>&1
build/cc2/drum/test | tee build/cc2/drum/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_drumr3.inc','src/objects_for3.inc','src/objects.c','src/scd_objects.h','src/sprite_order.h',
       'tools/cc_drum_test.c','tools/test-cc-drum.sh','build/cc2/drum/original.c',
       'build/audit/source/src/R3/TRAP_R3.C','build/audit/source/src/RIDECHK.C']
report=dict(json.loads(Path('build/cc2/drum/report.json').read_text()),passed=True,status='passed',result=Path('build/cc2/drum/result.txt').read_text().strip(),
            inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
            limits='Compiled original drum actor and RIDECHK.C versus native actor/player contacts in all four eras; complete emulator routes remain separate.')
Path('build/cc2/drum/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
