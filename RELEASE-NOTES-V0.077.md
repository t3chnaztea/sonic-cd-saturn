# V0.077 — Stardust Speedway and six-zone campaign candidate

Release date label: 2026-10-16. This is a private Saturn/SAROO test build.
The last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP
local. They contain assets from the owner's Sonic CD disc.

## Scope

Add Stardust Speedway to Palmtree Panic, Collision Chaos, Tidal Tempest,
Quartz Quadrant and Wacky Workbench. Cover SS1/2 in all four eras and SS3
in both futures. Earlier zones must pass the same full matrix.

## Implemented changes

- R7 actor registration, layouts, code overlay, original update order and
  camera/collision behavior, including springs and badnik children.
- Original actor, flower and boss art with phase palettes and priority.
- Metal Sonic race, Amy behavior, results and ordinary act transitions.
- Ten stored controller routes, ten natural travel scripts, and an earned
  Good Future campaign harness through SS3 with cold Continue into MM1.
- Six-zone release validation with predecessor report and save-hash checks.

## Candidate evidence

BIN SHA-256: `a745c31e5c18f9428d5bfece945c2dac8c12ff880765925a7b4a7c7ac207a553`
Source: commit `c6950d5`, Makefile V0.077 / 20261016, clean tree.
Full QA run04 passed 185/185 commands on this one BIN (151.5 min):
`build/qa-loops/20261017-092435-947914/report.json`, log
`build/weekend-20261016/v077-full-04.log`.
Zone gates on the same BIN (`build/zone-gates/20261017-111606/report.json`):

| Zone | Retail (nine-field) | Saturn routes | Art | Travel | Campaign |
| --- | --- | --- | --- | --- | --- |
| PPZ | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| CC | 10/10 | 10/10 | 10/10 | 10/10 | 5/5 |
| TT | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| QQ | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| WW | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |
| SS | 10/10 | 10/10 | 10/10 | 10/10 | 3/3 |

The BIN hash was unchanged at the end of the zone gates. The campaign chain
earns Good Future from PPZ through SS and cold-Continues into MM Act 1.
Metallic Madness gameplay and final-game completion are outside this release.

## Hardware

Not yet tested. Emulator results do not close the console gate.

## Console checklist

1. Confirm BIN SHA-256 `a745c31e…a553` (full hash above) and the SAROO folder.
   Cold boot V0.077 twice.
   Record Saturn model, video mode, SAROO firmware and audio connection.
2. Play SS1/2 in all four eras and SS3 in both futures. Check loop layers,
   springs, platforms, badniks, flowers, palette changes and sprite priority.
3. Finish the Metal Sonic race and Amy/results sequence. Check each handoff.
4. Travel naturally in SS1/2. Check the second before and after each arrival.
5. Earn Good Future through zones1–6. Cold Continue into MM1. This entry
   check does not establish Metallic Madness gameplay acceptance.
6. Play the earlier five zones again. Check collision, art and frame pacing.
7. Check title/gameplay music and effects, simultaneous playback, pause/resume
   and repeated cold boots. Report anything worse than V0.065 with BIN hash,
   zone, act, era, position, inputs and a photo or video.

Only the maintainer's exact-BIN SAROO evidence closes the console gate.
