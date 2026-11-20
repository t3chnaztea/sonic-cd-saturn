# Palmtree Panic findings

Scope: the whole zone only. A passing unrelated test never closes one of these entries. Closed defects retain their reproducer and before/after evidence.

## Quick reference

Open entries have full text below. Fixed entries moved verbatim to
[docs/archive/PALMTREE-BUGS-HISTORY.md](docs/archive/PALMTREE-BUGS-HISTORY.md).
"Hardware pending" means no user-confirmed console closure is recorded for that
entry. V0.065's console report (`hardware-results/v0.065.json`) lists no new
defects but does not close named entries.

Open:

| ID | Summary | State |
| --- | --- | --- |
| PPZ-GFX-001 | User-observed graphical glitches | Not reproduced; blocks zone visual acceptance |
| PPZ-GFX-003 | Vertical lines in title clouds | V0.046 VRAM-cycle fix; console symptom unconfirmed |
| PPZ-GFX-004 | Monitors show black screens | V0.045 converter fix; hardware retest open |
| PPZ-PERF-001 | Measured missed refreshes | Measured cases fixed; whole-zone and console timing open |
| PPZ-GFX-002 | Provisional Sonic animation | V0.049 original dispatcher; zone-wide criteria open |
| PPZ-CLOCK-002 | Title-card clock lock | V0.057 development; release/hardware pending |
| PPZ-COV-001 | Act 3 Good Future route | Route added V0.054/055; wider coverage open |
| PPZ-QA-002 | Reactive route timers use refreshes | Recorded-input mitigation; driver fix open |

Fixed (hardware pending unless noted):

| ID | Summary | Fixed in | Still open |
| --- | --- | --- | --- |
| PPZ-HUD-001 | RINGS flash phase | V0.044 | Hardware |
| PPZ-GFX-006 | Sprite drift in vertical scroll | V0.047 | Full regression, hardware |
| PPZ-GFX-007 | Mapping compositor overlap order | V0.048 | Animation/occlusion coverage, hardware |
| PPZ-GFX-008 | Spring/disc pose persists | V0.050 | Zone coverage, hardware |
| PPZ-GFX-009 | Actors overwrite Sonic | V0.051 | Effect priorities, allocation lifecycle, hardware |
| PPZ-GFX-010 | Power-up animation/order | V0.052 | Broader overlaps, travel scheduling, hardware |
| PPZ-TRAVEL-001 | Stale actor/shield after travel | V0.053 | Travel scheduling, camera, hardware |
| PPZ-CHECKPOINT-001 | Missing respawn protection | V0.054 | Hardware |
| PPZ-CLOCK-001 | Checkpoint fraction survives reload | V0.056 | Camera/fade timing, hardware |
| PPZ-QA-001 | Mixed fixture identity (QA race) | V0.042 | None; closed |
| PPZ-GFX-005 | Bricks visible only when stood on | n/a | Original behavior; preserve it |

## PPZ-GFX-001 — user-observed graphical glitches

- Status: open, not yet reproduced. User deferred footage; independent zone-wide checks proceed without it.
- Evidence: after confirming V0.040 sound, the user reports seeing weird graphical bugs/glitches and requests zone-wide polishing.
- Act, era, coordinates, exact build and affected layer: not specified. Do not assume this is the older title-width defect.
- Next: independently sweep zone routes and transitions with recorded input/frame sequences; compare original art/priority/animation at matching state. Incorporate a user location or clip if supplied later; do not block the audit on it.
- Closure: verified root-cause fix plus a regression and user/hardware confirmation for any console-specific behavior. This report blocks final zone visual acceptance until resolved.
- V0.044 hardware follow-up: user reports a large improvement and no observed gameplay-affecting problem on their route. Four concrete presentation reports are tracked below as PPZ-GFX-003 through 006. This does not close unexamined routes or prove the earlier unidentified glitches all have the same causes.

## PPZ-GFX-003 — vertical lines in title clouds

- Status: open, reported on V0.044 Saturn/SAROO; not yet independently reproduced.
- Evidence: user sees vertical lines in clouds in the top third. No new blank-side-strip report; absence from this report is not an explicit edge-coverage certification.
- Next: capture consecutive title frames; inspect texture boundaries, stride/padding, palette/transparent texels and VDP fetch/VRAM timing. Existing exact emulator title pixels do not disprove a console-only artifact.
- Closure: identified cause, regression exercising the failing boundary/timing, and physical-console confirmation. Do not hide seams by weakening source-pixel tests.
- V0.046: corrected a documented title VRAM-cycle violation. A fresh V0.045 target state confirms duplicate pattern-name fetches and NBG1 T2/T3→T5 invalid character-fetch timing. V0.046's actual register state passes an independent timing validator while retaining all 823 V-INT states and 1,196 exact reference pictures. See `TITLE-HARDWARE-CYCLES.md`. This is a concrete hardware-correctness fix and plausible stripe cause, not yet physical-console symptom closure.

