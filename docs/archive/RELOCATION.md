# Standalone relocation preparation — 2026-09-20

Prepared in place. **This session did not move the folder or rebuild anything.**
Destination: `~/code/sonic-cd-saturn`, under the TECH NASTY launcher. Commands
below run from the repository root in Bash. The mover owns launcher registration
and any parent-repository edits.

## Processes and card

- No project emulator, compiler/build, watcher, background shell or QA loop
  remained running when process names and working directories were inspected.
  None needed killing. Unrelated sessions/services were left alone.
- `crontab -l`: no user crontab. No Sonic CD launch-agent entry was found.
  The QA scheduling proposal was never installed. No new scheduler starts.
- Prior card copy completed: all 950 V0.056 payloads plus manifest matched on
  readback; the card was safely ejected. Card folder is
  `SAROO/ISO/Sonic CD Saturn v0.056`. This is not a physical-console test.
- Old V0.044 was removed from the card and preserved, including its metadata,
  in `build/card-removed-v044-for-v056-20260920/`. Other games were untouched.

## Location audit and changes

First-party source/scripts contain no hardcoded former project root, no reads
of the parent project's `.env`, and no calls into its `scripts` directory.
Shell entry points derive the root from their filename. Python tools derive
it from `__file__`, or explicitly require execution from the repo root.
C includes `../src/...` stay within the repo. Configure calls
`../binutils-2.44/configure` and `../gcc-13.4.0/configure` run from sibling
build directories under `.deps`. No escaping first-party relative path was found.

- `tools/env.sh`: discover `xorrisofs` through PATH; override with
  `MAKE_ISO_XORRISOFS`.
- `tools/build-toolchain.sh`: discover Homebrew with `brew --prefix`; override
  with `SATURN_BREW_PREFIX`. Apple Silicon/macOS remains the tested platform.
- Forty generated absolute documentation symlinks in the two binutils build
  trees are now relative and resolve to the same files inside this repo. All
  remaining 35 symlinks were already relative. No target file was changed.
- Historical Desktop-copy prose no longer requires a particular username/path.
- Standalone `.gitignore` excludes dependencies/toolchain/build/dist/CD/audio,
  all assets, images/ROMs/audio/captures, compiler outputs, archives, credentials
  and local agent/editor state. Dependencies are not submodules.

`python3 tools/audit-relocation.py` generates ignored, file-by-file inventories:

- `build/relocation-audit/path-bearing-files.txt`: every detected artifact name.
- `build/relocation-audit/inventory.json`: groups, links, repos and archives.
- `build/relocation-audit/inventory-before-symlink-fix.json`: pre-fix link targets.
- `build/relocation-audit/NEXT-SESSION-before-move.md`: preserved old handoff.

The byte scan found **3,842 files** with the old root spelling. **No CMakeCache.txt
files** were found. Matches are generated outputs/historical evidence, not live
first-party configuration. Counts below precede the newly generated audit files.

| Artifact family | Files | Treatment |
| --- | ---: | --- |
| `.deps/build-binutils/` | 420 | Reconfigure/rebuild: Makefiles, config.status/log, libtool, host objects |
| `.deps/build-binutils-m68k/` | 342 | Reconfigure/rebuild offline oracle assembler/linker |
| `.deps/build-gcc/` | 1,339 | Reconfigure/rebuild compiler/libgcc, host/target Makefiles, headers/config |
| `.deps/libyaul/build/` | 471 | Rebuild SDK objects, dependency files and tools |
| `.toolchain/` | 103 | Reinstall cross-tools and SDK at new prefix |
| `build/` | 1,161 | Rebuild active outputs; preserve historical tests, binaries, states and archives |
| `dist/` | 5 | Regenerate current ISO/BIN/reports; never relabel old hashes |
| `cd/A.BIN` | 1 | Regenerate staged executable |

Installed path-bearing config includes
`.toolchain/lib/gcc/sh-elf/13.4.0/install-tools/mkheaders.conf`,
`.toolchain/lib/gcc/sh-elf/13.4.0/plugin/include/configargs.h`,
`.toolchain/libexec/gcc/sh-elf/13.4.0/install-tools/mkheaders`,
`.toolchain/libexec/gcc/sh-elf/13.4.0/liblto_plugin.la`, and all listed `shelf.*` /
`shlelf.*` linker scripts under `.toolchain/sh-elf/lib/ldscripts/`.
The inventory also names executable debug/config strings, libraries, native host
binaries/dSYM files, `.d` files and report/log paths. Installed Yaul make fragments
and specs use runtime prefix variables but are reinstalled with the toolchain.

