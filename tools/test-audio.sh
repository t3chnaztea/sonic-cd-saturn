#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/audio-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/audio_test
mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
audio_mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
build/audio_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" "$PWD/build/audio-qa" "$mailbox" "$audio_mailbox" audio > build/audio-qa/results.log 2> build/audio-qa/core.log
python3 tools/check_audio.py
