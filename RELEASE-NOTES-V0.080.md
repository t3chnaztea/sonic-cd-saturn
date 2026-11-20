# V0.080 — Launch build: secret pictures, save safety, gap fixes, public source

Release date label: `20261025`.
This is a private Saturn/SAROO test build. The last user-confirmed console
build is V0.065. Keep the BIN/CUE and ZIP local. They contain assets from the
owner's Sonic CD disc.

Every result below comes from the V0.080 full QA run (201 of 201 steps) unless a line says otherwise.

## Scope

Close the V0.079 gaps that have a retail answer, make saves safe against a
reset or power cut, add the secret sound-test pictures, and make the public
source build from a fresh clone with the same BIN. Classic stays the default
and must pass the same gates as V0.079.

## Implemented changes

- Secret sound-test pictures: the five Sound Test codes (CheckEasterEgg exits
  2-6) show "Fun is infinite", M.C. Sonic, Tails, Batman and Cute Sonic from
  NISI.MMD and DUMMY0-3.MMD on your disc, with the palette fade, Start to
  leave, and the music SPX.asm plays with each. Each picture is compared with
  retail pixel for pixel (9d74001, frontend case `sound-test-images`).
- Save safety (df557ee):
  - RESET is held off (SMPC RESDISA) during every backup write and verify:
    progress slots, the `SCDSATURNCF` setting file and the Time Attack records
    (45cfa57).
  - Time Attack records are a torn-write-safe file pair per preset (Classic
    `SCDSATURNTA`/`TB`, CD++ `SCDSATURNTP`/`TQ`, format SCDT v2). A store
    writes the file that does not hold the current records, reads it back,
    and only then removes the older one, so a power cut keeps the previous
    records. A V0.079 single file loads as generation 0 (0a715ab).
  - A save slot that fails to read with a device error is never overwritten
    with a lower generation; the save waits until both slots read (8950c74).
- Lost rings (e2c635c): the Collision Chaos spike touch runs in Sonic's update
  as retail COLI3 does, so CC lost rings start in the hurt's own update; CC
  lost rings are collected at their pre-move position with the retail 6x6 box;
  every zone deletes lost rings on one global spill timer (255 updates), and a
  later spill keeps earlier rings alive.
- Collision Chaos Act 1: the hari3x spikes join the collision mask, so Sonic
  takes their touch once, in the object step, also with 31 or more objects
  loaded (a294920, `tools/test-cc-hari3x-mask.sh`).
- Metallic Madness Act 2: the BEAM touch box takes its Y half-size from
  Sonic's X radius, as retail R82A does. An audit of every retail read of the
  player size bytes in all 70 level programs found no other mismatch. The R82A
  attract demo now equals retail for all 2006 updates (a6d1df3).
- Public source and reproducible builds (c65112c, 633c048, fd7c843):
  - The test tools hold no retail code bytes; they read named spans from your
    disc and check them by SHA-256.
  - The ISO dates come from `IP_RELEASE_DATE` (or `SOURCE_DATE_EPOCH`), and
    libyaul is built without the checkout path (`tools/patches/`), so the same
    source and discs give the same BIN from any directory.
  - A fresh clone builds with the README steps alone: `tools/prepare_retail.py`,
    a zone harvest that creates its own manifest and re-extracts a stale round,
    and the Quartz Quadrant terrain step.
  - `tools/export-public.py` exports HEAD as one audited commit.

- Art (ce17626, merged in d24e978):
  - Tidal Tempest Acts 1-2: the water entry splash (PLAYSUB4.C exit2), checked
    against retail PLC bytes in all eight programs (99e7be2).
  - Badnik flowers in TT1 and TT2 Present/Past and in WW1 Past (d84f798).
  - Metallic Madness Act 2 Present: the ET8 generator art, packed from PLC 4/8's
    own bank and checked against retail VRAM (790fe2e).
  - The zone art pack region is 120,832 B; the pack addresses are generated
    from one table (`PACK_*_ADDRESS`), which the front end now uses too.
