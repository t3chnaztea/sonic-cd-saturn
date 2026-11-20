#!/bin/bash
# Build tools/ppz_journey_search.c against the tools/ppz_journey.c host model.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/ppz-journey
clang -std=gnu11 -O2 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A \
 tools/ppz_journey_search.c tools/ppz_journey.c src/player_replay.c src/player.c src/camera_v.c src/sonic_animation.c \
 src/stage.c src/objects.c src/world.c src/act.c src/title_card.c src/boss.c \
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/ppz-journey/search
