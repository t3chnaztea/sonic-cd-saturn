#!/bin/bash
# Collapse-break batched spawner: the resumed slot scans (with SCD_OBJECTS_VERIFY
# asserts) must assign the same slots and leave the same actor/view state as the
# original from-slot-0 scans (SCD_COLLAPSE_FULL_SCAN), for every PPZ Act 1/2
# collapse placement in every era over a fragmented pool.
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/collapse-spawn;mkdir -p "$out"
src=(tools/collapse_spawn_test.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c
     build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c)
flags=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all)
clang "${flags[@]}" -DSCD_COLLAPSE_FULL_SCAN "${src[@]}" -o "$out/reference"
clang "${flags[@]}" -DSCD_OBJECTS_VERIFY "${src[@]}" -o "$out/resumed"
"$out/reference" > "$out/reference.txt"
"$out/resumed" > "$out/resumed.txt"
cmp "$out/reference.txt" "$out/resumed.txt" || { diff "$out/reference.txt" "$out/resumed.txt" | head -5; echo "FAIL: collapse slot assignment or state differs"; exit 1; }
echo "PASS: $(tail -1 "$out/resumed.txt"); slots and state identical to the from-slot-0 reference"
