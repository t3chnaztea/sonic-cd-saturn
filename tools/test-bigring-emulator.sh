#!/bin/bash
# Load the big ring fixture (Start+Left+C: Act 1 Present before the goal post with 50
# rings), jump into the big ring after the signpost, let the tally lead into Special
# Stage 1, play the retail win route's pad script, and require Act 2 to start with time
# stone 1 and the carried score and lives (tools/check_bigring.py).
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/bigring-qa
[ -f build/special-retail/win-route.json ] || python3 tools/special_route.py > build/bigring-qa/route.log
for route in timeout win; do
    [ -f "build/special-retail/$route.pad" ] || python3 tools/special_retail.py "$route" > "build/bigring-qa/retail-$route.log"
done
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
export SCD_SPECIAL_GAME=$(symbol _scd_special_game_mailbox)
export SCD_SPECIAL_ROUTES="$PWD/build/special-retail"
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/bigring-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" bigring > build/bigring-qa/results.log 2> build/bigring-qa/core.log
python3 tools/check_bigring.py
