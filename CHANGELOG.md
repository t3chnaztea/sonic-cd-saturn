# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version numbers are
the disc `IP_VERSION` in the [Makefile](Makefile). They are build numbers, not
[Semantic Versioning](https://semver.org/).

Dates are the release date label in each version's release notes, or the
`IP_RELEASE_DATE` in the Makefile. A version without a recorded date has none.
No built image is distributed for any version. Every build is made from the
owner's own discs.

"Emulator" means the Beetle Saturn gates. Only a console test on a real Saturn
confirms a build. The last console-confirmed build is **V0.065**.

Full notes for each version are in `RELEASE-NOTES-V<version>.md`, in the
repository root or in [docs/archive/](docs/archive/). Each version heading
links to its notes.

## [Unreleased]

## [V0.082](RELEASE-NOTES-V0.082.md) - 2026-11-17

Software regression completed on 2026-11-19: 215/215 checks, 347/347 matrix
windows, and 70 art cases with zero misses. Hardware acceptance remains open.
The tested game source is `49bfd89`. BIN SHA-256:
`cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66`.

The release preserves the accumulated baseline and fixes the Source18
disc-dependency probe. The QA startup accepts V0.082's complete declared
scope. The release notes distinguish retained evidence, resumed execution,
and the bound audit view. Full-game path coverage remains unverified.

The 2026-11-20 local handoff adds a browser patcher preview. Its downloaded
BIN/CUE match the accepted candidate. The required private delta includes
converted game data and must not be distributed. Public payload preparation,
remote publication, and console acceptance remain separate open items.

## [V0.080] - 2026-10-25

Launch build: the secret sound-test pictures, save safety, retail gap fixes
and a public source tree that builds the same BIN from a fresh clone.
Full QA 201/201. Console test pending (Monday). BIN SHA-256
`7bbce369beba939b9f30f2a85d847a5b2623d419ecdc327a0a89e949f8c05338`.

### Added

- The five secret sound-test pictures ("Fun is infinite", M.C. Sonic, Tails,
  Batman, Cute Sonic) from NISI.MMD and DUMMY0-3.MMD on your disc, each
  compared with retail pixel for pixel.
- Time Attack records are stored as a torn-write-safe file pair per preset
  (`SCDSATURNTA`/`TB`, `SCDSATURNTP`/`TQ`). V0.079 records still load.
- `tools/export-public.py`: exports HEAD as one audited commit (no retail
  code bytes, private paths, disc files or secrets).
- `tools/prepare_retail.py`, and a zone harvest that creates its own manifest,
  so a fresh clone builds with the README steps alone.
- Tidal Tempest Acts 1-2 water entry splash; badnik flowers in TT1/TT2
  Present and Past and WW1 Past; the MM2A ET8 generator art.
- `tools/cdpp_fuzz.py` in fast QA: CD++ moves fuzzed on every zone's host.

### Changed

- RESET is held off during every backup write, and a save slot that cannot be
  read is never overwritten with a lower generation.
- Collision Chaos lost rings start in the hurt's own update and are collected
  with the retail box; every zone uses one global 255-update spill timer.
- Collision Chaos Act 1 hari3x spikes hurt Sonic once, also with 31 or more
  objects loaded.
- Metallic Madness Act 2 BEAM uses Sonic's X radius for its Y half-size, as
  retail does. The R82A attract demo now equals retail.
- The test tools read retail code from your disc by SHA-256 instead of
  holding its bytes.
- Builds are reproducible: fixed ISO dates (`IP_RELEASE_DATE` or
  `SOURCE_DATE_EPOCH`) and no checkout path in libyaul. A stale zone harvest
  is re-extracted before its packs are installed.
- Private notes (handoffs, parked patches, agent plans) left the tracked tree.
- Animation phases match retail: ring spin, monitor flicker, zone palette
  cycles (CC neon) restarting with each level program, Stardust Speedway
  searchlights and animated tiles (WW mesh) restarting on death.
- Hardware guards: overlay and stage-pack reads retry before the CD error
  screen, the movie preload times out after 10 s, the QQ and D.A. Garden
  slave-CPU waits have master fallbacks, VDP1 overruns are counted, a build
  check keeps the CD sector buffer aligned, and the movie mailbox is cleared
  at each movie start.
- CD++: attract demos always run Classic, and the homing attack yields when an
  object takes over Sonic's speed.

## [V0.079] - 2026-10-24

The complete front end, credits and endings, and an optional CD++-style preset.
Full QA pending. Console test pending (Monday). BIN SHA-256 `<BIN-SHA256>`.

### Added

- D.A. Garden: the native program with its track list (Japanese titles) and
  looping music, checked against a retail oracle and emulator routes.
- Visual Mode: the retail menu screen and flow (VM____.MMD), with the opening,
  both endings and the pencil test.
- The pencil-test movie (PTEST.STM), converted and checked against retail.
- Credits and endings: the staff roll, the end screens and the "PRESENTED BY
  SEGA" card from ENDING.MMD, the "Thank You" screen (THANKS_M.MMD) after
  Visual Mode's good ending, and the Special Stage 8 credits. Results are in
  [docs/CREDITS-AUDIT.md](docs/CREDITS-AUDIT.md).
- CD++ preset: Sonic 2 spin dash, no air speed cap, air roll, homing attack and
  mini Sonic spin dash, behind one setting in RAM Data. Saved in its own
  backup file (`SCDSATURNCF`). Time Attack keeps CD++ records apart
  (`SCDSATURNTP`). Classic stays the default. Spec:
  [docs/CDPP-PRESET-SPEC.md](docs/CDPP-PRESET-SPEC.md).
- CD++ tests: host traces, the settings codec, the Saturn toggle and one
  emulator route per move.
- GitHub project files: contributing guide, code of conduct, security policy,
  issue and pull request templates, and asset-free CI.
- `tools/release.py`: builds a source-only release package (docs, build
  instructions, tested BIN SHA-256, manifest) and refuses disc images,
  BIOS files, audio and private or build paths. `--local-saroo` writes your
  own BIN/CUE to a local SAROO folder.

### Changed

- The ending movies stop where ENDING.MMD stops, and the staff roll runs on
  retail time. The Japanese roll was 9% slow and missed some text tiles.
- README rewritten for the GitHub release, with a CD++ section, a "How this
  was checked" section and a credit to a related Saturn port.

## [V0.078] - 2026-10-18

Metallic Madness, special stages and the seven-zone campaign. Console test
pending. BIN SHA-256 `11b162218b49201b51cf9fc6d205844731c5bd49079abce76a6cc9347187f4a6`.

### Added

- Metallic Madness: Acts 1 and 2 in all four eras and Act 3 in both futures.
  Original actor registration (ids 157-188), retail layouts and record order,
  a zone code overlay, the original update order, layer collision, springs,
  time posts and score popups.
- Original Metallic Madness actor, flower, boss and Amy art, with phase
  palettes and draw priority.
- The Metal Sonic fight, the ending control, and the game end: a completed
  save, the ALL ZONES CLEAR screen and the return to the title.
- Special stages 1-8, entered from the big ring in every zone. Win, time-out
  and hazard cases match retail routes. Time Stones and the current special
  stage save. Both endings (Time Stones or Good Futures) play the ending
  movie. The seven-stone return works.
- Time Attack menu, runs, records and unlocks. Attract demos.
- The retail CD-DA tracks that were missing (Time Attack, game over, D.A.
  Garden, intro, ending, warp), copied from the Japanese disc. The disc now has
  42 tracks.
- Ten stored Metallic Madness controller routes, ten natural time-travel
  scripts, and an earned Good Future campaign from NEW GAME through Metallic
  Madness Act 3 with a cold Continue.

### Verified (emulator)

- Full QA: 187 of 187 commands pass on one BIN.
- All seven zones: 10/10 retail-match routes, 10/10 Saturn routes, 10/10 time
  travel, and full art (12/12 in Metallic Madness). Campaign gates 3/3 per zone
  (5/5 in Collision Chaos).
- Special-stage and front-end cases: 42 of 42.
- The campaign earns Good Future from Palmtree Panic through Metallic Madness
  and ends the game after Act 3.

### Known issues

- Wacky Workbench: retail actor order (train timing) and late frames.
- Lost-ring pickup and floor timing after a hit or a lag frame.
- Quartz Quadrant Act 1 Past: era sign timing.
- Flowers in Tidal Tempest Acts 1-2 (Present, Past) and Wacky Workbench Act 1
  Past exceed their art budget.
- Tidal Tempest Acts 1-2: no water-entry splash art.
- Metallic Madness Act 2 Past: one generator's art is not packed.
- Some Metallic Madness objects read Sonic's size by its retail byte position.
- The Metallic Madness Act 2 attract demo diverges from retail at update 127.
- Some animation phases differ: monitor flicker, ring spin, Collision Chaos
  neon, Stardust Speedway searchlights, Wacky Workbench mesh.
- Secret sound-test images are missing. The pencil-test movie is not
  converted. D.A. Garden is not built.
- Stardust Speedway special-stage jump headroom needs a console check.

## [V0.077] - 2026-10-16

Stardust Speedway and the six-zone campaign. Console test pending.

### Added

- Stardust Speedway: Acts 1 and 2 in all four eras and Act 3 in both futures,
  with original actors, layouts, a code overlay, camera, collision, springs and
  badniks.
- Original Stardust Speedway actor, flower and boss art. The Metal Sonic race,
  Amy, results and act transitions.

## [V0.076] - 2026-10-12

Wacky Workbench and the five-zone campaign. Console test pending.

### Added

- Wacky Workbench: original zone art, collision, placement stream, 24 actor
  routines, the Act 3 boss and earned Good Future progression.
- Controller routes for all ten Wacky Workbench act/era variants.

## [V0.075] - 2026-10-11

Four-zone retail parity. Console test pending.

### Changed

- Palmtree Panic, Collision Chaos, Tidal Tempest and Quartz Quadrant each have
  ten controller routes that match the Sega CD retail run, plus art, natural
  time-travel and earned Good Future campaign gates on one BIN.
- Title cards hold controls through the original wait in every zone.

## [V0.074] - 2026-10-05

Tidal Tempest ten-route retail parity. Console test pending.

### Changed

- All ten Tidal Tempest controller routes match the retail run.
- Object slots keep retail order during ring loss, capsule seed spawns and
  monitor contact.
- Sprite palettes refresh on the first draw after a palette change. This
  removed Tidal Tempest Act 3 late frames.

## [V0.073] - 2026-10-04

### Fixed

- Player physics and object fixes found by running retail Tidal Tempest beside
  the port. Sonic starts each stage grounded, as in the original. These shared
  code paths affect all four zones ported at the time.

## [V0.072] - 2026-10-03

### Fixed

- A dying or drowning Sonic now draws at his own priority and in front of
  high-priority foreground cells, as in the original.
- Tidal Tempest console test candidate.

## [V0.071] - 2026-10-03

### Fixed

- Collected rings keep their actor slots through the four original sparkle
  poses.

### Added

- QA: `targeted --from-report` resumes a failed or interrupted full run.

## [V0.070] - 2026-10-03

### Fixed

- Top-contact springs apply the original ride transition before launch.
  Collision Chaos routes were re-recorded for it.

## [V0.069] - 2026-10-02

### Fixed

- Collision Chaos actor palettes: the EMIE3 zone-art palette follows the live
  palette.

## [V0.068] - 2026-10-02

Collision Chaos console test candidate.

### Added

- Collision Chaos Acts 1 and 2 in all four eras and Act 3 in both futures,
  with the boss, capsule, results and the Tidal Tempest handoff.
- Original background line scroll, foreground distortion, drum animation,
  palette cycles and object art.

## [V0.067] - 2026-10-01

Palmtree Panic console test candidate.

### Fixed

- The Palmtree Panic placement stream rejects distant placements first. This
  cleared a repeated late interval in Act 1 Bad Future.

### Added

- Controller scripts for Act 1 in all four eras.

## [V0.066] - 2026-09-30

Quartz Quadrant candidate.

### Changed

- The Quartz Quadrant background switch follows the original redraw timing.
- Full background redraws split between the two SH-2 CPUs.

## [V0.065] - 2026-09-26

Tidal Tempest and the original player physics. **Confirmed on a real Saturn
with SAROO** (report: "works, no new defects").

### Added

- Tidal Tempest Acts 1-3 and the boss, with water, the original vertical and
  horizontal cameras, looping levels and zone art cycling.

### Changed

- Palmtree Panic and Collision Chaos run the original player physics and
  camera.

## [V0.064] - 2026-09-25

### Added

- Collision Chaos Acts 1-3 on controller routes in every era, with bumper
  blocks, the Act 2 drum, the Act 3 boss and earned campaign saves.

## [V0.063]

Re-cut of V0.062 as a hardware candidate.

## [V0.062]

### Added

- A Collision Chaos Act 1 campaign route from a real Continue save, with time
  travel, the robot generator and a saved Good Future.

## [V0.061]

### Added

- Collision Chaos pinball objects, platforms and palette cycles. No release
  notes were written for this version.

## [V0.060]

### Added

- Saves to Saturn internal backup RAM, and Continue on the title menu.

## [V0.059]

### Added

- Japanese music for every zone and era.

## [V0.058]

### Added

- First objects from later zones (Tidal Tempest, Quartz Quadrant, Stardust
  Speedway, Metallic Madness) and the Japanese soundtrack.

## [V0.057]

### Added

- Terrain for all seven zones. No release notes were written for this
  version.

## [V0.056] - 2026-09-13

First version in this repository.

### Fixed

- Checkpoint respawns drop fractional seconds, as in the original.

## [V0.047] to [V0.055]

Palmtree Panic fidelity builds made before this repository. They fixed sprite
piece order, Sonic's animations, shield and star effects, time-travel arrival,
and checkpoint protection and timing. V0.044 was the console-tested build
before them. Earlier versions are recorded only in
[docs/archive/](docs/archive/).

[Unreleased]: https://github.com/t3chnaztea/sonic-cd-saturn/compare/4269266...HEAD
[V0.080]: RELEASE-NOTES-V0.080.md
[V0.079]: RELEASE-NOTES-V0.079.md
[V0.078]: RELEASE-NOTES-V0.078.md
[V0.077]: RELEASE-NOTES-V0.077.md
[V0.076]: RELEASE-NOTES-V0.076.md
[V0.075]: RELEASE-NOTES-V0.075.md
[V0.074]: RELEASE-NOTES-V0.074.md
[V0.073]: docs/archive/RELEASE-NOTES-V0.073.md
[V0.072]: docs/archive/RELEASE-NOTES-V0.072.md
[V0.071]: docs/archive/RELEASE-NOTES-V0.071.md
[V0.070]: docs/archive/RELEASE-NOTES-V0.070.md
[V0.069]: docs/archive/RELEASE-NOTES-V0.069.md
[V0.068]: docs/archive/RELEASE-NOTES-V0.068.md
[V0.067]: RELEASE-NOTES-V0.067.md
[V0.066]: RELEASE-NOTES-V0.066.md
[V0.065]: docs/archive/RELEASE-NOTES-V0.065.md
[V0.064]: docs/archive/RELEASE-NOTES-V0.064.md
[V0.063]: docs/archive/RELEASE-NOTES-V0.063.md
[V0.062]: docs/archive/RELEASE-NOTES-V0.062.md
[V0.061]: https://github.com/t3chnaztea/sonic-cd-saturn/commit/bb0f4d4
[V0.060]: docs/archive/RELEASE-NOTES-V0.060.md
[V0.059]: docs/archive/RELEASE-NOTES-V0.059.md
[V0.058]: docs/archive/RELEASE-NOTES-V0.058.md
[V0.057]: https://github.com/t3chnaztea/sonic-cd-saturn/commit/7dbf5c5
[V0.056]: docs/archive/RELEASE-NOTES-V0.056.md
[V0.047]: docs/archive/RELEASE-NOTES-V0.047.md
[V0.055]: docs/archive/RELEASE-NOTES-V0.055.md
