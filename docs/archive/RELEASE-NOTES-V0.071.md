# V0.071 — Collision Chaos ring sparkle candidate

Release date label: 2026-10-03. This is a private Saturn/SAROO test build. The
last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP local;
they contain assets from the owner's Sonic CD disc.

## Changes

- Collected placed and lost rings retain their actor slots through the four
  original sparkle poses. Each pose lasts six updates. The final terminator
  removes the slot after 24 updates.
- Four retail sparkle mapping frames are appended at object atlas indices
  394–397. Collected sparkle draws at priority 1. Earlier object indices stay
  fixed.
- The Palmtree Panic Act 2 Past no-damage controller route was repaired after
  the longer ring lifetime changed its path. It reaches the tally at update
  6,342 and passes 6,342 host/Saturn states with zero late intervals.
- QA now supports `targeted --from-report` for failed or interrupted full runs.
  It runs the failed or next unfinished check and all later checks. Its report
  is partial. A clean full run remains mandatory for a hardware package.

## Candidate evidence

Final BIN SHA-256:
`24c990f519a790527dbffb6d63229dc1872c66859d4bfacd77983781605840a8`.
Full QA passed 165 checks in
`build/qa-loops/20261003-164417-663625/report.json`. Fast QA passed 131
checks on the same BIN in
`build/qa-loops/20261003-180215-489763/report.json`.

The final-hash CC2 Past ring capture is byte-for-byte identical to the
pre-full capture at sequences 418 and 419. In the calibrated comparison,
sequence 418's 1,800-pixel ring/Sonic box improves from 1,350 to 1,410
exact pixels. Sequence 419 improves from 1,740 to 1,800. All 60 changed
pixels match the retail source. The comparison is a sampled, aligned
diagnostic, not a whole-zone visual pass. Evidence and input hashes are in
`build/cc-natural-align/ring/v071-final/report.json`.

## Console checklist

1. Boot V0.071 twice. Record Saturn model, video mode, and SAROO firmware.
2. In Collision Chaos Act 2 Past, collect a placed ring beside Sonic. Watch
   all four sparkle poses and check Sonic/ring overlap and frame pacing.
3. Lose and recollect rings in Collision Chaos. Check sparkle timing, ring
   count, sound, and object visibility under load.
4. Play Collision Chaos Acts 1 and 2 in all four eras. Check drums, traps,
   supports, enemies, backgrounds, music, and frame pacing.
5. Earn Good and Bad Future Act 3 through normal play. Beat both bosses,
   open each capsule, and check the Tidal Tempest handoff. Cold boot Continue
   from each earned save.
6. Record faults with the BIN hash, act, era, position, controller inputs,
   and a photo or video. Console results decide hardware acceptance.

This candidate does not claim full-game completion or Saturn acceptance. Do
not copy it to the SD card without the owner's separate instruction.
