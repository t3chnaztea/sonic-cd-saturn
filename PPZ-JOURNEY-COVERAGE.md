# Controller-only Palmtree Panic journey coverage

Latest functional run: final uninstrumented V0.055, BIN SHA-256
`b6951d679663e352b94c1b1c49085c1cb87946e72efd254ff4b20e90dc92b378`.
This development image changes arrival-view prewarming and removes redundant
object-stream searches. It is not a packaged release or hardware acceptance;
card contents are unchanged. The focused local candidate is now preserved in
`build/hardware-candidate-v0.055-01`; it is not a full-QA release. See
NEXT-SESSION.md for archive hashes and broader regression status.

## Verified route

From ordinary NEW GAME, recorded controller inputs activate Act 1's Past post,
travel to Past, climb the upper route, destroy the generator, complete results,
enter Act 2 with Good Future flag 1, activate its Past post and travel to Past,
destroy its generator, finish Act 2, naturally enter Good Future Act 3, defeat
the boss, open the capsule, finish results and return from the prototype end
screen to the title.
No teleport, inventory injection, debug-era load or direct progression writes.

- Act 1 Past departure: update 1,286; generator destruction: 8,421.
- Act 2 begins: update 9,380; Past departure: 14,990.
- Act 2 generator: 18,968; third warp (Past to Present): 19,947.
- Good Future Act 3 begins: 21,442; both persistent flags set.
- Boss fight: 23,906; defeat: 24,290; capsule/results: 25,377.
- End: update 26,029, Act 3 Good Future, three lives, 15,300 points, flags 3.
- Host and ASAN/UBSAN standalone match all adapter words.
- Actual Saturn executable matches 26,029 controller/state rows: 416,464 words.
- Each update also matches six progression values read after coherent publication:
  act, era, persistent Good Future flags, current good future, clock and score.

Strict reference: `build/ppz-journey/good-zone-v055-reference-03`.
Target evidence/report: `build/ppz-journey/target-good-zone-v055-03`.
Final packaging uses `good-zone-v055-release-reference-01` /
`target-good-zone-v055-release-01`: a fresh, byte-identical sanitized host
reference and hash-verified copies of target pass 03's raw evidence after a
packaging-only JSON-normalization correction. The provenance JSON explicitly
records reuse, not an additional emulator run; all current bindings were rechecked.
The build manifest pins compiler-discovered/source/runtime-asset inputs and both host
binaries. Reports additionally hash controller inputs, raw states, sanitizer
output, target traces/captures, test tools and the actual disc.

Reproduce into **new** output directories, after verifying current input hashes:

```sh
bash tools/build-ppz-journey.sh
python3 tools/ppz_journey.py --label good-zone-reference-new \
  --prefix build/ppz-journey/good-zone-results-01/pads.txt \
  --steps 26029 --until-zone-results
bash tools/test-ppz-journey.sh \
  build/ppz-journey/good-zone-reference-new \
  build/ppz-journey/target-good-zone-new
python3 tools/check_journey_results.py build/ppz-journey/target-good-zone-new
```

V0.054 `good-zone-reference-02` / `target-good-zone-02` matched this entire
route first. The V0.055 target trace is byte-identical. V0.054 had three
3-VBlank gaps after travel; the initial V0.055 run has one 2-VBlank gap at
14,992. Both measure 26,023 same-act/era intervals. Cross-load intervals are
excluded; this is not an assertion that loading is instantaneous. The final
V0.055 run removes that remaining miss: all 26,023 measured intervals are one
VBlank, with profiling disabled and byte-identical controller/gameplay traces.
See PERFORMANCE.md for diagnosis, differential tests and retained failed runs.

`source-results-report.json` independently checks 1,829 HUD, 4,006 original
Good Future title, 1,466 counter-label and 421 digit opaque pixels at stable
final results. An altered HUD texel is rejected. These 7,722 checks do not
cover transparent-background composition or the entire scene.

## Failed attempt retained and corrected

`target-act2-past-01` rejected row1,287: the movement trace was new while the
world-mailbox clock still described the previous update. Inspection confirms
`main.c` publishes the trace before drawing and the world mailbox. The existing
effect mailbox clears its marker before trace publication and publishes it only
after the world snapshot/drawing. The harness now requires that marker and the
matching player frame before checking all six fields. No assertion was relaxed,
no game state was changed and no timing mismatch was accepted as a tolerance.
`target-act2-past-02` then passed every update, without sample gaps.

## Limits and next work

This shared-code host adapter establishes native/Saturn consistency and route
reachability, **not independent original-game fidelity**. It omits loading,
warp-cutscene and fade-only VBlanks. Special-stage entry is explicitly unsupported
and fails exploration instead of silently skipping it. End-of-zone handling
now explicitly verifies prototype exit and title return. Event-time images
are not synchronized original-pixel comparisons; generator/boss display can
lag its logical hit update. Only the stable final HUD/results art is separately
source-pixel checked.
There is no new hardware/audio or whole-zone performance claim.

Act 2's generator, both flags, natural Good Future Act 3 entry and the complete
boss/results route are reached and checked. Upper/lower alternate routes,
remaining object behavior and broader original source comparisons remain in the
PPZ acceptance matrix. Do not begin another zone on the strength of this pass.
