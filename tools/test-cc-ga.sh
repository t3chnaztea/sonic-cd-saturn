#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ga
python3 tools/cc_enemy_reference.py
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_ga_test.c build/cc1/ga/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/ga/test >build/cc1/ga/build.log 2>&1
build/cc1/ga/test | tee build/cc1/ga/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_cc_enemy.inc','src/objects_ga.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h','src/sprite_order.h',
       'tools/cc_ga_test.c','tools/cc_enemy_test_fixture.h','tools/cc_enemy_reference.py','tools/test-cc-ga.sh','build/cc1/ga/original.c',
       'build/audit/source/src/R3/GA3.C','build/audit/source/src/R3/COLI3.C',
       'build/audit/source/src/SUICIDE.C','build/audit/source/src/PLAYSUB.C',
       'tools/cc_ga_source.py','build/cc1/ga/retail-animation.json']
report=dict(passed=True,result=Path('build/cc1/ga/result.txt').read_text().strip(),
    inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
    limits='Original GA3 motion, animation, children and COLI3 enemy contact fixtures. Console animation helper replaces the PC sentinel scan. Offscreen streaming and explosion animation are not original-console equivalence claims.')
Path('build/cc1/ga/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
