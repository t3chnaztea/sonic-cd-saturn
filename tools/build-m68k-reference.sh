#!/bin/bash
# Offline original-code QA only; these tools/code never enter the Saturn game.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .deps/build-binutils-m68k build
# Match the cross-compiler's Darwin weak-link workaround (see build-toolchain.sh).
if [ "$(uname -s)" = Darwin ]; then export ac_cv_func_pipe2=no; fi
if [ ! -x .deps/build-binutils-m68k/gas/as-new ] || [ ! -x .deps/build-binutils-m68k/binutils/objcopy ] || [ ! -x .deps/build-binutils-m68k/ld/ld-new ]; then
    (
        cd .deps/build-binutils-m68k
        ../binutils-2.44/configure --target=m68k-elf --disable-nls --disable-werror \
          --disable-gdb --disable-sim --disable-gprofng --with-system-zlib
        gmake -j8 all-gas all-binutils all-ld MAKEINFO=true
    ) > build/m68k-reference-build.log 2>&1
fi
.deps/build-binutils-m68k/gas/as-new --version | head -1
