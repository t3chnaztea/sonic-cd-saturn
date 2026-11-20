#!/bin/bash
# Tidal Tempest water: src/water.c against the compiled original routines
# (PLAYER.C plwaterchk, R4/GAME4.C water*/watercoli, R4/PLAYSUB4.C plairset,
# plawamaster, plawa, exit2), traced frame by frame over entry/exit speed
# sweeps, water level paths, every current box, and air countdowns to drowning.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py
python3 tools/prepare_player.py
python3 tools/water_assets.py >/dev/null
python3 tools/water_original.py
out=build/water
mkdir -p "$out"
common=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value
    -Wno-implicit-function-declaration -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A
    -fsanitize=address,undefined -fno-sanitize-recover=all)
helpers=(build/probe-source/movement.c build/probe-source/etc.c build/probe-source/equ.c)
helpers+=("$out/jumpcolsub.c")
clang "${common[@]}" -DWATER_ORIGINAL tools/water_test.c "$out/original.c" "${helpers[@]}" -o "$out/water_original"
clang "${common[@]}" tools/water_test.c src/water.c "${helpers[@]}" -o "$out/water_native"
"$out/water_original" 2> "$out/original.log"
"$out/water_native" 2> "$out/native.log"
if ! cmp -s "$out/original.log" "$out/native.log"; then
    WATER_TRACE=1 "$out/water_original" > "$out/original-trace.txt" 2>/dev/null
    WATER_TRACE=1 "$out/water_native" > "$out/native-trace.txt" 2>/dev/null
    diff "$out/original-trace.txt" "$out/native-trace.txt" | head -n 20 || true
    echo "FAIL: water native trace differs from compiled original"
    exit 1
fi
echo "$(cat "$out/original.log") (native identical)"
echo "PASS: water native matches compiled original"
