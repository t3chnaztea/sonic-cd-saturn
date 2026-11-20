# V0.065 — Tidal Tempest Acts 1–3 and the original physics (hardware candidate)

Tidal Tempest now plays from the Collision Chaos Act 3 handoff through Act 3
and its boss to the Quartz Quadrant handoff. It has water, the vertical and
horizontal original cameras, looping Act 2/3 levels and zone art cycling.
Palmtree Panic and Collision Chaos now run the original player physics and
camera. This is not the full game.

Build: BIN SHA-256 `3cfec26970ff358a8eaf09ae45af112a7a034567c2dae3302a40b5870695e396`,
CUE SHA-256 `4bbb14f02228d17c802f6aaf6a4df774b2d0bed2a5adbb6cc23c331dacd11d07`.
Full QA: `build/qa-loops/20260926-083649-864414/report.json`, 157 steps, all pass.

Controller routes (every observed Sonic position matches the native host):

- Route batch on this BIN: 38 of 38 pass, with zero respawns and zero late
  gameplay intervals. Palmtree Panic 7/7 (Act 1 Present; Act 2 all four eras;
  Act 3 both futures). Collision Chaos 18/18 (Acts 1–3, the generator route,
  the Act 2 Good Future ring-loss stress route, the earned campaign saves and
  their Continues). Tidal Tempest 13/13 (Acts 1 and 2 in all four eras, Act 3
  in both futures with 4,704 positions each, and the Continue chain).
- Tidal Tempest Continue chain: from the earned Collision Chaos Act 3 save,
  Act 1 (9,678 positions) → Act 2 (9,255) → Act 3 Bad Future (4,704) → the
  Quartz Quadrant handoff. Each act starts from the previous act's save through
  the real Continue menu, and a cold Continue of the final save passes.

Routes are found by a fixed-seed native-host search and accepted only by the
Saturn replay. Gate routes are now scripts under `tests/routes/` and do not
use reactive controllers. That now includes the Palmtree Panic Act 2 Present
gate, which the physics change had broken. After the physics change every
route was searched again.

Hardware testing is pending. Emulator results do not establish console
acceptance or original-console parity.

## Also in this build

- **Original physics:** player movement uses the original ground-sensor settle
  (`levermove` settle 13), drag, spring side contacts (`RIDECHK.C`) and chain
  scoring (`emyscorecnt`). Palmtree Panic, Collision Chaos and Tidal Tempest
  routes were re-accepted against this physics.
- **Original camera:** the horizontal `scroll_h` programs for every stage, plus
  the vertical `scroll_v` added for Tidal Tempest. Retail camera captures match
  on 8 stages.
- **Tidal Tempest:** water line, currents and drowning; looping (wrapped) Act 2
  and Act 3 levels with redraw at the wrap; the stream window; sprite CLUT
  cycling; the zone's objects, enemies and platforms; the Act 3 boss
  (`BOSS_4.C`) and capsule, then the Quartz Quadrant handoff.
- **Tidal Tempest art:** all 10 act/era programs match the original sprite
  pixels (8,252 pictures, 4,140,792 original pixels; colour-cycled palette
  slots checked against the live colour RAM).
- **Stability:** fixed a libyaul DMA queue overflow. With 11 or more VDP
  transfers in one frame it overwrote the DMA callback list, which hung
  Tidal Tempest Act 1 and a Collision Chaos Act 2 ring-loss route. Game DMA
  now goes through a guard; QA fails any run that needed its fallback.
- **Memory:** zone-only tables load per zone from `ZTR*.BIN` on the CD, so
  zone data no longer occupies resident RAM. A link-time check now proves the
  title screen's allocation fits the heap's allocator class. Fast QA now boots
  the disc to Palmtree Panic gameplay.
- **Performance:** perf rounds 2–4: Sonic texture uploads by DMA, a zone gate for the Tidal
  Tempest helpers, a faster zone-art lookup and zone tile-cycle uploads by DMA.

## Known limits

- Quartz Quadrant, Wacky Workbench, Stardust Speedway and Metallic Madness are
  not integrated on the Saturn. Their backgrounds, objects and bosses exist only
  as host ports. The Quartz Quadrant handoff ends the playable path. Metallic
  Madness also has 4 retail capture fixtures that were skipped because the
  level freezes during capture.
- Sonic's texture uploads now use SCU DMA, and the zone-art lookup is faster.
  The route batch has 0 late gameplay intervals. A streak of texture-cache misses on a
  very heavy frame could still overrun: the worst measured frame (CC Act 2
  Present) uses 46.6k of about 48k cycles.
- The Tidal Tempest Act 3 boss is verified in the emulator: the probe passes in
  both futures through the fourth egg hit, capsule, results and the Quartz
  Quadrant handoff. The Act 3 controller routes pass in both futures
  with 5 boss hits plus the egg.
- Tidal Tempest Act 1 matches the retail game for 2,052 compared updates
  (through sequence 2182; host against retail, measured before the physics
  bundle). Full retail parity is not claimed.
- Heap headroom at the title is 16,633 B (fast QA `test_zone_tables`).
- Loading a zone's sound bank still adds a short pause at zone entry.

## Hardware test checklist

Tidal Tempest (new):

1. Play Tidal Tempest Acts 1–3 from a New Game (or Continue into TT1) in every
   era: Present, Past, Good Future and Bad Future. Play Act 3 in both futures.
2. Water: enter and leave water; the line colours Sonic and the level; currents
   push Sonic; the air countdown and drowning work; bubbles refill air.
3. Acts 2 and 3: cross the vertical wrap in both directions; there must be no
   missing rows, torn tiles or camera jumps.
4. Act 3 boss: four hits defeat it; capsule, results, then the Quartz Quadrant
   handoff.
5. Continue chain: save at each Tidal Tempest act start. Power-cycle and
   Continue into Act 1, Act 2 and Act 3.
6. Watch for slowdown with many objects or ring losses, and for any freeze.
   Note the location and time.

Collision Chaos (carried from V0.064):

7. New Game through Palmtree Panic into Collision Chaos; play all three acts
   once for Good Future (destroy both generators) and once for Bad Future.
8. Check bumpers, bumper blocks, drums, flippers, Act 3 platforms and the boss.
9. Listen for the boss hit and bumper sounds; check music in every era.
10. After the Tidal Tempest handoff, power-cycle and Continue.
