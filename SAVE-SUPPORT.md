# Saturn save support — research and implementation

Implemented in V0.060. The emulator-verified hardware-test candidate is
`build/save-v0.060-01/`. Real-console persistence still needs acceptance.

## Primary references

- Sega [Saturn System Library User's Guide, ST-162](https://antime.kapsi.fi/sega/files/ST-162-R1-092994.pdf), backup library chapter: use the BIOS backup library,
  allocate its 16 KiB expansion area, disable the reset button around writes,
  and use directory metadata to determine the read size. `BUP_Read` has no
  destination-capacity argument. `BupConfig` is two 16-bit fields.
- Sega's [updated backup library guide](https://www.infochunk.com/saturn/segahtml_en/prgg/sysg/bkup/hon/p01_10.htm)
  references STN-52 and allocates **2048 + 30 words** of workspace. The pinned
  libyaul allocates only 2048 and uses an enum for the configuration's first
  field. `src/save_saturn.c` supplies the documented layout and allocation
  without modifying the dependency checkout. Its other ABI structures have
  target compile-time size/offset checks.
- Original Sonic CD source in `.deps/scddisasm/src/CD Initial Program/IPX.asm`,
  `LoadGame`, `ReadSaveData`, `WriteSaveData`, and `RunR1` through `RunR8`:
  Continue resets lives to three; saves carry zone progress, future flags and
  Time Stones. The original uses zone checkpoints. This port deliberately
  saves **act starts**, so finishing an act does not require replaying it.
- Original `Backup RAM/Main CPU Functions.asm` verifies successful writes.
  The Saturn port also reads back and compares every byte before publishing
  a new checkpoint.

## Save contract

One game in the Saturn's internal backup RAM, represented by alternating files
`SCDSATURN00` and `SCDSATURN01`. The game never formats backup RAM or deletes
another game's files. A valid older record remains available during a new
write. This does not guarantee survival of damage to the entire filesystem or
loss of the console battery.

Each 32-byte record has an explicit version, big-endian generation counter,
zone, act, start era, all seven Time Stone bits, two current-zone act future
flags, seven completed-zone future flags, completion flag and CRC-32. Reads
reject unexpected file sizes before calling the BIOS, unsupported versions,
invalid stage values and checksum failures. Neither native struct padding nor
host byte order is persisted. At load, the newest valid generation wins; a
damaged companion record produces a recovery message. With no valid record,
Continue is unavailable. Missing files are a normal first run.

Autosave points are New Game, the next act after results (after the special
stage when entered), the next zone and final completion. Continue starts at
the checkpoint with three lives, zero rings, a fresh clock and the retained
Time Stones/future flags. Live position, rings, checkpoint poles and score
are not saved. Completed games can replay the final act. Level select, replay,
placement fixtures and debug era changes disable autosaving for that session;
New Game or Continue starts a normal saving session again.

New Game requires confirmation when existing save data would be replaced.
RAM DATA exposes the verified checkpoint and storage status. Failed writes
retain the pending checkpoint for retry and must be reported clearly without
preventing play. Unformatted RAM is left for the Saturn system manager.

## Verification required before release

- Host sanitizers: record validation, corruption, generation wrap, read/write
  failures, recovery and retry (`bash tools/test-save.sh`).
- Actual BIOS write/read/verify, exported internal RAM, separate fresh emulator
  processes and controller-driven Continue; stage, stones and both future
  masks must match after boot.
- Empty, full, unformatted, damaged and recovered save fixtures; no unrelated
  save changes; pending retry and New Game confirmation/cancel.
- Ordinary act/zone advancement and special-stage return autosaves, title
  regressions and Japanese music on Continue.
- Versioned BIN/CUE, evidence and readback manifest, plus hardware acceptance
  instructions. Emulator results do not establish real-console persistence.

All of these release checks pass. In addition to the storage tests below,
all 39 fast gates and six focused target regressions pass. The latter cover
gameplay replay, original title presentation/game-over return, music,
diagnostics, world interactions, and 5,208 Past ring-loss stress states with
zero missed refreshes. Evidence: `build/save-regression/report.json` and
`build/qa-loops/20260921-102114-321464/report.json`. The candidate manifest
binds the copied reports to the exact BIN and records readback hashes.

## Executed storage and progression checks

`python3 tools/test_save_matrix.py` passes 29 cases, with real BIOS access and
separate emulator processes for cold boots. It covers empty saves, two later
zones, full Time Stone masks, current-act and completed-zone future flags,
confirmation/cancel, replacement, corruption/recovery, oversized files,
unsupported versions, full and unformatted memory, unsuccessful retry,
successful retry after space becomes available, and overwriting an inactive
record when both slots already exist on a full device. Read-only and failed
writes preserve the entire backup image. Writes with available space leave
unrelated sentinel files byte-identical. Continue captures identify the
correct Japanese CD track and its playing state.

`python3 tools/test_save_progression.py` passes eight steps:

- Controller-only Palmtree Panic Acts 1–3, autosaving into Collision Chaos,
  followed by a fresh process that Continues there (generation 4).
- A won Special Stage 1 saves Time Stone 1 and Act 2 (generation 2), then a
  fresh process restores both. Entry uses the established 50-ring fixture;
  the harness explicitly enables saving after fixture placement. The stone
  itself is earned through the retail win controller route.
- The same big-ring fixture without that test override leaves the original
  New Game save untouched, including after the special-stage win.
- Continue from a seeded PPZ Act 2 record, complete the ordinary act route,
  save Act 3 Bad Future and cold-boot it. The nonzero stone mask `0x55`, act
  future mask `1`, and completed-zone future mask `0x0b` survive both the real
  BIOS update (generation 20 to 21) and subsequent boot.

The emulator exports only its 32 KiB internal backup memory between processes;
these are not emulator save states. Missing-device and interrupted-write
service behavior is additionally covered by host fault injection. Internal
RAM is always present in this emulator, so a physically absent device is not
claimed as a target test. Reports live in `build/save-matrix/report.json` and
`build/save-progression/report.json`.

## Real Saturn / SAROO acceptance

Use the matching V0.060 BIN and CUE together. Leave older known-good packages
available until this candidate is accepted. The port uses the standard BIOS
internal backup device; cartridge storage selection is not implemented.

1. Boot and open RAM DATA. Existing valid progress should expose Continue;
   first use should show NO SAVED GAME. B returns to the original title.
2. Start New Game. Complete an act and wait until the next act's title card
   has finished. Save writes occur during stage loading; do not switch off
   during that transition.
3. Power off, boot the same image again, choose Continue and verify the next
   act starts with three lives and the proper Japanese song.
4. After earning a Time Stone or a good future, finish the stage transition,
   repeat the cold boot and inspect the stone count/future flags in RAM DATA.
   A completed zone's future flag appears under GOOD ZONES.
5. Choose New Game, cancel the confirmation, then Continue: the old checkpoint
   must remain. Confirm New Game only when intentionally replacing it.

RESET is held off (SMPC RESDISA) for every backup write, verify and delete,
then enabled again. Time Attack records use a file pair per preset
(SCDSATURNTA/TB Classic, SCDSATURNTP/TQ CD++): a store writes the other name
with the next generation, reads it back, and only then removes the older file,
so a torn write keeps the previous records and one file stays in use. If the
other file cannot fit, the store returns BIOS code 4. The current verified
record remains intact. The menu reports RECORDS NOT SAVED and keeps the new
result in memory. A later record write can retry after space is available.
A cold boot loads the last verified record. An earlier build's single
SCDSATURNTA loads. A slot or record file whose read
fails with a device error is read again before the next write; while it stays
unreadable nothing is written, so a lower generation never replaces it.

The game does not format storage or erase other games to make space. A save
failure is displayed during play and in RAM DATA; its latest pending
checkpoint can be retried with A during the same running session. If both
records are damaged, Continue is hidden and a confirmed New Game can replace
this game's records. If one survives, RAM DATA reports OLDER SAVE RECOVERED.
The two small records together use four internal 64-byte blocks (256 bytes).
Their 32-byte payloads are not Sega CD save-file compatible. No card deployment
or physical-console save acceptance has occurred during this task.
