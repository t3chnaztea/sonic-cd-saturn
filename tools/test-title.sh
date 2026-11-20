#!/bin/bash
# Host title screen check: runs src/title.c under ASan/UBSan with the retail pad scripts
# (tools/title_retail.py) and compares every V-INT with the retail records (tools/check_title.py host).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/title-host
python3 tools/title_assets.py > build/title-host/assets.log
for route in newgame timeout; do
    [ -f "build/title-retail/$route.jsonl" ] && [ -f "build/title-retail/$route.pad" ] || python3 tools/title_retail.py "$route" > "build/title-host/retail-$route.log"
done
python3 tools/title_retail.py stafftimes > build/title-host/retail-stafftimes.log
clang -std=gnu11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/title_test.c src/title.c -o build/title-host/title_test
for route in newgame timeout stafftimes; do
    build/title-host/title_test assets/generated/title.bin "build/title-retail/$route.pad" > "build/title-host/$route.jsonl"
done
clang -std=gnu11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/test_staff_times_entry.c src/title.c -o build/title-host/staff_times_entry
build/title-host/staff_times_entry assets/generated/title.bin
python3 tools/check_title.py host
