#!/bin/bash
# Special Stage 8 win (swin-ss8) on the Saturn disc against retail.
# Usage: tools/test-special-ss8-emulator.sh <out>. Exit 0 on pass; writes <out>/report.json.
# The run starts from the sound test code 07/07/07 (Sound Test.asm CheckEasterEgg),
# which runs IPX.asm SoundTest_SpecStg8 (temporary|secret, stage 8); the gate reads
# back the mode, the stage and the loaded SSM pack from
# RAM after the start (tools/special_mode_gate.py SP8-win).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 tools/special_mode_gate.py SP8-win --output "${1:?usage: test-special-ss8-emulator.sh <out>}"
