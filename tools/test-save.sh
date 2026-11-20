#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/save-qa
clang -std=gnu11 -Wall -Wextra -Werror -g -O1 -Isrc -fsanitize=address,undefined -fno-sanitize-recover=all tools/save_test.c src/save.c -o build/save-qa/save_test
build/save-qa/save_test
