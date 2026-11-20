#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/special-game-qa
[ -f build/special-retail/win-route.json ] || python3 tools/special_route.py > build/special-game-qa/route.log
for route in timeout win; do
    python3 tools/special_retail.py "$route" > "build/special-game-qa/retail-$route.log"
done
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/special_game_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_SPECIAL_GAME=$(symbol _scd_special_game_mailbox)
export SCD_SPECIAL_ROUTES="$PWD/build/special-retail"
build/special_game_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$PWD/build/special-game-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" specialgame > build/special-game-qa/results.log 2> build/special-game-qa/core.log
python3 tools/check_special_game.py
# Stages 2-7 entered from the floor inspection (X, then B; L+B for win routes):
# steering time-outs with a pause, stored win routes, and stored hazard sweeps
# (every stamp type, then a time-out; tests/routes/special).
run_set(){
    local set=$1 names="";shift
    for route in "$@"; do
        python3 tools/special_retail.py "$route" > "build/special-game-qa/retail-$route.log"
        names="$names${names:+,}$route"
    done
    SCD_SPECIAL_ROUTE_NAMES="$names" build/special_game_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$PWD/build/special-game-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" specialgame > "build/special-game-qa/results-$set.log" 2> "build/special-game-qa/core-$set.log"
    python3 tools/check_special_game.py "--$set"
}
sets=${SCD_SPECIAL_SETS:-stages hazards wins}
for set in $sets; do
    case $set in
        stages) run_set stages steer-ss2 steer-ss3 steer-ss4 steer-ss5 steer-ss6 steer-ss7;;
        wins) run_set wins win-ss2 win-ss3 win-ss4 win-ss5 win-ss6 win-ss7;;
        hazards) run_set hazards hazard-ss1 hazard-ss2 hazard-ss3 hazard-ss4 hazard-ss5 hazard-ss6 hazard-ss7;;
    esac
done
