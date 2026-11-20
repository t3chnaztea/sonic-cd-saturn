# V0.068 — Collision Chaos console test candidate

Local console test candidate. Full and fast QA passed on the packaged BIN.

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

## Candidate evidence

Final BIN SHA-256: `e9bd5599a1b14250e9d8206524754835b8652aa1c894c380b6325fb5f1817f3e`.
Full QA report: `build/qa-loops/20261002-131002-876416/report.json` (165 steps).
Fast QA report: `build/qa-loops/20261002-143511-141346/report.json` (130 steps).
Private readback: `build/release-v68-readback.json` (526 members, ten CC routes).
Private ZIP SHA-256: `193f8463cec9ee60952dca50b72ae22fe0f1107961c1eda750c11ea44488f12f`.
The final packaged BIN passed all ten level-entry scenes with
520,933/528,000 exact pixels below the HUD and 15,733/16,000 exact pixels in
Sonic's area. Ten moving entry scenes matched 518,924/528,000 scene pixels
and 15,594/16,000 Sonic-area pixels. The live VDP2 scroll and map gates passed
all ten variants.
The final-hash fast run repeated the visual gates after disc packaging.

## Console checklist

1. Boot V0.068 twice. Record Saturn model, video mode and SAROO firmware.
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
