# V0.060 — save progress and Continue

The port now saves to Saturn internal backup RAM. Continue appears on the
original title menu when a verified save exists and restarts the saved act
with three lives, retaining Time Stones and good-future flags. The correct
Japanese zone/era music plays after loading.

Progress saves when starting a New Game, advancing to the next act or zone,
returning from a special stage and completing the final zone. Position, rings,
score and checkpoint poles are not saved. New Game asks before replacing
existing data; B cancels. RAM DATA shows the saved stage, stone count, future
flags and storage status.

Missing saves are handled as first use. Damaged records are rejected, with an
older valid copy used when available. Full or unformatted memory does not
prevent play: an on-screen message reports unsaved progress, and RAM DATA can
retry the latest pending checkpoint during that running session. The game
never formats memory or removes other games' saves. Two small files use four
internal backup blocks in total. Debug level selection, placement fixtures,
replays and era changes do not advance a normal save.

Research followed Sega's BIOS backup-library documentation and the original
Sonic CD save flow. The local BIOS adapter corrects the pinned SDK's device
table stride and workspace allocation; every successful write is verified
and read back before becoming the active checkpoint.

Validation passes: 39 fast checks, 29 storage/menu cases, eight progression and
cold-boot steps, and six focused target regressions. Cold boots use separate
emulator processes with exported internal RAM, not save states. Special-stage
entry uses the established ring fixture, then earns the stone through the
retail controller route. Ordinary act/zone progression uses normal controls.
The existing Past stress run matches 5,208 states with no missed refreshes.

Candidate: `build/save-v0.060-01/`. It is ready for real Saturn/SAROO save testing;
no hardware persistence result or card deployment is claimed. Follow the
acceptance steps in [SAVE-SUPPORT.md](SAVE-SUPPORT.md).
