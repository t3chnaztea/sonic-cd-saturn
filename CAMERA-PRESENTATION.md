# V0.047 camera presentation investigation

The V0.044 hardware report of sprites floating during vertical scrolling now
has a reproduced **one-update sprite/terrain phase mismatch**. Physical-console
closure still requires a retest; V0.046 remains the preserved handoff candidate
until the complete V0.047 regression set passes.

## Source-backed reproducer

The isolated Present vertical speed-tag fixture previously contained only Sonic
and an invisible tag. Sonic stays at the camera's tracking point, so it could
not establish whether stationary sprites moved with the terrain. The fixture
now also contains two original Present spring placements, (8816,744) and
(9072,936), both outside Sonic's path. Normal level spawning is unchanged.

`tools/emulator_test.c` records consecutive pictures and game/camera samples.
`tools/camera_pixels.py` independently reconstructs terrain from original tiles,
blocks, chunks and layout. It reconstructs springs from original placement,
mapping, art and palette data, not the target's reported sprite coordinates.
Opaque source HUD-label texels that cover a spring are excluded from sprite
coverage; the separate original HUD/flash gate owns that behavior. Visible
spring pixels must identify exactly one camera, identical to the terrain camera.
Exposed bottom foreground also has exact pixel checks to catch stale buffers.

The automatic-drawing baseline has unchanged physics but different displayed
cameras: at capture tick 2, terrain uses (8752,678), spring uses (8752,665).
At tick 3 they use Y=691 and 678 respectively. The mismatch vanishes once the
camera stops. The 596 logged samples from both tag routes remain identical
after the presentation changes. No movement or collision constant was changed.

Before archive: `build/camera-v047-auto-baseline`, including BIN/CUE, source,
logs, pictures and serialized VDP1/VDP2 state. BIN:
`654d5e9309226b0c2ecdf06d201b42224f262e5d60f853a9a365729c25346f20`.

## Cause and rejected approaches

The default SDK automatic mode sets PTMR=2 on command transfer, starting VDP1
drawing after the framebuffer change. VDP2 displays the camera committed at
the preceding VBlank-in, leaving sprites one update behind.

1. Explicit drawing with variable/manual swap aligns the layers, but its
   VBlank-only erase leaves stale pixels. Preserved under
   `build/camera-v047-partial-erase` (BIN `c6955b9edfc49d325c0761394e084977329737b6fc9c12af84048ee76ecb65bb`).
2. Adding a full-screen transparent clear polygon fixes those pixels, but the
   full Act 1 run has **1,226 late intervals out of 8,060**. Rejected, preserved
   under `build/camera-v047-clear-slow` (BIN `c9a59c17243702bf5907b5b653ab432d4baeefebeb14a11ff20a44f5c39b01ba`).
3. Explicit drawing with normal automatic swaps restores pacing and aligns
   the measured camera, but a loading-boundary swap aborts the first projector
   draw. The SH-2 waits at `sprite_draw`'s completion fence with CEF=0,
   DrawingActive=0 and an unfinished command list. Rejected; machine state,
   BIN/CUE and source are in `build/camera-v047-onecycle-abort` (BIN
   `59baaf864e45efb561608426cda7f3220bb4fc0227d4d6ac507903cbb11b474d`).

