# V0.058 — first additional-zone objects and Japanese music

Tidal Tempest walls, Quartz Quadrant platforms, Stardust Speedway walls, and
Metallic Madness conveyors and pistons now use their original behavior and
sprite frames. This adds 441 translated placements. Their graphics cover
40 act/era programs and 250 frames, including original offsets, palette
indices and flips. Missing draw priorities no longer abort the renderer;
staged asset changes now invalidate the disc build.

The build requires the supplied Japanese soundtrack. All nine supported
CD-DA songs come directly from the Japanese disc's track starts, and the
shared Past music and effects remain verified. Later zones still need their
own era music routing. See [JAPANESE-MUSIC.md](JAPANESE-MUSIC.md).

[ZONE-OBJECTS.md](ZONE-OBJECTS.md) describes extraction, memory layout,
source behavior/pixel checks and the Saturn artwork fixture. Package hashes
and the completed validation record are maintained at the top of
[NEXT-SESSION.md](NEXT-SESSION.md).

This is a local development candidate. Hardware acceptance, later bosses,
remaining object families, water, parallax, terrain animation and complete
routes through the later zones remain open. Metallic Madness Act 3's
separate conveyor family and the Metal Sonic race are outside this batch.
