#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc/friend
python3 - <<'PY'
from pathlib import Path
import re
source=Path('build/audit/source/src/R3/FRIEND3.C').read_text()
body=source[source.rindex('static void p_move('):source.rindex('static void p_movie(')]
body=re.sub(r'\(\(int\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*((int*)((char*){m[1]}->actfree+{4*int(m[2])-46})))',body)
text='#include "EQU.H"\nvoid actionsub(sprite_status*);\nvoid frameout_s(sprite_status*);\nshort emycol_d(sprite_status*);\nvoid p_end(sprite_status*);\nvoid p_rev(sprite_status*);\n'+body
text+='\nvoid source_friend_step(sprite_status* o){if(o->r_no0==6)p_rev(o);else p_move(o);}\n'
Path('build/cc/friend/original.c').write_text(text)
PY
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_friend_ground_test.c build/cc/friend/original.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc/friend/test > build/cc/friend/build.log 2>&1
build/cc/friend/test | tee build/cc/friend/result.txt
