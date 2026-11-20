#!/bin/bash
# Play Act 1 Present from the ordinary spawn to its tally, let the original fade
# and title card lead into Act 2 Present, play the Act 2 route to its tally, then
# Act 3 in the bad future through the boss and the flower capsule to its tally and
# automatic entry into Collision Chaos Act 1. No debug input.
# All three traces are replayed on the host from the carried progress.
set -euo pipefail
cd "$(dirname "$0")/.."
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
mkdir -p build/sequence-qa
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
# Since the 68k player fixes and camera-X the built-in Act 1 controller and
# the Act 2/3 region rules no longer finish. The three acts replay the staged
# host scripts (tests/routes/ppz, SCD_PPZ_ROUTES): each becomes placeholder
# SCD_SEQUENCE_PAD_DIR input (tools/act_reference_from_script.py) for an
# SCD_ACT_PAD_RECORD run, so the Saturn takes exactly the scripted buttons;
# tools/act_test.c below then replays every act's own trace strictly.
routes=${SCD_PPZ_ROUTES:-tests/routes/ppz}
inputs=build/sequence-qa/pad-input
mkdir -p "$inputs"
clang -std=gnu11 -O2 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
    -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A tools/cc_campaign_search.c \
    src/{title_card,world,act,player,camera_v,sonic_animation,stage,boss,boss_r3,objects}.c \
    build/probe-source/{boss_1,boss_3,playsp3,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/ppz_route_host
for leg in "p0:A p0A.seq player-target-trace.txt" "p1:A p1A act2-target-trace.txt" "p2:D p2D.found act3-target-trace.txt"; do
    set -- $leg
    cp "$routes/$2.txt" "$inputs/$2.script"
    env -u PPZ_DIRECT_ENTRY build/ppz_route_host replay "$1" "$inputs/$2.script" 40000 "$inputs/$2.host.txt" 2> "$inputs/$2.host.log"
    updates=$(sed -n 's/^Tally complete: sequence=\([0-9]*\).*/\1/p' "$inputs/$2.host.log")
    test -n "$updates" || { echo "host route $2 did not reach the tally" >&2; exit 1; }
    python3 tools/act_reference_from_script.py "$inputs/$2.script" "$updates" "$inputs/$3"
done
export SCD_SEQUENCE_PAD_DIR="$inputs" SCD_ACT_PAD_RECORD=1
unset SCD_ACT2_ROUTE SCD_ACT3_ROUTE SCD_ACT_PAD_TRACE SCD_ACT_ERA SCD_ACT_START SCD_ACT_RIGHT
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
    "$PWD/build/sequence-qa" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" sequence > build/sequence-qa/results.log 2> build/sequence-qa/core.log
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/act_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/boss.c \
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/act_test
SCD_ACT_TRACE=build/sequence-qa/player-target-trace.txt build/act_test > build/sequence-qa/host-act1.log 2>&1
read score lives < <(sed -n 's/^Full Present act: .* score=\([0-9]*\) bonus=[0-9]* lives=\([0-9]*\) .*/\1 \2/p' build/sequence-qa/results.log)
SCD_ACT_TRACE=build/sequence-qa/act2-target-trace.txt build/act_test act2 "$score" "$lives" 50000 > build/sequence-qa/host-act2.log 2>&1
read score lives < <(sed -n 's/^Full Act 2 Present: .* score=\([0-9]*\) bonus=[0-9]* lives=\([0-9]*\) .*/\1 \2/p' build/sequence-qa/results.log)
SCD_ACT_TRACE=build/sequence-qa/act3-target-trace.txt build/act_test act3 "$score" "$lives" $(( score < 50000 ? 50000 : 100000 )) > build/sequence-qa/host-act3.log 2>&1
python3 tools/check_sequence.py
