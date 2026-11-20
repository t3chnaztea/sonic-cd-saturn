#!/bin/bash
# Boot the built program from a data-only disc without WARP.BIN. The game must
# stop on the CD STAGE DATA ERROR screen with the failed pack in its mailbox
# (src/stage_packs.h: PACK_WARP is index 8, reported as 9).
set -euo pipefail
cd "$(dirname "$0")/.."
source tools/env.sh
out=build/stage-load-failure
rm -rf "$out";mkdir -p "$out/cd"
cp cd/* "$out/cd/"
rm "$out/cd/WARP.BIN"
.toolchain/bin/make-iso "$out/cd" build/saturn/IP.BIN "$PWD/$out" missing-warp > "$out/make-iso.log" 2>&1
test -s "$out/missing-warp.iso"
printf 'FILE "missing-warp.iso" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n' > "$out/missing-warp.cue"
clang -std=gnu11 -Wall -Wextra -Werror -I.deps/beetle-saturn/libretro-common/include tools/emulator_test.c -o build/stage_load_failure_test
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_STAGE_PACKS=$(symbol _scd_stage_pack_mailbox)
build/stage_load_failure_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/$out/missing-warp.cue" "$PWD/assets/private" "$PWD/$out" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" packfail > "$out/results.log" 2> "$out/core.log"
python3 - <<'EOF'
import re
from pathlib import Path
out=Path('build/stage-load-failure')
m=re.search(r'Stage packs: magic=5350414b vblanks=\d+ bytes=\d+ error=(\d+)',(out/'results.log').read_text())
assert m and int(m[1])==9,('expected WARP.BIN failure (9)',m and m[1])
raw=(out/'stage-load-failure.ppm').read_bytes().split(b'255\n',1)[1]
pixels=[raw[i:i+3] for i in range(0,len(raw),3)]
background=max(set(pixels),key=pixels.count)
text=sum(p!=background for p in pixels)
assert text>200,('error screen has no text',text)
print(f'Stage load failure: WARP.BIN missing stops on the error screen ({text} text pixels)')
EOF
