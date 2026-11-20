#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/ppz-journey
sources=(tools/ppz_journey.c src/player_replay.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c src/world.c src/act.c src/title_card.c src/boss.c
 build/probe-source/{boss_1,interaction,player,dircol,fcol,etc,equ,movement}.c)
flags=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A)
clang "${flags[@]}" -dynamiclib "${sources[@]}" -o build/ppz-journey/native.dylib
clang "${flags[@]}" -DJOURNEY_MAIN -fsanitize=address,undefined -fno-sanitize-recover=all "${sources[@]}" -o build/ppz-journey/sanitized
clang "${flags[@]}" -MM "${sources[@]}" > build/ppz-journey/dependencies.mk
python3 tools/ppz_journey_manifest.py
