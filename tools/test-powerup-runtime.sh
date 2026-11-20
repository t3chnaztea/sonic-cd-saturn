#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/powerup_assets.py
python3 tools/prepare_probe.py
python3 tools/prepare_player.py
mkdir -p build/powerup-runtime
python3 tools/test_powerup_culling.py
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
 -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A \
 -fsanitize=address,undefined -fno-sanitize-recover=all \
 tools/powerup_runtime_test.c src/powerup_runtime.c src/powerup_visual.c src/player.c src/sonic_animation.c \
 src/stage.c src/objects.c src/act.c \
 build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/powerup-runtime/test
build/powerup-runtime/test | tee build/powerup-runtime/sanitized.log
python3 tools/powerup_runtime_report.py
