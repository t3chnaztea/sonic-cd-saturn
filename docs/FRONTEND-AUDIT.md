# Front-End Audit (title, menus, special stages, warp, FMV)

Date: 2026-09-26. Branch `zones/terrain-all-seven` (4081c1d + uncommitted work).
Scope: code reading only. No build or emulator run backs this audit.
Abbreviations: `IPX` = `.deps/scddisasm/src/CD Initial Program/IPX.asm`;
`PC` = `build/audit/source/src/TITLE/`; `DIS` = `.deps/scddisasm/src/`.

## 1. Title screen and menus

The Sega CD title returns an exit code. IPX runs a scene from it (IPX:77-87):
0 demo, 1 new game, 2 load game, 3 time attack, 4 Backup RAM manager, 5 D.A. Garden,
6 Visual Mode, 7 sound test, 8 stage select, 9 best staff times.

| Feature | Native state | Evidence | Original reference |
|---|---|---|---|
| Title scene (Sonic, planet, clouds, emblem, press start) | Exists. Traced against retail. | src/title.c:95-225, 364-494 | DIS `Title Screen/Main.asm`, `Sub.asm` |
| Menu carousel (arrows, slide in/out, idle timer) | Exists | src/title.c:142-214 | `Title Screen/Objects/Menu/Main.asm` |
| New game / continue | Exists. Continue needs a valid save. | src/title.c:151-156; src/main.c:1244-1247 | IPX `NewGame`, `LoadGame` (137-163) |
| RAM DATA (Backup RAM manager) | Replaced by a native save panel | src/main.c:1248, 1252-1262 | PC `SAVEDATA/` (2340 lines), IPX:101 |
| Menu flags | Fixed at `0x90` plus `0x40` for continue. Bits 5, 3 and 2 never set. | src/title.c:153 | titleFlags from save data, `Menu/Main.asm:75` |
| Time Attack | Missing. Menu never offers it. No record storage. | src/save.h:7 has no time fields | PC `TA/` (2875 lines), IPX:1214, `UnlockTimeAttackLevel` IPX:638 |
| D.A. Garden | Missing | none in src/ | DIS `DA Garden/` (5113 lines), PC `PLANET/` (6455 lines), IPX:1206 |
| Visual Mode | Missing | none in src/ | DIS `Visual Mode/Main.asm` (1684 lines), PC `VISUALMD/` (930), IPX:1125-1170 |
| Sound test + easter eggs | Missing. main.c `audio_test` is a debug hook, not the SOUNDTST screen. | src/main.c:1490-1491 | PC `SOUNDTST/` (1246), `Title Screen/Secrets/Sound Test.asm`, IPX:1035-1120 (SS8, Fun is infinite, M.C. Sonic, Tails, Batman, Cute Sonic) |
| Stage select | Non-original stand-in: A+B+C+Start opens a zone/act/era picker | src/main.c:1228-1229, 1263-1293 | PC `STAGETST/` (794), `Secrets/Stage Select.asm`, IPX:710 |
| Best staff times | Missing | none | PC `BESTTIME/` (916), `Secrets/Best Staff Times.asm`, IPX:93 |
| Title cheat codes (clouds, sound test, stage select, best times) | Missing. Press-start state reads only Start. | src/title.c:146-163 | `Menu/Main.asm:46-59, 291-300` |
| Cloud control by pad 2 (clouds cheat) | Missing | src/title.c:340-350 renders only | `Title Screen/Sub.asm:169`, `Main.asm:570-578` |
| Attract (exit 0 / timeout) | Cycle order kept; SS1 and SS6 demos play and return to the title. FMV and R11A/R43C/R82A slots return at once. | src/main.c (title exit 0); src/title.c:162, 210 | IPX `Demo` 929-960: opening FMV, R11A, SS1, R43C, SS6, R82A |
| Ending and credits | GameDone choice + GOODEND/BADEND movie (staff roll, end screen) from the front-end overlay R0, then the title; text card only if the movie cannot play | src/ending.c, src/fmv_saturn.c, main.c `prototype_end` | IPX `GameDone` 301-330; ENDING.MMD; PC `THANKS/` (4868), `AVIGOOD/`, `AVIOPEN/` |

Notes: PC `OPENING/` is the PC title screen (hand, planet, water, clouds, menu enable
logic `GetEnabeMenu`, OPNDO.C:16-17), not the FMV. It is a secondary check for
native title.c. Region deltas (menu timer, extras cue) are tracked in
`docs/REGION-BUILD-INVENTORY.md:41-46`.

## 2. Special stages, time stones, good futures

