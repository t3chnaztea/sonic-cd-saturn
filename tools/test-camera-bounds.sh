#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/camera-bounds
mkdir -p "$out"
clang -x c -std=gnu11 -O1 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-shift-negative-value \
    -Isrc -Ibuild/probe-source -I.deps/soniccd/src -DR1 -DR11A \
    -fsanitize=address,undefined -fno-sanitize-recover=all tools/camera_bounds_test.c \
    .deps/soniccd/src/SCRCHK.C build/probe-source/equ.c -o "$out/test"
"$out/test"
