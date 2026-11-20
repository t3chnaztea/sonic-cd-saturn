#!/bin/bash
# macOS Apple Silicon. All cross tools install inside this project.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
brew install make xorriso gmp mpfr libmpc isl
python3 tools/fetch_sources.py "$@"
bash tools/build-toolchain.sh
source tools/env.sh
# Clean first: make does not track flags, and tools/patches can change them.
gmake -C .deps/libyaul clean-release > build/yaul.log 2>&1
gmake -C .deps/libyaul -j8 install-release >> build/yaul.log 2>&1
gmake -C .deps/libyaul install-tools STRIP=true > build/yaul-tools.log 2>&1
if [ "${1:-}" = '--emulator' ]; then
    gmake -C .deps/beetle-saturn -j8 platform=osx ARCH=arm64 > build/beetle-build.log 2>&1
fi
echo 'Toolchain ready. Run bash tools/build.sh'
