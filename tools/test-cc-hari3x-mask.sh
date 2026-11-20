#!/bin/bash
# CC1 hari3x spikes take Sonic's CC contact once, in cc_scan, at every pool
# index (tools/cc_hari3x_mask_test.c).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/hari3x-mask
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_hari3x_mask_test.c \
    src/title_card.c src/world.c src/act.c src/player.c src/camera_v.c src/sonic_animation.c src/stage.c \
    src/boss.c src/boss_r3.c \
    build/probe-source/{boss_1,boss_3,playsp3,interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/hari3x-mask/test >build/cc1/hari3x-mask/build.log 2>&1 || { tail -n 20 build/cc1/hari3x-mask/build.log; exit 1; }
build/cc1/hari3x-mask/test | tee build/cc1/hari3x-mask/result.txt
