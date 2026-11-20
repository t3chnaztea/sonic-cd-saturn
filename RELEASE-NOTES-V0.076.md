# V0.076 — Wacky Workbench and five-zone campaign candidate

Release date label: 2026-10-12. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP
local. They contain assets from the owner's Sonic CD disc.

## Scope

Palmtree Panic, Collision Chaos, Tidal Tempest, Quartz Quadrant, and Wacky
Workbench are the five-zone target. Wacky Workbench covers Acts 1 and 2 in
all four eras and Act 3 in both futures. The hardware acceptance gate remains
open until the maintainer tests the exact BIN on SAROO.

## Changes since V0.075

- Wacky Workbench now has its original zone art, collision, placement stream,
  24 actor routines, Act 3 boss, and earned Good Future progression.
- WW1 A–D, WW2 A–D, and WW3 C/D have controller routes that match complete
  retail host windows across nine fields. WW2A/B routes were searched again
  after the final object timing fixes.
- WW badnik points, flowers, Minomusi, Snake Block children, monitors, ring
  sparkles, and title-card object clocks follow the original update order.
- WW3 Good and Bad Future boss lifts, doors, meca, beam art, and capsule
  sequence now match retail captures.
- The PPZ through WW campaign can continue into Stardust Speedway Act 1.
- Time posts now take effect after Sonic's warp processing, as in the
  original. An active warp timer is no longer reset by a second post.
- PPZ: a badnik hurts Sonic in slot 0 order, and the damaged Tamabboh fire
  cycle matches the original timing.
- TT: actor slots follow the retail allocator (checkpoint ball, flowers,
  door countdown, ring collision order, escalator frameout). All ten TT
  windows now match retail on all nine fields.
- WW2 earned route, WW2 AB/BA/DA travel routes and the WW2C route were
  searched again on the corrected source.

## Candidate evidence

BIN SHA-256: `ba1ffa337f5d7bc1c6bc7db079d86014d5ee0d3e903389a5b0e4258b16b2c539`
Source: commit `2f98ce1`, Makefile V0.076 / 20261012, clean tree.
Full QA run08 passed 177/177 commands on this one BIN (104.5 min):
`build/qa-loops/20261017-012356-757951/report.json`, log
`build/weekend-20261016/full-08.log`.
Zone gates on the same BIN (`build/zone-gates/20261017-024619/report.json`):

| Zone | Retail (nine-field) | Saturn routes | Art | Travel | Campaign |
| --- | --- | --- | --- | --- | --- |
| PPZ | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| CC | 10/10 | 10/10 | 10/10 | 10/10 | 5/5 |
| TT | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| QQ | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| WW | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |

Saturn routes have zero respawns and zero late intervals. The campaign chain
earns Good Future from PPZ through WW and cold-Continues into SS Act 1.

## Hardware

Not yet tested. Emulator results do not close the console gate.

## Console checklist

1. Confirm BIN SHA-256 `ba1ffa33…c539` (full hash above) and the SAROO folder. Boot V0.076 twice.
   Record Saturn model, video mode, SAROO firmware, and audio connection.
2. In WW1 and WW2, play Present, Past, Good Future, and Bad Future. In WW3,
   play both futures. Check springs, rings, monitors, badniks, beams, spark
   blocks, platforms, and the boss/capsule.
3. Travel naturally in each zone. Check the second before and after arrival.
4. Earn Good Future through PPZ, CC, TT, QQ, and WW. Check each handoff and
   a cold Continue into Stardust Speedway Act 1.
5. Play PPZ, CC, TT, and QQ again. Report any new collision, art, audio, or
   frame-pacing defect.
6. Check audible title/gameplay music and effects, simultaneous playback,
   pause/resume, and repeated cold boots.
7. Note anything worse than V0.065, the prior console-tested build. Record
   faults with BIN hash, zone, act, era, position, inputs, and a photo or video.
