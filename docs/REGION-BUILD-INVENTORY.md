# Region build inventory: `make REGION=us|jp`

Read-only survey, 2026-09-26, branch `zones/terrain-all-seven` @ 4081c1d.

## (a) How the build ingests discs today

The build uses two private discs, not one.

| Input | Path | Used for | Region check |
| --- | --- | --- | --- |
| U.S. retail CHD | `assets/private/sonic-cd.chd` | All graphics, layouts, collision, objects, SFX, PCM Past drivers, MMD programs | None. README.md:216 says "verified against the supplied US image; other disc revisions are not tested." |
| U.S. Sega CD BIOS | `assets/private/bios_CD_U.bin` | Offline Genesis Plus GX capture of Past/PCM audio | None |
| Japanese CUE/BIN | `assets/private/sonic-cd-japan.cue` (symlink) | All 34 music tracks | Header byte 0x1F0 must be `J` (prepare_japanese_music.py:79) |

- `sources.lock.json` (1,139 bytes) pins only tool sources: libyaul, examples, soniccd (nfroggy Win95 decomp), scddisasm, beetle-saturn, genesis-plus-gx commits, plus sha256 for binutils/gcc tarballs. It pins **no disc hash**.
- `tools/prepare_audio.py:10-31` fingerprints the CHD by full sha256 and runs `chdman extractcd` into `build/retail/sonic.{cue,bin}`. That cache feeds ~60 tools (`git grep -l "sonic.bin\|disc_files" tools/*.py`).
- The disc is identified by content, not hash. Checks: a unique Z80 driver signature (prepare_audio.py:39), the file names `SNCBNK*B.BIN`, and `R11A__.MMD`…`R13D__.MMD` (README.md:275).
- 17 tools assert sha256 of blocks cut from U.S. MMD programs. Examples: `tools/cc_generator_source.py:34`, `tools/cc_pocket_source.py:42`. These act as implicit U.S.-revision pins.
- JP selector (`tools/prepare_japanese_music.py`): the CUE must use raw BINARY files and consecutive tracks. It needs 35 tracks. It copies CD-DA from INDEX 01 and excludes pregaps. It also checks JP `SNCBNK1B.BIN` against the U.S. `build/retail/past-driver.bin` byte for byte (line 81-83). Output hashes go to `build/feedback-source.json`.
- `tools/package.py:16-18` refuses to package unless there are 34 tracks and `music_source.region == 'Japan'`.

## (b) U.S. vs JP differences (source: .deps/scddisasm, `REGION` = JAPAN 0 / USA 1 / EUROPE 2)

Soundtrack:
- The CD-DA track layout is region-independent. `src/_Include/Sound.inc:35-68` has no REGION branch: WARP, R1A/C/D…R8A/C/D, BOSS, FINAL, TITLE, TMATK, RESULTS, SHOES, INVINC, GAMEOVER, SPECIAL, DAGARDEN, INTRO, ENDING. So 34 audio tracks plus 1 data track in both regions.
- The Past music is PCM in **both** regions, not only in the U.S. release (SNCBNK*B.BIN, SCMD_FADEPCM). The build already proves JP bank 1 equals the U.S. bank 1. Only the Present/Future/event CD-DA content differs (U.S. Nilsen/Crowe score vs JP Hataya/Ogata).
- The old U.S. music path still exists: `prepare_audio.py:130-140` copies U.S. tracks 3,4,5,28,29,30,32,24,26. The JP selector then replaces them.

Gameplay/data (scddisasm path:line). The port currently matches the **U.S.** values:
| Item | U.S. | JP/EU | Source | Port today |
| --- | --- | --- | --- | --- |
| Invincibility / shoes timer | 1320 | 1200 | Level/_Objects/Monitor and Time Post/Main.asm:531,564 | 1320 (src/player.c:97-98) |
| Results tally timer | 480 | 360 | Level/_Objects/Results/Main.asm:66,77 | check |
| Pause-quit | any of A/B/C | A+B+C together | Level/Main.asm:362 | check |
| Pause blocked while dying | yes | no | Level/Main.asm:337 | check |
| Roll-tunnel roll SFX | no | FM_9C | Level/_Objects/Sonic/Main.asm:2595; WW Sonic:2977 | check |
| PPZ1 Present scroll event order | USA branch | other | Palmtree Panic/Scroll (Act 1 Present).asm:188 | check |
| Level data padding | `(U).bin` | `(JE).bin` | PPZ/WW Data (Act 1 Present).asm:251,137 | offsets shift |
| Special stage "EXTRA PLAYERS" text art | extra U.S. art | JP tiles | Special Stage/Main.asm:342,2235,4012,4722 | check |
| Special stage gravity | same as JP | EU differs | Special Stage/Objects/Sonic/Main.asm:201-653 | n/a (EU out of scope) |
| Title menu idle timer | $3FC | $1E0 | Title Screen/Objects/Menu/Main.asm:29 | check |
| Title object count / RAM | +2 objects | fewer | Title Screen/Main.asm:60-70 | check |
| Copyright/trademark sprite | U.S. mappings, TM | JPN/EUR mappings | Title Screen/Objects/Copyright/Main.asm:11-34 | check |
| Title "extra" menu music | D.A. Garden | Time Attack | CD System Program/SPX.asm:1350 | check |
| BRAM init screens/art | U.S. art/text | JP text | Backup RAM/Initialization/Main.asm:111-1163 | not ported |
| Opening FMV read routine | same | EU differs | FMV/Main (Opening).asm:318,371 | FMV not ported |
| Boot header volume/date | SEGASONICCD, 10061993 | SEGAIPSAMP, 08061993 | Main.asm:12-53 | n/a |

