#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ga build/cc1/kama
python3 tools/cc_kama_reference.py
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_kama_test.c build/cc1/kama/original.c build/cc1/ga/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/kama/test >build/cc1/kama/build.log 2>&1
build/cc1/kama/test | tee build/cc1/kama/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_kama.inc','src/objects_banpa.inc','src/objects_cc_enemy.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h','src/sprite_order.h','src/act.c','src/act.h',
       'tools/cc_kama_test.c','tools/cc_enemy_test_fixture.h','tools/cc_enemy_reference.py','tools/cc_kama_reference.py','tools/cc_kama_source.py','build/cc1/kama/retail.json','tools/test-cc-kama.sh',
       'build/cc1/kama/original.c','build/cc1/ga/original.c','build/audit/source/src/R3/KAMA.C','build/audit/source/src/R3/BANPA.C','build/audit/source/src/ACTION.C',
       'build/audit/source/src/PLAYSUB.C','build/audit/source/src/R3/COLI3.C','build/audit/source/src/SUICIDE.C','build/probe-source/dircol.c','build/probe-source/fcol.c']
report=dict(passed=True,result=Path('build/cc1/kama/result.txt').read_text().strip(),
 inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
 limits='Compiled original Kama/Banpa movement, contacts, blade states and viewport bounds. Draw-queue saturation, full offscreen streaming and enemy-death effects remain separate.')
Path('build/cc1/kama/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
