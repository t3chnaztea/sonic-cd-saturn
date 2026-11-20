#!/bin/bash
# Quartz Quadrant BG cache pacing: periodic cache equivalence on all ten R5
# packs (the sweep), then a synthetic camera route per program through
# tools/cc_cache_replay.c (identical maps every frame; BG tile writes per frame
# are the phase-5 cost proxy).  Routes run the full act width at 8 px/frame
# with a slow vertical sweep.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/qq/cache
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated -DSCD_ZONE_R5 \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_cache_replay.c src/stage.c src/background.c src/background_r3.c -o build/qq/cache/replay
packs=(qq51A:36 qq51B:37 qq51C:38 qq51D:39 qq52A:40 qq52B:41 qq52C:42 qq52D:43 qq53C:46 qq53D:47)
limit=${QQ_BG_WRITE_LIMIT:-640}
worst=0
for p in "${packs[@]}"; do
    pack=${p%%:*}; id=${p##*:}
    build/qq/cache/replay "assets/generated/$pack.bin" "$id" sweep >/dev/null
    case $pack in qq51*) w=10903 h=784;; qq53*) w=3735 h=800;; *) w=10903 h=800;; esac
    route=build/qq/cache/$pack-route.log
    python3 - "$w" "$h" > "$route" <<'PY'
import sys
w, h = int(sys.argv[1]), int(sys.argv[2])
f = x = 0
y = h // 2
while x < w:
    y = max(0, min(h, y + (6 if (f // 180) % 2 else -6) * (f % 3 != 0)))
    print('Frame profile:', ' '.join(map(str, [0, f] + [0] * 19 + [x, y])))
    f += 1
    x += 8
PY
    out=$(build/qq/cache/replay "assets/generated/$pack.bin" "$id" "$route")
    max=$(echo "$out" | sed -E 's/.*\(max [0-9]+@[0-9]+ -> ([0-9]+)@.*/\1/')
    echo "$pack: $out" | cut -c1-220
    [ "$max" -gt "$worst" ] && worst=$max
done
# enkeino layout switches (SCR51A-52D mapset2) through the paced redraw:
# out along each act and back, crossing both enkeichg bands twice.  The
# switch frame is one full redraw (the original's mapwrtb); every other frame
# stays within the budget and the cached rows always equal a fresh draw.
clang -std=c11 -O1 -g -Wall -Wextra -Werror -Isrc -Iassets/generated \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/qq_enkei_replay.c src/stage.c src/background_r5.c -o build/qq/cache/enkei
switches=0
for p in "${packs[@]}"; do
    pack=${p%%:*}; id=$(( ${p##*:} - 36 ))
    case $pack in qq51*) w=10903 h=784;; qq53*) w=3735 h=800;; *) w=10903 h=800;; esac
    out=$(build/qq/cache/enkei "assets/generated/$pack.bin" "$id" "$w" "$h" "$limit" 1)
    echo "$pack: $out"
    max=$(echo "$out" | sed -E 's/.*max BG writes ([0-9]+)@.*/\1/')
    [ "$max" -gt "$worst" ] && worst=$max
    n=$(echo "$out" | sed -E 's/.*frames, ([0-9]+) layout switches.*/\1/'); switches=$((switches+n))
    sw=$(echo "$out" | sed -E 's/.*switch frames up to ([0-9]+),.*/\1/'); [ "$sw" -gt "${switch_worst:-0}" ] && switch_worst=$sw
done
if [ "$worst" -gt "$limit" ]; then echo "FAIL: QQ cache pacing: BG writes $worst in one frame > $limit"; exit 1; fi
echo "PASS: QQ cache pacing: ${#packs[@]} packs match the plain cache on every sweep and route row; $switches enkeino layout switches redraw in their own frame (up to ${switch_worst:-0} writes, as mapwrtb); max BG writes/frame $worst <= $limit"
