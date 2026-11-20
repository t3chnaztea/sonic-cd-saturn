# V0.067 — Palmtree Panic console test candidate

Release date label: 2026-10-01. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Hardware acceptance of this
candidate is pending. Keep the BIN/CUE and ZIP local; they contain assets from
the owner's Sonic CD disc.

## Changes

- Palmtree Panic's placement stream now rejects distant placements before
  checking object-specific rules. A repeated Act 1 Bad Future two-VBlank
  gameplay interval cleared without changing the controller route or physics.
- Deterministic controller scripts now cover Act 1 Present, Past, Good Future
  and Bad Future. The default Act 1 replay checks all four.
- Earlier PPZ presentation work remains in this build: corrected title VRAM
  timing, monitor icon composition and sprite/terrain draw synchronization.
  These need console checks because emulator results cannot resolve the V0.044
  hardware reports.

## Candidate evidence

Final BIN SHA-256:
`7d8587edef7fad8aa106dd3870d1b884216c17c616e804463cd3c87ff61ccfbd`.
All ten PPZ controller routes passed on this exact full-QA BIN with zero
respawns, zero late gameplay intervals and the expected act handoffs. The
stream differential matched 81,920 source-state comparisons. The packaging
step verifies and includes each route report and controller script.
Fast QA passed: `build/qa-loops/20261001-194508-895434/report.json`.
Full QA passed 162 gates: `build/qa-loops/20261001-213616-908522/report.json`.
The private bundle readback verified 471 members, including the final-hash BIN,
full-QA report, ten PPZ route reports and ten controller scripts. The package
remains local. Saturn/SAROO acceptance is pending.

## Console checklist

1. Boot V0.067 twice. Record Saturn model, video mode and SAROO firmware.
   Check title clouds for vertical lines on both boots.
2. Enter Palmtree Panic from NEW GAME. Play Act 1 and Act 2 in each reachable
   era. Check the four era-specific backgrounds, scenery, music and effects.
3. Break each monitor subtype found. Check the icon before the hit, during the
   break and as the item rises. Record act, era, location and subtype for a
   black or wrong icon.
4. Cross the reported brick platform both without touching it and while
   standing on it. Record location and whether visibility matches the original.
5. Test fast upward and downward camera movement near springs, slopes and
   moving supports. Watch for one-frame sprite/terrain drift or stalls.
6. Use Past and Future posts naturally. Finish both Act 3 futures through the
   boss, capsule, results and Collision Chaos handoff. Test death, checkpoint,
   pause/resume and special-stage return.
7. Record every fault with build hash, act, era, position, controller inputs and
   a photo or video. Console observations decide hardware acceptance.

This is a Palmtree Panic test candidate. Full-game completion and hardware
acceptance are not claimed. Do not copy it to the SD card without the owner's
separate instruction.
