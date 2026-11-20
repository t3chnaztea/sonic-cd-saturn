# V0.045 visual-correctness work in progress

This is a development build, not a hardware-tested release or complete-port
claim. V0.044 remains the last user-tested candidate and has not been replaced
on the card.

## Monitor root cause and correction

Original monitor mappings put the 16x16 item/static piece first, then casing
pieces containing opaque screen pixels. Original `DrawSprite` writes them in
SAT link order, where the first opaque sprite wins. The asset converter used
the opposite painter order and covered the icon. This is an asset defect,
not a missing power-up implementation or a speculative Saturn palette fault.

`tools/convert_objects.py` now uses first-piece-front composition for all twelve
monitor frames. `tools/monitor_pixels.py` independently evaluates each output
pixel by walking original pieces until the first opaque source texel. It does
not invoke the production painter. Changed pixels in frames 0..11 are
212, 92, 156, 99, 100, 142, 92, 100, 224, 224, 0, 0. All eight item icons are
distinct. The old `object-art-baseline.json` is preserved; tests prove it matches
the old defective composition, then require corrected source pixels instead.

## Memory safety and presentation preservation

Restoring ten distinct icon/static textures initially grew object art beyond
the fixed UFO texture boundary. This failure was not waived. VDP1 heights are
in rows (only widths require eight-pixel units), so transparent vertical padding
now uses a width-dependent row quantum instead of unconditional eight-row
alignment: `32 / gcd(32, width / 2)`. Texture starts and following CLUTs remain
**32-byte aligned**. Existing origin/flip logic uses exact crop metadata.
Canonical decoded art and all four flips retain
historical pixels except for the independently verified monitor correction.

Decoded object art is now 345,344 bytes (previously 374,016; naive corrected
pack 379,456), ending at VDP1 0x6F500, below the unchanged 0x76800 UFO boundary.
Converter and tests explicitly enforce that boundary and the CD pack capacity.
Thirty object asset tests pass, including independent monitor/digit comparisons.

## Current validation

- Corrected build completed: `build/build-v045-aligned.log` (existing compiler
  warnings remain). BIN SHA-256:
  `1491384837b644a4039010d24940158a7e70682e333a180aa2f65ba0bea3b8fc`.
- Final aligned fast pass passed all 19 gates:
  `build/qa-loops/20260919-231406-286358/report.json`, `build/fast-v045-final.log`.
  Do not confuse host asset success with target
  palette/addressing verification.
- World target pass **passes**: `build/world-v045-aligned.log` and final checker
  `build/world-v045-readback-final.log`, `dist/world-report.json`. Adds 100 monitor captures
  across five ordinary controller break/grant routes, requiring each capture to
  match exactly one recently submitted source composition. Item and static
  animation both appear: 83,300 opaque source pixels across five item subtypes.
  All eight subtype assets and all twelve frames have host oracle coverage.
  Three-frame presentation history accommodates
  the existing measured display pipeline, not arbitrary pixel tolerances.
- Earlier world evidence moved intact to `build/pre-v045-qa/world-qa`.
- Full target VDP1 readback matches all 345,344 object bytes, 392 frame layouts,
  initial high-priority conversion and Past-era palettes; capture hash and
  source identities are recorded. Total world captures: 222. The actual Sonic
  icon was also visually inspected (`build/monitor-v045-icon.png`).
- Same-BIN main replay passes 16,800 states / 268,800 state words and 21 scene
  checks (`build/emulator-v045.log`). Audio passes four-era music, effects mix,
  silent pause with fixed disc position, resume and looping
  (`build/audio-v045-final.log`). The first audio check correctly rejected the
  stale V0.044 gameplay-audio report; it was rerun after the matching replay,
  without relaxing the identity gate. No hardware retest yet.
- Audio/CD/sound-memory source hashes still equal the user-confirmed V0.040
  implementation. Title, full-act pacing, isolated audio probes and special
  return have not been rerun on this BIN; historical passes are not relabeled.

## Failed development attempts retained

The first padding reduction mistakenly preserved only eight-byte alignment.
The target test failed at the travel-cutscene color gate; inspection showed
corrupt/missing sprites. Saturn CLUT fetch masks the low two address units
(`vdp1_sprite.c` uses `(color & ~3) << 2`), requiring 32-byte alignment. The
failed BIN/CUE and captures remain in `build/world-v045-failed-01`. The gate was
not weakened; corrected packing now passes it and exact VRAM comparison.
A diagnostic attempt to read an unexported core VRAM symbol stopped explicitly;
`build/world-v045-readback-failed-01` retains that run. The verified readback
uses the exported debug-read function, not an assumed private memory symbol.
Sega's [VDP1 table specification](https://www.infochunk.com/saturn/segahtml_en/hard/vdp1/hon/p02_20.htm)
independently documents the 32-byte CLUT boundary.

Other three hardware reports remain open. The original Present floating-block
behavior is a lead for the brick report, not proof of exact report identity.
Additional shared-compositor findings are tracked as PPZ-GFX-007. No physics or
audio implementation changes were made.
