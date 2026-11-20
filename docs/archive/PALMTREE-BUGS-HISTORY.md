# PALMTREE-BUGS fixed entries

Moved verbatim from `PALMTREE-BUGS.md` on 2026-10-03, in original order.
Open entries and the status table: [PALMTREE-BUGS.md](../../PALMTREE-BUGS.md).

## PPZ-CLOCK-001 — checkpoint fraction survives reload

- V0.056 corrects the saved-spawn clock boundary: saved fractions are discarded
  at reload, as in original LoadCheckpointData plus its first normal HUD tick.
- 1,444 real native/original cases and 174,724 clock states pass; archived V0.055
  fails 1,180 fractional cases. Fresh starts and ordinary tick progression stay
  unchanged. Target route verifies 32 saved ticks reload as zero, all next 120
  ticks, and 2,653 original-HUD pixels in two pictures.
- Source/native/target gates close this measured clock defect; full checkpoint
  camera, fade/initialization timing and hardware acceptance remain open. See
  CHECKPOINT-FIDELITY.md and NEXT-SESSION.md.

## PPZ-CHECKPOINT-001 — missing saved-respawn protection

- V0.054: native checkpoint reload omitted original `LoadPlayer`'s 120-update
  hurt protection. Fixed only for saved spawns; fresh starts remain unprotected.
- 259 real native death/reload cases agree with original saved-spawn behavior;
  255 checkpoint IDs exercise 30,600 protected states and damage on expiry.
  Archived V0.053 fails all 255 checkpoint cases. All 30 host gates pass.
- Target passes 885 route states and the complete 121-state countdown, including
  60 hidden decisions. Hardware acceptance remains open; see
  CHECKPOINT-FIDELITY.md and NEXT-SESSION.md. Do not infer clock/camera parity:
  original reload drops fractional frames, whereas native still preserves them.

## PPZ-GFX-005 — brick platforms visible only when stood upon

- Status: reported visibility rule identified as original behavior on 2026-09-20.
  User supplied `IMG_8393.HEIC` and clarified that these blocks are invisible
  until Sonic stands on them. The pictured orange block with a diagonal inset
  matches Floating Block mapping frame 5 decoded from the original artwork.
  The original Present routine selects empty frame 0 until its standing flag
  is set, then starts the appearing animation. Preserve this behavior.
  Exact level coordinates, build version of the photo, and frame-by-frame
  animation parity remain unverified; this identification does not certify them.
- Next: inventory small brick/platform placements and original object behavior; test approaches from above/below/both sides, standing, leaving, re-entry and camera edges. Compare inactive and occupied visibility/priority, not just collision success. Distinguish intentionally appearing/falling objects from missing rendering.
- Closure: source-backed identification, failing route/frame sequence and targeted correction plus regression/hardware retest. Do not globally force all platforms visible without checking original behavior.
- Source finding: `_Objects/Floating Block/Main.asm` explicitly selects invisible frame 0 in the Present and starts appearing when stood upon; Past remains visible and Future falls. The native state machine follows that broad behavior. The supplied photo now identifies the reported object type. Local inspection artifacts: `build/IMG_8393.png` and `build/floating-block-source.png`.

## PPZ-GFX-007 — shared mapping compositor has legacy overlap order

- Status: source-composition defect fixed in V0.048, with independent pixel checks and complete target object-VRAM verification. Exhaustive animation/occlusion coverage and physical-console acceptance remain open.
- Evidence: 43 conversion calls change opaque pixels when reversing overlapping source pieces, including ten monitor icon/static frames. Original `Level/Object Functions.asm` `DrawSprite` emits pieces in mapping order; Genesis Plus GX `make_lut_obj` retains the first opaque sprite pixel. The legacy converter instead lets the last piece win.
- Next: retain the source-first gate while expanding visible animation/occlusion coverage and testing on hardware. The original V0.045 monitor-only correction is now superseded by first-piece priority for all converter calls.
- V0.048: all remaining 33 compositions / 5,032 pixels are corrected, independently checked by a pixel-first source oracle. Every other object frame and all 392 frames' geometry/palette-bank/priority assignments remain unchanged. 391 compositions / 1,515,328 exact pixels and the existing 30 object tests pass. Same-BIN world/VRAM and camera checks pass, as do all 22 fast gates, main replay, title/audio, zone sequence and special return. Independent Amy screenshot checks pass and reject V0.047's black patches. See SPRITE-COMPOSITION.md for coverage limits.

