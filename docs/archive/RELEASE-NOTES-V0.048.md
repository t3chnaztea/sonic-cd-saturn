# V0.048 — original sprite-piece ordering

Focused host/emulator checks pass; hardware confirmation is pending.
BIN SHA-256: `95224d40113a0fe4730e6faab86674050c17867c5d4c838b4dd94d1a43bb3eaf`.

## New since V0.047

- Corrected 33 frames where overlapping pieces hid original artwork: enemies,
  robot generators, the 3D ramp, Amy and boss parts. This fixes 5,032 pixels;
  every other object frame remains unchanged.
- Kept all frame geometry, palette-bank assignments and priority settings.
  Gameplay/physics, the working audio implementation and camera timing are
  unchanged.
- Added independent source/packed-texture checks for 391 compositions and a
  same-build link to complete target texture-memory readback. Amy screenshot
  checks now use the independent compositor and reject the old black patches.
- Corrected the general hardware README's stale version heading; packaging
  now checks that heading against the actual build version.

Validation: 22 fast gates, 16,800-state player replay, original title pictures,
world/camera/source-pixel checks, audio/isolated probes, the full three-act
sequence, Act 1, special-stage win/return and opening pacing. The sequence's
16,116 gameplay states remain identical and all 16,113 intervals have zero
missed refreshes. Hardware and exhaustive animation/occlusion coverage remain
separate acceptance work.

Includes the previous monitor-icon, title-fetch-schedule, vertical camera
alignment and dense Act 2 pacing corrections. Card unchanged. Palmtree Panic
is not yet complete: original Sonic animation integration and broader coverage
remain, followed by later zones, optional CD++-style play and complete-game flow.
