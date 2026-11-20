#!/bin/bash
# Original camera: (a) dedupe fixtures, the shared scroll_v and scroll_h texts
# against every program's own copy; (b) retail oracle, native scroll_v fed each
# retail update's player state must reproduce retail cameraY (16.16), and native
# PLAYER.C scr_h + scroll_h must reproduce retail camXCenter and cameraX, for PPZ,
# CC, TT and QQ (all six scroll_h texts).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_probe.py
python3 tools/camera_source.py --per-program >/dev/null
out=build/camera
mkdir -p "$out"
flags=(-std=gnu11 -O1 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-shift-negative-value -Isrc -Ibuild/probe-source -DR1 -DR11A)
clang "${flags[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all tools/camera_test.c src/camera_v.c \
    "$out/camera_v_programs.c" build/probe-source/equ.c -o "$out/camera_test"
"$out/camera_test"
clang "${flags[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all tools/camera_h_test.c src/camera_v.c \
    "$out/camera_h_programs.c" build/probe-source/equ.c -o "$out/camera_h_test"
"$out/camera_h_test"
clang "${flags[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all tools/camera_h_retail_test.c src/camera_v.c \
    build/probe-source/equ.c -o "$out/camera_h_retail_test"
clang "${flags[@]}" tools/camera_retail_test.c src/camera_v.c build/probe-source/equ.c -o "$out/camera_retail_test"
printf "100 0\n900 128\n" > "$out/hold-right.txt"
printf "100 0\n400 128\n30 129\n300 128\n" > "$out/ppz-run.txt"
printf "200 0\n30 1\n100 0\n200 128\n300 129\n" > "$out/tt1.txt"
printf "100 0\n350 128\n250 64\n60 65\n240 128\n" > "$out/lr.txt"
# program zone act era script
while read -r name zone act era script; do
    key=$(shasum -a 256 "$out/$script" tools/camera_retail.py | shasum -a 256 | cut -c1-12)
    trace="$out/$name-$key.txt" htrace="$out/$name-$key-h.txt"
    [ -s "$trace" ] && [ -s "$htrace" ] || python3 tools/camera_retail.py "$name" "$out/$script" "$trace" 1000 "$htrace" >/dev/null
    "$out/camera_retail_test" "$zone" "$act" "$era" "$trace"
    "$out/camera_h_retail_test" "$zone" "$act" "$era" "$htrace"
done <<'LIST'
R11A 0 0 0 ppz-run.txt
R11B 0 0 1 hold-right.txt
R12A 0 1 0 hold-right.txt
R31A 1 0 0 ppz-run.txt
R41A 2 0 0 tt1.txt
R42A 2 1 0 hold-right.txt
R11A 0 0 0 lr.txt
R11B 0 0 1 lr.txt
R12A 0 1 0 lr.txt
R12B 0 1 1 lr.txt
R31A 1 0 0 lr.txt
R51A 3 0 0 lr.txt
LIST
echo "PASS: camera matches the original scroll_h/scroll_v texts and retail cameraX/cameraY"
