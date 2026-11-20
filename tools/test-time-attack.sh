#!/bin/bash
# Host test for the Time Attack records (src/time_attack.c).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/time-attack-qa
clang -std=gnu11 -Wall -Wextra -Werror -g -O1 -Isrc -fsanitize=address,undefined -fno-sanitize-recover=all tools/time_attack_test.c src/time_attack.c -o build/time-attack-qa/time_attack_test
build/time-attack-qa/time_attack_test
