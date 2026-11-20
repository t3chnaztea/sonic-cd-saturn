#!/bin/bash
# Underwater player motion: src/player.c against the original PLAYER.C mode bodies
# (tools/water_player_test.c), plus a mutation check: dropping the underwater
# gravity (-40) must fail.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py
python3 tools/prepare_player.py
python3 tools/water_player_original.py
out=build/water
common=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value
    -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all)
clang "${common[@]}" tools/water_player_test.c "$out/player_original.c" src/act.c src/player.c src/sonic_animation.c \
    src/stage.c src/player_replay.c src/objects.c src/water.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o "$out/water_player"
"$out/water_player" > "$out/water-player.log" 2>&1 || { if "$out/water_player" --mutation-no-32 > "$out/water-player-mutation32.log" 2>&1; then
    echo "FAIL: mutation without the underwater hurt -32 was not detected"; exit 1
fi
cat "$out/water-player.log"
echo "mutation (no underwater hurt -32): $(grep -o '[0-9]* mismatches' "$out/water-player-mutation32.log") detected"; echo "FAIL: underwater player motion differs from PLAYER.C"; exit 1; }
if "$out/water_player" --mutation-no-40 > "$out/water-player-mutation.log" 2>&1; then
    echo "FAIL: mutation without the underwater -40 was not detected"; exit 1
fi
if "$out/water_player" --mutation-no-32 > "$out/water-player-mutation32.log" 2>&1; then
    echo "FAIL: mutation without the underwater hurt -32 was not detected"; exit 1
fi
cat "$out/water-player.log"
echo "mutation (no underwater hurt -32): $(grep -o '[0-9]* mismatches' "$out/water-player-mutation32.log") detected"
echo "mutation (no underwater -40): $(grep -o '[0-9]* mismatches' "$out/water-player-mutation.log") detected"
echo "PASS: underwater player motion matches PLAYER.C"
