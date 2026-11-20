#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc \
  -fsanitize=address,undefined -fno-sanitize-recover=all \
  tools/arrival_camera_test.c -o build/arrival_camera_test
build/arrival_camera_test
