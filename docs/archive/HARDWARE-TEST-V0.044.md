# Sonic CD Saturn v0.044 — hardware test

Keep `sonic-cd-saturn-prototype.bin` and `sonic-cd-saturn-prototype.cue`
together. Select the CUE in SAROO. The version is in the enclosing folder;
the filenames must remain as supplied because the CUE refers to the BIN.

Your v0.040 sound fix is preserved. This build adds measured rendering-speed
improvements, the full-width original title, and original HUD presentation,
including the corrected RINGS-label flash after collecting/losing rings.
It is a test candidate, not a finished Palmtree Panic release.

## Quick check

1. Cold-boot the game. On the title screen, check that the background fills both
   sides and that the clouds animate without obvious flickering/corruption.
2. Start a new game. Check SCORE, TIME, RINGS and the life icon. Collect rings,
   jump, then pause/resume. Confirm music and effects still work together.
3. Play the opening section and a busier section. Compare responsiveness with
   your previous build. If Sonic takes damage and loses all rings, the RINGS
   label should flash; collecting a ring should make it stay yellow.

A short reply is enough: **title okay/problem; HUD okay/problem; speed
okay/slower; sound okay/problem**. No photo or video is required.

Optional if something feels slow: hold Start and press Z after playing that
area. Confirm the panel reads `AUDIO TEST V0.044`. Its last 60-update window
reads `60 STEPS 60 VB MAX 1` if it missed no refreshes in that window. Larger
VB/MAX values are useful to report. Start+Z exits. This is a refresh-relative
measurement, not proof of 60 Hz on every video mode. There is no need to run
the independent test tone when normal game sound is working.

## Build identity and limits

- BIN SHA-256: `fd18db44c07bc9c296f675049dcc9bbd2e543fac5620231cd5ce918f6129c55c`
- CUE SHA-256: `af73da39224db801d5ce7fe85e5970c35fed224880876d3f2ce27811914e8634`
- All 19 host gates and focused emulator checks pass. Tested opening, complete
  Act 1, dense Act 2 and ring-loss stress routes have zero missed refreshes.
- The full-width title matches all 1,196 reference pictures. The new native
  HUD regression covers 1,088 cases against original artwork and retail code.
- These do not replace hardware visual/performance testing. Existing v0.040
  hardware sound confirmation is not a claim that v0.044 has been tested there.
- No new level content, firmware changes, or recurring QA job are included.

The immutable project candidate and detailed evidence are in
`build/hardware-candidate-v0.044-01`. Older candidate archives remain intact.
