# V0.073 — original physics and object fixes from Tidal Tempest retail parity

Release date label: 2026-10-04. This is a private Saturn/SAROO test build. The
last user-confirmed console build is V0.065. Keep the BIN/CUE and ZIP local;
they contain assets from the owner's Sonic CD disc.

## Changes

Each change follows the Sega CD original. The retail Tidal Tempest programs,
run beside the native host, showed each difference
(`build/tt-parity/v072/`, `build/tt-parity/v073/`). These are shared player and
object code paths. They affect all four ported zones.

- Sonic starts each stage grounded. `ObjSonic_Init` sets no status bits
  (scddisasm `Sonic/Main.asm:135-155`). His first update sets the air bit only
  when no floor is under him. Before, native Sonic started airborne and fell
  for two updates, which left a Y subpixel offset (`src/player.c`).
- At the stage start, placed actors get one update before Sonic's first move,
  as the level loop runs objects while Sonic runs only his Init
  (`Level/Main.asm`, `src/player.c` `scd_player_objects_lead`).
- Tidal Tempest random numbers use the 68000 `Random` routine
  (`Level/Functions (General).asm:14-33`). The PC port's routine gives a
  different seed chain. This changes bubbles and other random actors
  (`src/objects_tt_common.inc`, `src/water.c`).
- Monitors are 25 pixels wide for solid contact (`oWidth` $F,
  `Monitor and Time Post/Main.asm:113`). They were 24 (`src/objects.c`).
- A rolling Sonic no longer lands on a monitor (`Object Solid.asm:329-332`).
  He passes into it and breaks it on the next contact (`src/objects.c`).
- A right-wall hit in the air copies the Y speed into the ground speed, as the
  left wall does (`Sonic/Main.asm:2252-2254`). The PC port copied the zeroed X
  speed (`tools/player_fixes.py`).
- Springs use the original top contact: a 2-pixel tolerance, the smaller
  penetration picks the axis, and Sonic is placed on the spring top before the
  launch. A spring keeps Sonic's ground speed (`RIDECHK.C` `hitchk`, `hit_y`,
  `ride_on_set`; `src/objects.c`, `src/objects_bobin.inc`).
- Windowed zone actors (Tidal Tempest, Quartz Quadrant) load on the camera
  window alone (`Object Spawner.asm`, `SpawnObjects_Forward`), not within 480
  pixels of Sonic (`src/objects.c`).

- A time-warp arrival runs the placed actors' first update during the load,
  while the display is off, as the restarted level program does
  (`Level/Main.asm`, `src/main.c` `load_era`). The first update after a warp
  no longer pays for two object steps (Palmtree Panic and Collision Chaos
  arrivals had late frames).
- Tidal Tempest placements stream in retail record order: the spawner runs
  when the camera's 128-pixel chunk changes, and each placed actor frames
  itself out of that window (`Level/Object Spawner.asm`, `src/objects.c`
  `tt_stream`). Ring groups spawn from their first ring (`Ring/Main.asm`).
- Tidal Tempest touch response handles one contact per update, as retail
  `pcol` does (R41D__.MMD $7060-$7232). A bounce off an enemy halves the speed
  with `asr` (rounds down; R43C__.MMD $7160).
- Riding a platform reads both foot sensors (`Object Solid.asm:396-406`).
  Leaving a pushed object keeps the push bits (`Object Solid.asm:473-479`).
- Sonic's right edge stops 56 pixels earlier while a boss locks the screen
  (`ObjSonic_LevelBound`, `Sonic/Main.asm:1686-1694`).
- Rolling slope resistance rounds down (`ObjSonic_SlopeResistRoll`, `asr.l #2`).
- Tidal Tempest Act 3 boss (egg4air): the chase stops on each waypoint and
  reads Sonic's speed, not its own (R43C/R43D__.MMD $BB8A, $BDF8).
- Tidal Tempest water entry and the vertical scroll wrap follow retail
  (R41D__.MMD $4376, R43D__.MMD $3058).

Documented deviation: retail Tidal Tempest moves the water level once per
V-INT frame, so a lag frame moves it again. The Saturn build moves it once per
gameplay update. Gameplay does not depend on Saturn lag.

