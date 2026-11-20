#!/bin/bash
# Quartz Quadrant conveyor belts: compiled R5/PLAYSP5.C belt versus the native
# src/player.c scd_playsp5 on every Quartz Quadrant map (tools/playsp5_test.c).
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/playsp5-qa
mkdir -p "$out"
python3 - <<'PY'
import re
from pathlib import Path
t=Path('build/audit/source/src/R5/PLAYSP5.C').read_text(encoding='latin1')
t=re.sub(r'^#include .*\n','',t,flags=re.M)
for name in ('playsp','belt_effect','belt_chk','belt_tbl','belt_a','belt_b','belt_c','belt_d','belt'):
    t=re.sub(r'\b%s\b'%name,'orig_'+name,t)
# The Mega-CD GetLevelBlock returns chunk 1's first block for a blank chunk
# (tools/playsp5_test.c orig_level_block); the PC FCOL.C scramapad returns 0.
t=re.sub(r'\bscramapad\(','orig_level_block(',t)
Path("build/playsp5-qa/original.c").write_text("#include \"EQU.H\"\n#include \"DIRCOL.H\"\n#include \"FCOL.H\"\nvoid orig_belt(void);void orig_belt_effect(void);int orig_belt_chk(short);short orig_level_block(sprite_status*,short,short);\n"+t)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Wno-incompatible-pointer-types -Wno-int-conversion \
    -Isrc -Iassets/generated -Ibuild/probe-source -Itools -DR1 -DR11A \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/playsp5_test.c "$out/original.c" \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c src/water.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >"$out/build.log" 2>&1 || { grep -m20 error "$out/build.log" >&2 || tail -n 20 "$out/build.log" >&2; exit 1; }
"$out/test" | tee "$out/result.txt"
