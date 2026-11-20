#!/bin/bash
# Original for3 + frdr3 + RIDECHK.C versus native actors on two adjacent
# CC1 Present platforms. Reuses the generated single-actor oracles.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/ride-handoff
bash tools/test-cc-traps.sh >/dev/null
bash tools/test-cc-platform.sh >/dev/null
python3 - <<'PY'
from pathlib import Path
traps=Path('build/cc1/traps/original.c').read_text()
platform=Path('build/cc1/platform/original.c').read_text()
body=platform[platform.index('void for3(sprite_status* floorwk) {'):platform.index('short ride_on_clr(sprite_status* pActwk, sprite_status* pPlayerwk) {')]
names=['for3','for3_init','for3_move','for3_ridechk','dai3sub','for3_fix','for3_lmv','for3_rmv','for3_umv','for3_dmv','for3_rup','for3_rup1','for3_rup2','for3_rup3']
prototypes=''.join(f'void {n}(sprite_status*);\n' for n in names if f'void {n}(' not in traps)
for n in names:
    if f'void {n}(sprite_status* floorwk) {{' in traps or f'void {n}(sprite_status* thingwk) {{' in traps:
        raise SystemExit(f'duplicate {n}')
Path('build/cc1/ride-handoff/original.c').write_text(traps+'\n'+prototypes+body)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_ride_handoff_test.c build/cc1/ride-handoff/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/ride-handoff/test >build/cc1/ride-handoff/build.log 2>&1
build/cc1/ride-handoff/test | tee build/cc1/ride-handoff/result.txt
