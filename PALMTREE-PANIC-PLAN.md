# Palmtree Panic: complete the zone, then polish it to acceptance

Scope update: the resumed user Goal now requests the whole port. This document
remains the PPZ acceptance milestone, with remaining zones authorized afterward
under `PORT-ROADMAP.md`. Earlier "stop at this zone" wording below records the
prior boundary, not the new final objective.

## Scope and baseline

User directive: finish everything about Palmtree Panic; do not move into other zones. Once functional completion is reached, activate a recurring QA/repair job and stay on Palmtree Panic until its acceptance criteria are met. Use this zone to establish a reusable porting process.

Latest hardware checkpoint (2026-09-19): the user tested V0.044 and reports a
large improvement with no noticed gameplay-affecting problem on their route.
Four concrete graphical reports now take first priority: black monitor icons,
contact-dependent brick visibility, title-cloud vertical lines and possible
vertical-scroll sprite drift. See `hardware-results/v0.044.json`, the individual
entries in `PALMTREE-BUGS.md`, and `NEXT-SESSION.md` for the current ordered work
list and continuation controls. The recurring loop is still not installed;
the existing blocked Goal needs user edit/resume. CD++ is a separate optional
settings/behavior stretch goal, not permission to change Classic physics.

V0.040 is the first user-confirmed working Saturn/SAROO audio baseline. Its immutable BIN hash is `32e461959d053be26661675c222169d3b558280a0c72aa1666d9242a9ea79fe8`; candidate: `build/hardware-candidate-v0.040-01`; subsequent hardware result: `hardware-results/v0.040.json`. Do not overwrite it or rewrite historical test results.

Cover the ten original act/time-period combinations: Acts 1 and 2 each have Present, Past, Good Future and Bad Future; Act 3 has Good Future and Bad Future. Include all zone objects, scenery, routes and outcomes, not just a path to the goal. Use the supplied original retail disc and pinned source as the fidelity reference; explicitly resolve differences between retail and the PC reconstruction instead of treating shared native/host code as independent proof.

Include title-to-NEW GAME entry, act title cards, original HUD, pause, death/checkpoint/game over, results, zone progression and the existing special-stage entry/return boundaries. Preserve existing special-stage tests; do not expand special stages or global menu modes as a detour. Later zones and unrelated UI/save-mode expansion are out of scope. The end-of-prototype boundary must remain explicit, not imply that the next zone exists.

## What the evidence currently establishes

| Area | Evidence available | Gap to close |
| --- | --- | --- |
| Audio | User confirms working V0.040 sound; CD response-decoder regression and emulator probes pass | Preserve it; exercise each zone event, transitions, overlapping effects, pause/resume and cold boots |
| Act 1 | V0.040 Present completion: 8,061 matched states; original HUD checks | Full ordinary routes and visual coverage across every era, alternate branches and transitions |
| Act 2 | All four era routes passed on V0.037 | Rerun on current build; debug-selected eras do not prove natural time travel/progression |
| Act 3 | Existing Bad Future boss/capsule route; Good Future source/host coverage | Complete Good Future target route; natural good/bad-future selection and independent visual/behavior verification |
| Object inventory | Existing generated inventory explicitly covers PPZ1 | Extend source-backed inventory to Acts 2/3; imported assets are not proof of complete behavior |
| Graphics | Exact full-width title comparison, selected object/background/HUD/result pixel checks | User reports additional glitches; whole-zone motion, occlusion and transition coverage are not established |
| Pacing | V0.042 development: zero missed refreshes versus V0.040's 51 on both opening and full Act 1 routes; map/replay equivalence passes | Measure other eras/worst scenes; confirm original/console timing; see `PERFORMANCE.md`, not a whole-zone locked-60 claim |
| Automation | `tools/qa-loop.py` runs one finite fast/full pass | No recurring scheduler or automatic defect-repair loop is installed |

## V0.067 console-candidate ledger (2026-10-01)

