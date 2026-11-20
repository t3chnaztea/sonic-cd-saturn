#!/bin/bash
# Wacky Workbench BG cache pacing: periodic cache equivalence on all ten R6 packs
# (the sweep), then a synthetic camera route per program through
# tools/cc_cache_replay.c (identical maps every frame; BG tile writes per frame
# are the phase-5 cost proxy).  Routes run the full act width at 8 px/frame with
# a slow vertical sweep, across the whole camera Y range (background Y = camera Y / 4).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/ww/cache
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_cache_replay.c src/stage.c src/background.c src/background_r3.c -o build/ww/cache/replay
packs=(ww61A:48 ww61B:49 ww61C:50 ww61D:51 ww62A:52 ww62B:53 ww62C:54 ww62D:55 ww63C:58 ww63D:59)
limit=${WW_BG_WRITE_LIMIT:-640}
worst=0
for p in "${packs[@]}"; do
    pack=${p%%:*}; id=${p##*:}
    build/ww/cache/replay "assets/generated/$pack.bin" "$id" sweep >/dev/null
    case $pack in ww61*) w=8855;; ww62*) w=9111;; *) w=3479;; esac; h=1808
    route=build/ww/cache/$pack-route.log
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
    out=$(build/ww/cache/replay "assets/generated/$pack.bin" "$id" "$route")
    max=$(echo "$out" | sed -E 's/.*\(max [0-9]+@[0-9]+ -> ([0-9]+)@.*/\1/')
    echo "$pack: $out" | cut -c1-220
    [ "$max" -gt "$worst" ] && worst=$max
done
if [ "$worst" -gt "$limit" ]; then echo "FAIL: WW cache pacing: BG writes $worst in one frame > $limit"; exit 1; fi
echo "PASS: WW cache pacing: ${#packs[@]} packs match the plain cache on every sweep and route row; max BG writes/frame $worst <= $limit"
