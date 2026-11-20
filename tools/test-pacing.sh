#!/bin/bash
# Comparable 1800-update route; archived BINs need no matching ELF.
set -euo pipefail
cd "$(dirname "$0")/.."
cue="${1:-$PWD/dist/sonic-cd-saturn-prototype.cue}"
out="${2:-build/pacing-qa}"
mkdir -p "$out"
export SCD_PACING_HARNESS_SHA256=$(shasum -a 256 tools/emulator_test.c | awk '{print $1}')
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include \
    tools/emulator_test.c -o build/pacing_test
build/pacing_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
    "$cue" "$PWD/assets/private" "$out" 0 0 pacing > "$out/results.log" 2> "$out/core.log"
tail -n 1 "$out/results.log"
python3 tools/check_pacing.py "$cue" "$out"
