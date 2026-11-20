#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py
python3 tools/prepare_player.py
common=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -DR1 -DR11A)
# camera_v.c: src/main.c runs GAME.C scroll() after each replay update; a dead Sonic
# pins scralim_down to the camera (tools/player_trace.c).
sources=(tools/player_trace.c tools/player_slot_model.c src/act.c src/player.c src/sonic_animation.c src/stage.c src/player_replay.c src/objects.c src/camera_v.c)
clang "${common[@]}" -Ibuild/probe-source -fsanitize=address,undefined -fno-sanitize-recover=all \
    "${sources[@]}" build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/player_trace_sanitized
SCD_PLAYER_VISUAL_TRACE_FILE=build/player-host-visual-trace.txt build/player_trace_sanitized > build/player-host-trace.txt
clang "${common[@]}" -Ibuild/player-reference -Ibuild/probe-source "${sources[@]}" \
    build/player-reference/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/player_trace_reference
SCD_PLAYER_VISUAL_TRACE_FILE=build/player-reference-visual-trace.txt build/player_trace_reference > build/player-reference-trace.txt
cmp build/player-host-trace.txt build/player-reference-trace.txt
cmp build/player-host-visual-trace.txt build/player-reference-visual-trace.txt
python3 tools/check_player.py --host-only
