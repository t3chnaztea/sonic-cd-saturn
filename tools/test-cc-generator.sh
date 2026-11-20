#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ga build/cc1/generator
python3 tools/cc_generator_reference.py
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_generator_test.c build/cc1/generator/original.c build/cc1/ga/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/generator/test >build/cc1/generator/build.log 2>&1
build/cc1/generator/test | tee build/cc1/generator/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_cc_generator.inc','src/objects_cc_enemy.inc','src/objects_tentou.inc','src/objects_cc_traps.inc','src/objects_for3.inc','src/objects_bobin.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h','src/sprite_order.h',
       'tools/cc_generator_test.c','tools/cc_generator_reference.py','tools/cc_generator_source.py','tools/test-cc-generator.sh','tools/cc_enemy_test_fixture.h','tools/cc_enemy_reference.py',
       'build/cc1/generator/retail.json','build/cc1/generator/original.c','build/cc1/ga/original.c','build/audit/source/src/R3/ET3.C','build/audit/source/src/R3/COLI3.C','build/audit/source/src/RIDECHK.C','build/audit/source/src/PLAYSUB.C','build/audit/source/src/ACTSET.C','build/audit/source/src/ACTION.C','build/audit/source/src/TBL1.C']
report=dict(passed=True,result=Path('build/cc1/generator/result.txt').read_text().strip(),inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},limits='Original generator hover, initialization, collision/solidity, destruction sequence and non-enemy explosion dispatch with console corrections. Includes full-pool failure and earlier-slot allocation. Era travel, persistence, broad mixed-family collision ordering, target rendering and ordinary routes remain separate.')
Path('build/cc1/generator/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
