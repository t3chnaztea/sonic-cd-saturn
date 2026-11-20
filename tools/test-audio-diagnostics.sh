#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/diagnostic-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/diagnostic_test
mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
audio_mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
build/diagnostic_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$PWD/build/diagnostic-qa" "$mailbox" "$audio_mailbox" diagnostic > build/diagnostic-qa/results.log 2> build/diagnostic-qa/core.log

python3 tools/check_audio_diagnostics.py
