#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/emulator-qa
clang -std=gnu11 -Wall -Wextra -Werror \
    -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
test -n "$mailbox"
audio_mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
export SCD_STAGE_PACKS=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_stage_pack_mailbox" {print $1}')
export SCD_SONIC_VIEW=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_sonic_view_mailbox" {print $1}')
export SCD_PLAYER_VISUAL_TRACE=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_player_visual_trace" {print $1}')
export SCD_FLOOR_MAILBOX=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_floor_mailbox" {print $1}')
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
    "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/emulator-qa" "$mailbox" "$audio_mailbox" > build/emulator-qa/results.log 2> build/emulator-qa/core.log
python3 tools/check_emulator.py
python3 tools/check_player.py
python3 tools/check_player_visual.py
python3 tools/check_sonic_pixels.py
