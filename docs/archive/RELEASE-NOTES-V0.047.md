# V0.047 — visual/pacing hardware-test candidate

Status: focused same-BIN host/emulator checks pass. Not hardware accepted, not
a complete Palmtree Panic or full-game release. BIN SHA-256:
`8e50d87b961be55f37ed3c5ed74f4a69899eb35aca737df1247a2ab1698e6825`.

## Changes since the last hardware-tested V0.044

- Monitor screens: corrected overlapping source-art pieces that hid item icons.
  All twelve monitor frames now use the original first-piece priority.
- Title clouds: corrected the VDP2 fetch schedule. Original title pictures and
  timing remain protected; Saturn confirmation of the reported stripes is needed.
- Scrolling: corrected a reproduced one-update difference between terrain and
  sprite presentation. Manual framebuffer swaps plus an early software clear
  keep the layers together without old pixels trailing at the bottom.
- Dense Act 2: removed a missed refresh during ring scatter. Constant cloud
  scroll bands are computed once, and ring creation skips already-searched
  occupied slots. Controller inputs, gameplay states and ring velocities are
  unchanged on the recorded complete-zone comparison.
- QA: added exact controller replay across all three acts, per-act timing
  acceptance, source-backed camera-motion checks, raster-table comparisons and
  dense/fragmented/full object-pool ring-scatter tests.

The hardware-confirmed audio implementation is unchanged. Test evidence and
known limits are in PERFORMANCE.md and CAMERA-PRESENTATION.md.

Validation: 21 fast gates; 16,800-state player replay; 1,196 exact title pictures;
world/monitor/VRAM and 16-frame camera checks; four-era and isolated audio;
full three-act progression and host replay; special-stage win/return. The zone
sequence has zero late intervals over 16,113 updates, with all 16,116 states
unchanged. Separate opening and Act 1 pacing also have zero misses.

## Hardware retest priorities

1. Cold boot: watch the upper title clouds for vertical lines/flicker and check
   title music. Start the game normally.
2. Check monitor item icons and static animation before breaking them. Confirm
   item behavior, ring/jump effects, music and pause/resume.
3. Watch stationary springs/platforms against the terrain while the camera
   moves vertically. Look for relative floating, flicker or bottom-edge trails.
4. In dense Act 2 sections, lose a substantial ring collection and watch for
   stalls, corruption or missing rings. The automated regression reaches its
   stress case near X 7997 / Y 552; this is a test location, not a changed level.

## Still open

The reported small brick platform has not been positively identified. Original
Present floating blocks intentionally appear on contact; no global visibility
change was made. Other sprite-piece overlap cases and original Sonic animation
integration remain, along with broader route/era and hardware acceptance work.
CD++-style options, later zones, complete-game flow and fantasy box art are not
included in this candidate. The full-port goal remains active.
