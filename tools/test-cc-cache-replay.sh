#!/bin/bash
# Periodic BG cache equivalence on every stage pack, plus the recorded CC2
# Present route replay when its frame-profile log is present.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_cache_replay.c src/stage.c src/background.c src/background_r3.c -o build/cc_cache_replay
packs=(ppz0:0 ppz1:1 ppz2:2 ppz3:3 ppz12A:4 ppz12B:5 ppz12C:6 ppz12D:7 ppz13C:10 ppz13D:11
       cc31A:12 cc31B:13 cc31C:14 cc31D:15 cc32A:16 cc32B:17 cc32C:18 cc32D:19 cc33C:22 cc33D:23)
for p in "${packs[@]}"; do build/cc_cache_replay "assets/generated/${p%%:*}.bin" "${p##*:}" sweep >/dev/null; done
echo "Periodic BG cache: ${#packs[@]} packs match the plain cache on every sweep row"
route=build/cc2/controller/A/results.log
# Only a run recorded with SCD_FRAME_PROFILE carries the "Frame profile:" lines
# cc_cache_replay parses; a route log without them is skipped, not replayed.
if [ -f "$route" ] && grep -q 'Frame profile:' "$route"; then build/cc_cache_replay assets/generated/cc32A.bin 16 "$route"
elif [ -f "$route" ]; then echo "SKIP: CC2 Present route replay: $route has no Frame profile: lines"; fi
