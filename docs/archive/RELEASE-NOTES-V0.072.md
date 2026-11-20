# V0.072 — dying Sonic priority and Tidal Tempest console candidate

Release date label: 2026-10-03. This is a private Saturn/SAROO test build. The
last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP local;
they contain assets from the owner's Sonic CD disc.

## Changes

- Sonic now queues at his own draw priority, `actwk[0].sprpri`, like every
  other actor (`src/main.c`). It is 2 in play and 0 after death or time over
  (COLI3.C:556). A dying Sonic now draws in front of priority 0 and 1 actors.
  Before this build, native Sonic always queued at priority 2.
- A dying or drowning Sonic now draws in front of high-priority foreground
  cells. The original sets `sproffset` bit 15 in `playdieset` (COLI3.C:555),
  and `actionsub` turns that bit into the sprite priority bit (ACTION.C:322).
  Native Sonic now takes a palette-code lookup table with sprite priority
  register 1 while that bit is set (`src/sonic_view.inc`, `src/main.c`). In
  play, Sonic keeps his normal priority.
- New Tidal Tempest natural time-travel routes: Acts 1 and 2, Present to Past,
  Present to Bad Future, Past to Present, and Bad Future to Present
  (`tools/test_tt_travel.py`, `tests/routes/tt/travel/`).
- New natural-route draw-order audit for Collision Chaos
  (`tools/check_cc_draw_order.py`) and a dying-priority picture test
  (`tools/test_dying_priority.py`).

## Candidate evidence

Final BIN SHA-256:
`ed89c145aaf3da0f24428a4dba712e4be049f611eb8cdc1ea76ab180b4dc2785`.
Full QA passed 165 checks in
`build/qa-loops/20261003-205753-821666/report.json`. Its disc-dependency step
rebuilds the ISO, which changes only ISO timestamps. The CC scroll-target,
entry-scene and EMIE3 checks were rerun on the final BIN and pass.

Dying priority (`build/dying-priority/report.json`): one forced death in a
Palmtree Panic fixture behind high-priority cells, 48 pictures. On this BIN,
461 of 461 Sonic pixels over high-priority cells show Sonic. With the fix
disabled, 461 of 461 showed the foreground cell. Emulator only.

Tidal Tempest on the final BIN, emulator only:

- Sprite art matrix: 10 of 10 programs (`tools/run-tt-art-matrix.sh`).
- Controller routes: 10 of 10 (TT1 A–D, TT2 A–D, TT3 C–D), 0 respawns, 0 late
  intervals. The eight TT1/TT2 routes were searched again with the same seed,
  because the saved V0.065 scripts drowned after later physics changes.
- Continue chain: CC3 → TT1 → TT2 → TT3 → Quartz Quadrant, 4 of 4.
- Natural time travel: 8 of 8 routes (`build/tt-travel/v072/`). Good Future
  to Present has no route.
- R4 boss, capsule and Quartz Quadrant handoff: full-QA step
  `tools/test_tt3_boss_emulator.py`.

## Console checklist

1. Confirm the audio diagnostic version string, the BIN hash above, and the
   SAROO folder. Boot V0.072 twice. Record Saturn model, video mode, and
   SAROO firmware.
2. Collision Chaos: collect a placed ring beside Sonic in Act 2 Past. Watch
   all four sparkle poses. Lose and recollect rings. Check sparkle timing,
   ring count, sound, and frame pacing.
3. Collision Chaos: die on purpose near an enemy or a bumper, and once behind
   foreground scenery. Dying Sonic must draw in front of the actor and the
   scenery for the whole fall. Repeat once in Act 1 and once in Act 2.
4. Tidal Tempest: play Act 1 and Act 2 in all four eras (Present, Past, Good
   Future, Bad Future) and Act 3 in both futures. That is ten variants. Check
   water line, palette, currents, bubbles, enemies, music, and frame pacing.
5. Tidal Tempest time travel: warp Present to Past and Present to Future
   with the time posts. Warp back from Past and from Future to Present. Check
   the warp effect, the arrival era, music, and the first seconds after
   arrival.
6. Tidal Tempest: drown once. Sonic must draw in front of the foreground
   during the drowning fall. Lose a life and check the respawn.
7. Tidal Tempest Act 3: beat the boss in the Good Future and in the Bad
   Future. Open the capsule. Check results and the Quartz Quadrant handoff.
8. Continue: save at a Tidal Tempest act end, power off, cold boot, and
   choose Continue. Check that the next act and era load. Repeat from the
   Collision Chaos Act 3 save into Tidal Tempest Act 1.
9. Note anything worse than V0.065, the prior console-tested build.
10. Record faults with the BIN hash, zone, act, era, position, controller
   inputs, and a photo or video. Console results decide hardware acceptance.

This candidate does not claim full-game completion or Saturn acceptance. Do
not copy it to the SD card without the owner's separate instruction.
