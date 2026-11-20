#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/foreground_cache_test.c src/stage.c -o build/foreground_cache_test
build/foreground_cache_test assets/generated/ppz{0,1,2,3,12A,12B,12C,12D,13C,13D}.bin \
    assets/generated/cc3{1A,1B,1C,1D,2A,2B,2C,2D,3C,3D}.bin
