# V0.070 — Collision Chaos spring and route candidate

Release date label: 2026-10-03. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP
local; they contain assets from the owner's Sonic CD disc.

## Changes

- Top-contact springs now apply the original ride transition before launch.
  This restores Sonic's standing state. A following spin tag can return him
  to the rolling pose, as in the original Collision Chaos Act 2 Bad Future.
- Palmtree Panic and Collision Chaos controller recordings were regenerated
  for the corrected spring contact. The CC2 Good Future stress route still
  loses at least 30 rings in one update.
- Collision Chaos Act 1 and Act 2 routes cover four eras each. Good and Bad
  Future Act 3 routes beat the boss, clear the capsule, and reach Tidal
  Tempest. Earned saves and cold Continue cover both futures.
- The Act 3 Continue check now uses the saves earned by the current campaign
  run and verifies their disc and source hashes.

## Candidate evidence

Final packaged BIN SHA-256:
`b10ef705860c8e9db4dc7091c2117bff7b562eda90530580e1fb07e98e28d221`.
Full QA passed 165 checks in
`build/qa-loops/20261003-073818-019708/report.json`. Fast QA passed 131
checks on the same BIN in `build/qa-loops/20261003-085710-170788/report.json`.
Both runs include original-derived CC visual and state checks. Full QA also
passes all ten CC controller routes, earned Good and Bad Future Act 3 saves,
cold Continue, zone art and emulator checks.

Final-hash R32D spring frame 440 matches 52,680/52,800 original scene pixels
and all 1,600 Sonic-region pixels. At frame 450, 509/509 selected Sonic-color
pixels match. R31A visible actor/Sonic overlap samples match 900/900 EMIE3
pixels and 772/772 HARI3X spike pixels. The later-motion comparison records
30 constant-Right scenes. Some late raw frames diverge after gameplay timing
differs; its nearby-frame alignment is diagnostic, not a zone-wide visual pass.
`build/cc-motion-scene/report.json`, `build/cc-overlap-priority/report.json`,
and `build/cc-motion-probe/R32D-final-hash/scene-comparison.json` record these
measurements and input hashes. Broader natural-route overlap ordering and
Saturn/SAROO play remain open.

## Console checklist

1. Boot V0.070 twice. Record Saturn model, video mode, and SAROO firmware.
2. Play Palmtree Panic through Collision Chaos. In Collision Chaos Act 2 Bad
   Future, use the spring near [848,760]. Check Sonic's rolling pose after
   the adjacent spin tag and inspect the next camera movement.
3. Play Collision Chaos Acts 1 and 2 in all four eras. Check drums, traps,
   supports, enemies, backgrounds, music, and frame pacing.
4. Earn Good and Bad Future Act 3 through normal play. Beat both bosses,
   open each capsule, and check the Tidal Tempest handoff.
5. Cold boot Continue from each earned Act 3 save. Check era, score, rings,
   lives, music, and the Good Future flag.
6. Record any fault with the build hash, act, era, position, controller
   inputs, and a photo or video. Console results decide hardware acceptance.

This candidate does not claim full-game completion or Saturn acceptance.
Do not copy it to the SD card without the owner's separate instruction.
