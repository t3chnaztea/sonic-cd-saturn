# Sonic CD Saturn implementation and QA loops

## Quick reference

Purpose: the build/test/fix loop and gate rules for every slice of the port.
`tools/bundle.py` copies this file into `dist/`. `tools/preserve-release.py`
compares that copy byte-for-byte with this file, so rebuild `dist/` after an edit.

Scope is the full port in `PORT-ROADMAP.md`. Per-zone gate ledgers:
`PALMTREE-PANIC-PLAN.md`, `COLLISION-CHAOS-PLAN.md`. Current build and latest
QA results: top of `NEXT-SESSION.md`.

Commands:

- Fast gates: `python3 tools/qa-loop.py fast 2>&1 | tail -n 30`.
- Full gates (stop at first failure, never retry automatically):
  `python3 tools/qa-loop.py full 2>&1 | tail -n 30`.
- Resume a failed full run: `python3 tools/qa-loop.py targeted --from-report <report>`
  reruns the failed or next unfinished check and every later one. The result is
  partial. See `docs/qa-targeted.md`.
- Player traces: `bash tools/test-player.sh`. Regenerate references with the script only.
- Pacing: `bash tools/test-pacing.sh <cue> <out-dir>`. See `PERFORMANCE.md`.

Binding rules:

- Follow the execution loop below. One bounded feature, with a test that can fail.
- Report the `PASS:`/`FAIL:` line verbatim. Bind every report to the final BIN SHA-256.
  Record build hash, input hashes and outcome; mark runs pending, then failed or interrupted.
- No blind retries. Never weaken an assertion to accept new output. A baseline
  change needs source evidence and a documented reason.
- Host/reference agreement is not original-console parity. Emulator passes never
  close a hardware gate. Record console results as in "Hardware result record".
- Each hardware build needs a new `IP_VERSION`/`IP_RELEASE_DATE` and release notes.

Open items:

- Hardware: the last user-confirmed console result is V0.065
  (`hardware-results/v0.065.json`). Newer candidates await console evidence.
- The feature-gate table below is the Palmtree Panic V0.015-era snapshot. Current
  zone status lives in the zone ledgers above.
- PPZ-QA-002 (reactive route timers clock on display refreshes) is open in `PALMTREE-BUGS.md`.

## Execution loop

1. Read the pinned original behavior/data and record the intended invariant.
2. Implement one bounded feature and a test that can expose its failure.
3. Run the affected asset and sanitized host tests. Investigate the first failure, fix its cause, and repeat those checks.
4. Build the Saturn disc and run target/emulator tests. Investigate mismatches or visual/audio failures; return to step 2 with a specific correction.
5. Inspect captures, bind validation reports to the final disc hash, and package only after all required automated gates pass.

No blind retries and no repeating a passing suite without a relevant change. Never weaken an assertion solely to accept new output. A baseline change requires source evidence and a documented reason. Host/reference agreement shares frontends and is not independent original-console parity.

## Feature gates

