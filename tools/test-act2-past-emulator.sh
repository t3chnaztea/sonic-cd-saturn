#!/bin/bash
# Complete Past route, selected via controller, plus sanitized host replay and source pixels.
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash tools/test-act2-era-emulator.sh 1
