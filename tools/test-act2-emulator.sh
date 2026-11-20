#!/bin/bash
# Load Act 2 Present with the Start+C debug entry, drive a controller route from
# its ordinary spawn to the results tally, replay the Saturn trace on the host
# and check captures (tools/check_act2.py).
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/act2-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
# Since the 68k player fixes and camera-X the SCD_ACT2_ROUTE region rules no
# longer finish: the Present replays the staged host script (tests/routes/ppz,
# SCD_PPZ_ROUTES) through tools/run-act2-era-script.sh (era 0), which feeds it as
# SCD_ACT_PAD_RECORD input; tools/act_test.c below replays the Saturn's trace strictly.
bash tools/run-act2-era-script.sh 0 "${SCD_PPZ_ROUTES:-tests/routes/ppz}/p1A.txt" build/act2-qa
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/act_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/boss.c \
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/act_test
build/act_test act2 > build/act2-qa/host-results.log 2>&1
# Travel: Start+C again places Sonic beside the past post above the tube shaft; walking
# left and then holding Right charges the warp and arrives in the Act 2 past.
mkdir -p build/act2-qa/travel-past
env -u SCD_ACT_PAD_TRACE SCD_ACT2_TRAVEL_CASE=past build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/act2-qa/travel-past" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" act2travel > build/act2-qa/travel-past/results.log 2> build/act2-qa/travel-past/core.log
python3 tools/check_act2.py
