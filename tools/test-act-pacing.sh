#!/bin/bash
# Host-only negative controls; does not run an emulator or schedule a job.
set -euo pipefail
cd "$(dirname "$0")/.."
clang -std=gnu11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
    -fno-sanitize-recover=all -I.deps/beetle-saturn/libretro-common/include \
    tools/act_pad_replay_test.c -o build/act_pad_replay_test
build/act_pad_replay_test
python3 tools/test_act_pacing.py
python3 tools/test_sequence_replay.py