- FMV: the opening and ending movie files carry region-specific vocals (U.S. "Sonic Boom" vs JP "Sonic – You Can Do Anything" / "Cosmic Eternity"). That is general knowledge, not verified in-repo. No FMV code exists in `src/` or `tools/`. PORT-ROADMAP.md:21 lists intro/ending as unstarted.
- `tools/title_retail.py:28-30` hard-codes `REGION=USA` when it preprocesses the disassembly's `if REGION` blocks.
- Saturn IP header (Makefile:36-44): `IP_AREAS:= JTUBKAEL` is already all-region. `IP_PERIPHERALS:= J`. `IP_TITLE` is fixed. No product number or region-specific title is set. Region needs no header change for SAROO. An optional per-region `IP_TITLE`/version suffix helps tell images apart.

## (c) Proposed interface

`make REGION=us` (default `jp`, which keeps today's output) and `bash tools/build.sh --region us|jp`. Output: `dist/iso/sonic-cd-saturn-<region>.{cue,bin}` plus `region` in `dist/build-report.json`.

Input layout (one disc per region, no second disc needed):
- `assets/private/sonic-cd-us.{chd|cue}` and `assets/private/sonic-cd-jp.{chd|cue}`. Accept CHD or CUE/BIN through one reader. Detect region from header byte 0x1F0 (`U`/`J`/`E`) and fail on a mismatch with REGION.
- The BIOS stays the U.S. BIOS for offline PCM capture only. It is not a region input. Document that.

Changes:
1. Makefile: `REGION ?= jp`, export to tools, add `-DSCD_REGION_US/JP` to CFLAGS, suffix `SH_PROGRAM` and the build dir so the two regions never share `build/` caches.
2. `tools/disc_source.py` (new): one resolver for CHD and CUE. It returns the data track ISO, the audio tracks, the region, and a sha256 per track. It replaces the hard-coded CHD path in prepare_audio.py:10 and the JP path in prepare_japanese_music.py:157.
3. Generalize `prepare_japanese_music.py` → `prepare_music.py --region`. Same 34-slot routing (layout is identical). Keep the Past-driver equality check per region.
4. `package.py:16`: require `music_source.region == REGION`, not 'Japan'.
5. `title_retail.py:30` and any other disassembly preprocessor: take REGION from the environment.
6. `src/`: a `region.h` with the table from (b) (power-up 1320/1200, results 480/360, pause-quit mask, roll SFX, title timer, copyright frame, extras-menu cue). Party 1 "exact match" means each region builds its own values.
7. Extractors: parametrize expected-block sha256 constants by region (17 files). Record per-region fingerprints in a `region-lock.json` that holds **hashes only**. Hashes of the user's disc contain no SEGA data and are safe to commit.
8. Docs: replace JAPANESE-MUSIC.md with REGION.md. It explains where to put the user's own image. It gives no acquisition guidance.

QA gates per region:
- Both regions, fast: test_music (renamed), test_feedback, test_assets, test_objects, audit_source, boot smoke, test_zone_music (28 routes), plus a new `test_region_constants.py` that diffs `region.h` against the scddisasm branches in (b).
- Both regions, full: build, test_disc_dependency, package readback, act emulator routes, test_save_* (the music track asserts change per region).
- Region-independent (run once): test-player.sh traces, scroll/terrain/boss host parity. **But** the power-up timers affect traces that use monitors. Tag those traces per region or pin them to the default region.
- Hardware acceptance stays per region and per image.

## (d) Risks

- **Only one U.S. revision tested.** No disc hash is pinned. The 17 sha-asserted MMD blocks will fail on other revisions and on JP data. The `(U)`/`(JE)` padding differences shift offsets, and the U.S.-only code branches change MMD layout. Every `*_retail.py`/`*_source.py` extractor needs a JP run before JP-only builds work.
- **JP graphics were never extracted.** Today's "JP build" is U.S. data + U.S. gameplay constants + JP music. A true JP build needs a JP data extraction pass and the (b) constant table.
- JP-only hard-coding (grep `Japan|japanese`): package.py:16-18, build.sh:9, qa-loop.py:16, test_feedback.py:31-35, test_cc_audio.py:60, test_tt_audio.py:6, test_cc_campaign_route.py:180,234,293, test_cc_generator_route.py:162-202, test_save_matrix.py:42, test_save_progression.py:43, prepare_cc_campaign_checkpoint.py:50-56 (`japanese_track=12`). The track numbers in these asserts are region-neutral. Only the names and the `region == 'Japan'` checks are JP-bound.
- U.S.-only hard-coding: prepare_audio.py:10 (`sonic-cd.chd`, `bios_CD_U.bin`), title_retail.py:30 (`REGION=USA`), capture_retail_audio.py:19 (fake header `U`), src/player.c:97-98 (1320).
- Multiple dump formats: CHD vs CUE/BIN, and single-BIN vs per-track BIN. The JP reader rejects non-BINARY FILE lines and needs INDEX 01 on every track. Redump per-track dumps pass. Other formats may not.
- Cache collision: `build/retail/` and `build/japanese-past/` do not include region in their keys. A second region would overwrite them. Key by disc sha256 and region.
- Distribution: the committed hash list and REGION.md must hold no ROM bytes, no BIOS, no links or acquisition steps. `assets/private/`, `build/`, and `dist/` must stay git-ignored.
- The EU (`E`) disc has different special-stage physics and FMV timing. Reject it explicitly unless it is added as a third region.
