#!/bin/bash
# Finite diagnostic: preserve exact inputs and all 16 state words across acts.
# Does not replace the full release sequence gate or write its report.
set -euo pipefail
cd "$(dirname "$0")/.."
reference=${1:?usage: replay-sequence.sh REFERENCE_DIRECTORY NEW_OUTPUT_DIRECTORY}
out=${2:?new output directory required}
test ! -e "$out"
mkdir -p "$out"
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
export SCD_SEQUENCE_PAD_DIR="$reference"
unset SCD_ACT_PAD_TRACE SCD_ACT_ERA SCD_ACT2_TRAVEL SCD_ACT_START SCD_ACT_RIGHT SCD_ACT2_ROUTE SCD_ACT3_ROUTE SCD_ACT2_SHOT SCD_FRAME_PROFILE
profile=$(symbol _scd_frame_profile)
if [ -n "$profile" ]; then export SCD_FRAME_PROFILE="$profile"; fi
shasum -a 256 dist/sonic-cd-saturn-prototype.bin dist/sonic-cd-saturn-prototype.cue \
    build/saturn/sonic-cd-saturn-prototype.elf tools/emulator_test.c tools/act_pad_replay.h \
    src/frame_profile.h src/main.c src/gameplay_video.inc src/background.c src/background.h src/objects.c \
    tools/replay-sequence.sh tools/check_sequence_replay.py \
    "$reference/player-target-trace.txt" "$reference/act2-target-trace.txt" "$reference/act3-target-trace.txt" > "$out/input-hashes.txt"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/replay_sequence_test
build/replay_sequence_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
    "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$out" \
    "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" sequence > "$out/results.log" 2> "$out/core.log"
shasum -a 256 -c "$out/input-hashes.txt" > "$out/hash-check.log"
rg '^Act pacing:|^Full |^Act 3 end:' "$out/results.log"
python3 tools/check_sequence_replay.py "$out" "$reference"
