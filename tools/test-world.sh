#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/world_test.c src/world_qa.c src/world.c src/background.c src/background_r3.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c src/objects.c \
 build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/world_test
build/world_test
