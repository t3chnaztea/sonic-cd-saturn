# V0.069 — Collision Chaos actor palette candidate

Release date label: 2026-10-02. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP
local; they contain assets from the owner's Sonic CD disc.

## Changes

- Collision Chaos Acts 1 and 2 have native Present, Past, Good Future and Bad
  Future stages. Act 3 has both futures, the R3 boss, capsule, results and
  the Tidal Tempest handoff.
- R3 source-derived background line scroll, foreground distortion, Act 2 drum
  animation, palette cycles and object art now run in the native renderer.
- Controller routes cover all ten stage variants. Earned campaigns cover both
  Act 3 futures and cold Continue from their saves.
- Idle and moving entry scenes have fixed-camera original-versus-Saturn
  comparisons in all ten variants. They check Sonic's area and the terrain.
- EMIE3's zone-art CLUT now follows the live palette. Its 16 colors use the
  original video output levels. The R31A frame-360 companion region matches
  the original in 925/925 fixed-offset pixels on the packaged BIN.

## Candidate evidence

Final BIN SHA-256: `0df57c19634d2032d6fb8373ec3398b1d4c99e92a2b326c3b144c7c5022efd26`.
Full QA passed 165 steps: `build/qa-loops/20261002-153600-349326/report.json`.
Fast QA passed 131 steps on the packaged BIN:
`build/qa-loops/20261002-173603-052617/report.json`.
The final-hash EMIE3 comparison is `build/cc-emie-palette/final-report.json`:
925/925 companion pixels and 52,067/52,800 scene pixels match the original.
Private bundle readback is recorded at `build/release-v69-readback.json`.

## Console checklist

1. Boot V0.069 twice. Record Saturn model, video mode and SAROO firmware.
   Check the title and the first Collision Chaos entry for visual faults.
2. Play Collision Chaos Acts 1 and 2 in all four eras. Check each background,
   drum, trap, platform, enemy, music cue and effect against the original.
3. Use the time posts and break the Past generator. Check both Good Future and
   Bad Future paths into Act 3 without level select.
4. Finish both Act 3 futures through boss defeat, capsule, results and the
   Tidal Tempest handoff. Check score, rings, lives and Good Future flags.
5. Cold boot Continue after each earned Act 3 save. Check the era, position,
   score, rings and music after the power cycle.
6. Test fast camera movement, springs, drums and moving supports. Watch for
   one-frame terrain or sprite priority errors, stalls and audio dropouts.
7. Record each fault with build hash, act, era, position, controller inputs
   and a photo or video. Console observations decide hardware acceptance.

This candidate does not claim full-game completion or Saturn acceptance. Do
not copy it to the SD card without the owner's separate instruction.
