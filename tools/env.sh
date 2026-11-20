#!/bin/bash
SATURN_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export YAUL_INSTALL_ROOT="$SATURN_PROJECT_ROOT/.toolchain"
export YAUL_ARCH_SH_PREFIX=sh-elf
export YAUL_PROG_SH_PREFIX=sh-elf
export YAUL_ARCH_M68K_PREFIX=m68k-elf
export YAUL_BUILD_ROOT="$SATURN_PROJECT_ROOT/.deps/libyaul"
export YAUL_BUILD=build
export YAUL_OPTION_MALLOC_IMPL=tlsf
export SILENT=1 NOCOLOR=1
export DEBUG_RELEASE=1
# make-iso runs the real xorrisofs through a wrapper that fixes every ISO date.
_scd_xorrisofs="${SCD_XORRISOFS:-${MAKE_ISO_XORRISOFS:-$(command -v xorrisofs)}}"
case "$_scd_xorrisofs" in */xorrisofs-reproducible.sh) _scd_xorrisofs="$(command -v xorrisofs)";; esac
export SCD_XORRISOFS="$_scd_xorrisofs"
export MAKE_ISO_XORRISOFS="$SATURN_PROJECT_ROOT/tools/xorrisofs-reproducible.sh"
export PATH="$YAUL_INSTALL_ROOT/bin:$PATH"
