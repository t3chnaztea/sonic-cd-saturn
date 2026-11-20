# V0.064 — Collision Chaos Acts 1–3 routes and earned campaign saves (hardware candidate)

Collision Chaos now runs from Act 1 through Act 3 on position-matched
controller routes in every era, and an ordinary saving campaign reaches Act 3
in both futures. New in the game since V0.063: Collision Chaos terrain bumper
blocks (PLAYSP3.C), the Act 2 drum, Mecha Sonic props, Act 3 objects and boss,
and background/foreground cache fixes that remove the Palmtree Panic Act 2 and
Collision Chaos Act 2 late frames. This is not the full game.

Build: BIN SHA-256 `4b6d8fb1278680b240d6ad576b56398756ed446f77c139d6db66e25d30711d0f`,
CUE SHA-256 `6a4ea423414c3cbd85836b6c34e8e4a8d88ec9e226a3f1bb7631202bcac43038`.
Full QA: `build/qa-loops/20260925-190504-186134/report.json`, 99 steps, all pass.

Controller routes (every observed Sonic position matches the native host;
zero respawns and zero late gameplay intervals):

- CC1 into Act 2 from level select: Present 10,114, Past 9,356, Good Future
  8,714, Bad Future 9,683 positions.
- CC2 into Act 3 from level select: Present 9,544, Past 8,468, Good Future
  7,489, Bad Future 8,217 positions. A separate Good Future route with a
  39-ring loss stays within one refresh.
- CC1 campaign from the earned Palmtree Panic save: Present → Past generator
  → Present → Good Future → tally → Act 2, 14,925 positions, cold Continue.
- Earned CC3-entry saves through an ordinary saving campaign: Good Future
  (both acts' generators destroyed) and Bad Future (Act 1 only). Each cold
  Continue reloads the Act 3 checkpoint. No save is constructed.

Routes are found by a fixed-seed native-host search (`tools/cc_campaign_search.c`)
and accepted only by the Saturn replay. Palmtree Panic Act 2 era routes now
align their era-switch inputs to gameplay updates, not CD load time.

Hardware testing is pending. Emulator results do not establish console
acceptance or original-console parity.

## Also in this build

- **Act 3 boss** compiled from the original `BOSS_3.C`; three hits defeat it
  (`colicnt` 4→1). Act 3 Good and Bad Future routes pass the entrance lift,
  boss track, boss, capsule and results, then save at the Tidal Tempest Act 1
  handoff; a cold Continue reloads that save in both futures.
- **Act 3 objects:** `sikake33` (rotating platform, light, stopper) with its art.
- **Backgrounds:** Act 2 and Act 3 rasters match original CPU captures; Act 2
  drum tile cycles run. Palmtree Panic cloud rows now match the original plane.
- **Audio:** sound effects load per zone, so all Collision Chaos effects fit,
  including the boss hit. The CC spike trap plays FM $B7, not Amy's giggle.
- **Capsule flowers** in Collision Chaos Act 3 use the zone's own art.

## Known limits

- Loading the Collision Chaos sound bank adds about 0.65 s at zone entry; the
  previous picture stays on screen meanwhile.
- Tidal Tempest and later zones are outside this milestone.

## Hardware test checklist

1. New Game through Palmtree Panic into Collision Chaos; play all three acts,
   once for Good Future (destroy both generators) and once for Bad Future.
2. Check bumpers, bumper blocks, drums, flippers, Act 3 platforms and the boss.
3. Listen for the boss hit and bumper sounds; check music in every era.
4. Watch for slowdown on large ring losses and fast scrolling.
5. After the Tidal Tempest handoff, power-cycle and Continue.
