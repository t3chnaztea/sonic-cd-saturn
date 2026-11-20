#!/bin/bash
# Finite diagnostic run using real controller input and an exact state oracle.
set -euo pipefail
cd "$(dirname "$0")/.."
era=${1:?usage: profile-act.sh ERA REFERENCE_TRACE OUTPUT_DIRECTORY}
reference=${2:?reference trace required}
out=${3:?new output directory required}
case "$era" in 0|1|2|3) ;; *) exit 2;; esac
test ! -e "$out"
mkdir -p "$out"
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
export SCD_FRAME_PROFILE=$(symbol _scd_frame_profile)
test -n "$SCD_FRAME_PROFILE"
export SCD_ACT_PAD_TRACE="$reference"
unset SCD_ACT_ERA SCD_ACT2_TRAVEL SCD_ACT_START SCD_ACT_RIGHT SCD_ACT2_ROUTE SCD_ACT2_SHOT
if [ "$era" -ne 0 ]; then export SCD_ACT_ERA="$era"; fi
shasum -a 256 dist/sonic-cd-saturn-prototype.bin dist/sonic-cd-saturn-prototype.cue \
    build/saturn/sonic-cd-saturn-prototype.elf tools/emulator_test.c tools/act_pad_replay.h \
    src/frame_profile.h src/main.c "$reference" > "$out/input-hashes.txt"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/profile_act_test
build/profile_act_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
    "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$out" \
    "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" act2 > "$out/results.log" 2> "$out/core.log"
shasum -a 256 -c "$out/input-hashes.txt" > "$out/hash-check.log"
tail -n 2 "$out/results.log"
