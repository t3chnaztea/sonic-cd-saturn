# Credits audit

Scope: every credits-related screen of the Sega CD original: the staff roll, the end
screens, the "PRESENTED BY SEGA" card, the "Thank You" screen and the Special Stage 8
credits. Each item names its retail reference, the port's evidence and the result.
This is emulator evidence (Beetle Saturn for the port, Genesis Plus GX for retail). It
is not a hardware result.

## Where retail shows each screen

- GameDone (story mode) runs GOODEND or BADEND and returns. It does not run the
  "Thank You" screen (`CD Initial Program/IPX.asm:300-326`).
- `VisualMode_GoodEnd` runs GOODEND, then `RunMMD(SCMD_THANKYOU)`
  (`IPX.asm:1176-1186`). This is the only path to THANKS_M.MMD. The PC version shows
  THANKS after story endings too (`WINEXE/WINMAIN.C` cases 7 and 8, EndingMes). That
  is PC only, so the port does not do it.
- `SoundTest_SpecStg8` runs SPEEND.MMD after a won Special Stage 8 (`IPX.asm:1073`).

Port entry points: `fe_vm_thanks()` (src/credits_saturn.c) replaces Visual Mode's weak
hook at src/visual_mode.c:181. `scd_credits_thanks_play()` is the resident entry.
`scd_credits_test_entry()` (src/ending.c) is the emulator test entry: "THNK", "ENDG" or
"ENDB" in `scd_credits_mailbox[0]` at the title.

## Disc data

The Saturn disc carries the Japanese ENDING.MMD, GOODEND.STM and BADEND.STM
(`tools/fmv_extract.py`, JAPANESE-MUSIC.md). The core has only the US Sega CD BIOS, so
`tools/credits_roll_retail.py --jp` builds a local test disc: the user's US disc with
those three files replaced. It is never shared. The US IPX then runs the Japanese ending
program. The US streams (`fmv_extract.py --iso build/retail/sonic.iso`) are the control
build.

## Results

