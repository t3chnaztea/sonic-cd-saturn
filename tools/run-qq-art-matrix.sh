#!/bin/bash
# Full Quartz Quadrant zone-art matrix (R51A-D, R52A-D, R53C/D) on the current
# dist/ bin with SCD_CLUT_CYCLE=1 (normal sprite pixels must follow the COL5
# palette scripts and the enkeichg zone5color swap;
# tools/check_zone_object_target.py r5_cycles). Emulator only, no build.
# Each chunk takes the build lock on its own (same pattern as
# tools/run-tt-art-matrix.sh). The bin hash is recorded per chunk; a changed
# bin between chunks is a failure.
# usage: tools/run-qq-art-matrix.sh [LOCK_WRAPPER]   (default: run unlocked)
set -uo pipefail
cd "$(dirname "$0")/.."
LOCK=${1:-}
mkdir -p build/zone-art-qa
out=build/zone-art-qa/qq-matrix.log
: >"$out"
hash0=$(shasum -a 256 dist/sonic-cd-saturn-prototype.bin | cut -c1-16)
echo "bin $hash0" | tee -a "$out"
status=0
# Chunks balanced by record count (R52A 82, R51A 80, R52B 77, R51B 67,
# R51C 47, R51D 45, R52C 45, R52D 43, R53C/D 16 each; 518 in all).
for chunk in "R52A R51A R53C" "R52B R51B R53D" "R51C R51D R52C R52D"; do
    start=$(date +%s)
    ${LOCK:+$LOCK} env SCD_CLUT_CYCLE=1 bash -o pipefail -c "
        h=\$(shasum -a 256 dist/sonic-cd-saturn-prototype.bin | cut -c1-16)
        [ \"\$h\" = \"$hash0\" ] || { echo \"FAIL: bin changed to \$h\"; exit 3; }
        python3 tools/test_zone_art_emulator.py $chunk >build/zone-art-qa/qq-matrix-chunk.log 2>&1; rc=\$?
        grep -E 'match|PASS|passed|Error|FAIL' build/zone-art-qa/qq-matrix-chunk.log; exit \$rc" >>"$out" 2>&1
    rc=$?
    echo "chunk [$chunk] exit $rc in $(( $(date +%s)-start ))s" | tee -a "$out"
    [ $rc -eq 0 ] || status=1
done
grep -E "match$|FAIL|Error" "$out"
[ $status -eq 0 ] && echo "PASS: QQ zone-art matrix, 10 programs, SCD_CLUT_CYCLE=1, bin $hash0" || echo "FAIL: QQ zone-art matrix (see $out)"
exit $status
