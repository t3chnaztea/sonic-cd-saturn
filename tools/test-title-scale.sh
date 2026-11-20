#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
clang -std=c11 -O1 -Wall -Wextra -Werror -Isrc -fsanitize=address,undefined -fno-sanitize-recover=all tools/title_scale_test.c -o build/title_scale_test
build/title_scale_test
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/title_prewarm_test.c src/title.c -o build/title_prewarm_test
build/title_prewarm_test assets/generated/title.bin
