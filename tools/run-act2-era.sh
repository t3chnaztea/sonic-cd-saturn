#!/bin/bash
# Exploratory controller route; writes only to its explicit output directory.
set -euo pipefail
cd "$(dirname "$0")/.."
era=${1:?era 1-3 required}
case "$era" in 1|2|3) ;; *) exit 2;; esac
out=${2:?output directory required}
: "${SCD_ACT2_ROUTE:?controller route required}"
mkdir -p "$out"
# Save the exact controller recipe with both successful and incomplete attempts.
printf '%s\n' "$SCD_ACT2_ROUTE" > "$out/route.txt"
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
export SCD_ACT_ERA=$era
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
 "$out" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" act2 > "$out/results.log" 2> "$out/core.log"
