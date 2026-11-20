#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# test-cc-traps.sh builds the shared independent original source first.
mkdir -p build/cc1/gandair
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_gandair_test.c build/cc1/traps/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/gandair/test >build/cc1/gandair/build.log 2>&1
build/cc1/gandair/test | tee build/cc1/gandair/result.txt
python3 - <<'PY'
from pathlib import Path
import hashlib,json
paths=['src/objects_cc_traps.inc','src/objects_for3.inc','src/objects_bobin.inc','src/objects.c','src/scd_actor.h','src/scd_objects.h',
       'tools/cc_gandair_test.c','tools/cc_traps_test.c','tools/test-cc-traps.sh','tools/test-cc-gandair.sh','build/cc1/traps/original.c',
       'build/audit/source/src/R3/TRAP_R3.C','build/audit/source/src/RIDECHK.C','build/audit/source/src/R3/COLI3.C',
       'build/audit/source/src/PLAYSUB.C','tools/cc_gandair_source.py','build/cc1/gandair/retail-animation.json']
report=dict(passed=True,result=Path('build/cc1/gandair/result.txt').read_text().strip(),
            inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
            limits='Compiled original multi-actor routines, full-solid geometry and bullet hitboxes. Animation delay reload is corrected to the verified Sega CD instruction. Allocation/retry/removal fixtures are bounded; no complete gameplay or offscreen-streaming equivalence claim.')
Path('build/cc1/gandair/report.json').write_text(json.dumps(report,indent=2)+'\n')
PY
