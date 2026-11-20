# V0.066 — Quartz Quadrant candidate

Release date label: 2026-09-30. Candidate verification passed on 2026-10-01.
This candidate is ready for local packaging and a Saturn/SAROO console test.
Hardware acceptance remains pending. V0.065 is the last user-confirmed build.
Final normal BIN SHA-256:
`24596e211c97f164bf0b9ce87a82476b86ceb7cb9c1eddc894f4ca9f4757af7c`.
Keep all built images and private release bundles on the local machine.

## Changes

- Quartz Quadrant's background switch keeps the old plane on the switch frame,
  then performs the original `GAME5.C` mapwrtb redraw on frame N+1. The pending
  switch survives until the next displayed snapshot.
- Eligible full redraws split 30 rows between the master and slave SH-2s.
  Cache metadata is committed after both halves complete. Ordinary row fills
  remain synchronous. The slave stops before era loads, title rendering and
  special-stage rendering take ownership.
- Quartz Quadrant sprite palettes follow the original zone colour cycles.
- Route diagnostics record background switches, slave work and overlay faults.
  Overlay faults still stop execution.
- Save tests now include the v2 special-stage index in saved mailbox flags.
  They check legacy v1 imports and an explicit v2 cycle position. The game's
  save format did not change for these verifier corrections.
- Sprite-art verification samples the preceding VDP1 draw palette for stored
  RGB pixels. Indexed priority pixels use current CRAM. Independent capture
  diagnostics rejected the current, two-frame and three-frame RGB samples.
  This correction changed the verifier, not game code.

## Verified evidence

Full QA passed all 161 gates with zero failures:
`build/qa-loops/20261001-030504-286740/report.json`.
The final QQ batch passed with unchanged inputs:
`build/overnight-20260930/qq-final-13/run.json`.
`dist/qq-acceptance.json` binds 83 evidence files to the final image and sources.

All ten QQ act/era routes passed with 78,467 matched host/Saturn positions,
zero respawns and zero late gameplay intervals. Both QQ3 boss futures passed.
The earned TT1 → TT2 → TT3 → QQ1 → QQ2 → QQ3 chain reached WW Continue.
Cold Continue verified the saved checkpoint. The save matrix passed 34 cases.
Save progression and cold-boot persistence passed. Classic save coverage uses
this build's original-rule gameplay; the optional CD++ preset is later roadmap work.

Actual R5 hold/redraw markers verified two Present redraws and four Good
Future redraws. Maximum post-reset work was 21,969 ticks in Present and 19,376
in Good Future, below the 47,355-tick limit. Each redraw followed its hold in
the next target VBlank and completed its slave work. The normal final routes
recorded the same six completions with zero fallback/unavailable events.
`build/overnight-20260930/profile-02/report.json` binds timing, source restoration
and normal executable/disc identity. Only ISO date fields differ between
rebuilds. Boot data, layout, payloads, padding, audio and executable stay bound.
The prior threshold-based 12,164-tick timing claim is withdrawn.

All 50 zone-art programs passed. The ten QQ variants matched 2,196,384 original
sprite pixels across 2,944 captures. R5 host checks matched 81,528,832 original/
native scroll words, ten cache packs and 573,440 retail plane cells. Comparison
exclusions remain documented in the corresponding logs.

QQ lifecycle fixtures passed special-stage entry/return, eight era reloads,
and game-over/title return. The resumed level advanced 120 updates after its
special-stage return. These explicit fixtures do not prove natural time travel.
Additional natural-travel, ring-loss and repeated cold-boot stress runs remain
separate from this initial candidate acceptance and are recorded in the handoff.

## Limits and console checks

Whole-act retail QQ parity remains unproved. WW's cold Continue checkpoint
verifies progression, not a completed WW port. This is not a complete-game release.
Emulator/host results do not establish real Saturn timing or hardware acceptance.

1. Play QQ Acts 1–2 in all four eras. Play Act 3 in both futures through boss,
   capsule, results and the WW handoff.
2. Cross Act 2's background switches in both directions. Watch for missing
   rows, torn tiles, pauses or freezes. Record act, era and location for faults.
3. Exercise era travel, special-stage entry/return and title return from QQ.
4. Save and cold-Continue at each QQ act start. Check the final WW checkpoint.
   Check original movement behavior and preservation of saved progress.
5. Check Japanese music, effects, palette cycles and ring-loss pacing.

Record console model, video mode, SAROO firmware and this candidate hash with
the user's result. Leave the current SD card unchanged until a separate request.
