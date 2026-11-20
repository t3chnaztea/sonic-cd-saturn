# Original gameplay HUD — V0.044 ring-flash correction

V0.043 remains preserved unchanged. V0.044 changes presentation only: the RINGS
label now keeps the original palette state instead of deriving its color from
`player.frame & 16`. Audio, player physics, score, time and ring counts are not
changed. The build is not hardware-accepted.

## Reproducer and original behavior

Start without rings, update through V-INT 16 (red), collect a ring at 17 (yellow),
then lose it at 18. Retail keeps the label yellow until the next eligible toggle
at 32. The former native selector immediately turns it red at 18 and then yellow
at 32: it has lost the original state.

`Level/_Objects/HUD and Points/Main.asm`, `ObjHUD_Main/.Rings`, clears the palette
bit whenever rings are nonzero. With zero rings, it toggles that bit only when an
object update observes `levelVIntCounter & 15 == 0`. `Level/Main.asm` increments
that counter in V-INT even while paused, but does not run objects while paused.
Thus the clock is the VBlank counter, not the simulation clock; a missed boundary
does not cause a catch-up toggle.

`src/hud_animation.h` implements this small state transition. `main.c` invokes it
once in the normal gameplay-update branch, using the captured `simulation_tick`
(the actual VBlank counter), after acquiring the current ring count. Merely
redrawing a frame does not toggle the label. Loading a stage and player reset
clear the stored palette state. This does not establish identical absolute
startup V-INT phase between the two consoles.

## Independent renderer regression

Run `python3 tools/test_hud_render.py`.

- The oracle executes the unchanged retail R11A `.Rings` machine code at
  `0x20AD28` in the pinned Genesis Plus GX 68000 CPU. Its downstream `DrawObject`
  submission at `0x203AF2` is replaced with RTS in isolated fixture memory only.
  No disc or gameplay program file is modified. Instruction signatures, variable
  addresses, successful return and unchanged unrelated actor bytes are checked.
- The host harness includes the production `hud_view.inc`, not a second copy of
  the native rendering algorithm. AddressSanitizer and UndefinedBehaviorSanitizer
  guard command generation, texture bounds/alignment and upload integrity.
- Original HUD mappings, number tiles, life art and monitor/time-post mappings
  independently reconstruct expected palette-index pixels. Every opaque pixel
  and the complete set of transparent positions must match the native commands.
  This checks full compositions, not a handful of sample pixels.
- 1,088 cases check 2,265,705 original opaque pixels: all four eras, score/ring/life
  boundaries, second/minute/maximum-clock boundaries, Past/Future icons on both
  sides of the 90-tick blink threshold, zero-ring color histories, VBlank wrap,
  skipped/repeated counters, and frozen/paused renders. The old frame-derived
  selector fails the explicit ring-loss case at frame 18.

Evidence is in `build/hud-render/`: `report.json`, actual input cases, native
command records and sanitizer log. This gate is part of the fast QA suite.
Existing emulator HUD pixel comparisons still test real target output; this
host test does not substitute for VDP priority/palette, whole-game clock-phase,
or real-hardware visual acceptance. It does not identify the user's unspecified
graphical glitches.
