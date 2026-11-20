#!/bin/bash
# Stardust Speedway BG cache pacing: periodic cache equivalence on all ten R7 packs
# (the sweep), then a synthetic camera route per program through
# tools/cc_cache_replay.c (identical maps every frame; BG tile writes per frame
# are the phase-5 cost proxy).  Routes run the full act width at 8 px/frame with
# a slow vertical sweep, across the whole camera Y range (background Y per program).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/ss/cache
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_cache_replay.c src/stage.c src/background.c src/background_r3.c -o build/ss/cache/replay
packs=(ss71A:60 ss71B:61 ss71C:62 ss71D:63 ss72A:64 ss72B:65 ss72C:66 ss72D:67 ss73C:70 ss73D:71)
limit=${SS_BG_WRITE_LIMIT:-640}
worst=0
for p in "${packs[@]}"; do
    pack=${p%%:*}; id=${p##*:}
    build/ss/cache/replay "assets/generated/$pack.bin" "$id" sweep >/dev/null
    case $pack in ss73*) w=16023;; *) w=11927;; esac; h=1296
    route=build/ss/cache/$pack-route.log
    python3 - "$w" "$h" > "$route" <<'EOF'
import sys
w, h = int(sys.argv[1]), int(sys.argv[2])
f = x = 0
y = h // 2
while x < w:
    # vertical sweep, 0-6 px/frame, so the background scrolls in both directions
    y = max(0, min(h, y + (6 if (f // 180) % 2 else -6) * (f % 3 != 0)))
    print('Frame profile:', ' '.join(map(str, [0, f] + [0] * 19 + [x, y])))
    f += 1
    x += 8
EOF
    out=$(build/ss/cache/replay "assets/generated/$pack.bin" "$id" "$route")
    max=$(echo "$out" | sed -E 's/.*\(max [0-9]+@[0-9]+ -> ([0-9]+)@.*/\1/')
    echo "$pack: $out" | cut -c1-220
    [ "$max" -gt "$worst" ] && worst=$max
done
if [ "$worst" -gt "$limit" ]; then echo "FAIL: SS cache pacing: BG writes $worst in one frame > $limit"; exit 1; fi
echo "PASS: SS cache pacing: ${#packs[@]} packs match the plain cache on every sweep and route row; max BG writes/frame $worst <= $limit"
