#!/bin/bash
# Full Tidal Tempest zone-art matrix (R41A-D, R42A-D, R43C/D) on the current
# dist/ bin with SCD_CLUT_CYCLE=1 (normal sprite pixels must follow the COL4
# palette cycles; tools/check_zone_object_target.py). Emulator only, no build.
# Each chunk takes the build lock on its own, so no lock hold covers more than
# about 480 pack records (R41A alone is 409 records, about 13k emulated frames).
# The bin hash is recorded per chunk; a changed bin between chunks is a failure.
# usage: tools/run-tt-art-matrix.sh [LOCK_WRAPPER]   (default: run unlocked)
set -uo pipefail
cd "$(dirname "$0")/.."
LOCK=${1:-}
out=build/zone-art-qa/tt-matrix.log
: >"$out"
hash0=$(shasum -a 256 dist/sonic-cd-saturn-prototype.bin | cut -c1-16)
echo "bin $hash0" | tee -a "$out"
status=0
# Chunks balanced by record count (R41A 409, R42B 363, R41B 304, R42A 255,
# R41D 146, R42D 132, R41C 119, R42C 117, R43C/D 109).
for chunk in "R41A" "R42B" "R41B R43C" "R42A R41D" "R42D R41C R42C R43D"; do
    start=$(date +%s)
    ${LOCK:+$LOCK} env SCD_CLUT_CYCLE=1 bash -o pipefail -c "
        h=\$(shasum -a 256 dist/sonic-cd-saturn-prototype.bin | cut -c1-16)
        [ \"\$h\" = \"$hash0\" ] || { echo \"FAIL: bin changed to \$h\"; exit 3; }
        python3 tools/test_zone_art_emulator.py $chunk >build/zone-art-qa/tt-matrix-chunk.log 2>&1; rc=\$?
        grep -E 'match|PASS|passed|Error|FAIL' build/zone-art-qa/tt-matrix-chunk.log; exit \$rc" >>"$out" 2>&1
    rc=$?
    echo "chunk [$chunk] exit $rc in $(( $(date +%s)-start ))s" | tee -a "$out"
    [ $rc -eq 0 ] || status=1
done
grep -E "match$|FAIL|Error" "$out"
[ $status -eq 0 ] && echo "PASS: TT zone-art matrix, 10 programs, SCD_CLUT_CYCLE=1, bin $hash0" || echo "FAIL: TT zone-art matrix (see $out)"
exit $status
