#!/bin/bash
# Enter every zone past Palmtree Panic through the level select on the Saturn
# build, and require its terrain and object layout to load from the CD and its
# objects to spawn. Usage: bash tools/test-zones-emulator.sh [ZONE...]
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/zones-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/zones_test
elf=build/saturn/sonic-cd-saturn-prototype.elf
mailbox=$(.toolchain/bin/sh-elf-nm $elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
audio_mailbox=$(.toolchain/bin/sh-elf-nm $elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
export SCD_WORLD_MAILBOX=$(.toolchain/bin/sh-elf-nm $elf | awk '$3 == "_scd_world_mailbox" {print $1}')
status=0
for zone in "${@:-0 1 2 3 4 5 6}"; do
    for z in $zone; do
        mkdir -p build/zones-qa/$z
        if SCD_ZONE=$z build/zones_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
            "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
            "$PWD/build/zones-qa/$z" "$mailbox" "$audio_mailbox" zones \
            > build/zones-qa/$z/results.log 2> build/zones-qa/$z/core.log; then
            grep '^Zone' build/zones-qa/$z/results.log
        else
            echo "Zone $z FAILED: $(tail -1 build/zones-qa/$z/core.log)"; status=1
        fi
    done
done
exit $status
