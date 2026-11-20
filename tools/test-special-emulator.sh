#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/special-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/special_test
mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
audio_mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
export SCD_SPECIAL_BENCHMARK=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_special_benchmark" {print $1}')
export SCD_SPECIAL_CONTACTS=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_special_contact_trace" {print $1}')
export SCD_SPECIAL_SONIC=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_special_sonic_mailbox" {print $1}')
export SCD_SPECIAL_MAILBOX=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_special_mailbox" {print $1}')
build/special_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$PWD/build/special-qa" "$mailbox" "$audio_mailbox" special > build/special-qa/results.log 2> build/special-qa/core.log

python3 tools/check_special.py