- Animation phases (ce8c3c4, 631a4aa):
  - All placed rings spin on the retail ring clock and lost rings on the
    retail spill clock (R11A: 26,688 and 4,242 samples) (2bb2755).
  - Monitors animate only after an on-screen draw (R11A: 3,277 samples)
    (b696749).
  - Zone palette cycles (CC neon) restart with each level program, death
    restart and time warp (e633d9a).
  - Stardust Speedway searchlights use the retail draw masks and alternate as
    retail does (2,762 samples, 0 mismatches); the SS level timer clears on a
    time warp (cc1d3a1, c669f40).
  - Animated tiles (WW mesh) restart on a death restart (R61A: 1,499 updates,
    0 mismatches) (adeb9f2).
  - Checks: `tools/test_anim_phase_retail.py`, `src/world_qa.c`.
- Hardware guards (b6c4670):
  - Overlay and stage pack reads retry three times before the CD error
    screen; the movie preload gives up after 10 s (cd_error 0xAA) instead of
    waiting forever (c845248).
  - The QQ slave-CPU redraw waits at most 30 V-blanks, then draws on the
    master (9ab2e93).
  - D.A. Garden re-notifies the slave CPU each V-blank, with a safe master
    fallback (117138f).
  - VDP1 overrun V-blanks are counted in `scd_world_mailbox[143]` (af0d21c).
  - A build check keeps libyaul's CD sector buffer 4-byte aligned (c658dee).
  - The movie mailbox and picture log in low work RAM are cleared at each
    movie start, so a real Saturn's power-on RAM cannot fake a CD error
    (a2f0d6a, 6094c92).
- CD++ (1a89a94):
  - Attract demos always run Classic, whatever MODE says; the setting itself
    is untouched (71c34b2).
  - The homing attack ends when an object (a bumper or launcher) takes over
    Sonic's speed (abed6eb).
  - `tools/cdpp_fuzz.py` in fast QA: random pad scripts with all five moves on
    every zone's Act 1 Present and Act 3 hosts under ASan/UBSan, failing on a
    crash, a map exit or a stall (948bf2d).

## Candidate evidence

BIN SHA-256: `7bbce369beba939b9f30f2a85d847a5b2623d419ecdc327a0a89e949f8c05338`
Source: commit `d2520ed`, Makefile V0.080 / `20261025`, clean tree.
Full QA: PASS 201/201, `build/qa-loops/20261025-051706-681337/report.json`; zone and special gates `build/zone-gates/20261025-073153/report.json`: every zone retail, routes, art, travel 10/10 (MM art 12/12), campaign 3/3 (CC 5/5), special 42/42. The first V0.080 run failed only the WW/SS/MM campaign; the cause was the WW route host's palette clock, fixed in f46e09e with the WW1/WW2 earned routes re-searched. The BIN did not change.
Reproducibility: the V0.080 BIN contains no build path. Two fresh clones of the public export
at different paths gave the same BIN on 2026-10-24 (pre-V0.080 tree).

| Feature | Check | Where |
| --- | --- | --- |
| Secret pictures | Five Saturn pictures against retail, pixel for pixel | `test_frontend_emulator.py sound-test-images` |
| Save safety | Torn store, failed write, unreadable slots, legacy v1 load | `tools/test-save.sh` (`save_test.c`), `tools/test-time-attack.sh` (`time_attack_test.c`), `test_frontend_emulator.py ta-pair`, `test_save_matrix.py ta-pair-kept` |
| Lost rings | CC2C seed 24: rings match retail over updates 3239-3255 | CC retail-match routes and zone gates; no dedicated new test (`build/lostring/` evidence, [docs/LAG-MODEL-NOTE.md](docs/LAG-MODEL-NOTE.md)) |
| CC1 spikes | One spike on Sonic in object pools 0-63 | `tools/test-cc-hari3x-mask.sh` (fast) |
| MM2 BEAM | BEAM oracle with the retail correction; R82A attract 2006/2006 | `tools/test-mm-actors.sh`, `test_frontend_emulator.py` |
| Fresh build | Public export audit; fresh-clone BIN equals a checkout build | `tools/export-public.py`; `tools/test_install_zone_packs.py` (fast) |
| Art | Splash tiles vs retail PLC bytes; ET8 vs retail VRAM | `tools/check_mm2a_et8_vram.py`, zone art gates |
| Animation | Ring, monitor, palette, searchlight and tile phases vs retail R11A/R71A/R61A | `tools/test_anim_phase_retail.py`, `src/world_qa.c` |
| CD++ | Demos Classic in CD++ mode; homing yield; all-zone fuzz | `tools/cdpp_fuzz.py` (fast), CD++ host traces |

