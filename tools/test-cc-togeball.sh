#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ga build/cc1/togeball
python3 tools/cc_togeball_reference.py
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_togeball_test.c build/cc1/togeball/original.c build/cc1/ga/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/togeball/test >build/cc1/togeball/build.log 2>&1
build/cc1/togeball/test | tee build/cc1/togeball/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_togeball.inc','src/objects_cc_enemy.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h','src/sprite_order.h','src/act.c','src/act.h',
       'tools/cc_togeball_test.c','tools/cc_enemy_test_fixture.h','tools/cc_enemy_reference.py','tools/cc_togeball_reference.py','tools/cc_togeball_source.py','build/cc1/togeball/retail.json','tools/test-cc-togeball.sh',
       'build/cc1/togeball/original.c','build/cc1/ga/original.c','build/audit/source/src/R3/TOGEBL3A.C','build/audit/source/src/R3/TOGEBL3B.C','build/audit/source/src/R3/TOGEBL3D.C','build/audit/source/src/ACTION.C','build/audit/source/src/ACTSET.C',
       'build/audit/source/src/R3/COLI3.C','build/probe-source/etc.c']
report=dict(passed=True,result=Path('build/cc1/togeball/result.txt').read_text().strip(),
 inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
 limits='Compiled original three-era routine family, console initial motion, COLI3 contacts, ordered allocation, draw bounds and ordinary frameout. Shared placement-loading window, travel cleanup and sprite-queue saturation remain separate.')
Path('build/cc1/togeball/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
