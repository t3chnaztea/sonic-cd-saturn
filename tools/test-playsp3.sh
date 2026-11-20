#!/bin/bash
# Collision Chaos terrain bumper blocks (R3/PLAYSP3.C, R3/BOBINB.C): the Saturn
# source (little-endian accessors) against the original casts on the PC actor
# (tools/playsp3_test.c). Traces must be identical and every era's bumper kinds bounce.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py >/dev/null
python3 tools/prepare_player.py >/dev/null
python3 tools/prepare_boss.py >/dev/null
python3 tools/prepare_boss_r3.py >/dev/null
python3 tools/prepare_playsp3.py >/dev/null
mkdir -p build/playsp3-qa
for side in native reference; do
    dir=build/probe-source; flag=
    if [ "$side" = reference ]; then dir=build/player-reference; flag=-DSCD_BOSS_REFERENCE; fi
    clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-implicit-function-declaration \
        -Isrc -I"$dir" -DR1 -DR11A $flag -fsanitize=address,undefined -fno-sanitize-recover=all \
        tools/playsp3_test.c src/boss.c src/boss_r3.c "$dir/playsp3.c" "$dir/boss_1.c" "$dir/boss_3.c" "$dir/etc.c" "$dir/equ.c" \
        build/player-reference/carry.c -o "build/playsp3-qa/playsp3_$side"
    status=0; "build/playsp3-qa/playsp3_$side" > "build/playsp3-qa/$side.log" || status=$?
    echo "$status" > "build/playsp3-qa/$side.status"
done
cmp build/playsp3-qa/native.log build/playsp3-qa/reference.log
tail -1 build/playsp3-qa/native.log
test "$(cat build/playsp3-qa/native.status)" = 0 && test "$(cat build/playsp3-qa/reference.status)" = 0
