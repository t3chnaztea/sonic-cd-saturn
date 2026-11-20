#!/bin/bash
# Dedicated damage/ring-loss stress route, separate from the no-damage Past gate.
# The Act 2 Past replays the staged host script (tests/routes/ppz/p1B.txt: 52
# hurt ticks, 44 rings lost in one update on the host) through
# tools/run-act2-era-script.sh era 1; tools/act_test.c then replays the Saturn's
# own trace strictly and tools/check_past_ring_loss.py requires the stress.
# usage: tools/test-past-ring-loss.sh SCRIPT OUTPUT
set -euo pipefail
cd "$(dirname "$0")/.."
script=${1:?route script required (tests/routes/ppz/p1B.txt)}
out=${2:?new output directory required}
test ! -e "$out"
mkdir -p "$out"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/emulator_test
shasum -a 256 dist/sonic-cd-saturn-prototype.bin tools/emulator_test.c src/main.c \
    src/player_replay.c src/player_replay.h tools/act_pad_replay.h "$script" > "$out/input-hashes.txt"
bash tools/run-act2-era-script.sh 1 "$script" "$out"
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
    -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/act_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/boss.c \
    build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/act_stress_host
SCD_ACT_ERA=1 SCD_ACT_TRACE="$out/player-target-trace.txt" build/act_stress_host act2 > "$out/host-results.log" 2>&1
shasum -a 256 -c "$out/input-hashes.txt" > "$out/hash-check.log"
python3 tools/check_past_ring_loss.py "$out"
