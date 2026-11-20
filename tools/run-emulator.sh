#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v mednafen >/dev/null || { echo 'Install Mednafen with brew install mednafen' >&2; exit 1; }
BIOS_PATH="${SATURN_BIOS_PATH:-$PWD/assets/private/saturn-bios.bin}"
test -s "$BIOS_PATH" || { echo 'Set SATURN_BIOS_PATH to your US/EU Saturn BIOS.' >&2; exit 1; }
mkdir -p build/emulator
export MEDNAFEN_HOME="$PWD/build/emulator"
exec mednafen -ss.bios_na_eu "$BIOS_PATH" -ss.region_autodetect 0 \
    -ss.region_default na -ss.cart none -sound 0 -video.driver softfb \
    -ss.xscale 3 -ss.yscale 3 "$PWD/dist/sonic-cd-saturn-prototype.cue"
