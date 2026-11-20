# V0.075 — Four-zone retail parity (PPZ, CC, TT, QQ)

Release date label: 2026-10-11. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP
local. They contain assets from the owner's Sonic CD disc.

## Scope

Palmtree Panic, Collision Chaos, Tidal Tempest and Quartz Quadrant now meet
the bar that Tidal Tempest set in V0.074. Each zone has ten controller routes
(Acts 1 and 2 in all four eras, Act 3 in both Futures) that match the Sega CD
retail run over their compared windows. Each zone also passes sprite art,
natural time travel and the earned Good Future campaign on one BIN.

## Changes since V0.074

- Title cards hold controls through the original PLC 2 wait in every zone.
  The wait latches at slide-out, as the original queues PLC 2 there. Stored
  routes gained the same neutral lead.
- The retail Object Spawner window walk and object-slot model now run in all
  four zones. PPZ, CC and QQ moved onto the TT spawner. Slot timing follows
  retail for ring sparkles, explosions, title-card pieces, Future animals,
  checkpoint balls and ring-group members.
- The Object Spawner re-initialises on time travel and on the death restart.
- Player_ObjCollide touch arbitration runs in every zone. Monitors break
  before their SolidObject push. Badnik touches use the pre-update state.
- Explosion and flower scripts stay resident. CC and QQ previously read
  bytes from the TT overlay. A link-time zone code audit now fails on any
  unreviewed resident-to-overlay data reference.
- The build fails when a zone terrain include is missing.
- Springs: SolidObject standing on side and diagonal springs in every zone.
  PPZ side springs set ground speed on landing. Diagonal springs land Sonic
  before the launch. A hurt player lands on and is launched by springs.
  Springs relaunch on the 13th update.
- Ring pickup uses the retail pcol box. Lost rings collect only below flash
  90. Broken monitors and used posts reload as retail.
- CC fixes: bumper axis and aim, COLI3 rebound and hari3x spikes, tentou
  wake range, flipper rider, breakable-bumper update skip.
- TT fixes: WALL42 frame-out, unsigned AWA and tagameb range tests, tonbo
  init, R4 actor flip bits.
- QQ fixes: DAI_RD5 frame-out, monitor touch order, boss bounce, conveyor
  belt blank-chunk read.
- PPZ fixes: Tamabboh range and missile, spin-tunnel doors, Anton and
  Tamabboh placement, Taga-Taga timing, broken walls and collapsed platforms
  stay unloaded, ring records reload after full collection.
- Physics: skid high-byte test, roll-right $80 boundary, collapsing pieces
  not solid on their first update, powerup timers after Sonic moves.
- Frame time: cheaper per-update object scans, Sonic pose prefetch during the
  VDP1 wait, and once-per-group ring slot sync. TT3C and CC2C report 0 late.
- Controller routes were re-searched with the existing search tools after
  each retail fix. No route was edited by hand.

## Known deviations

- Classic mode keeps the Down+Jump spin dash buffer.
- Warp-out freezes 19 updates before arrival in the new era.
- TT3 Act 3 capsule shower has thin frame headroom: 3.9k FRT ticks minimum
  slack of a 47,740-tick deadline. This is the first scene to check on
  SAROO.

## Candidate evidence

Final BIN SHA-256: `b3fd1a04b370ff3424a60c6885caaf3bac02e4f04586e19d55c6300974167ad2`.
Full QA: `build/qa-loops/20261011-191109-200260/report.json` (172/172 steps
PASS, head fb6000c).

| Gate | PPZ | CC | TT | QQ |
| --- | --- | --- | --- | --- |
| Retail parity routes | 10/10 | 10/10 | 10/10 | 10/10 |
| Saturn routes | 10/10 | 10/10 | 10/10 | 10/10 |
| Sprite art | 10/10 | 10/10 | 10/10 | 10/10 |
| Natural travel | 10/10 | 10/10 | 10/10 | 10/10 |
| Earned campaign | 3/3 | 5/5 | 3/3 | 3/3 |

Zone gates: 174/174 PASS in the full-QA zones step on the final BIN
(`build/zone-gates/20261011-203415/report.json`). Player traces passed in the
same run.

The release BIN differs from the earlier full-QA evidence BIN `6b34fde8…`
(full QA `build/qa-loops/20261011-170949-675350/report.json`) only in the
IP header version and date, the ISO9660 dates written at build time, and the
sector EDC/ECC derived from them: 423 bytes, zero file-payload bytes. The
classify script used was a session-scratchpad `classify.py` (not kept).

Private package: `build/hardware-v0.075/`. The V0.074 package lives in the
main checkout's `build/hardware-v0.074`, so this worktree's readback reports
`previous_preserved_verified: null`.

## Hardware

Not yet tested. SAROO console test pending (The maintainer). Console results decide
hardware acceptance. Emulator passes do not close it.

## Console checklist

1. Confirm the exact BIN hash above and the SAROO folder. Boot V0.075
   twice. Record Saturn model, video mode, SAROO firmware, and audio
   connection.
2. Play TT3 Good Future and Bad Future to the capsule. Watch the capsule
   shower for slowdown or late frames.
3. In each of PPZ, CC, TT and QQ, play Act 1 and Act 2 in Present, Past, Good
   Future and Bad Future. Watch the title card, springs, monitors, rings and
   badnik explosions.
4. Travel naturally from Present to Past and Future in each zone. Watch the
   last second before and the first second after each arrival.
5. Earn Good Future through PPZ, CC, TT and QQ. Check each zone handoff and
   a cold Continue.
6. Lose rings and recover them in each zone. Check scatter, sound and frame
   pacing.
7. Note anything worse than V0.065, the prior console-tested build. Record
   faults with BIN hash, zone, act, era, position, inputs, and a photo or
   video.