| Item | Retail reference | Port evidence | Result |
| --- | --- | --- | --- |
| Staff roll text and order | ENDING.MMD job 10/NO: the credits table (`$C090`), SR text tiles to VRAM $14C0 (US 720, JP 990 tiles: DMA jobs $14C0..$9080) | `fmv_convert.py` copies the table and reads the tile count. `test_credits_roll_emulator.py`: every roll frame's right half (x 160-319) equals the retail frame of the same step. JP: 7,831 frames per ending. US control: 9,416. | Pass (fixed: JP tiles $376-$483 were missing) |
| Roll scroll timing | `addi.l #step,$C08A` per V-blank: US $9100, JP $A000 (`$FF2500`), one row per 8 lines | Step read from ENDING.MMD into the FMV header. Per-step pixel match as above. | Pass (fixed: JP rolled 9% slow) |
| Roll window position | Plane B, 40 columns, rows at ((scroll + 224) & $F8) / 8; window picture at plane A column 4, row 6 | Same frames, whole right half, pixel for pixel | Pass |
| End screen "YOU'RE TOO COOL!" / "TRY AGAIN" | Job 11 (`$FF2AD0`): rows 21-22 (good, 2x16) or 21-25 (bad, 5x30), tiles to $76C0, fade of line 2 colours 11/15; each fade V-int writes V-scroll 0 (`$FF28FA`) | Same pictures in order (`end` check). End tiles now load in job 11. Scroll 0 after a roll that outlasts job 11. | Pass (fixed: JP text missing, later garbage) |
| Stream end | Sub (Ending).asm `.CheckStatus`/`.Exit`: the Sub CPU reports the end once it takes the last packet and mutes PCM. ENDING.MMD (`$FF20F0`) leaves its loop, clears CRAM line 0 (`$FF210E`), waits 61 V-blanks (`$FF214E`, `move.w #$3C,d1`), then jumps to `$FFC100`. No picture of the last packet shows. | The stream loop ends one video slot before the last packet's first picture, stops the PCM slot, clears the picture's line 0, waits `FMV_SAT_END_WAIT` (61, read from ENDING.MMD) V-blanks, then plays the card. | Pass (fixed: the Saturn played the PCM out) |
| Picture times | Retail, from the movie's start (JP good, JP bad, opening) | Before: the roll section (SR to the roll's end) ran about 7 frames late against the movie's other pictures, and the roll gained 1.7 frames over its 7,800 steps. Cause 1: ENDING.MMD's SR, its "15" frames and the roll start one video slot before the packet's audio, as RS and the stream end do; the player put them at the packet's start. Cause 2: the roll's V-blank was 32,743.6 Hz / 59.9227 Hz of audio, while the slot plays at 32,752.1 Hz (OCT -1, FNS 497). Now: worst picture good 1.64, bad -1.45, opening -1.36 frames; pencil test 1.43 (`test_fmv_emulator.py`). | Pass (fixed; bound 1 frame plus 1 of V-blank rounding) |
| "PRESENTED BY SEGA" card | `$FFC100`: fade out ($FFC2D6, 24 steps R/G/B), Nemesis art, 20x3 map at plane A row 11 col 10, palette, fade in ($FFC35A, B/G/R), hold (US 600 V-blanks or Start held; JP until Start held), fade out | `card_play` (src/fmv_saturn.c) with data from ENDING.MMD. Pictures identical and in order. Hold matches (124 frames vs retail 123, Start after 120). | Pass (added: the port had no card) |
| Card start after the last movie picture | Retail: 63 frames (all four streams: the report, then the line 0 clear one frame later, 61 V-blanks, 2 card V-blanks) | Saturn JP: 63 (good), 63 (bad). US control: 63 (bad), 70 (good). | Pass on the JP disc (test bound +-1). US good control: open (below) |
| "Thank You" logic | THANKS_M.MMD (`$FF2000`), PC TITLE/THANKS | `test_credits.py`: PC parity (12 scenarios, 105,219 frames). Sega CD mode against the retail run: 12,224 calls, every sprite table, all 64 colours, name tiles and all 64 actors in work RAM ($FF9200), through the 3-minute end timer and a Start quit. | Pass |
| "Thank You" retail differences from the PC | Retail random ($FF3CF6), bird inits leave SPR_TIMER 0 ($FF5A86), no X wrap after the actor dispatch ($FF4706), Amy's jump speed and catch side from Sonic's flip ($FF4F24, $FF4FC4), 24-colour cycle ($FF3B12), m_furi_map with 1 frame, name scoring by rank ($FF2142), sticky quit, V-int order, 22-step fades ($FF3E48/$FF3EE4) | `SCD_CREDITS_SEGA_CD` in src/credits.c | Pass |
| "Thank You" pictures | Retail frames 124 + call | `test_credits_emulator.py`: 10,822 Saturn pictures (no input) and 627 (Start) equal retail CRC for CRC. This includes Mega Drive sprite masking (X 0). | Pass |
| "Thank You" reachable | `IPX.asm:1184` | `test_frontend_emulator.py visual-mode-movies`: good ending, card, THANKS, menu | Pass |
| Special Stage 8 credits | `Title Screen/Secrets/Special Stage 8 Credits.asm`, SPEEND.MMD | `special_mode_gate.py SP8-credits`: the steady picture equals retail (82b6e99e, 210 frames). Every retail fade-in (22) and fade-out (12) picture appears in order. The title returns. | Pass |
| Story-mode ending route | `IPX.asm:300-326` | `test_ending_emulator.py`: 3 cases (stones, futures, none), every picture shown, the title returns. Start ends the JP card. | Pass |

## Tests

- `tools/test_credits.py` (fast QA): PC parity and the Sega CD mode against retail.
- `tools/test_credits_emulator.py` (full QA): the "Thank You" pictures.
- `tools/test_credits_roll_emulator.py` (full QA): both endings' roll, end screen and
  card against retail (JP test disc, or US with US streams), and the picture times of
  both endings and the opening.
- Oracles: `tools/credits_retail.py` (THANKS_M.MMD) and `tools/credits_roll_retail.py`
  (ENDING.MMD or OPEN_M.MMD, `--jp`, `--card-press`).

Picture-time bound: 2.0 frames (`PICTURE_SLACK`; the pencil test uses the same). That
is 1 frame of timing error, plus 1 frame of V-blank rounding. Each machine shows a
change at its own next V-blank: the Saturn field at 59.83 Hz, retail at 59.92 Hz. The
two grids do not line up, so one change can land up to almost 1 frame apart with no
timing error at all. Times count from the movie's start: the median offset of the first
100 pictures, so the start's own rounding does not bias the rest.

## Open

- US-stream control, good ending: the card starts 7 frames late (70 against 63). That
  stream's own picture turns black one slot before the Saturn's end, so the clear
  shows no change. The US streams end on an 18-sector partial packet, and the retail
  Sub CPU's end report there follows its CD and PCM phase, which differs per stream
  (US good and bad have the same packet layout and report 7 frames apart). The
  shipped disc carries the JP streams, which match exactly.
- Hardware: none of this has been seen on a console.