## Known gaps

Carried over from V0.079:

- Lost rings: the floor-check phase after a lag frame. Retail tests the floor
  on `(levelVIntCounter + d7) & 3`, and a lagging Sega CD update advances that
  counter twice. The port does not copy Sega CD slowdown, so the bounce can
  differ by one update after retail lag ([docs/LAG-MODEL-NOTE.md](docs/LAG-MODEL-NOTE.md)).
- QQ1A update 601 "era sign": not reproduced on the current routes. The QQ1A
  level-select window and the `qq1AD`/`qq1AB` travel routes match retail
  ([docs/LAG-MODEL-NOTE.md](docs/LAG-MODEL-NOTE.md)). Kept open until a route
  shows it or it is ruled out.
- SS3/SS4 jump-peak headroom needs console confirmation (SS4 minimum 5.4%).
- US-stream control build only: the good ending's SEGA card starts 7 frames
  late (70 against 63). The shipped disc uses the Japanese streams, which
  match retail.
- CD++: no CD++ copy of the per-zone or boss routes yet; one route per move
  only. Homing attack and air roll timing are design choices, not CD++
  parity. The CD++ readme's terms are not yet recorded.
- No front-end addition or CD++ move has run on a console.

Closed since V0.079: the secret sound-test pictures; lost-ring pickup and the
CC spike touch order (only the lag-dependent floor phase remains); the MM
player-size reads (only BEAM differed); the R82A attract demo; TT1/TT2 and
WW1 Past flowers; the TT Acts 1-2 water splash; MM2A ET8 art; all five
animation phases (monitor flicker, ring spin, CC neon, SS searchlight, WW
mesh).

New in V0.080 (post-launch work):

- Collision Chaos touch response runs in four scans (cc_touch_arbitrate, the
  generic pcol, cc_scan, in-step touches). Retail R31A ($2071A4) runs one
  slot-order loop that returns at the first overlap. Unifying them needs
  changes to shared player/pcol code (`src/player.c:848`).
- Lag-frame modeling (host parity only): the lost-ring floor phase (CC2C
  update 3256) and the QQ1A sign. Outline in
  [docs/LAG-MODEL-NOTE.md](docs/LAG-MODEL-NOTE.md).
- TT Act 3 water splash: R43C needs 62,272 B of the 61,440 B VDP1 zone-art
  region, so Act 3 has no splash.
- Disc-only build: stage art, layouts, palettes and mappings still come from
  scddisasm at build time; 113 of its .asm/.inc manifest files are not yet
  mapped to the user's disc by `retail_src.py`.
- Save safety and the secret pictures have not run on a console.

## Hardware

No V0.080 content has run on hardware. Console test pending (Monday). The last
user-confirmed console build is V0.065. Emulator results do not close the
console gate.

## Console checklist

1. Confirm BIN SHA-256 (full hash above) and the SAROO folder. Cold boot
   V0.080 twice. Record Saturn model, region, video mode, SAROO firmware and
   audio connection.
2. In the Sound Test, enter each of the five secret codes. Check the picture,
   its music, Start to leave and the return to the title.
3. Saves: press RESET while a progress save and a Time Attack record are
   being written. RESET is held off during the write, so after the reset the
   new save must be there. Optional: cut the power during a save; the old or
   the new state must load, never an empty one.
4. Load a V0.079 save and Time Attack records; check they are kept.
5. Collision Chaos Act 2: take a hit with many rings and collect lost rings.
   Metallic Madness Act 2: touch a BEAM while standing, rolling and small.
   Watch the R82A attract demo, and one attract demo with MODE set to CD++.
6. Tidal Tempest Acts 1-2: jump into water and check the splash; check the
   flowers in TT1/TT2 Present and Past and WW1 Past. Stardust Speedway: the
   searchlights alternate. Watch ring spin and monitor flicker in any act.
   Play each movie once (the CD read and movie guards run on real hardware
   here).
7. Repeat V0.079's front-end and CD++ steps (D.A. Garden, Visual Mode, good
   ending, MODE toggle, one act per zone in Classic).
8. Check title/gameplay music and effects, pause/resume and repeated cold
   boots. Report anything worse than V0.065 with BIN hash, zone, act, era,
   position, inputs and a photo or video.

Only the maintainer's exact-BIN SAROO evidence closes the console gate.
