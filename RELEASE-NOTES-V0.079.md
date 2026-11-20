# V0.079 — Front end, credits, endings and CD++ preset candidate

Release date label: 2026-10-24.
This is a private Saturn/SAROO test build. The last user-confirmed console
build is V0.065. Keep the BIN/CUE and ZIP local. They contain assets from the
owner's Sonic CD disc.

## Scope

Finish the complete-game flow (roadmap milestone 4) and add the optional
CD++-style preset (milestone 5) on top of the V0.078 seven-zone game. Classic
stays the default and must pass the same gates as V0.078.

## Implemented changes

- D.A. Garden: native program, retail oracle and host parity check, retail lag
  model, Japanese track titles, looping music without an effect-bank reload,
  and an emulator route (61af0ad, 6db6a71, aae62fb, 367878f, 91bc794, ceef0d9).
- Visual Mode: the retail menu screen and IPX flow from VM____.MMD, checked
  pixel for pixel against retail (e502dc4, 212d7d3).
- Pencil test: the mute 5-sector PTEST.STM format, converter, retail oracle,
  Visual Mode entry and emulator route (9c1cc1f, b68ce64, f0cfdcd, 36e25d1).
- Credits and endings: the "Thank You" screen (THANKS_M.MMD) after Visual
  Mode's good ending, the Japanese staff roll, the end screens and the
  "PRESENTED BY SEGA" card from ENDING.MMD, stream end and picture times on
  retail time (fd6ae25, 086ca0c, 1203ff3, 20db646, 8888069, f07cd60, 3ea505f).
  Fixed against retail: the JP roll ran 9% slow and missed text tiles, the
  end-screen text was missing, and the Saturn played the PCM past the
  stream's end. Full table: [docs/CREDITS-AUDIT.md](docs/CREDITS-AUDIT.md).
- CD++ preset: Sonic 2 spin dash, air speed cap off, air roll, homing attack
  and mini Sonic spin dash in `src/player_plus.c`, each behind one flag bit;
  a MODE CLASSIC / CD++ row in RAM Data; the `SCDSATURNCF` setting file; a
  separate CD++ Time Attack table `SCDSATURNTP` (0de450a, bf1f1ca, 97abd00,
  076addd, 18072f7). Inspired by Sonic CD++ by qiuu and snkenjoi (2009),
  small spin dash sprites by MKAmeX
  ([romhacking.net 1070](https://www.romhacking.net/hacks/1070/)). No CD++
  code, patch data or sprites are used. Values marked "design" in
  [docs/CDPP-PRESET-SPEC.md](docs/CDPP-PRESET-SPEC.md) are this port's
  choices, not CD++ parity.
- `tools/release.py`: source-only release package with forbidden-file tests.

## Candidate evidence

BIN SHA-256: `3370c557d71dbebc14d52a11de5440a2dc92110314b8e4aae0543a8cc72632b8`
Source: commit `ae20691`, Makefile V0.079 / 20261024, clean tree.
Full QA: PASS 197/197, `build/qa-loops/20261024-153416-727426/report.json`; zone and special gates `build/zone-gates/20261024-174502/report.json`.

The rc tree 3ea505f failed one gate: the MM3 campaign game end timed out.
The port was right and the harness was wrong (ddd3ac0). The shipped Japanese
ENDING.MMD holds its "PRESENTED BY SEGA" card until Start (retail loop at
file offset $A270, no timer; the US disc times out after 600 V-blanks), and
the harness never pressed Start. The seven-zone campaign chain passes on the
fixed harness (`build/zone-gates/20261024-145948/report.json`). Emulator per-feature checks:

| Feature | Check | Where |
| --- | --- | --- |
| D.A. Garden | Retail oracle and host parity, emulator route | `tools/test_dagarden.py` (fast), `tools/test_dagarden_emulator.py` (full) |
| Visual Mode | 10 Saturn shots against retail, menu cursor, movies to their ends | `tools/visual_mode_retail.py`, `test_frontend_emulator.py visual-mode`, `visual-mode-movies` |
| Pencil test | Picture times against retail (worst 1.43 frames, bound 2.0) | `tools/test_fmv_emulator.py` |
| Credits | Staff roll, end screens, card, Thank You, SS8 credits | [docs/CREDITS-AUDIT.md](docs/CREDITS-AUDIT.md) |
| CD++ | 18 host trace cases, settings codec, Saturn toggle, one route per move | `tools/test_cdpp_player.py`, `tools/test_cdpp_routes.py` |
| Classic | Player traces unchanged with `player_plus.c` built in | `bash tools/test-player.sh` |

## Known gaps

Carried over from V0.078:

- Lost-ring pickup and floor timing after hurts and lag frames.
- QQ1A update 601: era sign timing (retail lag).
- Flowers in TT1/TT2 Present and Past and in WW1 Past exceed their exact-byte
  art limits.
- TT Acts 1-2: water entry splash art.
- MM2A: ET8 generator (et) art is not packed; no stored route draws it.
- Some MM objects written in C read Sonic's size fields by their retail byte
  position (oPriority/oXRadius), while the port stores the named radii (for
  example `src/objects_mm_common.inc:88`).
- R82A attract demo diverges from retail at update 127 (137/2006 equal): the
  BEAM touch box differs. The byte-layout fix broke normal MM2 play and was
  reverted.
- Secret sound-test images are missing.
- Animation phases: monitor flicker, ring spin, CC neon, SS searchlight and
  WW mesh.
- SS3/SS4 jump-peak headroom needs console confirmation (SS4 minimum 5.4%).

Closed since V0.078: the pencil test movie and D.A. Garden.

New in V0.079:

- US-stream control build only: the good ending's SEGA card starts 7 frames
  late (70 against 63). The shipped disc uses the Japanese streams, which
  match retail.
- CD++: no CD++ copy of the per-zone or boss routes yet; one route per move
  only. Homing attack and air roll timing are design choices, not CD++
  parity. The CD++ readme's terms are not yet recorded.
- No front-end addition or CD++ move has run on a console.

## Hardware

No V0.079 content has run on hardware. Console test pending (Monday). The last
user-confirmed console build is V0.065. Emulator results do not close the
console gate.

## Console checklist

1. Confirm BIN SHA-256 (full hash above) and the SAROO folder. Cold boot
   V0.079 twice. Record Saturn model, region, video mode, SAROO firmware and
   audio connection.
2. Open D.A. Garden. Play several tracks and let one loop. Check the planet,
   the track titles and the exit.
3. Open Visual Mode. Play the opening, both endings and the pencil test. Check
   sound sync, the staff roll, the end screen, the SEGA card and the "Thank
   You" screen after the good ending.
4. Earn the good ending in story mode. Check the ending movie, the card and
   the return to the title.
5. In RAM Data, switch MODE to CD++. Cold boot and confirm the setting stays.
   Try each move: spin dash, mini Sonic spin dash, air roll, homing attack,
   air speed. Run one Time Attack act in each mode and check the records stay
   apart.
6. Switch back to Classic. Play one act per zone. Check collision, art and
   frame pacing against V0.078.
7. Check title/gameplay music and effects, pause/resume and repeated cold
   boots. Report anything worse than V0.065 with BIN hash, zone, act, era,
   position, inputs and a photo or video.

Only the maintainer's exact-BIN SAROO evidence closes the console gate.
