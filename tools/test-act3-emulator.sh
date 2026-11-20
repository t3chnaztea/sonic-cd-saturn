#!/bin/bash
# Load Act 3 (bad future) with the Start+Up+C debug entry, drive a controller route
# through the boss and the flower capsule to the results tally and the
# end-of-prototype screen, then replay the Saturn trace on the host.
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/act3-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
# Route areas: jump onto the Future Tamabboh at (888,640) (retail range box and
# fire timing, 29538f5), spin dash from the valley floor after the boss arena
# (X 3290-3380) up the quarter pipe, then jump onto the flower capsule at X 3656.
export SCD_ACT2_ROUTE="${SCD_ACT3_ROUTE:-790-840/600-660j,3290-3380/430-470D,3540-3620/940-1000j}"
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/act3-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" act3 > build/act3-qa/results.log 2> build/act3-qa/core.log
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/act_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/boss.c \
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/act3_test
build/act3_test act3 > build/act3-qa/host-results.log 2>&1
python3 tools/check_act3.py
