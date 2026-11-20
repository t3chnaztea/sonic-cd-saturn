# Collision Chaos — natural Good Future checkpoint

The full Collision Chaos goal remains active and unfinished. This checkpoint
adds an ordinary generator → Present → Good Future controller route and fixes
one extra refresh during the opaque-white departure hold. It is not a final
hardware release or proof of whole-act equivalence to the original.

## Current build

- Current V0.063 BIN SHA-256: `87a05fe81d831375d6f90794685937f598f8add6f41b2026821ab2d681220812`.
- `src/frame_profile.h` is restored to `SCD_FRAME_PROFILE 0`.
- The Japanese soundtrack remains mandatory. The earlier verified V0.059
  Japanese and V0.060 save hardware packages remain unchanged.
- Source/evidence/BIN snapshot: `build/cc1/good-future-validation.json` and its
  sibling directory. Earlier generator snapshots retain their original hashes.

## Ordinary controller proof

Run `python3 tools/test_cc_generator_route.py --good-future`.
The native-host recorder begins at the ordinary CC1 Past level-select spawn.
Saturn receives only controller buttons, and every observed integer position
must match before the next command is supplied. No gameplay memory writes,
placement edits, velocity edits or diagnostic scene jumps are used.

- 6,600 matched observations, zero respawns.
- Generator destruction at sequence 3891, Sonic at (5036,641): +1,500 points,
  score 300→1,800, Good Future set, active and subsequently broken art verified.
- Future post at (4384,887), Past→Present arrival at sequence 5501.
- Return left to the Present-era version of that post, then turn right below
  its ledge once Y exceeds 940. Lower springs sustain the second warp.
- Present→Good Future arrival at sequence 6157. The Good Future flag stays set
  for all 2,711 observations from destruction through the final resting state.
- Japanese CD tracks 13 → 12 → 14 verified requested, actual and playing.
- 6,595 gameplay intervals, zero late refreshes. This includes the frozen
  white-screen holds. The two explicit cutscene setups take 2 VBlanks each;
  the two cutscene/load transitions take 248 VBlanks each.
- 143,360 white-hold pixels checked: two complete 320×224 screenshots with
  the expected overscan borders. Good Future arrival was visually inspected.

The generic route summary counts each deliberate setup as one late interval.
The dedicated verifier checks timer 240, unchanged player position, world ticks
230 and the immediately following era transition before classifying it as a
cutscene setup. Every other same-era interval must equal one VBlank.

Evidence: `build/cc1/generator/controller-good-future-target/report.json`,
controller recording, raw host/core/state logs and screenshots. `--travel`
retains the shorter 6,000-observation route ending in Present; running without
an option retains the 4,200-observation destruction-only route. Both pass on this same BIN.
Full QA now runs the further extended `--act2` variant described below.

## Same journey through Act 2

Run `python3 tools/test_cc_generator_route.py --act2`. On the same BIN above:

- 11,282 exact native-host/Saturn positions from Past spawn through the
  generator, both warps, Good Future finish and completed tally at sequence
  11283. The recorder now reproduces the goal camera lock.
- 300 explicitly neutral tail observations. The ordinary fade/load enters
  Act 2 Present at sequence 11284 (208 VBlanks for this stage transition).
- All seven sign/tally phases occur in order; the bonus is added once. Score
  6,100 carries into Act 2, rings reset, and the live per-act Good Future mask
  is 1. Act 2 starts at its packed spawn; Japanese track 12 is playing.
- 11,576 gameplay intervals, no late refreshes or respawns. Both departure
  setups and both era load gaps retain the strict checks described above.
- Evidence: `build/cc1/generator/controller-act2-target/report.json`, controller
  file, host/core/state logs, save mailbox observations and screenshots.
- Snapshot index: `build/cc1/generator-act2-validation.json`. The BIN is unchanged
  from the preceding checkpoint; this batch changes controller tooling and QA.

Level select disables saving (`save_session=0`). The test verifies the live
Good Future bit without enabling that session, writing gameplay RAM, or claiming
that this completed journey has been saved. The neutral tail deliberately has
no host position oracle; its stage, spawn, score, rings, flag, music and pacing
are independently checked from the actual Saturn observations.

## Campaign checkpoint and saved Good Future route

Run `python3 tools/prepare_cc_campaign_checkpoint.py` to earn a fresh CC1
Present checkpoint from New Game through PPZ Acts 1–3 and verify a separate
cold Continue. It is a generation-4, zone-1/act-0 Present save with Japanese
track 12 and a live save session; the cold boot leaves backup RAM unchanged.
Evidence is `build/cc1/generator/campaign-checkpoint-report.json`,
`campaign-continue/`, `dist/sequence-report.json` and `build/sequence-qa/`.

