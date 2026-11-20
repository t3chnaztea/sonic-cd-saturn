# Title-card clock and controls — V0.057 development

The original level HUD skips clock increments while `ctrlLocked` is set.
Its title parent initialization consumes one update without drawing/moving
the parent; newly allocated children execute later in that same object sweep.
HUD/player work sees the lock before the card runs, so an unlock affects
the next update. Native textures are preloaded and do not require a simulated
original decompression delay.

V0.057 samples the pre-update lock, masks controller buttons, temporarily holds
the player clock, runs the player, and then advances the card. The temporary
hold is independent of the permanent goal/capsule stop. Player initialization
clears the hold. With no extra PLC wait, card release is update130 and first
input/clock is131. V0.056 allowed input129; the intended shift is two updates.

## Verified after relocation

- All 34 host gates pass:
  `build/qa-loops/20260920-152859-680177/report.json`.
- `build/title-card-clock/v057-integration-01-report.json`: 2,880 original
  CPU states, 720 native card states and 2,400 real-player states across all
  ten valid act/era starts; zero mismatches. The player checks also exercise
  permanent-stop independence and clearing locks on initialization.
- Original CPU fixture varies PLC draining deliberately. It is an isolated
  card/clock oracle, not a full level-entry timing measurement. Historical
  full-retail fresh-entry fixtures remain under `retail-03-act1/2/3`; their
  varying decompression waits must not be imposed on preloaded Saturn art.
- `build/ppz-journey/target-good-zone-v057-01/report.json`: a normal-controller
  NEW GAME route matches 26,035 native/sanitized/Saturn states, reaches both
  generators, completes natural Good Future Act3, boss/capsule/results,
  prototype ending and title return. All 26,029 measured simulation intervals
  have a one-VBlank gap; none is late.
- The same target run verifies 573 intro clock/input samples: 191 per act.
  Each holds the clock at zero through update130, then increments normally.
  Nine screenshots at updates120/131/191 pass independent original-HUD pixel
  checks. Display output is allowed to lag coherent simulation by exactly one
  update; pictures at131 show0, and at191 show60.
- `tools/check_journey_results.py` passes the same target's independent original
  HUD/results pixels, including a deliberately altered HUD rejection.

Route inputs in `build/title-card-clock/v057-route-input/` derive from the
preserved V0.056 route by adding two held inputs at each act entry. The route
was regenerated and rerun; old evidence was not relabeled. V0.056's immutable
candidate BIN still matches its recorded SHA-256.

## Still required

The V0.057 target regression suite now passes on BIN
`064ef17c4ec6905c66f9d1ea33e923c93e691de5d2589fddc4875d12ffb4f2db`
(`build/v057-target-qa.log`). Its first run failed on a ring-loss frame overrun
in the shifted Act 1 route; see the V0.057 section of `PERFORMANCE.md`. The
natural Bad Future sequence, special-stage return, and complete release
evidence/package validation are still pending. Non-Present Act2 debug-entry ordering still needs its target replay. The
re-recorded Past ring-loss stress route now measures that entry: the Saturn
holds the act clock for 130 updates there and its HUD agrees, while
`tools/act_test.c` starts no card on that path and its clock does not hold
(host elapsed 4,530, target 4,400). See `build/act2-past-stress-v057-02` and
the V0.057 section of `PERFORMANCE.md`.
No V0.057 physical-console test is claimed. These measured clock/input checks
do not establish full original gameplay, camera, fade or hardware equivalence.