## PPZ-GFX-006 — possible sprite drift during vertical scrolling

- Status: reproduced as a one-update sprite/terrain camera mismatch in an original-position vertical-tag/spring fixture. V0.047 explicit drawing/manual swaps with an early software clear passes a 16-picture coherence check; complete regression and hardware acceptance remain pending. See `CAMERA-PRESENTATION.md` for exact evidence and rejected alternatives. Normal automatic swaps were rejected because they could abort a loading-boundary draw.
- Next: capture synchronized sprite/tile motion through upward/downward camera movement, slopes, springs and moving supports. Check VDP1/VDP2 presentation phase, shared camera sampling and fixed-point rounding before changing physics or camera constants.
- Closure: motion-sequence comparison demonstrating correct relative positions and hardware retest; matching isolated screenshots is insufficient.

## PPZ-GFX-008 — spring/disc pose persists during unrolled descent

- Status: reproduced in V0.049; source-backed V0.050 correction passes all focused
  host/target, audio and pacing gates. Physical-console
  acceptance and wider zone coverage remain open.
- Cause: the original animation interpreter was integrated, but the air-mode
  selection before movement was omitted. At nonnegative incoming Y velocity,
  unrolled Sonic should select animation 0 unless in a wind tunnel or animation
  21. Object-controlled and rolling modes do not execute that branch.
- Evidence: 2,400 actual player selections match unmodified retail 68000 code;
  the old adapter fails. All 33 consecutive yellow-spring pictures match source
  artwork, including the apex transition. Natural disc release shows original
  walking frame 53; the V0.049 frozen-pose screenshot is rejected.
- Regression: 16,800 main replay states and the 16,116-state three-act sequence
  preserve inputs and every non-animation bit. Only 605 main and 152 Act 2
  animation bytes change. See AIR-ANIMATION.md and `dist/air-regression-report.json`.
- Closure: retain these regression gates, broaden relevant motion/era coverage
  and confirm on hardware. Do not conflate this with the user's unidentified
  visual report or claim every original actor behavior is integrated.

## PPZ-GFX-009 — ordinary actors overwrite Sonic and earlier actors

- Status: V0.051 source-backed correction passes focused world/source-pixel,
  host, recorded gameplay, audio, title and pacing gates. Hardware,
  original actor allocation lifecycle and generated-effect priorities remain open.
- Cause: most actors were painted after Sonic regardless of original priority,
  and same-priority native actors were painted in forward submission order.
- Fix: one eight-bucket painter queue for Sonic, ordinary objects and boss parts,
  reversing original SAT priority/submission order. Dynamic source priorities
  are derived independently from original initializers.
- Evidence: 39,881 real retail 68000 enqueue calls / 512 lists; 159,744 priority
  metadata cases. All 100 TV pictures retain full opaque-texel coverage, now
  including 2,100 Sonic-overlap texels. Six old TV/projector pictures are rejected
  by independent source-pixel checks. All 32,916 recorded gameplay states are
  unchanged; the full three-act route has zero missed refreshes.
- Next: shield/invincibility/time-star priority-1 effects, broader same-priority
  overlap and allocation lifecycle, all-era routes and console acceptance. See
  SPRITE-ORDER.md; this does not close the user's unlocated hardware reports.

## PPZ-GFX-010 — approximated power-up animation and effect ordering

- Status: V0.052 integrated correction passes focused source-state, source-pixel,
  gameplay, audio and pacing gates. Broader overlaps and hardware remain open.
- Historical renderer painted generated effects after ordinary actors. Its time-star
  formula cycles five always-visible poses rather than the source's nine scripts;
  cursor/history phase and source suppression timing are not represented.
- Development evidence: `powerup_visual.c` matches 36,948 complete untouched
  retail CPU actor updates, including 9,312 mixed reserved-slot updates; all
  cases pass sanitizers. All nine script data tables match retail bytes.
