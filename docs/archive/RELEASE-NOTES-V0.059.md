# V0.059 — Japanese music for every zone and era

Later zones previously replayed Palmtree Panic's four songs. Every stage now
selects its own Japanese Present, Past, Good Future or Bad Future music.
Temporary songs preserve the current zone, so returning from power-ups,
boss music, special modes or a cancelled warp restores the correct era song.

The disc contains 34 audio tracks: 27 copied directly from the supplied
Japanese CD and seven Past tracks rendered through its original PCM banks.
The original ten V0.058 tracks remain byte-identical. The other six zones
append their four songs. The expanded TOC handles the final track's leadout,
and pause/resume/looping use the resolved song rather than the logical cue.

The Past extractor accepts odd-length original banks and ignores stopped
channels when detecting a sequencer repeat. The original tempo routine still
increments their duration counters; including those counters could prevent a
repeat from being recognized. Capture provenance binds each bank, tool and
emulator core. Existing fade/seek loops remain non-gapless.

All 28 Saturn zone/era playback and pause/resume cases pass, including a
resumed loop on the final disc track. All 38 fast gates and eight focused audio/gameplay regression gates pass,
including 5,208 ring-loss stress states with zero missed refreshes. Package
hashes and evidence are recorded in NEXT-SESSION.md. This does not
claim hardware acceptance or completion of the remaining game systems.
