#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare_cd_block.py
clang -std=c11 -O1 -g -Wall -Wextra -Werror -DSCD_CD_HOST_TEST -Isrc -Itools -Ibuild/cd-block \
    -fsanitize=address,undefined -fno-sanitize-recover=all tools/cd_status_test.c -o build/cd_status_test
build/cd_status_test
