# V0.078 — Metallic Madness, special stages and seven-zone campaign candidate

Release date label: 2026-10-18.
This is a private Saturn/SAROO test build. The last user-confirmed console
build is V0.065. Keep the BIN/CUE and ZIP local. They contain assets from the
owner's Sonic CD disc.

## Scope

Add Metallic Madness to Palmtree Panic, Collision Chaos, Tidal Tempest,
Quartz Quadrant, Wacky Workbench and Stardust Speedway. Cover MM1/2 in all
four eras and MM3 in both futures, through the final boss, Amy and the game
end. Add the special stages (stages 1-8, big-ring entry from every zone,
save progression, both endings and the seven-stone return). Earlier zones
must pass the same full matrix.

## Implemented changes

- R8 actor registration (ids 157-188), retail layouts and record order, R8
  code overlay, original update order, layer (st_metalDataChk) collision,
  springs on screen, time posts in the COLI8 scan, and score popups.
- Original R8 actor, flower, boss (BOSS_8/COLI8/COL8C-D) and Amy art, phase
  palettes and priority; the Act 3 fight and Amy banks.
- Metal Sonic/boss fight, EMIE8 ending control and the game end: completed
  save, ALL ZONES CLEAR screen and return to the title.
- Ten stored MM controller routes, ten natural travel scripts, and an earned
  Good Future campaign from NEW GAME through MM3 with cold Continue.
- Special stages 1-8 against retail routes (win, time-out and hazard), big-ring
  entry from every zone, save progression of stones and curSpecStage, both
  endings (stones or good futures) with the ending movie, and the seven-stone
  return; Time Attack menu, runs, records and unlocks; attract demos.
- The retail DA tracks the game was missing (Time Attack, game over, D.A.
  Garden, intro, ending, warp) from the JP disc: 42 disc tracks.
- Seven-zone release validation (V0.078 scope) with predecessor report and
  save-hash links from PPZ3 through MM3.

## Candidate evidence

BIN SHA-256: `11b162218b49201b51cf9fc6d205844731c5bd49079abce76a6cc9347187f4a6`
Source: commit `bec6942`, Makefile V0.078 / 20261018, clean tree.
Full QA run06 passed 187/187 commands on this one BIN (189.9 min):
`build/qa-loops/20261018-120617-450877/report.json`.
Zone gates on the same BIN (`build/zone-gates/20261018-134837/report.json`):

| Zone | Retail (nine-field) | Saturn routes | Art | Travel | Campaign |
| --- | --- | --- | --- | --- | --- |
| PPZ | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| CC | 10/10 | 10/10 | 10/10 | 10/10 | 5/5 |
| TT | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| QQ | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| WW | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| SS | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| MM | 10/10 | 10/10 | 12/12 | 10/10 | 3/3 |

MM art adds the Act 3 fight and Amy banks (MM3C-fight, MM3C-ending).
Special-stage and front-end gates on the same BIN (zone `sp`, 42 cases):
42/42 pass.

The BIN hash was unchanged at the end of the zone gates. The campaign
chain earns Good Future from PPZ through MM and ends the game after MM3.

## Known gaps

Emulator evidence covers the gates above. These remain open in V0.078:

- Wacky Workbench: retail actor order (BLOCK6 train timing) and late frames
  on the Saturn.
- Lost-ring pickup and floor timing after hurts and lag frames.
- QQ1A update 601: era sign timing (retail lag).
- Flowers in TT1/TT2 Present and Past and in WW1 Past exceed their exact-byte
  art limits.
- TT Acts 1-2: water entry splash art.
- MM2A: ET8 generator (et) art is not packed; no stored route draws it.
- Some MM objects written in C read Sonic's size fields by their retail byte
  position (oPriority/oXRadius), while the port stores the named radii. None
  is fixed in V0.078 (for example `src/objects_mm_common.inc:88`).
- R82A attract demo diverges from retail at update 127 (137/2006 equal): the
  BEAM touch box differs. A byte-layout fix matched the demo but broke normal
  MM2 play, so it was reverted.
- Secret sound-test images are missing.
- The pencil test movie is not converted.
- D.A. Garden is not built.
- Animation phases: monitor flicker, ring spin, CC neon, SS searchlight and
  WW mesh.
- SS3/SS4 jump-peak headroom needs console confirmation (SS4 minimum 5.4%).

## Hardware

No V0.078 content has run on hardware. Console acceptance is pending; the last
user-confirmed console build is V0.065. Emulator results do not close the
console gate.

## Console checklist

1. Confirm BIN SHA-256 (full hash above) and the SAROO folder. Cold boot
   V0.078 twice. Record Saturn model, video mode, SAROO firmware and audio
   connection.
2. Play MM1/2 in all four eras and MM3 in both futures. Check layer changes,
   conveyors, springs, badniks, flowers, palette cycles and sprite priority.
3. Beat the MM3 boss. Check Amy, the ending flash, the ALL ZONES CLEAR
   screen and the return to the title.
4. Travel naturally in MM1/2. Check the second before and after each arrival.
5. Enter a special stage from a big ring in each zone. Win, lose on time and
   take a hazard. Check the stone count, the return to the act and the save.
6. Earn Good Future through all seven zones. Check the ending. Cold Continue
   the completed save.
7. Play the earlier six zones again. Check collision, art and frame pacing.
8. Check title/gameplay music and effects, simultaneous playback, pause/resume
   and repeated cold boots. Report anything worse than V0.065 with BIN hash,
   zone, act, era, position, inputs and a photo or video.

Only the maintainer's exact-BIN SAROO evidence closes the console gate.
