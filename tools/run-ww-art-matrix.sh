#!/bin/bash
# Full Wacky Workbench zone-art matrix (R61A-D, R62A-D, R63C/D) on the current
# dist/ bin. Emulator only, no build. A copy of tools/run-tt-art-matrix.sh
# without SCD_CLUT_CYCLE: tools/check_zone_object_target.py checks CLUT cycles
# for the COL4 (R4) scripts only.
# Each chunk takes the build lock on its own, so no lock hold covers more than
# about 200 pack records (tools/zone_object_assets.py ZART6x, 552 in all).
# The bin hash is recorded per chunk; a changed bin between chunks is a failure.
# usage: tools/run-ww-art-matrix.sh [LOCK_WRAPPER]   (default: run unlocked)
set -uo pipefail
cd "$(dirname "$0")/.."
LOCK=${1:-}
mkdir -p build/zone-art-qa
out=build/zone-art-qa/ww-matrix.log
: >"$out"
hash0=$(shasum -a 256 dist/sonic-cd-saturn-prototype.bin | cut -c1-16)
echo "bin $hash0" | tee -a "$out"
status=0
# Chunks balanced by record count (R61A 91, R61B 84, R61D 74, R62A 71,
# R61C 53, R62B 52, R62D 52, R62C 41, R63C 21, R63D 13).
for chunk in "R61A R62A R63D" "R61B R61D R63C" "R61C R62B R62C R62D"; do
    start=$(date +%s)
    ${LOCK:+$LOCK} bash -o pipefail -c "
        h=\$(shasum -a 256 dist/sonic-cd-saturn-prototype.bin | cut -c1-16)
        [ \"\$h\" = \"$hash0\" ] || { echo \"FAIL: bin changed to \$h\"; exit 3; }
        python3 tools/test_zone_art_emulator.py $chunk >build/zone-art-qa/ww-matrix-chunk.log 2>&1; rc=\$?
        grep -E 'match|PASS|passed|Error|FAIL' build/zone-art-qa/ww-matrix-chunk.log; exit \$rc" >>"$out" 2>&1
    rc=$?
    echo "chunk [$chunk] exit $rc in $(( $(date +%s)-start ))s" | tee -a "$out"
    [ $rc -eq 0 ] || status=1
done
grep -E "match$|FAIL|Error" "$out"
[ $status -eq 0 ] && echo "PASS: WW zone-art matrix, 10 programs, bin $hash0" || echo "FAIL: WW zone-art matrix (see $out)"
exit $status