Native flow: src/main.c:157-181 holds `time_stones`, `good_future_flags`,
`saved_good_zones` and the save mailbox. The big ring sets `special_pending`
(main.c:1576). The tally enters the special stage (main.c:1509-1519). Act 3 picks
good future when `good_future_flags==3 || time_stones==127` (main.c:1319, 1548).

Gaps:

1. **Always Special Stage 1.** `scd_special_game_start` sets `g->stage=1` and loads
   stage 1 (src/special_game.c:37-38). `special_game_begin` calls `special_load(1)`
   (src/special_game_view.inc:176). The original sends `curSpecStage`
   (IPX:586-588). Native computes `next_stage` (special_game.c:50-53) but nothing
   stores or uses it. Stages 2-7 are reachable only in the X-key inspection
   (src/special_view.inc:170).
2. **`curSpecStage` is not saved.** `scd_save_progress` has `time_stones` but no
   next-stage field (src/save.h:7). A continue restarts at stage 1.
3. **All-stones good future.** IPX sets `goodFuture=1` and fade-from-white after
   the 7th stone (IPX:594-597), and `LevelStart` forces it on every level load
   (Level/Main.asm:22-26). Native: fade from white on every special return, Act 3
   good future (main.c `act3_load`), and `load_era` forces the world's good future,
   so a future warp lands in the good one. Open: objects.c `scd_objects_reset`
   still sets `good_future=era==2` (past generator and badniks should read the
   forced flag), and Continue restores the stones after its first load.
4. **Special Stage 8 and demos.** Mode flags (temporary, time attack, secret) run in
   `src/special_game.c` with host parity per V-INT (`tools/test_special_game.py`
   demo-ss1, demo-ss6, steer-ss8, taexit-ss1). SS1/SS6 attract demos play from the
   title time-out (`src/main.c` IPX Demo cycle; `tools/test-special-modes-emulator.sh`).
   SS8 runs (cd/SSM8.BIN) but has no entry: the sound test (FM07/PCM07/DA07,
   Sound Test.asm:276) does not exist. No stored SS8 win route yet.
5. **Ending choice.** Done: `scd_ending_good` (src/ending.h) is IPX:301-330 (all 7
   good futures or all 7 stones). In-game GameDone plays only the movie and returns
   to the title; the THANKS screen follows only Visual Mode's good ending (IPX:1184).
   ENDING.MMD's last screen reads "YOU'RE TOO COOL!" ($7F) or "TRY AGAIN" (0).
6. **Time Attack special-stage mode.** The stage mode works (count-up timer, A/B/C
   pause exit, win in lives). No menu reaches it. Retail ATTACK.MMD 0xff2cd6-0xff2d1a:
   with all 21 acts unlocked, a best-time total under 30'21"05 sets titleFlags bit 1
   (special-stage column), under 25'46"12 bit 2 (Visual Mode), under 37'27"57 bit 3
   (D.A. Garden). Records: 28 x 3 times (21 acts + SS1-7). Needs zone Time Attack first.

## 3. Time warp cutscene

References: DIS `Time Warp Cutscene/Main.asm` (the Sega CD program) and PC
`WARP/WARP.C` (PC port, 420-frame timer at WARP.C:189). Match the Sega CD version.

| Item | Sega CD | Native | Status |
|---|---|---|---|
| Hold timer | 240 frames (Main.asm:170) | 240 (src/main.c:1628) | match |
| Sonic path | Y 288 to 120 at 8 px, hold 120, exit up (Objects/Sonic/Main.asm:28-64) | same curve (src/main.c:657-658) | match |
| Start skips | yes (Main.asm:192) | yes (src/main.c:1499) | match |
| Pre-delay for PCM music fade | 90 frames (Main.asm:164) | none | gap |
| Fade from white in, fade to white out | Main.asm:177-183, 198 | none (hard cut, src/main.c:1003-1016) | gap |
| Warp SFX `FM_D8` | Main.asm:172-174 | `scd_audio_warp(1)` | verify cue id |
| Trail objects | 4 spawned trail objects, own timers (Main.asm:311-316) | 3 fixed-offset sprites (src/main.c:659) | approximate |
| Sparkle objects | spawned (Main.asm:318-325, Objects/Sparkle) | missing | gap |
| Palette cycle, BG scroll -4/frame | Main.asm:188, 272 | green cycle + scroll (src/main.c:1017-1029) | check phase |

## 4. Intro and ending FMV