## PPZ-GFX-004 — functional monitors have black screens

- Status: open, reported on V0.044 hardware. Act/era/location unspecified.
- Evidence: TVs grant power-ups but do not visibly show their contents.
- Next: exercise every monitor subtype through intact animation and break/item rise; compare original frame/palette and indexed transparency with actual submitted VDP1 texture/CLUT/commands. Existing grant/nonblank tests are not an icon-fidelity gate.
- Closure: recognizable source-correct icons across required eras/subtypes with a regression, followed by hardware retest. Preserve item behavior and audio.
- V0.045 development: reproduced in the converter. It paints later mapping pieces over the first icon; the original `DrawSprite` emits first-piece-highest-priority SAT entries. Correct monitor compositions use reverse painter order. An independent destination-pixel-first oracle verifies all twelve monitor frames and proves the unchanged historical snapshot contains the old defect. Target verification passes 100 motion captures / 83,300 opaque source pixels across five item subtypes; all 345,344 object VRAM bytes match including palettes. Hardware retest remains open. See `VISUAL-CORRECTNESS-V0.045.md` for retained failed attempts and corrected palette alignment.

## PPZ-PERF-001 — measured missed refreshes

- Status: open performance investigation, not a proven slowdown versus the previous build.
- V0.040 evidence: `build/pacing-v040-final.log`, 1,800 intervals, 1,851 VBlanks, 51 two-refresh gaps; same as V0.038/039, versus 60 gaps in V0.037. Full Act 1 has 51 gaps too.
- V0.041 development improvement: incremental background row decoding reduces the freshly rerun opening-route comparison from 51 to 2 late intervals; the full Act 1 route also has only 2, with all 8,061 states still matching. 1,737,120 sanitized full-map comparisons across ten packs pass. See [PERFORMANCE.md](PERFORMANCE.md) for hashes, reproducer and remaining limitations. Not hardware-verified.
- V0.042 resolves those two route misses: profiling identified avoidable full-viewport foreground scanning; direct edge updates preserve all writes and reduce the dense-scene foreground phase by 46%. The uninstrumented opening and full Act 1 routes now have zero missed refreshes, with exact replay retained. Another 794,250 sanitized full-map comparisons pass. Other-scene/original/hardware timing remains open.
- Expanded same-BIN measurements find one two-refresh gap in Act 2 Present (update 3,670, X~7,993/Y~549, 80 active objects); both Act 2 Future routes have a three-refresh gap at update 2 after loading. Exact-recorded Past and Act 3 Bad Future routes have zero gaps. The failed reactive Past route has another stress case after ring loss at update 3,384. See [PERFORMANCE.md](PERFORMANCE.md); no whole-zone speed claim is made.
- V0.043 progress: profile-backed snapshot reuse removes the duplicate object hash/count pass; stage-map prewarming plus a fresh update boundary removes the Future loading gaps. The uninstrumented opening, full Act 1, all four recorded Act 2 eras, Act 3 Bad Future and separate ring-loss stress route now have zero misses, with identical recorded gameplay states. The uninterrupted zone run, world checks, title, audio and special-stage return also pass on the same BIN. Title reveal cold uploads found during validation were separately corrected and source-verified. See [PERFORMANCE.md](PERFORMANCE.md).
- Next: investigate other worst-case routes, establish original gameplay cadence, and gather console timing. The measured cases are fixed; whole-zone/hardware performance acceptance remains open.
- V0.047: the camera-correct pipeline exposed one crowded Act 2 ring-loss miss. Exact sequence replay reproduces it; constant-band raster batching and non-redundant ring-slot searches remove it without changing any of 16,116 gameplay states. Final uninstrumented sequence intervals are 8,060 / 5,192 / 2,861, all with zero misses; the camera/source-pixel and audio gates still pass. See PERFORMANCE.md. Other routes and physical-console timing remain open.
- V0.055: the new complete Good Future route exposed three post-travel gaps.
  Destination-view prewarming and non-redundant object-stream searches remove
  them: 26,023 intervals with zero misses, all 26,029 input/state rows unchanged.
  81,920 sanitized old/new stream comparisons across ten packs pass. Existing
  main/sequence, visual, audio and measured pacing gates pass; hardware remains open.
- Closure: fix avoidable misses without changing physics, document source-intentional cadence, and verify responsive hardware play. Do not label the current result locked 60 Hz.

