# V0.074 — Tidal Tempest ten-route retail parity

Release date label: 2026-10-05. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP
local. They contain assets from the owner's Sonic CD disc.

## Changes

- All ten Tidal Tempest act and era controller routes match the Sega CD retail
  run for their whole compared windows: TT1 A–D, TT2 A–D, TT3 C/D.
- Tidal Tempest object slots now preserve retail order during ring loss,
  capsule seed spawning, and monitor contact. TT3 water objects and the boss
  follow the retail reference through the results and Quartz Quadrant handoff.
- Stage sprite palette CLUTs refresh on the first draw after a palette change.
  This removed TT3 late frames without changing the displayed colors.
- Level object V-INT state resets on load. The host player replay models the
  retail object-slot map. These keep the player and Saturn traces aligned.
- Re-searched changed Palmtree Panic, Collision Chaos, Tidal Tempest, and
  Quartz Quadrant controller scripts with the existing search tools. No route
  was edited by hand.

## Candidate evidence

Final BIN SHA-256: `253344b446a3683055e9ceb34e0c2e754048eb75e4e48cd4b16ff139a8cf81b0`.
Full QA: `build/qa-loops/20261005-141001-653051/report.json`.

The final V0.074 BIN passed 165 full-QA checks. TT sprite art passed 10/10
programs. TT routes passed 10/10 with whole-window retail matches, zero
respawns, and zero late intervals. Natural travel passed 10/10 with 300
updates after each arrival (`build/tt-travel/v074-final/`). The CC3 → TT1 →
TT2 → TT3 → QQ Continue chain passed 4/4. Earned Good Future campaign
passed TT1–3, including both Past generators, the boss, results, QQ save,
and cold Continue (`build/tt-campaign/v074-final/`). PPZ and QQ each passed
10/10 routes. Full QA passed CC routes, CC campaign, and seed-25 ring-loss
stress on the same BIN. Console acceptance remains pending the maintainer's SAROO test.

## Console checklist

1. Confirm audio diagnostic panel version **V0.040**, the exact BIN hash
   above, and the SAROO folder. Boot V0.074 twice. Record Saturn model,
   video mode, SAROO firmware, and audio connection.
2. Play TT Acts 1 and 2 in Present, Past, Good Future, and Bad Future.
   Play Act 3 in both Futures. Watch water line, bubbles, enemies, moving
   platforms, monitors, and boss. Breathe from a large bubble in each act.
3. Lose rings in TT and check scatter, recovery, sound, and frame pacing.
   Break a monitor while rolling. Ride a platform and step off. Push a block
   and walk away. Watch the TT3 boss and capsule results.
4. Travel naturally in TT from Present to Past and Future, and from both
   Futures back to Present. Watch the first second after each arrival.
5. Earn Good Future by destroying the generators in TT1 and TT2 Past.
   Finish TT3 Good Future. Check the QQ handoff and cold Continue from the
   saved QQ stage.
6. Check stage starts and time travel in PPZ and CC. Check the CC3 → TT
   Continue and the TT3 → QQ → WW handoffs.
7. Test title and gameplay music with effects, pause and resume, and repeated
   cold boots. Note anything worse than V0.065, the prior console-tested
   build. Record faults with BIN hash, zone, act, era, position, inputs, and
   a photo or video.

Console results decide hardware acceptance. Emulator passes do not close it.
