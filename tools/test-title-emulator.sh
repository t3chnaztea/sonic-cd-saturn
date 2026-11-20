#!/bin/bash
# Boot the disc into the title screen, replay the retail NEW GAME route (tools/title_retail.py) by
# title V-INT, record the title state and picture every frame, then require Act 1 to start.
# tools/check_title.py saturn compares the run with the retail records.
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/title-qa
for route in newgame timeout; do
    [ -f "build/title-retail/$route-pixels.zip" ] && [ -f "build/title-retail/$route.jsonl" ] && [ -f "build/title-retail/$route.pad" ] || python3 tools/title_retail.py "$route" > "build/title-qa/retail-$route.log"
done
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_TITLE_MAILBOX=$(symbol _scd_title_mailbox)
export SCD_TITLE_ROUTES="$PWD/build/title-retail"
export SCD_TITLE_SHOTS=${SCD_TITLE_SHOTS:-40,60,74,90,120,202,203,702,710,730,801,812}
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/title-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" title > build/title-qa/results.log 2> build/title-qa/core.log
python3 tools/check_title.py saturn