| Gate | Implemented | Verified | Outstanding |
| --- | --- | --- | --- |
| Ten act/era completion routes | Act 1 A–D, Act 2 A–D, Act 3 C–D scripts in `tests/routes/ppz/` | Full-QA BIN `7d8587edef7fad8aa106dd3870d1b884216c17c616e804463cd3c87ff61ccfbd`: all ten passed with zero respawns and late intervals; `build/ppz{1,2,3}/controller/{era}/report.json` | Alternate paths, natural travel, full object/subtype and retail parity coverage |
| Natural Act 1 Good Future | Controller-only NEW GAME route through Present → Past, generator, results, and Act 2 entry in `build/ppz-journey/v067-act1-good-reference-01/` | Same V0.067 BIN: `build/ppz-journey/v067-act1-good-target-01/report.json` matches 4,457 host/target states, one warp, one generator, Good Future flag 1, zero late intervals. Original travel, generator, and results rules are `.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm:573`, `.deps/scddisasm/src/Level/_Objects/Robot Generator/Main.asm:73`, and `.deps/scddisasm/src/Level/_Objects/Results/Main.asm:301` | Independent original visual comparison, console acceptance |
| Natural Act 1 return travel | `tests/routes/ppz/natural-act1-return.pads` reaches the Past Future post from NEW GAME and sustains the 230-tick warp timer back to Present | Same V0.067 BIN: `build/ppz-journey/v067-act1-return-target-01/report.json` matches 2,976 native/sanitized/Saturn states, two warps, Act 1 Present return, zero late intervals. Original timer and destination rules: `.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm:573` | Independent original visual comparison, console acceptance |
| Natural Act 2 return and Future travel | `tests/routes/ppz/natural-past-return.pads` uses an Act 2 Past Future post to return to Present; `tests/routes/ppz/natural-present-future.pads` then uses a Present Future post to reach Bad Future | Same V0.067 BIN: `build/ppz-journey/v067-act2-return-target-01/report.json` matches 7,095 states and three warps; `build/ppz-journey/v067-act2-future-target-01/report.json` matches 8,099 states and four warps. Both pass native/sanitized/Saturn replay with zero late intervals. Original timer and destination rules: `.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm:573` | Independent original visual comparison, console acceptance |
| Natural Future return travel | `tests/routes/ppz/natural-future-return.pads` reaches the Act 2 Bad Future Past post from NEW GAME, reverses to qualify speed, and returns to Present | Same V0.067 BIN: `build/ppz-journey/v067-future-return-target-01/report.json` matches 9,069 native/sanitized/Saturn states, five warps, Act 2 Present return, and zero late intervals. Original source `.deps/scddisasm/src/Level/_Objects/Sonic/Main.asm:603-644` uses the 230-tick timer and subtracts one from Future time zone 2 to reach Present time zone 1 | Independent original visual comparison, console acceptance |
| Natural Good Future sequence | NEW GAME → Act 1 Past generator/results → Act 2 Past generator/results → Act 3 Good Future boss/capsule/results → Collision Chaos, all with controller input in `tests/routes/ppz/natural-good-results.pads` | Same V0.067 BIN: `build/ppz-journey/v067-act3-good-results-target-03/report.json` matches 15,035 states, two warps, two generators, both good flags, boss defeat at row 13,468, capsule at row 14,477, next-zone entry and zero late intervals. Its `source-results-report.json` matches 7,709 original-source HUD/results pixels. `source-scenes-report-02.json` matches all 3,748 intact capsule pixels and 130 exposed boss pixels | Other boss poses and whole-scene motion; user-confirmed console acceptance |
| Natural special-stage return | `tests/routes/ppz/natural-special-entry.pads` collects 55 rings in Act 2 Past and touches the goal ring; the original retail win route plays Special Stage 1 | Same V0.067 BIN: `build/ppz-journey/v067-special-return-target-02/report.json` matches 11,840 pre-entry states, two generators, two warps, zero late intervals; returns to Act 3 Good Future with time stone 1, three lives and zero rings. `build/ppz-journey/v067-act3-good-results-target-03/source-scenes-report-02.json` matches 1,876 original-source return HUD pixels and the original retail time-stone win. Original big-ring and results rules: `.deps/scddisasm/src/Level/_Objects/Level End/Main.asm:352` and `.deps/scddisasm/src/Level/_Objects/Results/Main.asm:186` | Whole-stage visual comparison and user-confirmed console acceptance |
| Natural Bad Future sequence | NEW GAME Act 1 Present → Act 2 Present → Act 3 Bad Future with controller scripts | Same V0.067 BIN: `dist/sequence-report.json` passed 9,173 + 7,004 + 2,852 matched host/target states, boss defeat, capsule, results and Collision Chaos entry. `build/ppz-journey/v067-act2-final-approach-01/bad-source-results.json` matches 6,537 original-source HUD/results pixels; `source-scenes-report-02.json` above matches 120 exposed boss pixels. Original boss runtime/source comparison is `build/ppz-journey/v067-act2-final-approach-01/boss-source-parity.json`; original flags rule is `.deps/scddisasm/src/Level/_Objects/Results/Main.asm:290` | Alternate Bad Future travel route and user-confirmed console acceptance |
| Act 1 B pacing | Far placements skip object checks while boss reload semantics remain | The repeatable two-VBlank interval at route update 2007 cleared on the final build; 81,920 stream comparisons pass | Real-console cadence and other stress scenes |
| V0.044 presentation reports | Title timing, monitor compositor and draw synchronization fixes remain in the candidate; contact-dependent brick behavior is source-backed | Prior focused emulator/source checks in `PALMTREE-BUGS.md` | Console retest of PPZ-GFX-003 through 006; broader motion and monitor coverage |
| Candidate gates | V0.067 normal build, profiling off, release notes and console checklist | Full-QA BIN hash above; 162 full gates passed in `build/qa-loops/20261001-213616-908522/report.json`; current fast QA passed 127 gates in `build/qa-loops/20261002-012901-821459/report.json`; stream differential, ten final-hash routes and 471-member private package readback passed | User-confirmed Saturn/SAROO results |

