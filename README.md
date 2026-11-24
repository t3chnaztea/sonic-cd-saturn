<p align="center">
  <img src="docs/media/banner.svg" alt="Sonic CD for Sega Saturn: unofficial fan port, native SH-2 code" width="100%">
</p>

# Sonic CD for Sega Saturn

![CI](https://github.com/t3chnaztea/sonic-cd-saturn/actions/workflows/ci.yml/badge.svg)
![V0.082: software regression passed](https://img.shields.io/badge/V0.082-software%20regression%20passed-2ea44f)
![Saturn console test: V0.082 works](https://img.shields.io/badge/Saturn%20console%20test-V0.082%20works-2ea44f)

I'm a software developer by day. I make retro game projects on the side. You might know me from the Snatcher "uncensored" patcher. That was a quick side project; I've been working on this Sonic CD port for months.

As a kid, I loved Sonic CD on the Sega CD and hoped for a sequel on the Saturn. This is my way of making that childhood wish happen: Sonic CD running as a native Saturn game. The game logic is rewritten in C for the Saturn's SH-2 CPUs. There is no Sega CD emulation. The port follows the 1993 game and keeps its original art.

All seven zones are in, with all four eras, time travel, bosses, Metal Sonic, special stages and both endings. Classic is the default. The optional CD++ preset adds extra moves. It ran on my Saturn from a SAROO on 2026-11-21, CD++ included.

<p align="center">
  <a href="https://www.reddit.com/r/SegaSaturn/comments/1y2utdy/unofficial_native_sega_saturn_port_of_sonic_cd/"><img src="https://external-preview.redd.it/eDFqeHRheHA3NzNpMWeC7g9S3e_mt-DLPAZd6jtEFBHif26HZWpyiMlgQk6q.png?width=640&crop=smart&format=pjpg&auto=webp&s=f5f41a7411ed3c3faa75ef5a982944acf493ff2f" alt="Sonic CD running on a Sega Saturn with SAROO" width="640"></a><br>
  <a href="https://www.reddit.com/r/SegaSaturn/comments/1y2utdy/unofficial_native_sega_saturn_port_of_sonic_cd/">Watch the Saturn/SAROO video</a>
</p>

> [!IMPORTANT]
> This repository contains no SEGA art, audio, level data, program files, disc images or BIOS files, and no playable image will be distributed. The game logic is reimplemented in C; like the decompilation it follows, it keeps some of the original's numeric tables, and the test tools find code on your disc by short byte patterns. To build it you need your own U.S. and Japanese Sonic CD discs. Do not share the images you build. If you do not own the game, it is sold in [Sonic Origins](https://www.sega.com/games/sonic-origins).

<p align="center">
  <img src="https://github.com/user-attachments/assets/2ec70176-3266-41e0-8916-79be67c8c80f" alt="Palmtree Panic Act 1: Sonic passes a time post and warps into the Past (V0.078, emulator capture)" width="640">
</p>

## Status

V0.082 is the current published version. Its software regression passed. I played it on my Saturn with SAROO on 2026-11-21, including CD++. Expect some bugs. Exact results and image hashes are in the [V0.082 release notes](RELEASE-NOTES-V0.082.md). Older versions are in the [changelog](CHANGELOG.md).

V0.083 is an unpublished audio prerelease candidate. It changes the opening movie sound setup and lowers music by 20% relative to effects. Release checks are in progress. Its console test is pending.

The [Easy Patcher](https://t3chnaztea.github.io/sonic-cd-saturn/web/patcher/) builds V0.082 in desktop Chrome from your own Japanese disc, U.S. disc and U.S. Sega CD BIOS. Nothing is uploaded. It checks your files first, and you only get a download if the result matches the build I tested, byte for byte. Allow about 45 minutes and at least 4 GiB of spare memory. The time depends on your computer. Each disc has to be in the dump layout the page asks for. You can also build from source (see [Building](#building)).

**Step 23 is slow.** `background_tables.py` took about 15–17 minutes on my M4 Mac. Several minutes between updates can be normal. The patcher now shows substep progress, elapsed time, a running log and an estimated countdown for that step. The estimate can run past zero on slower machines. Keep the tab open and your computer awake. Refreshing starts the conversion over.

The patcher's code is in [`web/patcher`](web/patcher/README.md). The recipe it downloads contains compiled program code, the MIT-licensed sound driver and the disc's file layout. It has no art, audio, level data or disc bytes. Your browser rebuilds all of that from your files and from pinned public sources. The source tree on `main` contains no generated recipe. No BIOS or disc image is provided. Test results are in the [verification record](web/patcher/IMPLEMENTATION.md).

Implemented game features:

- All 7 zones: Palmtree Panic, Collision Chaos, Tidal Tempest, Quartz Quadrant, Wacky Workbench, Stardust Speedway and Metallic Madness. There are 70 act/era variants: Acts 1 and 2 in Present, Past, Good Future and Bad Future, plus Act 3 in both futures. Time posts let you travel between eras.
- All seven bosses, Metal Sonic, Amy, and both endings.
- Special stages 1 to 8, entered from the big ring.
- Title screen, New Game, Continue, RAM Data and Time Attack.
- D.A. Garden, with its track list and looping music.
- Visual Mode: the opening, both endings and the pencil-test movie.
- The staff roll, the end screens, the "Thank You" screen and the Special Stage 8 credits. Each one is checked against the original, picture by picture ([credits audit](docs/CREDITS-AUDIT.md)).
- Backup RAM saves for progress, Time Stones and future flags. Save writes preserve the previous record until its replacement is complete. A slot that cannot be read is not overwritten.
- The five secret sound-test pictures, from your disc (V0.080).
- The Japanese soundtrack. This choice is intentional. A U.S. soundtrack option is planned but is not in the patcher yet.
- An optional CD++-style preset (see below). Classic is the default.

The video demonstrates console play. A full zone-by-zone hardware checklist remains open. Automated checks cover selected routes and states. They do not establish a percentage of every possible path through the game.

## CD++ preset

An optional preset adds five moves inspired by the 2009 Sonic CD++ hack: the Sonic 2 spin dash, no air speed cap, an air roll, a homing attack and the mini Sonic spin dash. Turn it on in RAM Data (MODE CLASSIC / CD++). The setting has its own save file, and Time Attack keeps separate CD++ records. I wrote the moves from scratch using public references. No CD++ code, patch data or sprites are used. Some values are my own choices, so it won't match the hack frame for frame. Details are in [docs/CDPP-PRESET-SPEC.md](docs/CDPP-PRESET-SPEC.md).

## How this was checked

- The game logic follows the [Sonic CD C decompilation](https://github.com/nfroggy/soniccddecompilation) and is checked against [scddisasm](https://github.com/sonicretro/scddisasm), the disassembly of the Sega CD original. When they disagree, the original wins.
- Retail match: I record a controller run on the original Sega CD game in an emulator, then play the same inputs on the Saturn build in Beetle Saturn. Nine state values have to match. Each zone has 10 of these runs.
- Many objects, bosses, menus and movies are also compared with the original, picture by picture or state by state. Examples: the credits, D.A. Garden, Visual Mode and the special stages.
- Player physics has its own test (`tools/test-player.sh`). Classic physics must stay identical when the CD++ code is built in.
- V0.082 passed 215/215 full-regression checks and 347/347 zone and special-stage matrix windows. The missing-art scan passed all 70 act/era cases. These are finite test inventories, not proof that every possible game path was tested.
- Emulator evidence and console evidence are recorded separately. V0.082 ran on my Saturn/SAROO, including CD++. V0.083 still needs its own console test.

## Related project

orca_earth_md is making a separate Sonic CD port for the Saturn ([r/SegaSaturn post](https://www.reddit.com/r/SegaSaturn/comments/1wlryos/)). It was shown on real hardware in September 2026. The two projects are not connected. This one rewrites the game logic in C, tests it against the original Sega CD game, and is built only from your own discs.

## Known issues

- V0.082: a player reported that the opening movie has no sound and can leave gameplay audio corrupted. The reporter said entering gameplay before the movie started avoided the fault. V0.083 has a startup repair under test. It has not yet been confirmed on a console.
- V0.082: music can be too loud relative to effects. V0.083 reduces music by 20%. Console listening tests are pending.
- Lost rings can bounce one update off from the original after a moment where the Sega CD would lag. The port doesn't copy Sega CD slowdown ([lag note](docs/LAG-MODEL-NOTE.md)).
- Quartz Quadrant Act 1 Present: a timing difference on the era sign was reported in V0.078. I can't reproduce it on the current test runs. It stays open until I can reproduce it or rule it out.
- Tidal Tempest Act 3 has no splash when you enter the water. It doesn't fit in sprite memory.
- Collision Chaos checks object touches in four passes. The original uses one loop that stops at the first hit.
- Jump headroom in the Stardust Speedway special stage still needs a console check.

## Screenshots

These stills are V0.078 in Beetle Saturn, scaled 2x. They are emulator captures. V0.082 has since run on my Saturn with SAROO, including CD++.

| | |
| --- | --- |
| ![Title screen](https://github.com/user-attachments/assets/81989a68-ef56-4de0-8a3b-d221f3fbf79f) | ![Palmtree Panic Act 1 Present](https://github.com/user-attachments/assets/4e4b2b1c-6a85-47b2-86ae-ffa234f9d4c7) |
| ![Stardust Speedway Act 1 Bad Future](https://github.com/user-attachments/assets/6288bb17-4ac7-4f49-b8fd-8ffd43d3fe05) | ![Special Stage 1](https://github.com/user-attachments/assets/c5c76a6d-afd6-4eb9-8636-e69d24caee40) |
| ![Metallic Madness Act 3 boss](https://github.com/user-attachments/assets/1da9274e-3524-45be-bf5a-b46139af87fa) | |

## Compatibility

| Target | State |
| --- | --- |
| Beetle Saturn (libretro) | Emulator checks run here. V0.082 passes its software regression. |
| Real Saturn + [SAROO](https://github.com/tpunix/SAROO) | Main target. V0.082 ran on my console, including CD++ (2026-11-21). V0.083 console test pending. |
| Mednafen | Used for manual play during development. |
| Yaba Sanshiro, Kronos, SSF | Untested. |
| Burned CD-R, other ODEs | Untested. |

The disc header lists every Saturn region (`IP_AREAS JTUBKAEL`), but it has only run on my console. I haven't written down its model, region, video mode or SAROO firmware yet. PAL timing is untested.

The build makes one BIN/CUE with 42 tracks: one data track plus CD audio. Load the CUE. The ISO in `dist/iso/` has no music.

## Requirements

| Input | Path | Used for |
| --- | --- | --- |
| Sonic CD, U.S. disc, CHD | `assets/private/sonic-cd.chd` | Game programs, sound effects, Past music driver, demos, movies |
| Sonic CD, Japanese disc, CUE/BIN | `assets/private/sonic-cd-japan.cue` (symlink) | All 34 music tracks |
| U.S. Sega CD BIOS | `assets/private/bios_CD_U.bin` | Offline render of the Past music |
| U.S./EU Saturn BIOS | `assets/private/mpr-17933.bin` | Emulator tests only |

You need two discs because the port uses the Japanese soundtrack, and the game data and sound driver come from the U.S. disc. The tools are tested against one U.S. disc image. Other U.S. revisions are untested. The Japanese disc is checked by its header and track layout. The build stops if a file is missing or doesn't match.

The build also downloads [scddisasm](https://github.com/sonicretro/scddisasm), the Sonic Retro disassembly, at a pinned commit. Stage art, layouts, palettes and mappings come from it for now. That repo contains SEGA-owned data, so nothing from it is redistributed here. A later version will read these from your disc instead. See [THIRD-PARTY.md](THIRD-PARTY.md).

Do not post disc images, BIOS files, built images or links to them in issues or pull requests. They will be deleted.

## Building

Tested only on Apple Silicon Macs. I haven't tried Linux or Intel Macs.

You need the Xcode command-line tools, Homebrew, Python 3.12+, Git, `ffmpeg` and `chdman` (`brew install ffmpeg rom-tools`), and about 6 GB of disk space. The bootstrap script runs `brew install make xorriso gmp mpfr libmpc isl`, then builds a pinned toolchain (binutils 2.44, GCC 13.4.0 sh-elf, Yaul 0.3.1) inside the repo, with the fixes in `tools/patches/` applied to Yaul. Exact source versions are in [sources.lock.json](sources.lock.json).

```sh
git clone https://github.com/t3chnaztea/sonic-cd-saturn.git
cd sonic-cd-saturn

# Your own dumps (see Requirements)
mkdir -p assets/private
cp /path/to/your/sonic-cd-us.chd assets/private/sonic-cd.chd
cp /path/to/your/bios_CD_U.bin   assets/private/bios_CD_U.bin
ln -s "/path/to/Sonic the Hedgehog CD (Japan).cue" assets/private/sonic-cd-japan.cue
cp /path/to/your/mpr-17933.bin   assets/private/mpr-17933.bin   # emulator tests only

# Toolchain and pinned sources (--emulator also fetches Beetle Saturn for tests)
bash tools/bootstrap.sh --emulator

# Extract, convert and build the disc
bash tools/build.sh
```

This writes `dist/sonic-cd-saturn-prototype.cue` and its `.bin`. On an M-series Mac the toolchain takes about 10 minutes to build, and the first `tools/build.sh` about 20. The same source and discs always give the same `.bin`, whatever folder you build in: ISO dates come from `IP_RELEASE_DATE` in the `Makefile` (or `SOURCE_DATE_EPOCH`), and no build path is compiled in. Everything stays in `.toolchain/`, `.deps/`, `build/` and `dist/`, which Git ignores. Japanese disc setup is in [JAPANESE-MUSIC.md](JAPANESE-MUSIC.md).

To play on a Saturn, copy the `.bin` and `.cue` into a folder on the SAROO SD card and pick the game from the SAROO menu. To play in Mednafen with your Saturn BIOS, run `bash tools/run-emulator.sh`.

Tests:

```sh
python3 tools/qa-loop.py fast    # quick gates
python3 tools/qa-loop.py full    # full regression; allow several hours
bash tools/test-player.sh        # player physics trace comparison
```

## Technical notes

Sprites are drawn by VDP1. Terrain and scrolling backgrounds are drawn by VDP2. Each act loads its own data from the disc. Music plays as CD audio from the Japanese tracks. The Past music is rendered ahead of time from the original Z80/PCM driver. Sound effects come from the original sound bank and play on the SCSP.

## Hardware reports

Console results are the most useful thing you can send. Use the [hardware test form](https://github.com/t3chnaztea/sonic-cd-saturn/issues/new?template=hardware_report.yml) and include the BIN SHA-256, Saturn model, region, video mode, SAROO firmware and what you saw. A photo or video helps. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

- [Sonic Retro](https://www.sonicretro.org/) and the [scddisasm](https://github.com/sonicretro/scddisasm) contributors, for the disassembly every behavior is checked against.
- [nfroggy and the Sonic CD C decompilation](https://github.com/nfroggy/soniccddecompilation) (CC0), the game-logic reference.
- [Yaul](https://github.com/yaul-org/libyaul) by Israel Jacquez and contributors (MIT), the Saturn SDK.
- [PoneSound](https://github.com/yaul-org/libyaul-examples) by ponut64 (MIT), the Saturn sound driver.
- [SAROO](https://github.com/tpunix/SAROO) by TPU, the optical drive emulator used for console tests.
- [Beetle Saturn](https://github.com/libretro/beetle-saturn-libretro) (Mednafen authors and libretro, GPL-2.0+) and [Genesis Plus GX](https://github.com/libretro/Genesis-Plus-GX) (Eke-Eke and contributors), used only for testing and audio rendering. Neither is linked into the game.
- qiuu and snkenjoi for [Sonic CD++](https://www.romhacking.net/hacks/1070/) (2009), with small spin dash sprites by MKAmeX, which inspired the CD++ preset. Christian Whitehead and SEGA for the 2011 remaster's spin dash option.
- Sonic Team and SEGA, for Sonic CD.

Full notices are in [THIRD-PARTY.md](THIRD-PARTY.md).

## AI use

I used AI coding agents for code, research and automated tests. I set the goals, made the design decisions and tested the game on my Saturn. The source and test notes are in this repo. The game keeps the original art; I did not use generative AI artwork in it. The trace and emulator tests are described in [QA-PLAN.md](QA-PLAN.md). Hardware results decide console acceptance.

## Legal

This is a non-profit fan project. It is not affiliated with or endorsed by SEGA or Sonic Team. Sonic the Hedgehog, Sonic CD and all related names, characters and marks belong to SEGA and are used here only to describe what this software works with. The repository contains no SEGA program files, graphics, music, sound or level data. The project does not accept donations.

## License

The port's own source code is under the [MIT License](LICENSE). It grants no rights to Sonic CD or any SEGA content. Third-party components keep their own licenses (see [THIRD-PARTY.md](THIRD-PARTY.md)). See also [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md) and [SECURITY.md](SECURITY.md).
