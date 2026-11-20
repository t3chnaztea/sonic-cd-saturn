#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/act-qa
clang -std=gnu11 -Wall -Wextra -Werror \
    -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_trace_mailbox" {print $1}')
test -n "$mailbox"
audio_mailbox=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_audio_mailbox" {print $1}')
export SCD_WORLD_MAILBOX=$(.toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk '$3 == "_scd_world_mailbox" {print $1}')
# V0.073 (grounded spawn, original spring contact, roll rounding, warp lead
# update): the Right + periodic Jump policy reaches the signpost from jump
# phase 609 (scan of 591..620 on BIN dc05d1ee: 609, 613, 620 complete; 607
# stops short). Override with SCD_ACT_START.
export SCD_ACT_START=${SCD_ACT_START:-609}
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" \
    "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/act-qa" "$mailbox" "$audio_mailbox" act > build/act-qa/results.log 2> build/act-qa/core.log

clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/act_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/boss.c \
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/act_test
build/act_test > build/act-qa/host-results.log 2>&1
python3 tools/check_act.py
