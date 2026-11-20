# V0.049 — original Sonic animation integration

Focused same-BIN host/emulator validation passes. This is a hardware-test
candidate, not a complete-zone or hardware-accepted release. BIN SHA-256:
`e505d621b79ae2c374fdb5d3498efcc594ce5597f43beb6e883a0d0b3c8653a4`.

## New since V0.048

- Gameplay now uses the original Sonic animation scripts, mapping frames and
  horizontal/vertical flips, replacing provisional animation and extra rotation.
- All 198 original poses are available from a lossless, source-verified frame
  pack. Build-time composition avoids the slower runtime DPLC experiment.
- Disc poses follow the original player-before-object timing. Disc art no
  longer covers Sonic's shoes; Amy, Sonic and hearts use their original
  relative priorities. Amy's displayed idle pose comes from Sonic's actor.
- Added exact host/SH-2 presentation-state comparisons, real-player calls
  checked against retail 68000 execution, source-pixel gameplay captures and
  guarded texture-cache/transition tests.
- Reduced diagnostic stack usage after the expanded player state exposed a
  Saturn exception; no diagnostic assertions were removed.

The tested integration has 85,299 retail-matching host animation calls,
16,800 matching target presentation states and 162 source-pixel pictures.
All 198 poses / 811,008 source pixels are verified before compression. The
final build has zero missed refreshes in the 1,800-interval opening, complete
8,060-interval Act 1 and recorded three-act sequence (16,113 intervals).
World/source-pixel, main replay, title, audio, isolated diagnostics and
special-stage return gates all pass. The sequence's 16,116 gameplay states
remain unchanged; original title cadence retains 823 V-INTs / 1,196 pictures.

Retains V0.048's object composition, monitor, title, camera and performance
corrections. All four audio/CD source files still match hardware-confirmed
V0.040. Card unchanged; V0.044 remains the latest console-tested build.

Still open: broader original actor animation selection, diagnostic-only Amy
clock cleanup, remaining priority/occlusion and route/era coverage, hardware
confirmation, later zones, optional CD++-style play and complete-game flow.