## Stage 1 — establish the complete zone checklist

1. Build an act/era matrix from the original layouts, dispatch tables, placements, art, palettes, scroll scripts, collision and progression rules. Account for every record/subtype and source dependency. Distinguish absent-by-design content from missing implementation.
2. Revalidate the current build, labeling historical results by their actual BIN hash. Add complete Act 3 Good Future coverage early; enumerate missing Act 1/2 era, branch and natural-travel routes.
3. Maintain [PALMTREE-BUGS.md](PALMTREE-BUGS.md). Each entry records version, act/era, camera/player position, route/input, expected source behavior, actual image/video, severity and a reproducible test. The user's unspecified glitches remain open until identified, not silently marked fixed.
4. Define camera/animation/palette synchronization for retail comparisons. Save baseline footage and representative frame sequences before editing rendering behavior.

Exit: every zone feature has an explicit implemented/tested/missing/unverified status; every known report is recorded; next work is ordered by evidence rather than by which test is easiest to make green.

## Stage 2 — functional completion of Palmtree Panic

- Complete all ten act/era combinations from their legitimate starting states. Include upper/lower paths, tunnels, ramps, moving/falling platforms, off-camera return and alternate approaches, not only the existing deterministic completion route.
- Audit every enemy, projectile, monitor, spring, door, wall, platform, checkpoint, hazard and decorative object against original behavior/art. Cover flips/subtypes, parent/child lifetime, pool pressure, collisions from every relevant side and load/unload persistence.
- Verify Sonic's motion and interactions: slopes, loops, wall/ceiling transitions, rolling/dash/peel-out, jump variants, springs, damage/ring loss, shield/invulnerability, moving supports, crushing/death and source boundary rules. Fix demonstrated differences; do not retune constants to conceal performance issues.
- Complete time-post activation, speed qualification and cancellation, all legal travel directions, destination geometry, player/camera state, audio changes and return travel. Verify generator/projector destruction, animals, good-future persistence and Act 3 future selection under the original rules, including time-stone-related branches that affect this zone.
- Complete score/time/rings/lives and extra-life thresholds, checkpoint respawn, game over, time limit, signpost, boss phases/hit rules/defeat, capsule, result tally/bonuses and Act 1 → 2 → 3 progression.
- Verify existing big-ring/special-stage entry and return preserve the correct score, lives, time stones, act and era. Exercise the zone-side outcomes without undertaking development of additional special stages.
- Keep music/effects correct throughout all of the above. The real-hardware audio fix is a regression requirement, not something to reconsider speculatively.

Exit: no known missing Palmtree Panic functionality; reproducible completion routes cover every act/era and progression branch; every source record is accounted for; no gameplay-blocking defects. Tests run during implementation. This milestone starts scheduled hardening, not a claim that graphics are already perfect.

## Stage 3 — recurring visual, behavior and performance QA

Activate the requested local cron job only after Stage 2, and verify an actual scheduled launch. Planned initial cadence: every 30 minutes; a single-instance lock skips overlapping launches. Schedule frequency is a launch opportunity, not a deadline that kills a valid long run.

Each cycle:

