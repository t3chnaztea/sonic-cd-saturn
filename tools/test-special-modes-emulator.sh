#!/bin/bash
# Special stage mode entries on the Saturn disc against retail (IPX.asm):
# the title times out into the attract cycle, Special Stage 1 and 6 demos play
# their recorded input in temporary mode and return to the title.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/special-game-qa
routes=demo-ss1,demo-ss6
for route in ${routes//,/ }; do
    python3 tools/special_retail.py "$route" > "build/special-game-qa/retail-$route.log"
done
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/special_game_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_SPECIAL_GAME=$(symbol _scd_special_game_mailbox)
export SCD_SPECIAL_ROUTES="$PWD/build/special-retail"
# The title runs about 5,700 frames per time-out; SS1 is the third scene and SS6 the fifth.
SCD_SPECIAL_FRAMES=${SCD_SPECIAL_FRAMES:-40000} SCD_SPECIAL_ATTRACT=1 SCD_SPECIAL_ROUTE_NAMES="$routes" build/special_game_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$PWD/build/special-game-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" specialgame > build/special-game-qa/results-modes.log 2> build/special-game-qa/core-modes.log
python3 tools/check_special_game.py --modes "$routes"