Route scripts were searched again with the existing search tools: all Palmtree
Panic, Collision Chaos and Quartz Quadrant routes, ten Tidal Tempest routes,
nine natural-travel routes and both Good Future campaign routes. The Tidal
Tempest Act 3 search now scores the egg4 fight above the cells before it and
counts popped shield bubbles (`tools/tt_route_search.c`). No route was edited
by hand.

## Candidate evidence

Final BIN SHA-256:
`5879a195c031588a504db8fa7125266f94599b4cde58907b367d2a05e54ccf25`.
Full QA passed 165 checks in
`build/qa-loops/20261004-163735-999328/report.json`. Its disc-dependency step
rebuilds the ISO, which changes only ISO timestamps. The CC scroll-target,
entry-scene and EMIE3 checks were rerun on the final BIN and pass.

Two fixed-policy emulator drivers were retuned for the new physics, by scan,
not by hand: the Palmtree Panic Act 1 policy starts its jump phase at 609
(`tools/test-act-emulator.sh`), and the Act 3 boss policy holds Jump 16
updates and rests 4 (`tools/emulator_test.c`). The pass conditions are
unchanged.

Tidal Tempest on the final BIN, emulator only:

- Sprite art matrix: 10 of 10 programs (`tools/run-tt-art-matrix.sh`).
- Controller routes: 10 of 10 (TT1 A–D, TT2 A–D, TT3 C–D), 0 respawns, 0 late
  intervals. TT3 C and D were searched again (seed 41).
- Continue chain: CC3 → TT1 → TT2 → TT3 → Quartz Quadrant, 4 of 4.
- Natural time travel: 10 of 10 routes (`build/tt-travel/v073/`).
- Earned Good Future campaign: Acts 1–3, 3 of 3 (`build/tt-campaign/v073/`).
- R4 boss, capsule and Quartz Quadrant handoff: full-QA step
  `tools/test_tt3_boss_emulator.py`.
- Retail parity, contiguous matched updates from the stage start: 1A 6,848
  (whole), 1B 2,047 (whole), 1C 1,569, 1D 4,725, 2A 8,231 (whole), 2B 2,405,
  2C 1,289, 2D 4,865 (whole), 3C 5,535, 3D 5,538. This is evidence, not a gate.

## Console checklist

1. Confirm the audio diagnostic version string, the BIN hash above, and the
   SAROO folder. Boot V0.073 twice. Record Saturn model, video mode, and
   SAROO firmware.
2. Stage starts, all four zones (Palmtree Panic, Collision Chaos, Tidal
   Tempest, Quartz Quadrant): start Act 1 from level select and from a
   Continue. Sonic must stand still on the ground at the start, with no drop.
   Lose a life and check the restart the same way.
3. Monitors, all four zones: roll into a monitor from above and from the side.
   It must break; Sonic must not stand on it while rolling. Walk into a
   monitor: Sonic stops one pixel further from it than in V0.072.
4. Springs, all four zones: jump onto an upward spring, roll onto one, and run
   over one. The launch height and the running speed after landing must look
   right. Palmtree Panic and Collision Chaos springs are the main check.
5. Walls in the air: jump into a wall on the right and on the left, all four
   zones. Sonic must slide down and keep moving normally when he lands.
6. Tidal Tempest: play Act 1 and Act 2 in all four eras and Act 3 in both
   futures. Watch bubbles, enemies, moving platforms, the water line and
   currents. Breathe from a large bubble once in each act. Ride a moving
   platform to its end and step off. Push a block, then walk away from it.
   In the Act 3 boss arena, pop shield bubbles for air and check that Sonic
   cannot run past the right screen edge.
7. Tidal Tempest and Quartz Quadrant: run right fast through a stage. Enemies
   and platforms must appear at the screen edge, not pop in late.
8. Time travel, all three zones with warps (Palmtree Panic, Collision Chaos,
   Tidal Tempest): warp to the Past and to the Future. The first second after
   arrival must not stutter. Enemies and platforms near the arrival point must
   already be in place. In Tidal Tempest, warp Present to Past, destroy the
   robot generator in Acts 1 and 2, and beat the Act 3 boss in the Good
   Future. Check results and the Quartz Quadrant handoff.
9. Continue: save at a Tidal Tempest act end, power off, cold boot, and choose
   Continue. Repeat from the Collision Chaos Act 3 save.
10. Note anything worse than V0.065, the prior console-tested build. Record
   faults with the BIN hash, zone, act, era, position, controller inputs, and
   a photo or video. Console results decide hardware acceptance.
