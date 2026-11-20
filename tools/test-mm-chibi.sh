#!/bin/bash
# Host integration check for the R8 shrink form (tools/mm_chibi_test.c).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py
python3 tools/prepare_player.py
common=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -DR1 -DR11A)
sources=(tools/mm_chibi_test.c tools/player_slot_model.c src/act.c src/player.c src/sonic_animation.c src/stage.c src/player_replay.c src/objects.c src/camera_v.c)
clang "${common[@]}" -Ibuild/probe-source -fsanitize=address,undefined -fno-sanitize-recover=all \
    "${sources[@]}" build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/mm_chibi_test 2>build/mm_chibi_test.log
build/mm_chibi_test
