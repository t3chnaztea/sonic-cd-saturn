#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/world-qa
clang -std=gnu11 -Wall -Wextra -Werror \
    -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
test -n "$mailbox"
audio_mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
export SCD_WORLD_ITERATION=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_world_probe_iteration" {print $1}')
export SCD_WORLD_PROGRESS=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_world_probe_phase" {print $1}')
export SCD_WORLD_MAILBOX=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_world_mailbox" {print $1}')
export SCD_SONIC_VIEW=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_sonic_view_mailbox" {print $1}')
export SCD_EFFECT_MAILBOX=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_effect_mailbox" {print $1}')
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
    "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/world-qa" "$mailbox" "$audio_mailbox" world > build/world-qa/results.log 2> build/world-qa/core.log
python3 tools/check_world.py
python3 tools/check_powerup_target.py
python3 tools/check_powerup_pixels.py
