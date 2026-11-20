# First additional-zone object batch — V0.058

This batch integrates `wip/zone-objects` and completes its original sprite
path. The queued behavior code previously had no new draw-frame cases: its
objects fell back to Palmtree Panic's boulder. It also did not pass the new
actors' `patno` and render flags through `scd_objects_views`.

| Zone | Family | Native types | Placed records added |
| --- | --- | --- | --- |
| Tidal Tempest | wall1 | 67 | 127 |
| Quartz Quadrant | dair5 platforms | 69 | 126 |
| Stardust Speedway | wall7 and wall73 | 68 | 143 |
| Metallic Madness Act 1 | konbea conveyors | 70 | 18 |
| Metallic Madness | pistons | 71 | 27 |

These are 441 translated placements across acts, without counting the same
record again for every era in its mask. The source layout translator now
emits 4,723 non-PPZ placements in total. This does not establish complete
routes through those zones.

## Original artwork and runtime memory

`tools/zone_object_source.py` boots each relevant original level in the pinned
Sega CD core using the existing IPX entry fixture. It inserts a zero-subtype
actor in an unused dynamic slot and lets the original initializer choose
its tile base and mapping address. The recorded loaded VRAM and mappings
cover all 40 relevant act/era programs. Caches bind the program, capture tool,
emulator binary and dependent inputs by SHA-256.

`tools/zone_object_assets.py` flattens the original mapping pieces, preserving
the first opaque piece, palette indices and piece-local flips. It generates
250 frames, grouped into 12 act packs with separate era sections. The
runtime loads these into low work RAM at `0x002E6800`, after the object layout.
Only the current era is unpacked into VDP1 `0x76800–0x7FFFF`, the UFO texture
arena that is unused during normal gameplay. The largest era needs 15,744 of
38,912 available bytes. Palmtree Panic's existing textures stay intact.

`src/zone_object_art.h` validates the pack and each frame's bounds before it
is used. `src/zone_object_view.inc` applies the stage palette and draws the
correct frame, origin and global flips. It clips against the actual sprite
extent, including the 192-pixel-tall piston. Artwork is restored on every era
load, including return from modes that share the texture arena.

The existing draw-priority fix covers every spawnable type. The Makefile's
ISO dependency includes staged CD files, so an asset-only change reaches the
disc. Initialization has no side effects inside `assert`: the release SDK
compiles assertions away, and the first integration test caught precisely
that error in the new art loader before it was corrected.

## Verification

- `bash tools/test-zone-objects.sh`: sanitizer-enabled original-source
  behavior checks for walls, platforms, conveyors and pistons. The wall
  driver additionally verifies frame/flip propagation during actual updates,
  including all seven conveyor animation patterns.
- `python3 tools/test_zone_object_art.py`: the independent source compositor
  checks 673,792 pixels across 250 packed frames, all 1,000 global-flip cases,
  and the native pack reader's bounds handling.
- `python3 tools/test_zone_art_emulator.py`: enters all 40 variants through
  the Saturn level select, then uses an explicit mailbox-only art fixture
  to render every frame with all four flips through the production draw
  helper. V0.058 passes all 1,000 pictures and 2,606,256 original sprite
  pixels, plus the entire uploaded VDP1 bank readback. No controller enables this fixture;
  it does not claim to prove a gameplay route.
- `bash tools/test-zones-emulator.sh`: ordinary level-select entry and
  sustained simulation in all seven zones, including native objects.
- `python3 tools/test_disc_dependency.py`: proves a staged art change updates
  the ISO without changing the program, then restores the original asset
  and ISO even if the test fails. It never runs the temporary image.
- `python3 tools/qa-loop.py full`: all of the above, the existing fast
  checks and Palmtree Panic emulator regressions. The report identifies
  the final disc; inspect its result before treating a run as acceptance.

## Limits

Metallic Madness Act 3's separate `KONBEA83.C` family is still unported;
the converter excludes it. Stardust wall73's scripted motion supports the
existing bossflag interface, but the Metal Sonic race that drives it is
still absent. Other zone objects, water, bosses, animated terrain and
parallax remain unfinished. The Japanese soundtrack is retained; later
zones still need their own music routing. Hardware acceptance remains open.
