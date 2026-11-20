#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
    -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/object_stream_test.c src/act.c src/player.c src/sonic_animation.c src/stage.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/object_stream_test
build/object_stream_test
