#!/bin/sh
# Extract IR for Palmtree Panic from the retail C, compile it, and run the
# gate against the real src/background.c.  Writes only under tools/scroll/.
#   sh tools/scroll/run_gate.sh            full run (extraction takes ~15 s)
#   SKIP_EXTRACT=1 sh tools/scroll/run_gate.sh   reuse tools/scroll/ir/R1/*.json
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
S=$ROOT/tools/scroll
B=$S/build
CC=${CC:-cc}
mkdir -p "$B"

if [ -z "${SKIP_EXTRACT:-}" ]; then
    python3 "$S/extract.py" --round 1 --write
fi
python3 "$S/irc.py" "$S"/ir/R1/*.json -o "$B/ir_tables.c"
python3 "$S/patch_port.py"

rename() {
    for f in reset step raster_x lines lines_pair y x static palette; do
        printf ' -Dscd_background_%s=%s_%s' "$f" "$1" "$f"
    done
}
CFLAGS="-std=c99 -O2 -Wall -Wno-unused-function -I$ROOT/src -I$ROOT/assets/generated"
# shellcheck disable=SC2046
$CC $CFLAGS $(rename lit) -c "$ROOT/src/background.c" -o "$B/port_literal.o"
$CC $CFLAGS -c "$ROOT/src/background_r3.c" -o "$B/background_r3.o"
# shellcheck disable=SC2046
$CC $CFLAGS $(rename wrap) -c "$S/port/background_wrap.c" -o "$B/port_wrap.o"
# shellcheck disable=SC2046
$CC $CFLAGS $(rename wrapfloor) -c "$S/port/background_wrap_floor.c" -o "$B/port_wrap_floor.o"
$CC -std=c99 -O2 -Wall -I"$S" "$S/gate.c" "$S/evaluate.c" "$B/ir_tables.c" \
    "$B/port_literal.o" "$B/port_wrap.o" "$B/port_wrap_floor.o" "$B/background_r3.o" -o "$B/gate"
"$B/gate"