1. Verify the previous process is terminal before starting; a log/lock file alone is not proof. Select the next matrix cell, open defect or unexplored route with persisted coverage/seed state.
2. Build a source-identified candidate and run the relevant deterministic routes, sanitizers and adversarial input/route variants. Include repeated cold starts and long-session state transitions deliberately; do not simply repeat one passing route as evidence of new coverage.
3. Capture motion as frame sequences/video, not just selected screenshots. Inspect camera edges, foreground/background priority, parallax, palette/tile animation, transparency, sprite clipping/flips, seams, water/sky layers, animation order, HUD, title cards, boss scenes and fades/loading transitions. Include both scrolling directions, maximum speed, dense effects and re-entry after death/travel.
4. Compare with the independently synchronized original reference. Use exact data/pixels where appropriate and explicitly documented platform sampling differences elsewhere. Never weaken a tolerance or bless a new golden image just to hide a mismatch. A nonblank screenshot is not a fidelity pass.
5. Minimize each failure to a reproducer, fix one coherent root cause, add a regression, rebuild and run affected tests plus the broader regression set. The cron command launches a controlled QA/agent-repair cycle; cron alone cannot diagnose or repair code.
6. Save source/BIN/tool hashes, exact inputs and seeds, failures, before/after captures, timing metrics and the next action. Passing counts do not replace coverage. Recover cleanly after a crash/sleep or interrupted run.

Controls: one writer at a time; no race with foreground builds, no unrelated repository edits, no silent source/output mixing, no network publishing, no automatic card deletion/deployment, and no weakening tests. Use a dedicated project snapshot or explicit shared lock; this project is currently untracked within a dirty parent repository, so an ordinary Git worktree would not automatically contain it. Keep the working V0.040 archive and last passing QA candidate immutable. Handle credentials/permission/tool failures as explicit blocked runs, not success. Put a runtime watchdog around each bounded test/cycle; inspect confirmed live processes before recovery. Rotate disposable successful-run artifacts while retaining failures and accepted baselines.

Scheduling status: **planned, not installed or running**. Local `/usr/bin/crontab` and `/opt/homebrew/bin/codex` are available. Before activation, dry-run the exact runner under the cron environment, establish authentication/permissions, preserve unrelated crontab entries, verify locking/timeouts/restart behavior, and check launch logs. The Mac must be awake and the project available. The [OpenAI Docs scheduling guidance](https://developers.openai.com/es-419/docs/automations) confirms the CLI has no built-in Scheduled management interface; a local OS scheduler is the applicable route here, not a claimed cloud task.

## Stage 4 — acceptance, then stop at this zone

"Perfect" means no known unresolved Palmtree Panic defects, complete explicit coverage and original-presentation fidelity—not a mathematical promise that automation finds every possible bug.

- Every act/era, object/subtype and natural progression branch in the matrix is covered. No unsupported records are dismissed merely because the finish route avoids them.
- Every known user-reported glitch is reproduced and fixed or resolved with source-backed evidence; none is ignored because an unrelated suite passes.
- All required automated tests pass on the same immutable candidate. At least three complete scheduled passes cover the whole matrix plus different stress seeds; any code change resets final-candidate acceptance passes.
- Full-zone visual review shows no known missing tiles, seams, flicker, palette errors, priority errors or malformed animations; cold-start/travel/respawn/scene-transition sequences are included.
- Measure the worst-case performance and compare original frame cadence. Fix avoidable stalls without changing physics. Hardware play verifies responsiveness, speed and smoothness; unresolved meaningful stalls remain defects, even with green logic tests.
- User Saturn/SAROO play confirms music and effects, pause/resume and repeated boot stability, title/level visuals, travel, boss/results and normal zone progression. Hardware-only questions remain unverified until observed.
- Preserve a hash-verified accepted BIN/CUE, full evidence and a concise hardware checklist. Stop/pause the recurring job only after the acceptance matrix and user's hardware sign-off, or report a genuine blocker requiring input. Never move into another zone automatically.

## Reusable porting process produced by this work

Capture the actual successful procedure: original-source inventory → dependency/art conversion → behavior implementation → independent reference comparisons → deterministic routes → motion/visual diffing → stress/performance checks → real hardware → immutable acceptance package. Deliver reusable inventory schemas, fixtures, route/seed format, visual comparison helpers, failure reports and scheduling controls. Separate generic engine fixes from Palmtree-specific data and behavior, so later levels inherit verified infrastructure rather than unexplained exceptions.

Immediate next work: the zone-wide inventory/coverage audit and graphical bug intake, followed by closing the Act 3 Good Future route and remaining natural progression gaps. No other zone work.

Presentation subtask in progress: [SONIC-ANIMATION.md](SONIC-ANIMATION.md) records the original Sonic dispatcher/decoder now verified against retail CPU execution and all source poses. Integration, target rendering/cadence and controlled-pose regressions remain required; the current V0.042 executable is unchanged. The user's deferred glitch footage is not a blocker for this audit.
