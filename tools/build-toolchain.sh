#!/bin/bash
# Build only inside this project. Sources are fetched separately.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPS="$PROJECT_ROOT/.deps"
PREFIX="$PROJECT_ROOT/.toolchain"
JOBS="${JOBS:-8}"
SATURN_BREW_PREFIX="${SATURN_BREW_PREFIX:-$(brew --prefix)}"
mkdir -p "$PREFIX" "$DEPS/build-binutils" "$DEPS/build-gcc" "$PROJECT_ROOT/build"
export PATH="$PREFIX/bin:$PATH"
export MACOSX_DEPLOYMENT_TARGET=14.0
export CC=clang CXX=clang++
# Newer Xcode SDKs weak-link pipe2 even when the running macOS lacks it.
# Autoconf's link-only probe then selects a null function pointer in libiberty.
# Use its existing pipe + fcntl fallback on Darwin, including older hosts.
if [ "$(uname -s)" = Darwin ]; then export ac_cv_func_pipe2=no; fi

if [ ! -x "$PREFIX/bin/sh-elf-as" ]; then
    echo 'Building GNU binutils 2.44 (log: build/binutils.log)'
    (
        cd "$DEPS/build-binutils"
        ../binutils-2.44/configure --target=sh-elf --prefix="$PREFIX" \
            --disable-nls --disable-werror --disable-gdb --disable-sim \
            --disable-gprofng --with-system-zlib
        make -j"$JOBS" MAKEINFO=true
        make install MAKEINFO=true
    ) > "$PROJECT_ROOT/build/binutils.log" 2>&1
fi

if [ ! -f "$PREFIX/.gcc-complete" ]; then
    echo 'Building GCC 13.4.0 for big-endian SH-2 (log: build/gcc.log)'
    (
        cd "$DEPS/build-gcc"
        ../gcc-13.4.0/configure --target=sh-elf --prefix="$PREFIX" \
            --with-cpu=m2 --with-endian=big --enable-languages=c,c++ \
            --without-headers --disable-multilib --disable-nls \
            --disable-shared --disable-threads --disable-libssp \
            --disable-libquadmath --disable-libatomic --disable-libgomp \
            --disable-libstdcxx --disable-bootstrap --with-system-zlib \
            --with-gmp="$SATURN_BREW_PREFIX/opt/gmp" \
            --with-mpfr="$SATURN_BREW_PREFIX/opt/mpfr" \
            --with-mpc="$SATURN_BREW_PREFIX/opt/libmpc" \
            --with-isl="$SATURN_BREW_PREFIX/opt/isl"
        make -j"$JOBS" all-gcc MAKEINFO=true
        make install-gcc MAKEINFO=true
        # GCC's SH-specific unwind object omits this dependency. Generate the
        # header first to avoid a parallel libgcc build race.
        make configure-target-libgcc MAKEINFO=true
        make -C sh-elf/libgcc libgcc_tm.h MAKEINFO=true
        make -j"$JOBS" all-target-libgcc MAKEINFO=true
        make install-target-libgcc MAKEINFO=true
    ) > "$PROJECT_ROOT/build/gcc.log" 2>&1
    touch "$PREFIX/.gcc-complete"
fi
"$PREFIX/bin/sh-elf-gcc" --version | head -1