Beetle Saturn and Genesis Plus GX had no old-root byte matches; rebuild their
objects/cores anyway. The 48 compressed historical archives were **not unpacked**
by this scan and may contain further path-bearing members. Preserve them.

## Exact clean-rebuild commands AFTER the move

Do not run during relocation preparation. Open fresh Bash in the new repo root.
First review pending title-card integration and change the next build label to
V0.057 in Makefile and `src/main.c`; never publish different code as V0.056.
These commands archive replaceable outputs locally; they preserve historical
build subdirectories, private inputs and all ten dependency Git repositories.

```bash
set -euo pipefail
test -f Makefile
test -f sources.lock.json
test -d .git
test -s assets/private/sonic-cd.chd
test -s assets/private/bios_CD_U.bin
test -s assets/private/mpr-17933.bin
mkdir -p .relocation-backup
scd_rebuild_backup="$(mktemp -d "$PWD/.relocation-backup/pre-rebuild.XXXXXX")"
for scd_rebuild_path in \
  .toolchain .deps/build-binutils .deps/build-gcc .deps/build-binutils-m68k \
  .deps/libyaul/build build/saturn build/probe-source build/feedback \
  build/cd-block assets/generated dist cd \
  build/ppz-journey/native.dylib build/ppz-journey/sanitized \
  build/ppz-journey/dependencies.mk build/ppz-journey/build-manifest.json
do
  if test -e "$scd_rebuild_path"; then
    mkdir -p "$scd_rebuild_backup/$(dirname "$scd_rebuild_path")"
    mv "$scd_rebuild_path" "$scd_rebuild_backup/$scd_rebuild_path"
  fi
done
# Keep .deps/libyaul/libyaul/build and the other tracked SDK build/ folders:
# these contain SOURCE make fragments, not the generated SDK output above.
unset YAUL_INSTALL_ROOT YAUL_BUILD_ROOT
unset YAUL_ARCH_SH_PREFIX YAUL_PROG_SH_PREFIX YAUL_ARCH_M68K_PREFIX
brew install make xorriso gmp mpfr libmpc isl ffmpeg rom-tools
python3 tools/fetch_sources.py --emulator
bash tools/build-toolchain.sh
source tools/env.sh
gmake -C .deps/libyaul -j8 install-release
gmake -C .deps/libyaul install-tools STRIP=true
bash tools/build-m68k-reference.sh
gmake -C .deps/beetle-saturn platform=osx ARCH=arm64 clean
gmake -C .deps/beetle-saturn -j8 platform=osx ARCH=arm64
gmake -C .deps/genesis-plus-gx -f Makefile.libretro platform=osx clean
gmake -C .deps/genesis-plus-gx -f Makefile.libretro platform=osx -j8
bash tools/build.sh
bash tools/build-ppz-journey.sh
python3 tools/qa-loop.py fast
```

Derived from existing build entry points and clean targets; **not executed for
this handoff**. Host test runners recompile their native binaries. Historical
absolute-path reports, core hashes and archived debug info remain frozen. New
reports must bind new source/compiler/core/BIN hashes. Do not bulk-replace paths
inside hash-bound evidence or imply prior tests certify a rebuilt binary.
Full target QA and packaging follow completion of pending integration.

## Mover requirements and unresolved dependencies

- Move the **whole local folder**, not just Git files: hidden `.git`, `.deps`,
  private assets, ignored `build/` evidence, `.toolchain` and symlinks. Approximate
  sizes: build32 GB, deps2.9 GB, assets473 MB, dist318 MB, toolchain141 MB.
- Ten ignored nested repos: `beetle-saturn`, `examples`, `genesis-plus-gx`,
  `libyaul`, `mimas`, `ponesound`, `ponesound-srl`, `scddisasm`, `sonic-z-treme`,
  `soniccd`. Six build-required repos are pinned in `sources.lock.json`; four
  research checkouts will not be recreated by bootstrap. Preserve their `.git`.
- Remaining location dependencies are generated prefixes/caches and frozen
  historical reports/archives. Do not falsify their hashes or rewrite them;
  rebuild active outputs after the move. No active source dependency is unresolved.
- Private retail disc/BIOS files and Homebrew/Xcode are prerequisites, not
  downloadable contents of this Git repo. Initial commit excludes game assets,
  disc images, audio, generated output and secrets.
- Requested external plan: `~/.claude/plans/jiggly-prancing-stallman.md`.
  It is historical V0.029 planning, not a build input, and was not edited.
- Repo identity: `tech nasty` / `262050521+t3chnaztea@users.noreply.github.com`.
  No remote, parent-repo edit/commit, launcher registration or recurring job.
  No game development started during migration. Resume only on user direction.