This behavior is covered by Sega's original manuals: [PTMR drawing trigger](https://antime.kapsi.fi/sega/files/ST-013-R3-061694.pdf),
[framebuffer switching](https://www.infochunk.com/saturn/segahtml_en/hard/vdp1/hon/p04_12.htm),
and [limited VBlank erase capacity](https://www.infochunk.com/saturn/segahtml_en/hard/vdp1/hon/p04_14.htm).

## Current implementation and limits

Use controlled manual swaps and explicit drawing. `src/gameplay_video.inc`
starts a transparent full-buffer clear on the idle draw bank at the beginning
of each gameplay update, **overlapping the CPU's simulation work**. Wait for
that clear before transferring the gameplay list, then wait for completed
sprite drawing before requesting the swap and corresponding VDP2 commit.
This removes the late clear's measured cost from the critical path without
allowing an automatic swap to abort a draw. Title, floor inspection and special
stage retain their own automatic pipelines; transitions wait for the direct
clear before touching the bank or mode. The prototype end screen also waits
before submitting its list. No physics constants or simulation rate changed.

First camera-fixed development BIN (historical failed-pacing checkpoint):
`d7096389e77352f3ccc3b24944e3cab522c8924e6ea5e1d236a969a6626fa10d`.
The preceding overlapped-clear checkpoint (BIN `e0ea959a396303a21fe31544f9ff13f143de5847df30e6eb34de13c0e9eb7293`,
`build/camera-v047-preclear-checkpoint`) passes the 16 consecutive vertical
captures with 3,451 exposed spring pixels, 92,064
priority terrain pixels and 107,520 bottom foreground pixels. Actual captured
registers show PTMR=1, FBCR=3, TVMR=8 at VBlank. The partial VBlank erase is only
supplemental; exact foreground checks prove the software clear removes stale
pixels. Seven captures have distinct camera-history
positions. Opening pacing has zero misses; full Act 1 also records zero over
8,060 intervals and matches all 8,061 host states. These remain focused routes,
not whole-zone or hardware acceptance. The final BIN passes those same checks,
all 21 fast gates, the 16,800-state replay, all 1,196 title pictures, world
source/monitor/VRAM checks, music/effects/isolated audio and the big-ring →
special-stage → Act 2 transition.

Existing source-snapshot captures for doors, discs, scenery, projector animals
and Amy now request the exact recorded state one display frame later instead
of two. Their pixel assertions are unchanged. The camera sequence keeps its
original capture ticks, independently testing the new phase.

The overlapped-clear world run completes all controller routes, including the
formerly stalled projector. It then finds two source captures taken while TV
display-enable still crosses the loading boundary: completely black initial
door/scenery images. The harness now allows one additional field only for such
an initial all-black picture, retaining the exact original sprite snapshot and
every pixel assertion. It does not tolerate blank steady-state camera pictures,
allow approximate pixels, or repeatedly wait past a failure. The final world
run passes every unchanged source-pixel assertion, including those two scenes;
the failed initial captures are preserved with the checkpoint.

## Historical failed performance gate — preserved, not deployed

The uninterrupted Act 1 → Act 2 → Act 3 Bad Future → end screen → title run
completes and all three host replays match. Its expanded timing gate finds
**one two-refresh interval in Act 2**, at update 3,676, X=7996.5390625,
Y=552.40625, with 80 active objects. Act 1 has zero misses over 8,060 intervals;
Act 2 has one over 5,192; Act 3 has zero over 2,861. Scores are 2,800 / 7,300 /
18,500 with three lives. The reactive controller path is not identical to the
older recorded Act 2 route; preserve exact inputs when profiling/comparing.

The old functional-only sequence check initially passed. `check_sequence.py`
now validates timing against all three traces and requires zero misses; rerun
on the same evidence, it fails and replaces the old green report with an
explicit `passed:false` report. Hardware packaging refuses this report. See
`build/sequence-v047-pacing-failure.log` and the archived sequence report in
`build/visual-checkpoint-v0.047-01`.

Preserved failed checkpoint: `build/visual-checkpoint-v0.047-01`, not a
hardware-ready candidate. It must not be confused with the follow-up below.

## V0.047 follow-up — camera and pacing gates pass together

Uninstrumented BIN `8e50d87b961be55f37ed3c5ed74f4a69899eb35aca737df1247a2ab1698e6825`
preserves the same explicit drawing/manual-swap/early-clear pipeline. Two
output-preserving optimizations (constant raster bands and ring-scatter slot
searches) remove the dense Act 2 miss. All 16,116 sequence states and controller
inputs are byte-identical to the failed checkpoint, with zero late intervals
in all acts. The same-BIN world gate still checks all 16 camera pictures and
exactly 3,451 spring, 92,064 terrain and 107,520 clear pixels.

All 21 fast gates and the focused main replay, title, audio/diagnostic, Act 1,
big-ring return and opening-pacing tests pass on this BIN. See PERFORMANCE.md
for before/after profiling, independent output tests and raw evidence paths.
All test processes are terminal. No card/Desktop deployment or cron. Hardware
confirmation of the user's reported floating remains open.

Next coverage: upward motion, ordinary route camera changes, sloping terrain,
moving supports, dense sprite loads and physical Saturn verification.
