#!/bin/bash
# Controller-only route from the selected era's spawn, sanitized replay and source pixels.
set -euo pipefail
cd "$(dirname "$0")/.."
unset SCD_ACT2_TRAVEL SCD_ACT_START SCD_ACT_RIGHT SCD_ACT2_SHOT
era=${1:?usage: bash tools/test-act2-era-emulator.sh ERA (1=Past, 2=Good Future, 3=Bad Future)}
case "$era" in
  1)
    name=past
    # Since the 68k player fixes (settle, air drag, spring side, limitchk) and
    # camera-X the region rules below leave era 1 on Saturn; the gate replays a
    # host-searched no-damage Past script instead (PPZ_NO_DAMAGE=1 search).
    script=${SCD_PPZ_ROUTES:-tests/routes/ppz}/p1B.nohit.txt
    # The two added jump windows clear the enemies at x7177 and x7825 that this
    # route ran into on V0.057. This is the no-damage reference route, so a hit
    # fails the gate; V0.056 reached them with different speed and passed them.
    export SCD_ACT2_ROUTE='4250-4345/300-450D,4600-4710/800-920j,5480-5640/780-940R,5660-5830/560-640l,6560-6720/340-400w,6720-6912/320-400r,7100-7180/560-650j,7740-7830/480-560j,9660-9740/680-760j'
    ;;
  2)
    name=good
    # Host-searched script (the host masks input until the Saturn's first
    # accepted update, 128 C / 117 D); the region rules below no longer finish.
    script=${SCD_PPZ_ROUTES:-tests/routes/ppz}/p1C.era.txt
    # Run up the upper bank, ride the swing, then jump the two left-facing springs.
    # Two added spin dashes: out of the basin at x5070 where this route
    # oscillated, and through the x5926 wall, the same wall the Bad Future
    # route stops at. Both are speed-dependent and V0.057 arrives slower.
    export SCD_ACT2_ROUTE='4640-4720/380-440d,4800-4990/200-420R,5030-5120/900-980D,5660-5830/560-640l,5860-5930/760-820D,6560-6720/340-400w,6720-6912/320-400r,8000-8090/650-740j,8820-8860/560-620j,9660-9740/680-760j'
    ;;
  3)
    name=bad
    # Host-searched script (the host masks input until the Saturn's first
    # accepted update, 128 C / 117 D); the region rules below no longer finish.
    script=${SCD_PPZ_ROUTES:-tests/routes/ppz}/p1D.era.txt
    # Three lower curved walls need an in-place dash. Jump the low spring at X 8344.
    # V0.057 holds the controller through the title card, so Sonic reaches the
    # x5224 and x5926 walls with less speed than the V0.056 route assumed and
    # stopped dead at each. The two added windows retry them: a run-up at the
    # first, a spin dash at the second. Same score, bonus and lives as V0.056.
    export SCD_ACT2_ROUTE='2150-2265/850-1000D,4640-4720/380-440d,4800-4990/200-420R,5040-5090/890-1000D,5230-5320/560-620R,5660-5830/560-640l,5860-5930/760-820D,6560-6720/340-400w,6720-6912/320-400r,6830-6885/430-490D,8000-8090/650-740j,8240-8310/900-980j,8820-8860/560-620j,9660-9740/680-760j'
    ;;
  *) echo 'Supported reference routes: 1=Past, 2=Good Future, 3=Bad Future' >&2; exit 2 ;;
esac
test -s assets/private/mpr-17933.bin || { echo 'Place your US/EU Saturn BIOS at assets/private/mpr-17933.bin' >&2; exit 1; }
out="build/act2-$name-qa"
mkdir -p "$out"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
if [ -n "${script:-}" ]; then bash tools/run-act2-era-script.sh "$era" "$script" "$out"; else bash tools/run-act2-era.sh "$era" "$out"; fi
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/act_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/boss.c \
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/act_test
SCD_ACT_ERA="$era" SCD_ACT_TRACE="$out/player-target-trace.txt" build/act_test act2 > "$out/host-results.log" 2>&1
python3 tools/check_act2_era.py "$era" "$out"