- V0.052: pre-touch history and post-touch/pre-object snapshots feed the original
  actor state. Time stars spawn early; monitor grants initialize the following
  pass. Effects join priority 1. 23,638 target updates match 10,186 original CPU
  actor calls; 310 source-pixel pictures include all 47 script/pose pairs and
  12,093 effect/effect plus 29,714 effect/Sonic overlap texels. 13,211 source
  culling calls and the real monitor scheduler test pass with sanitizers.
- Next: additional ordinary-actor/scenery overlaps, original travel scheduling
  and arrival-persistence audit, and hardware. Native travel gameplay is unchanged.
- Closure: source-correct integrated effect behavior/presentation, scene reset,
  recollection and overlap sequences, followed by hardware acceptance. The
  isolated component is not a substitute for those checks. See POWERUP-VISUAL.md.

## PPZ-TRAVEL-001 — stale actor and shield survive time-travel arrival

- Status: source-backed V0.053 correction implemented; focused host/target
  arrival and travel tests pass. Whole travel flow/hardware acceptance remains open.
- Cause: copying the full departure actor restored animation, subpixels, angle,
  path/control scratch and shield that the original Save/LoadTimeWarpData does
  not save. Original Level/Main clears actors/power-ups; LoadPlayer grants 120
  updates of protection. Native arrival now follows that state boundary.
- Evidence: 2,048 ASAN/UBSAN native cases match five untouched retail code
  segments. Compiling the archived V0.052 adapter fails all 2,048 cases.
- Associated display correction: source flashing uses incoming hurt-timer bit 2,
  not global-frame phase. 2,080 host decisions and 1,200 target renderer decisions
  match; two complete protection countdowns reject 64 old flash decisions.
- Limits/next: exact original save-frame/travel scheduling, camera and terrain
  relocation, checkpoint spawn protection and all-era/console routes. Existing
  native clear-landing search is unchanged. See ARRIVAL-FIDELITY.md.

## PPZ-QA-001 — mixed fixture identity and sprite coordinates

- Status: fixed and regression verified; diagnostic publication race, not a demonstrated retail-art defect.
- Reproducer: initial V0.042 world run, Bad Future moving-spring fixture (route 4, pose 0), sampled X=-94/Y=-2 from the previous fixture. The unchanged source-pixel checker failed because that object was outside the image. Failed BIN/CUE, log and captures are preserved in `build/world-v042-failed-01` (BIN SHA-256 `903c7ce994a45e223c567a9cfd2639e2cd03c1f4e0e53eb5eb4cd5a450214e67`).
- Cause/fix: `main.c` published mailbox fixture ID before `sprite_draw` updated feature sprite state/coordinates. VBlank sampling could observe mixed fixture data. Publish identity after sprite recording/submission instead.
- Verification: `build/world-emulator-v042-final.log` passes the same full world/source-pixel checker; route 4 pose 0 is correctly sampled at X=152/Y=140, pose 1 at X=153/Y=141. No pixel tolerance or on-screen requirement was weakened. The user's separate unidentified visual report remains open.

## PPZ-HUD-001 — RINGS label loses its flash phase after ring pickup/loss

- Status: corrected in V0.044; independent native-renderer/retail-routine regression and focused target regression pass. Hardware acceptance remains separate and pending.
- Reproducer: zero rings at V-INT 16, collect at 17, lose at 18. The old `player.frame & 16` selector turns red immediately; the original remains yellow until the next toggle at 32. Pause and missed refreshes also separate VBlank time from player simulation time.
- Fix: retain the palette state; clear it when rings are nonzero, otherwise toggle only on an object update at a multiple-of-16 VBlank. Reset on stage/player restart; repeated rendering and pause do not update the state. No counter, physics or audio changes.
- Regression: 1,088 actual native HUD compositions, 2,265,705 original-source opaque pixels plus full transparency, ring-state decisions from the unmodified retail 68000 routine. See [HUD-FIDELITY.md](HUD-FIDELITY.md). This is not closure of PPZ-GFX-001 or proof of identical absolute startup phase on the two consoles.
- Target safety checks: same-BIN full-width title, 16,800-state replay, Act 1, recorded Act 2 Present/Past travel and the separate ring-loss stress route pass; the measured routes have zero missed refreshes. Audio probes and music/pause/resume pass with the V0.040 hardware-confirmed audio implementation unchanged. See [PERFORMANCE.md](PERFORMANCE.md).
