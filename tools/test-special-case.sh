#!/bin/bash
# One special-stage gate case: tools/test-special-case.sh <stage 1-7> <win|timeout|hazard> <out>.
# Records the retail run, checks the native program against it every V-INT on
# host (tools/test_special_game.py), plays the route in the Saturn emulator
# from the floor inspection and checks that run against retail. Writes
# <out>/report.json (passed, disc_sha256). Routes: win (SS1, planned), win-ss<n>
# and hazard-ss<n> (tests/routes/special), timeout (SS1, with a pause) and
# steer-ss<n> (time-out with a pause, stages 2-7).
set -euo pipefail
cd "$(dirname "$0")/.."
stage=$1 kind=$2 out=$3
case $kind in
    win) route=$([ "$stage" = 1 ] && echo win || echo "win-ss$stage");;
    timeout) route=$([ "$stage" = 1 ] && echo timeout || echo "steer-ss$stage");;
    hazard) route="hazard-ss$stage";;
    *) echo "unknown case $kind" >&2; exit 2;;
esac
mkdir -p "$out"
[ "$route" != win ] || [ -f build/special-retail/win-route.json ] || python3 tools/special_route.py > "$out/route.log"
python3 tools/special_retail.py "$route" > "$out/retail.log"
python3 tools/test_special_game.py "$route" > "$out/host.log"
mkdir -p build/special-game-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/special_game_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_SPECIAL_GAME=$(symbol _scd_special_game_mailbox)
export SCD_SPECIAL_ROUTES="$PWD/build/special-retail"
SCD_SPECIAL_ROUTE_NAMES="$route" build/special_game_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$out" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" specialgame > "$out/results.log" 2> "$out/core.log"
python3 tools/check_special_game.py --routes "$route" --log "$out/results.log" --report "$out/report.json"