## PPZ-GFX-002 — provisional Sonic animation selection

- Status: known presentation-fidelity gap found during source inspection; separate from the user's unreproduced glitch report.
- Historical evidence: through V0.048, gameplay selects a provisional 21-pose atlas using the global update count and continuous rotation.
- V0.049: the original dispatcher is linked to the actor and its mapping/flips drive gameplay rendering. The original 198-pose artwork is losslessly precomposed at build time after runtime DPLC composition missed 40/1,800 refreshes; the final compressed build has zero measured misses in opening, standalone Act 1 and recorded three-act routes. 85,299 real host animation calls match retail execution; 16,800 presentation states match host/reference/SH-2; 162 source-pixel captures exercise 49 mappings. Same-BIN focused world, title, audio, transition and replay gates pass, including all six disc poses and independently checked Amy/Sonic/heart priority. See [SONIC-ANIMATION.md](SONIC-ANIMATION.md) and NEXT-SESSION.md for evidence and limits.
- Next: retire the diagnostic-only Amy clock, audit omitted actor animation selections and broader object priority/tie order, then expand motion/era/hardware coverage. This finding stays open until zone-wide presentation criteria are met.
- Closure: required Sonic poses, transitions and cadence match the original across the zone; existing static sprite/physics tests alone cannot prove this.

## PPZ-CLOCK-002 — title-card clock lock needs source/runtime audit

- V0.057 development now passes all 34 host gates and the full 26,035-state
  Good Future Saturn journey. Real-player clock tests have zero mismatches
  across 2,400 states; target initial/next-act entries verify all 130 held
  updates, first clock/input131 and nine source-HUD pictures. Other target
  regressions, debug-entry ordering and release/hardware acceptance remain
  pending. See `docs/archive/TITLE-CARD-CLOCK.md` for exact evidence and limits.

- Post-V0.056 development: independent original RunObjects/HUD execution now
  reproduces 117 old native title-card mismatches; corrected isolated card
  passes all 720 native states against 2,880 original fixture states. Full
  retail fresh-entry captures for Acts1/2/3 prove clock remains zero while
  locked, including real variable PLC waits. Native preloaded textures retain
  zero-extra-PLC-wait policy. Parent initialization and pre-player lock/clock
  sequencing are implemented but integrated target/regression work is pending.
  No new packaged release or hardware closure. See latest NEXT-SESSION entry.

- Original V0.056 source finding: original UpdateHUD
  skips the clock increment while ctrlLocked is set. Packaged V0.056 uses the
  title-card step to suppress buttons, while player.c still increments elapsed.
- Next: measure original title-card release and HUD-update order versus native
  initial/next-act entry. Add an original-CPU timeline and target clock test
  before changing counts or result bonuses. Do not conflate this with V0.056's
  saved-checkpoint correction or claim ordinary startup timing is fully faithful.

## PPZ-COV-001 — Act 3 Good Future target route

- Status: open coverage gap, not by itself a proven gameplay bug.
- V0.054 and final V0.055 now complete the normal-controller route through
  both generators, natural Good Future Act 3, boss/capsule/results and title
  return. 26,029 Saturn/shared-native states and all six progression fields
  match; the two target traces are byte-identical. See PPZ-JOURNEY-COVERAGE.md.
- Evidence: `build/ppz-journey/target-good-zone-02` and
  `target-good-zone-v055-03`; 7,722 opaque original HUD/results art pixels also
  pass. This closes the missing legitimate route, not broader visual fidelity.
- Next: expand original scene/motion comparisons and alternate routes, and
  verify physical hardware. The measured post-travel stalls are fixed.
- Closure: current-BIN target report, exact state replay, original visual comparisons and progression coverage.

## PPZ-QA-002 — reactive route timers depend on display refreshes

- Status: identified; exact-recorded-input comparisons verified, general reactive driver still open.
- Evidence: the older Act 2 routes change inputs when renderer timing changes. Past fails its no-damage gate and Good Future does not complete. Jump/forced-jump/dash/wait counters in `tools/emulator_test.c` advance per emulator loop rather than committed simulation update. Failed outputs remain preserved, not accepted.
- Mitigation for performance comparisons: `SCD_ACT_PAD_TRACE` supplies an earlier successful controller sequence with the measured SMPC polling lead and requires exact equality of all inputs and 16 gameplay words. All four Act 2 eras and Act 3 Bad Future pass: 24,972 states. This is a stronger same-route comparison, not a gameplay workaround or proof that the adaptive driver is fixed.
- Next: make adaptive-controller timers simulation-clocked and use coherent state snapshots; retain exact recordings for performance comparisons. Do not weaken no-damage, completion or pixel assertions.