Run `python3 tools/test_cc_campaign_generator.py --milestone continue` to
compile the native route with the original `boss_1.c` collision routine,
generate a pad-only recording and replay it from that earned backup on the
Saturn emulator. `tools/test_cc_campaign_route.py` verifies each position,
the natural warps, generator event, tally, music, pacing, save and cold
Continue. The smaller `generator`, `present`, `good-future` and `act2`
milestones are also available. The controller and replay tools write under
`build/cc1/generator/`; their source is tracked in `tools/`.

- 17,039/17,039 exact positions plus 300 neutral Act 2 observations; zero
  late gameplay intervals or respawns. The final tracked replay carries
  11,200 points into Act 2.
- Present→Past arrives at sequence 5318. Sonic destroys the generator at
  sequence 8798 for 1,500 points and earns the Good Future bit. Past→Present
  arrives at 14537; Present→Good Future arrives at 15372. The three cutscene
  setups each take 2 VBlanks; all ordinary gameplay gaps are one VBlank.
- The complete sign/tally sequence enters Act 2 Present at 17041. The earned
  Good Future bit and score carry, rings reset, and Japanese track 12 plays.
  The game writes a generation-5 backup. A separate cold Continue loads that
  exact state without changing its bytes. Backup hashes can differ across
  repeated runs; compare each run's output with its own cold readback.
- Current-disc evidence: `build/cc1/generator/campaign-generated/target/report.json`,
  `build/cc1/generator/campaign-generated/report.json` and the raw
  controller, host, target and save logs. The V0.063 BIN hash is listed above;
  the route work changed verification tools, not gameplay code.

The earlier scratch `campaign-entry.c` and search JSON used a weak no-op
`pcol` because their host compile omitted `build/probe-source/boss_1.c`.
Their route conclusions are superseded. The tracked wrapper includes the
original collision source and requires exact Saturn-emulator replay. Physical
Saturn acceptance and whole-act original parity are still open.

## Departure rendering fix

The new route exposed one real late interval, at sequence 6136, after the first
white frame of the second departure. The renderer was submitting ordinary
actors, reserved effects and the HUD behind an opaque full-screen white panel.
`src/main.c` now suppresses those covered draws, including Sonic's draw, while
continuing simulation and the reserved-effect updates.

The diagnostic before/after runs preserve all 6,600 route states and all 18
common screenshots byte-for-byte. White frames drop from 30–40 draw commands
to 5. At the first second-warp white frame, construction costs fall from 7,014
to 228 FRT ticks and draw completion from 15,733 to 11,101. The extra refresh
is gone both under profiling and in the final build with profiling disabled.

Evidence: `build/cc1/generator/good-profile-{before,after}/`, including exact
source snapshots matching their recorded input hashes;
`build/cc1/generator/good-profile-comparison.json`; replay and comparison scripts
in the same research folder. The profiler's BIN hashes identify diagnostic
builds, not the final candidate. The final route report binds the candidate.

## Completed current-build checks

- 52 fast QA gates: `build/qa-loops/20260923-133719-608246/report.json`.
- 80 full QA gates on V0.063, including the earned campaign cold Continue:
  `build/qa-loops/20260923-130148-685694/report.json`. Its disc and campaign
  report hashes match the packaged BIN.
- Earlier V0.061 four-era validation has 71,992 gameplay intervals, zero
  late refreshes/respawns. Immutable raw/report/screenshot copies are under
  `build/cc1/good-future-four-era-validation/`; this was not rerun on V0.063.
- World emulator/semantic and power-up target/pixel gates pass. Power-up
  comparison covers 23,640 updates, 10,187 original actor calls and 310 pictures.
  Reports: `dist/world-report.json`, `dist/powerup-target-report.json`,
  `dist/powerup-render-report.json`. World fixtures include isolated scene
  setup; they are not ordinary whole-act routes.
- PPZ Act 1: 3,861 exact states, final score 6,200; `dist/act-report.json`.
- Generator-only, Past→Present and Past→Present→Good Future routes all pass.
- Python syntax and `git diff --check` pass.

Earlier ten-variant CC art, Past stress, later PPZ acts and save cold-boot
results belong to their earlier BIN hashes. Source/asset/save logic did not
change in this batch, but those target runs are not relabelled as current-build
results. No physical hardware acceptance has occurred for this candidate.

## Continue from here

The level-select and earned-campaign journeys through Act 2 now pass on the
Saturn emulator. Obtain user-confirmed physical Saturn/SAROO results for the
V0.063 local package, then complete the outstanding original actors (`hari3x`, `emie3` and children,
`movie`, round-specific `friend`/`et`), mixed-family interaction/lifecycle audit,
terrain animation, native raster/background behavior and original whole-act
comparison. Do not narrow the goal to this completed
travel milestone. Leave the pre-existing untracked `tools/scroll/` untouched.
