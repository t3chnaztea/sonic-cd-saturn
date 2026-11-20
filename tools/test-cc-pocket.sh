#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ga build/cc1/pocket
python3 tools/cc_pocket_reference.py
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_pocket_test.c build/cc1/pocket/original.c build/cc1/ga/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/pocket/test >build/cc1/pocket/build.log 2>&1
build/cc1/pocket/test | tee build/cc1/pocket/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_pocket.inc','src/objects_cc_enemy.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h','src/sprite_order.h','src/act.c','src/act.h',
       'tools/cc_pocket_test.c','tools/cc_enemy_test_fixture.h','tools/cc_enemy_reference.py','tools/cc_pocket_reference.py','tools/cc_pocket_source.py','build/cc1/pocket/retail.json','tools/test-cc-pocket.sh',
       'build/cc1/pocket/original.c','build/cc1/ga/original.c','build/audit/source/src/R3/POCKET.C','build/audit/source/src/SCORE.C','build/audit/source/src/PLAYSUB.C','build/audit/source/src/ACTION.C','build/audit/source/src/ACTSET.C',
       'build/audit/source/src/R3/COLI3.C']
report=dict(passed=True,result=Path('build/cc1/pocket/result.txt').read_text().strip(),
 inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
 limits='Compiled original pocket and popup routines with proven console corrections; capture bounds, cycles, score limits, control flags, art poses, audio requests, viewport and ordinary frameout. Audio samples, loaded artwork, ordinary gameplay routes, mixed-family ordering and travel cleanup are separate.')
Path('build/cc1/pocket/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
