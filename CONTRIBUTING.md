# Contributing

Thanks for helping with Sonic CD for Sega Saturn. This page covers what the
project accepts, the rules every change follows, and the checks a pull request
must pass.

Everyone who takes part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## What helps most

1. **Console test reports.** The project needs results from real Saturn
   hardware more than anything else. Use the
   [hardware report form](https://github.com/t3chnaztea/sonic-cd-saturn/issues/new?template=hardware_report.yml).
   Include the BIN SHA-256, Saturn model, region, video mode and SAROO
   firmware.
2. **Bug reports** with a zone, act, era and steps to reproduce. Use the
   [bug report form](https://github.com/t3chnaztea/sonic-cd-saturn/issues/new?template=bug_report.yml).
3. **Fixes for the known issues** listed in the [README](README.md#known-issues-in-v0078).
4. **Build reports** from hosts other than Apple Silicon macOS.

Open an issue before starting a large change, so the work does not overlap.

## Never commit game data

This rule has no exceptions.

- Do not commit, attach or link SEGA code, art, audio, level data, disc
  images, BIOS files, built images (`.bin`, `.cue`, `.iso`), save states or
  files extracted from a disc.
- Do not commit files from `.deps/` (including scddisasm), `assets/`,
  `build/`, `dist/`, `cd/` or `audio-tracks/`. `.gitignore` covers them. Do
  not force-add past it.
- Screenshots and captures of the game contain SEGA artwork. Do not commit
  them. Images in `docs/media/` are for original README art only.
- Issues, discussions or pull requests that contain or link such files will be
  deleted.

CI rejects tracked disc images, ROMs, audio, archives, compiled output and
binary files. It cannot catch everything. You are responsible for what you
push.

## Development rules

**Original first.** The goal is the 1993 Sega CD game, running natively. When
the port behaves differently from the original, check the
[scddisasm](https://github.com/sonicretro/scddisasm) reference (fetched into
`.deps/scddisasm/` by `tools/bootstrap.sh`) before you invent a fix. Match the
original unless [PORT-ROADMAP.md](PORT-ROADMAP.md) says otherwise. Cite the
source file and line in the commit message or pull request, for example
`Sonic/Main.asm:135-155` or `COLI3.C:556`. The
[C decompilation](https://github.com/nfroggy/soniccddecompilation) is a code
reference. Where it and scddisasm differ, scddisasm wins.

**Player physics and collision.** A change to player physics, collision or
camera code must keep the player traces green:

```sh
bash tools/test-player.sh
```

Regenerate the reference traces with the script only. Never edit a trace by
hand.

**One bounded change per pull request,** with a test that can fail. Follow the
execution loop in [QA-PLAN.md](QA-PLAN.md). Never weaken an assertion to make
new output pass. A changed baseline needs source evidence and a written reason.

**Emulator results do not prove console behavior.** Beetle Saturn passes are
required, but only a real Saturn closes a hardware gate. Do not claim a
hardware result you did not see on a console.

**Builds for console testing** get a new `IP_VERSION` and `IP_RELEASE_DATE` in
the [Makefile](Makefile) and a `RELEASE-NOTES-V<version>.md`. The maintainer
does this for releases. Do not bump the version in an ordinary pull request.

## Checks before a pull request

You need your own discs and BIOS for the full checks. See
[Build](README.md#build).

```sh
python3 tools/qa-loop.py fast 2>&1 | tail -n 30   # required
bash tools/test-player.sh                          # required for player, collision or camera changes
python3 tools/qa-loop.py full 2>&1 | tail -n 30   # for changes to shared systems; about 3 hours
```

Paste the `PASS:` or `FAIL:` line from `qa-loop.py` into the pull request
exactly as printed, with the BIN SHA-256 it ran on. A pass from an older
build does not count for new code.

A documentation-only change needs no game QA. Run `git diff --check` and
reread the text.

### What CI checks

GitHub CI has no game data, BIOS or Saturn toolchain. It cannot build the disc
or run the emulator gates. It checks:

- No disc images, ROMs, game data, audio, archives, compiled output or binary
  files are tracked, and no file is over 1 MiB.
- No whitespace errors in changed lines (`git diff --check`).
- Every tracked Python file compiles (`py_compile`, Python 3.12).
- Every tracked shell script parses (`bash -n`).
- The host unit tests that need no disc data pass.

A green CI run does not replace the local QA above.

## AI-assisted contributions

AI-assisted contributions are welcome. Most of this port was written with an
AI coding agent under human direction (see
[How it was built](README.md#how-it-was-built)). The same rules apply:

- Disclose it in the pull request: which tool, and which parts it wrote.
- The change must pass the same gates as any other change. Paste the real
  `PASS:` line from a run you did yourself.
- You must understand the change and be able to explain it. Check claims
  about the original game against scddisasm, not against the model's memory.
- Do not paste game data, disassembly listings or extracted assets into a
  prompt and commit the output.

## Style

- C: follow the code around your change. Name the original routine or table
  in a comment when you port one (for example `GAME5.C mapwrtb`).
- Python: standard library only where possible. The tools target Python 3.12+.
- Commits: one logical change per commit. Write the subject in the imperative
  mood ("Fix ring sparkle timing", not "Fixed").
- Docs: short sentences and plain words. Numbers over adjectives.

## License

By contributing, you agree that your contribution is released under the
[MIT License](LICENSE). This covers your code only. It grants no rights to
Sonic CD or any SEGA content.
