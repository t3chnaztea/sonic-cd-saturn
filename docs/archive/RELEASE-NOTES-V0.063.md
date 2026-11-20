# V0.063 — Collision Chaos campaign journey (hardware candidate)

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

The V0.063 BIN's focused replay passed 17,039 of 17,039 exact
positions, followed by 300 neutral target observations. Natural arrivals occur
in Past at sequence 5318, Present at 14537, Good Future at 15372, and Act 2
Present at 17041. The generator is destroyed at sequence 8798 for 1,500 points;
the completed act carries 11,200 points into Act 2. All ordinary gameplay
intervals meet the one-VBlank cadence, with no respawns. Japanese Collision
Chaos tracks 12, 13, and 14 play in their respective eras, and track 12 plays
after Act 2 entry and cold Continue. The Act 2 checkpoint advances backup RAM
to generation 5 and preserves the Act 1 Good Future flag. The cold boot reads
back that run's exact saved bytes. Evidence:
`build/cc1/generator/campaign-generated/target/report.json` (V0.063).

To reproduce the focused gate on a prepared local build:

```sh
python3 tools/prepare_cc_campaign_checkpoint.py
python3 tools/test_cc_campaign_generator.py --milestone continue
```

The build requires the owner's Japanese Sonic CD CUE at
`assets/private/sonic-cd-japan.cue`, with its referenced BIN files alongside
the original CUE; see [JAPANESE-MUSIC.md](JAPANESE-MUSIC.md). These private source
files and any built disc images must not be shared. V0.063 corrects the
in-game audio diagnostic label to match its boot header. V0.062 passed full
QA and was preserved locally but was not copied to SAROO; its diagnostic
label still read V0.061. The V0.063 BIN SHA-256 is
`87a05fe81d831375d6f90794685937f598f8add6f41b2026821ab2d681220812`.
All 52 fast gates passed at
`build/qa-loops/20260923-133719-608246/report.json`, and all 80 full gates
passed on this exact disc at
`build/qa-loops/20260923-130148-685694/report.json`. The full report binds the
campaign wrapper SHA-256
`ee79adfe291ca72dcda7c341274e256de208ae0bc6b1e8041e0ca428c53e01b7`.
The local-only package is `build/hardware-v0.063/`. Nothing has been copied
to SAROO.

Hardware acceptance is untested. On Saturn/SAROO, boot the packaged V0.063
candidate, start New Game, clear Palmtree Panic Acts 1–3, then use Continue
from the earned Collision Chaos Present save. In Act 1, travel to Past, destroy
the generator, return to Present, travel to Good Future, finish the act, and
verify Act 2 Present begins with the carried score. Power-cycle the console,
select Continue, and verify Act 2 Present loads with the earned Good Future
progress and Japanese Present music. Record the package/BIN hash and observed
console behavior before claiming this hardware gate.
