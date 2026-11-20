#!/bin/bash
# Replay a recorded explorer route through NEW GAME with normal controller pads.
set -euo pipefail
cd "$(dirname "$0")/.."
source_dir=${1:?usage: test-ppz-journey.sh EXPLORER_DIRECTORY OUTPUT_DIRECTORY}
out=${2:?output directory required}
test ! -e "$out"
test -s "$source_dir/states.bin"
mkdir -p "$out"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/journey-emulator-test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name || index($3, name ".lto_priv.") == 1 {print $1; exit}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
export SCD_JOURNEY_GOOD_FLAGS=$(symbol _good_future_flags)
export SCD_JOURNEY_EFFECTS=$(symbol _scd_effect_mailbox)
export SCD_FRAME_PROFILE=$(symbol _scd_frame_profile)
test -n "$SCD_WORLD_MAILBOX" && test -n "$SCD_JOURNEY_GOOD_FLAGS" && test -n "$SCD_JOURNEY_EFFECTS"
export SCD_JOURNEY_STATES="$source_dir/states.bin"
if [ "${SCD_JOURNEY_SPECIAL:-}" = 1 ]; then
    export SCD_SPECIAL_GAME=$(symbol _scd_special_game_mailbox)
    export SCD_SPECIAL_ROUTES="$PWD/build/special-retail"
    test -n "$SCD_SPECIAL_GAME" && test -s "$SCD_SPECIAL_ROUTES/timeout.pad" && test -s "$SCD_SPECIAL_ROUTES/win.pad"
fi
build/journey-emulator-test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
 "$PWD/$out" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" journey > "$out/results.log" 2> "$out/core.log"
python3 tools/check_ppz_journey.py "$source_dir" "$out"
