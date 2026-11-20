#!/bin/bash
# Compare the Saturn boss sources (little-endian scratch accessors) with the
# original casts on the PC actor layout: BOSS_1.C/COLI1.C (tools/boss_test.c)
# BOSS_3.C/GATE.C/COLI3.C (tools/boss3_test.c) and BOSS_4.C/BOSS_4_2.C/WALL4.C/COLI4.C
# (tools/boss4_test.c).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py >/dev/null
python3 tools/prepare_player.py >/dev/null
python3 tools/prepare_boss.py
python3 tools/prepare_boss_r3.py
python3 tools/prepare_boss_r4.py
python3 tools/prepare_boss_r5.py
mkdir -p build/boss-qa
for round in 1 3 4 5; do
    test=tools/boss_test.c; extra=; name=boss
    if [ "$round" = 3 ]; then test=tools/boss3_test.c; extra="src/boss_r3.c boss_3.c"; name=boss3; fi
    if [ "$round" = 4 ]; then test=tools/boss4_test.c; extra="src/boss_r4.c boss_4.c"; name=boss4; fi
    if [ "$round" = 5 ]; then test=tools/boss5_test.c; extra="src/boss_r5.c boss_5.c"; name=boss5; fi
    for side in native reference; do
        dir=build/probe-source; flag=
        if [ "$side" = reference ]; then dir=build/player-reference; flag=-DSCD_BOSS_REFERENCE; fi
        sources=()
        for f in $extra; do case "$f" in src/*) sources+=("$f");; *) sources+=("$dir/$f");; esac; done
        clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-implicit-function-declaration -Wno-tautological-constant-out-of-range-compare \
            -Isrc -I"$dir" -DR1 -DR11A $flag -fsanitize=address,undefined -fno-sanitize-recover=all \
            "$test" src/boss.c ${sources[@]+"${sources[@]}"} "$dir/boss_1.c" "$dir/etc.c" "$dir/equ.c" build/player-reference/carry.c -o "build/boss-qa/${name}_$side"
        # Rounds 3 and 4 run both futures: BOSS_3.C/BOSS_4_2.C pick the zone track by generate_flag.
        for era in $([ "$round" != 1 ] && echo "good bad" || echo "-"); do
            log="build/boss-qa/${name}-$side"; [ "$era" = - ] || log="$log-$era"
            status=0; "build/boss-qa/${name}_$side" $([ "$era" = - ] || echo "$era") > "$log.log" || status=$?
            echo "$status" > "$log.status"
        done
    done
    for era in $([ "$round" != 1 ] && echo "-good -bad" || echo "''"); do
        [ "$era" = "''" ] && era=
        cmp "build/boss-qa/${name}-native$era.log" "build/boss-qa/${name}-reference$era.log"
        echo "$name$era: $(grep -E '^(summary|era=)' "build/boss-qa/${name}-native$era.log" | tr '\n' ' ')"
        # Both runs must defeat the boss and cover its routines (see each test's exit code).
        test "$(cat build/boss-qa/${name}-native$era.status)" = 0 && test "$(cat build/boss-qa/${name}-reference$era.status)" = 0
    done
done
