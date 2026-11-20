#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc/movie
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_movie_lifecycle_test.c \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc/movie/test > build/cc/movie/build.log 2>&1
build/cc/movie/test | tee build/cc/movie/result.txt
