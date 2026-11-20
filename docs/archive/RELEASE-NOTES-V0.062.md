# V0.062 — Collision Chaos campaign journey (hardware candidate)

Collision Chaos Act 1 now has a controller-driven campaign route from a real
Continue save. Sonic starts in Present after clearing Palmtree Panic Acts 1–3,
travels to Past, destroys the robot generator, returns to Present, reaches Good
Future, finishes the act, and enters Act 2 Present. The earned Good Future flag
survives the Act 2 save and a separate cold Continue boot. This does not
complete the remaining Collision Chaos objects, terrain animation, backgrounds,
or the full game.

The focused emulator check starts by running ordinary New Game controls through
Palmtree Panic Acts 1–3. That progression writes a generation-4 Collision Chaos
Act 1 Present checkpoint to internal backup RAM. A separate emulator process
cold-boots Continue from those exported bytes and verifies the saved stage,
three lives, Japanese track 12, and unchanged backup. The campaign host then
records pad input using the original `pcol` collision routine. The target replay
boots that earned save, supplies only those pad commands, and compares every
observed Sonic position with the host before checking travel, generator,
results, music, save, and Continue events.

The V0.062 BIN's focused replay passes 17,039 of 17,039 exact
positions, followed by 300 neutral target observations. Natural arrivals occur
in Past at sequence 5318, Present at 14537, Good Future at 15372, and Act 2
Present at 17041. The generator is destroyed at sequence 8798 for 1,500 points;
the completed act carries 11,200 points into Act 2. All ordinary gameplay
intervals meet the one-VBlank cadence, with no respawns. Japanese Collision
Chaos tracks 12, 13, and 14 play in their respective eras, and track 12 plays
after Act 2 entry and cold Continue. The Act 2 checkpoint advances backup RAM
to generation 5 and preserves the Act 1 Good Future flag. The cold boot reads
back that run's exact saved bytes. Evidence:
`build/cc1/generator/campaign-generated/target/report.json`.

To reproduce the focused gate on a prepared local build:

```sh
python3 tools/prepare_cc_campaign_checkpoint.py
python3 tools/test_cc_campaign_generator.py --milestone continue
```

The build requires the owner's Japanese Sonic CD CUE at
`assets/private/sonic-cd-japan.cue`, with its referenced BIN files alongside
the original CUE; see [JAPANESE-MUSIC.md](JAPANESE-MUSIC.md). These private source
files and any built disc images must not be shared. The V0.062 BIN SHA-256 is
`2a64e2adfa48104e85a99573b063e2962ee3abe7e92ce0870bb5ad23392a09bb`.
All 52 fast gates pass in `build/qa-loops/20260923-121142-388096/report.json`;
all 80 full gates pass on this BIN in
`build/qa-loops/20260923-121733-169215/report.json`. The private local
full-QA archive is preserved at `build/hardware-v0.062/`; its BIN and ZIP
were read back and hash-checked. Nothing has been copied to SAROO.

Hardware acceptance is untested. On Saturn/SAROO, boot the packaged V0.062
candidate, start New Game, clear Palmtree Panic Acts 1–3, then use Continue
from the earned Collision Chaos Present save. In Act 1, travel to Past, destroy
the generator, return to Present, travel to Good Future, finish the act, and
verify Act 2 Present begins with the carried score. Power-cycle the console,
select Continue, and verify Act 2 Present loads with the earned Good Future
progress and Japanese Present music. Record the package/BIN hash and observed
console behavior before claiming this hardware gate.