Status: the endings play on the Saturn. `tools/fmv_convert.py` builds cd/*.FMV from the
user's disc; src/fmv_saturn.c runs from the front-end overlay R0 (src/fmv_fe_names.h), state in low
work RAM 0x00243000; `tools/test_ending_emulator.py` drives both endings from crafted
saves. The opening FMV and Visual Mode are not wired. The FMV soundtrack follows the
disc's region (a U disc plays the U ending song).

Original format (from DIS, derived, not yet measured):
- Files: `OPN.STM`, `GOODEND.STM`, `BADEND.STM`, `PTEST.STM` (DIS README; the
  sub programs are swapped by name, `Sub (Ending).asm:17-21`).
- Stream: 1x CD, cycles of 75 sectors. Sectors 0-14 are PCM, 15-74 graphics
  (`CD System Program/SP.asm:823-866`). So about 30 KB/s PCM and 120 KB/s graphics.
- Graphics: 8 frames per Word RAM bank (`FMV/Main (Opening).asm:346-347`), so about
  8 frames/s. Each frame is Mega Drive 4bpp tiles plus a 16-color palette line,
  double-buffered at VRAM $0200/$3A00 (Main (Opening).asm:215-251). A fixed border
  map (40x28, Main (Opening).asm:660-670) frames the picture.
- Audio: 8-bit RF5C164 PCM, double-buffered in 8 banks (`Sub (Opening).asm:43-77`).
- Visual Mode loops a movie while `mmdReturnCode` is negative (IPX:1147-1150).

Proposed Saturn design: **replay the STM data itself (recommended).**
- Codec: none new. MD 4bpp tiles map one-to-one to VDP2 4bpp cells. Convert the
  9-bit palette to RGB555 and the PCM sign-magnitude bytes to SCSP signed 8-bit at
  build time. The picture stays bit-exact to the Sega CD. No lossy re-encode.
- Rate: 150 KB/s source. Saturn CD at 2x gives 300 KB/s, so 50% headroom for seeks.
- Memory: ring buffer of 2 cycles (2 x 150 KB) in LWRAM. Two 14 KB cell buffers plus
  border in VDP2 VRAM. 64 KB PCM ring in SCSP RAM, fed by the sound CPU.
- Timing: swap cell pages at V-blank on the frame clock the PCM position drives,
  as `SyncWithPCM` does (`Sub (Opening).asm:220-235`).
- Build: `tools/extract_fmv.py` reads the user's disc image (same input as
  `prepare_audio.py`: CHD/ISO/cue), hashes the input, pulls the STM files, writes a
  Saturn stream file under `build/fmv/`, and records hashes in a report. The image
  build adds it to the local disc only. Nothing goes in git or `cd/`. Region vocals
  differ (U.S. vs JP/EU); the Japanese-music build needs the JP/EU stream.

Rejected alternatives:
- Cinepak through Sega's CPK library: the SBL/SGL library is proprietary and Yaul
  does not ship it. It also forces a lossy re-encode of already-lossy video.
- Custom Cinepak (or other) decoder on the slave SH-2: feasible, but costs CPU and
  fidelity. Keep it for a Party 2 upscaled option, not Party 1.

## 5. Ordered slice list

| # | Slice | Verification |
|---|---|---|
| 1 | Special stage ID: store `next_stage` as `curSpecStage`, pass it to `special_game_begin`, add it to save format | Route test: stones 0..6 give stages 1..7 in order; save/continue keeps the ID; `tools/test-player.sh` green; fast QA |
| 2 | Ending choice: replace `prototype_end` with good/bad routing per IPX:301-330 (placeholder card until FMV) | Unit test on 4 cases (7 futures, 7 stones, neither, both); emulator route through R8 |
| 3 | Menu flags from save: time attack unlock, D.A. Garden, Visual Mode bits (`Menu/Main.asm:75`) | Title trace vs retail for save states with each flag; `tools/title_retail.py` records |
| 4 | Title cheat codes + attract demo cycle (IPX:929-960) | Controller recording enters each code; timeout cycles 6 demos in order |
| 5 | Warp polish: 90-frame delay, white fades, sparkle + trail objects | Frame capture vs Sega CD emulator capture, frame-by-frame |
| 6 | FMV extractor + STM replay player (opening first) | Frame hash match vs decoded STM; A/V sync drift < 1 frame over full movie; hardware run |
| 7 | Good/bad ending FMV + credits (THANKS) | Same as 6; credits text vs retail capture |
| 8 | Visual Mode (opening, endings, pencil test, loop) | Menu route test; each movie plays |
| 9 | Sound test + SS8 + easter-egg screens | Codes reach each screen; SS8 credits after a win |
| 10 | Time Attack + best times + staff times | Record save/load; unlock order per `UnlockTimeAttackLevel` |
| 11 | D.A. Garden (planet, track list, unlocks) | Track titles vs `DA Garden/Track Titles.asm`; capture vs retail |

Every slice ends with fast QA (`PASS:` line), a new build hash, and a hardware run
before acceptance.
