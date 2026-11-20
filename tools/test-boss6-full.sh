#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py >/dev/null
python3 tools/prepare_player.py >/dev/null
python3 tools/prepare_boss.py >/dev/null
python3 tools/prepare_boss_r6.py >/dev/null
mkdir -p build/boss6-full
for side in native reference; do
    dir=build/probe-source;flag=
    if [ "$side" = reference ]; then dir=build/player-reference;flag=-DSCD_BOSS_REFERENCE; fi
    clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
        -Wno-parentheses -Wno-unused-value -Wno-implicit-function-declaration \
        -Wno-tautological-constant-out-of-range-compare -Isrc -I"$dir" -DR1 -DR11A $flag \
        -fsanitize=address,undefined -fno-sanitize-recover=all \
        tools/boss6_test.c src/boss.c src/boss_r6.c "$dir/boss_1.c" "$dir/boss_6.c" \
        "$dir/etc.c" "$dir/equ.c" build/player-reference/carry.c \
        -o "build/boss6-full/$side"
    for era in good bad; do
        "build/boss6-full/$side" "$era" > "build/boss6-full/$side-$era.log"
    done
done
for era in good bad; do
    cmp "build/boss6-full/native-$era.log" "build/boss6-full/reference-$era.log"
    grep '^summary' "build/boss6-full/native-$era.log"
done
echo "PASS: WW3 full boss fight matches compiled BOSS_6.C in both futures"
