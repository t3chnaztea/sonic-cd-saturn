# Sonic airborne selection — V0.050

V0.049 integrated the original animator, but the surrounding player adapter
still omitted the selection at the start of `ObjSonic_MdAir` / `play00jump`.
This left the spring animation active after the apex and retained disc poses
after a natural release. This is a reproduced fidelity defect, not a confirmed
identification of the user's unspecified sprite-floating report.

The source selects animation 0 on an unrolled airborne update whose **incoming**
vertical velocity is nonnegative, unless a wind tunnel is active or animation
21 (bubble breathing) is active. Rolled jumps and object-owned updates do not
execute this branch. The selection must happen before gravity changes velocity.

`src/player.c` now performs that missing selection. It does not change movement,
gravity, collision, input, audio or the animation interpreter. Original idle
boredom behavior, broader priorities and the diagnostic-only Amy clock remain
separate unfinished work.

## Independent regression

`python3 tools/test_player_air_animation.py` locates the exact original R11A
air-mode prelude at `0x2045F6`. The pinned Genesis Plus GX 68000 executes those
unmodified instructions one at a time until their original first BSR boundary.
No source or reference routine is patched. Every actor byte other than animation
is checked unchanged. The oracle is not a second copy of the new C condition.

An observer records the actual player adapter's pre-animation selection under
ASan/UBSan: all 60 animation IDs, five negative/zero/positive velocities, wind
on/off, rolled/unrolled and owned/unowned give 2,400 cases. A 150-update normal
spring-contact route also checks the original selector: 76 ascent observations,
74 descent observations and the first animation-16-to-0 transition at tick 73.

The unchanged V0.049 adapter fails this new test at animation 1 / incoming
velocity 0 (native keeps 1; retail selects 0). Its raw matrix/spring trace and
failure are preserved in `build/player-air-animation-v049-baseline` and
`build/player-air-animation-v049-baseline.log`. V0.050 passes.

The pre-existing animation-order test used animation 2 without its rolling flag
and assumed natural disc release would preserve animation 45 forever. Those
fixtures were corrected to actual rolling-jump flags and the source descending
transition; all controlled disc poses and the player-before-object rule remain
asserted. The target world probe now requires animation 0 / source walking pose
after the unrolled disc release, rather than freezing the old bug.

Across the 16,800-state gameplay replay, the first host differential contains
605 animation-byte changes and **no changes to any other state word or bit**.
The original terrain baseline still passes unchanged. Actual player calls
continue to match the original animation interpreter (610 order + 16,680 replay
+ 67,967 world calls). These host checks do not replace target validation.

Final target validation passes on BIN
`1fda1a9804bb02808cd100aa945e4fd66871e6f49795dc934bdf4e0b4c8a13f8`.
The main capture harness checks 33 consecutive yellow-spring ascent/apex/descent
frames, safely clear of the spring actor, plus the existing eight source-pixel
fixtures: 195 pictures / 54 mappings / 119,505 visible + 1,596 foreground pixels.
The spring-to-falling transition occurs at simulation 48. Natural disc release
also passes the exact frame-53 pixel check, which rejects the V0.049 capture.
Ascent, descent and disc-release pictures were visually inspected.

All 25 fast gates, target replay/world/title/audio/isolated diagnostics,
special-stage return and the three-act sequence pass. All 16,800 target
presentation states match the host/reference, as do the gameplay states.
`tools/check_air_regression.py` additionally compares the old/new three-act
traces: controller inputs and all non-animation bits are identical. Act 2 has
152 corrected animation bytes (97 from animation 16, 1 from 13, 54 from 2);
Acts 1 and 3 are unchanged. All these prior IDs are in the independently
retail-verified selection matrix. The new differential checker rejects changed
coordinates, buttons and unrelated animation changes.

Opening (1,800 intervals), standalone Act 1 (8,060) and the sequence
(8,060 / 5,192 / 2,861) have zero missed refreshes. Source/trace/BIN hashes are
preserved in the versioned candidate. This remains focused emulator evidence,
not complete-zone or physical-console acceptance. The card is unchanged.