| Gate | Required evidence | Current status |
| --- | --- | --- |
| Inventory | Source ID/name, placement/era counts, subtype and asset mappings for every PPZ1 record | 497 records / 33 IDs inventoried; partial imports explicit |
| Enemies | All five species and damaged variants; motion/turn/attack sequences, attack versus hurt, projectiles, cleanup, good-future suppression, bounded pool | Implemented; sanitized host and SH-2 semantic probe pass. Original-console parity unverified |
| Backgrounds | All four eras; original scroll regions, tile/palette animation, priority, matched camera captures, seams and era restoration | Raster/palette fixtures and four-era emulator scenes pass; ramp offsets have signed/fractional/stationary-camera host fixtures; full original-console visual comparison remains |
| Ramps | Source placement/secondary subtype, booster direction and timer, terrain entry/exit, plants, camera offsets and a route from spawn | Sanitized 900-tick spawn route and controller-driven SH-2 route pass, including entry/climb/exit captures and nonzero scroll offset |
| Platforms | All original floating-block eras and platform subtypes; standing, carry, jump/step-off, hurt landing, disappear/fall/reload, original-placement controller routes | Sanitized host, SH-2 semantic probe and four original-placement controller routes pass, including deferred reload after leaving/returning |
| Travel | Sign activation, speed qualification/cancel, valid destination, round trips, state carry/persistence, arrival geometry and music change | State-machine directions/cancellation and collision-safe arrival pass; emulator controller fixture completes past-to-present travel. Checkpoint identity/respawn across era changes is covered; one full Present route passes; subsequent-act progression remains outside this build |
| Walls/spikes | All original walls/subtypes/eras, attack versus ordinary contact, source debris, pool exhaustion and reload; upright/inverted/protected spike collision | Sanitized host and SH-2 semantics pass; controller routes cross the three original Past walls and two Present walls, with intact/break/passed captures reviewed |
| Checkpoints | Original placement/palette/contact bounds, ball animation, monotonic activation, saved time/position, era/death lifecycle and zero lives | Sanitized host and SH-2 probes pass; controller route activates at frame 6337, dies at 6348 and restores X=2740/tick 32 with two lives at 6571; active checkpoint reload capture reviewed |
| Regression | Existing terrain/player/contact tests plus new semantic cases on host and SH-2 | 16,800 existing states retained; new cross-target world probe and 32 spring contact cases pass |
| Monitors/power-ups | All 35 monitor records; break/bump/solid/pool/consumed lifecycle; grants and timer boundaries; original art/music | 75 host placement/era lifecycle cases and shared SH-2 semantics pass; all five controller rewards, shield/stars captures, once-only special music and expiration/restoration pass |
| Complete Present route | Untouched spawn/inventory/placements, actual controller inputs, no warp or reset, all finish phases, exact sanitized host replay and results pixels | Final-disc gate passes 4,224 states / 67,584 words, 59-second finish and 5,500 points |
| Collapsing platforms | All nine original records/21 era instances; source art, piece counts/timers/velocity/order, pool/rider/reload/sound rules | Host/SH-2 semantics and four era controller fixtures pass; 12 intact/break/fallen captures reviewed |
| Packaging | Current hash-bound reports, visual inspection, paired BIN/CUE and ZIP verification | All 12 final gates pass; seven hash-bound reports and 92 captures; ZIP CRC and every archived file match the staged build; V0.015 preserved |
| Hardware | Sound probes, ordinary gameplay and travel, smooth scrolling, measured pacing on Saturn/SAROO | Awaiting console test; emulator cannot satisfy |

## Test strategy

Keep existing terrain fixtures isolated from newly imported placements. Add object fixtures for every enemy species, defeat/hurt contacts, both projectile directions, offscreen cleanup, and a damage burst at pool capacity. Test travel as a pure state machine first, then with loaded destination geometry and controller input in the final image. Check inventory survives only the transitions specified by the source.

Background checks should verify tile selection and scroll values against source-derived fixtures and inspect screenshots at spawn, high/low scenery, loop, right boundary and seams. A nonblank screenshot is insufficient. Exercise animation across multiple frames and every era. Include new texture and command-list peaks in capacity assertions.

Run fast gates through `tools/qa-loop.py fast`; run the complete automated gate list through `tools/qa-loop.py full`. The runner records each command, exit status, duration and log, stops on the first failure, and never retries it automatically. Fix the failure and rerun the appropriate gate. Reports from the final disc remain the release authority.

## Hardware result record

Record build/hash, Saturn region/video mode, SAROO firmware and audio connection. Test Start+Z A/B/C probes and note DRIVER/DATA/RAM/RUN/CD INIT/TOC. Verify crouch/dash/HUD, enemies, background scrolling and legal travel round trips. Retain failed object era/location and transition steps. Pending hardware checks must stay pending in delivery notes.

## History

Per-version QA runs (V0.010–V0.040), the old Palmtree-Panic-only scope note,
and earlier loop findings moved verbatim to
[docs/archive/QA-PLAN-HISTORY.md](docs/archive/QA-PLAN-HISTORY.md).
