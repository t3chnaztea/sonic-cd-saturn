#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
case_name="${1:-new}"
output="${SCD_SAVE_OUTPUT_DIR:-build/save-target/$case_name}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_SAVE_MAILBOX=$(symbol _scd_save_mailbox)
export SCD_SAVE_CASE="$case_name"
export SCD_BACKUP_OUTPUT="$output/backup.bin"
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$output" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" save > "$output/results.log" 2> "$output/core.log"
cat "$output/save.json"
