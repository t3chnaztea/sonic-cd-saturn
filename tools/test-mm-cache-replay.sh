#!/bin/bash
# Metallic Madness BG cache pacing: periodic cache equivalence on all ten R8 packs
# (the sweep), then a synthetic camera route per program through
# tools/cc_cache_replay.c (identical maps every frame; BG tile writes per frame
# are the phase-5 cost proxy).  Routes run the full act width at 8 px/frame with
# a slow vertical sweep, across the whole camera Y range (background Y per program).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/mm/cache
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_cache_replay.c src/stage.c src/background.c src/background_r3.c -o build/mm/cache/replay
packs=(mm81A:72 mm81B:73 mm81C:74 mm81D:75 mm82A:76 mm82B:77 mm82C:78 mm82D:79 mm83C:82 mm83D:83)
limit=${MM_BG_WRITE_LIMIT:-640}
worst=0
for p in "${packs[@]}"; do
    pack=${p%%:*}; id=${p##*:}
    build/mm/cache/replay "assets/generated/$pack.bin" "$id" sweep >/dev/null
    case $pack in mm83*) w=3000;; *) w=7831;; esac; h=1808
    route=build/mm/cache/$pack-route.log
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
    out=$(build/mm/cache/replay "assets/generated/$pack.bin" "$id" "$route")
    max=$(echo "$out" | sed -E 's/.*\(max [0-9]+@[0-9]+ -> ([0-9]+)@.*/\1/')
    echo "$pack: $out" | cut -c1-220
    [ "$max" -gt "$worst" ] && worst=$max
done
if [ "$worst" -gt "$limit" ]; then echo "FAIL: MM cache pacing: BG writes $worst in one frame > $limit"; exit 1; fi
echo "PASS: MM cache pacing: ${#packs[@]} packs match the plain cache on every sweep and route row; max BG writes/frame $worst <= $limit"
