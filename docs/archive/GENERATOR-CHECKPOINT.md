# Day-end checkpoint — 2026-09-21

Paused at the user's request to restart. Do not resume development until asked.
The full Collision Chaos Act 1 goal remains unfinished: all four eras, remaining
actors and children, terrain animation, original backgrounds/foreground raster,
ordinary travel and Good Future creation, Act 2 progression with campaign saves,
Japanese music preservation, source comparison and hardware-test packaging.

Current development BIN (4,821 sectors):
`fc9cde4e2909efb6b66ab0c8d562bfb73eeebc2e7eba6f5fd27e32f6bf850eb0`.
BIN/CUE/ELF, reports and PPZ raw traces are copied under
`build/cc1/generator-checkpoint-20260921/`; the sibling JSON indexes their hashes.
This is not a hardware-accepted V0.061 release. Earlier V0.059/V0.060 packages
and the accepted pocket snapshot remain untouched. Frame profiling is off.
Do not modify or stage preexisting untracked `tools/scroll/`.

## Implemented in this checkpoint

- Native CC generator type 86, original CC1 placement (4992,624) and CC2
  placement (3168,621), Present/Past only. CC1 now has 608 records and
  A/B/C/D counts 489/471/474/474. Shared PPZ generators remain type 45;
  the translator regression that initially dropped them is fixed.
- Console hover, attack contact, 1,500 points, Good Future event, all 21 timed
  explosions, allocation failure/order, breakdown and restored broken pose.
  The console clears both collision bytes, copies integer child coordinates,
  and defers explosion initialization to normal dispatch; PC ET3.C differs.
- Complete normalized 468-byte routine proof across all ten CC programs and
  PPZ baseline, exact mappings/event table and console tile bases 830/874.
  `tools/cc_generator_source.py` and `build/cc1/generator/retail.json`.
- Correct Present withered artwork plus existing Past artwork, 394 static
  frames / 351,552 raw bytes. Generic camera-2048 captures loaded the wrong
  section bank; accepted captures use actual placement cameras 4832/3008 in
  `build/cc1/generator/art-placement/`. Old `art/` fixtures are invalid.
- One CD sector moved from FLOOR capacity to OBJART capacity: OBJART begins
  at 0x275800 and ends at unchanged 0x2AE000. All pack bounds pass.
- Fixed the original PPZ1 X<0x900 travel restriction incorrectly affecting
  every zone's Act 1. `scd_world_zone` is set on new games, level select/Continue,
  and campaign zone changes. The original Sonic/Main.asm tests full zoneAct=0.
  Host/SH-2 world QA now checks both boundary positions, all seven zones,
  both first acts and all four eras, including returning to PPZ context.

## Verification completed

- 52 fast gates passed: `build/qa-loops/20260921-154237-544298/report.json`.
  The two added overlapping generator frames and world verifier counts were
  updated explicitly; existing first-piece-wins pixel assertions remain.
- Generator reference comparison: 39,850,302 assertions, 757,397 updates,
  378,144 attack/contact cases; allocation failure and earlier/later slots.
- Source art: 81,920 exact pixels. Actual Saturn generator sprite builder:
  64 pictures / 327,680 exact pixels, all reachable poses and flips in both acts.
  Visually reviewed `build/cc1/generator/target/review.png`.
- Main/player: 16,800 exact host/reference/SH-2 states; Japanese audio passed.
- Target world semantics, power-ups and their pixel checks passed. The first
  world postprocessor stopped at stale object-frame count 382; corrected to
  384 and reran the postprocessors on the completed raw target capture.
- All eight save/progression/cold-boot checks passed on the current BIN.
- PPZ Acts 1–3 passed: 3,861 / 5,189 / 2,862 matched states. Their archived
  timing logs measure 11,909 total gameplay intervals, zero late refreshes.
- Present CC1 ordinary route passed 18,000 observations, no respawns or late
  refreshes, reaching Act 2. Past sweep was stopped for restart; C/D not run.
  Do not accept the mutable Past report beside its interrupted results.log.
  Rerun B/C/D before `tools/check_cc_routes.py` acceptance. Previous complete
  four-era evidence remains in the immutable pocket snapshot, on its older BIN.

## Resume work

No background test process was intentionally left running. PPZ chain ended 0;
route chain/session 9029 was terminated (143), including its Python and emulator
children. Main/audio/world chain ended 1 only for the corrected stale count;
world postprocessing/save chain subsequently ended 0. Target generator art ended 0.

First finish current-build regressions: rerun CC1 B/C/D ordinary routes, the ten
CC artwork variants with `tools/test_zone_art_emulator.py`, and Past ring-loss
stress using a fresh output directory. Preserve matched evidence and avoid
calling this full goal completion. Probe route options are recorded in
NEXT-SESSION.md; `tools/check_cc_routes.py` documents its limits.

The main gameplay gap is still an ordinary generator destruction route, followed
by natural time travel/Good Future, Act 2 and saved Continue. Existing Past route
passes generator X at Y1260, far below Y624. Single jump points in the earlier
towers did not reach the upper platform. No teleport/write-based proof is accepted.

Exploratory local route simulator files and logs are under `build/cc1/generator/`:
`route-host-replay.c`, `route-host-explore.c`, `route-host-staged.c`, executable
`route-host`, `host-*.log`/JSON and `route-map.py`/`past-route-map.png`.
These are research fixtures, not production or completed source-parity tests.
The replay matched target positions through sequence 4000 exactly: target pad
commands take effect two observed updates later, and title controls unlock at
sequence 131. Its baseline policy also matched sampled target commands/positions.
It currently simulates only Past gameplay, not world travel/act transitions.

Useful route finding: at sequence 3457, x5621, the spring at (5616,1226) lifts
Sonic. Hold Left once x>=5680 and y<700. Falling into the upper loop then hits
left-facing spring (5800,976); its -4096 velocity takes Sonic up the inner left
wall. Sequence 3615 exits near (5683,752), apex ~Y276, then crosses x5169 at Y658,
just short of landing on generator platform ending x5120 at Y640. Continuing
Left lands on middle path ~Y884. Jumping from that inner left wall launches
RIGHT (normal points into loop), so that attempted shortcut failed. A staged
braking/landing/spindash experiment also failed; inspect host-staged.log before
trying another route. No such new Left/Down route is in the Saturn harness yet.
An alternative is ordinary Present→Past travel near a better upper approach.

Remaining original actors include hari3x, emie3, movie and round-specific friend;
shared enemy score/flower behavior, mixed-family collision ordering/offscreen
lifecycle, original terrain animation and native raster integration also remain.
Existing retail raster captures are research evidence, not implemented scrolling.
