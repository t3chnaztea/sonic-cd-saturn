# Collision Chaos Act 1 — active development

> Archived 2026-10-03. Superseded by `COLLISION-CHAOS-PLAN.md` (repo root),
> which tracks all Collision Chaos acts from the V0.063 baseline onward.
> Relative links below point to repo-root files.

Resumed after the 2026-09-21 restart. [NEXT-SESSION.md](NEXT-SESSION.md) records
current generator/controller validation and natural Good Future arrival; [GENERATOR-CHECKPOINT.md](GENERATOR-CHECKPOINT.md)
preserves the earlier restart handoff. [GOOD-FUTURE-CHECKPOINT.md](GOOD-FUTURE-CHECKPOINT.md)
records the white-screen draw fix and latest evidence. These supersede older generator-gap and
latest-build notes below. The full goal remains unfinished.

Scope: Present, Past, Good Future and Bad Future; original object/enemy behavior,
art and animation, terrain animation, palette cycles and background scrolling.
Acceptance requires controller-driven routes, time travel, generator destruction
creating a Good Future, progression into Act 2, Japanese music and save regression
checks, original-game comparisons, and a readback-verified hardware-test package.
All four era controller routes now reach Act 2 from ordinary level-select spawn.
Full original-behavior acceptance, travel/Good Future creation, campaign saves
and a new physical-hardware result are still outstanding.

## Pocket mechanism and point popups

`src/objects_pocket.inc` implements original actor 47 as native type 84.
Negative subtypes are the pocket; zero is its blinking lid. Dynamic type 85
implements the original score actor's point-popup branch. These objects have
priority zero. The pocket disappears in Good Future; none are placed in Past.
The five CC1 and ten CC2 records now import, with all source era masks retained.
CC1 has 607 translated placements: 488/470/474/474 visible in A/B/C/D.

The parent captures a descending Sonic within the original 48-by-16 rectangle,
preserves position fractions, sets the roll/control flags, hides Sonic when its
lid is allocated, awards two 100-point grants per cycle, and releases him with
the retained -2048 vertical speed. There are seven grants per loaded instance
(700 points total). A complete capture-to-ready cycle takes 245 updates; the
hidden interval lasts 115. The original allocation failure leaves the player's
control bit set when removing the pocket; this path is preserved and tested.
Child/point allocation before and after the parent follows actor dispatch order.

`tools/cc_pocket_source.py` verifies the complete normalized pocket block,
allocator, links, mappings and point routines in all ten Sega CD CC programs.
It resolves three differences from the reconstructed PC sources: capture
returns through soundset without decrementing the timer, popup initialization
uses tile $6C6 and ORs its flags, and expiry returns before moving integer Y.
The reference fixture also preserves the final sprite pass's exclusion of a
removed actor, rather than marking its empty slot visible before reallocation.

`tools/test-cc-pocket.sh` independently compiles POCKET.C, SCORE.C, PLAYSUB.C,
ACTION.C and ACTSET.C with these console corrections. It passes 107,115,689
assertions over 1,839,719 updates: 33,280 capture edges, 72 repeated cycles,
16,392 lifecycle cases, 18 allocation cases, 1,769,472 timer cases and 96 popup
timelines. The generic placement window, original sprite-queue saturation and
mixed-family interactions remain outside this oracle.

Original requests 215/159 supply capture/release audio. The Z80 headers and
priority table prove that release replaces capture on FM6. The compiled native
request test checks cancellation while preserving the other 38 effect requests.
The full 40-effect bank is 460,365 bytes; it now starts at sound RAM $E000, above
the pinned driver's declared workspace and communication block, and ends below
the independent $7F000 diagnostic tone. All 38 earlier effect hashes and all 34
Japanese music track hashes are unchanged. General original FM-channel conflict
arbitration remains separate from this verified pocket pair.

Pockets add four parent poses, two lid poses and six point poses per CC1/CC2 era.
The closed parent and blink-off lid poses are original zero-piece mappings.
The horizontal pocket art differs by era, so deduplicating entire era blobs no
longer fit low RAM. `ZAR2` retains separate era records but shares identical
textures and CLUTs: CC1 is 45,714 packed bytes / 34,752 VDP1 bytes; CC2 is 42,252 /
32,384. Older `ZART` packs retain their format. The source-art gate passes 50
variants, 934 frames, 1,216,384 exact pixels and 3,736 flip cases. Native Saturn
fixtures cover all ten CC variants, including 348 pictures per CC1 era and 316
per CC2 era. The pocket and 100-point target images were inspected.

The first pocket candidates exposed a missed PPZ1 refresh during the dense
ring-loss scene near X 4560. Grouping CC actor dispatch was insufficient.
An instrumented replay isolated redundant scanline work: Present's flat
background bands were recalculated for every line. `scd_background_lines`
now repeats a value only within a 16-line flat run; slopes and the 2048-line
wrap retain the original scalar calculations. At player frame 1237, line-table
work dropped from 7,112 to 718 FRT ticks and the profiled route passed without
a late refresh. `build/cc1/pocket-profile-before/` and `pocket-profile-after/`
preserve both logs and ELFs. The expanded sanitizer test checks 732,354 complete
tables against the unchanged scalar function, including partial tables and
guards. This optimizes existing PPZ rendering; CC's missing raster behavior
still needs its own original tables and implementation.

Accepted development BIN:
`d93d3afe548182fed21bbdf26512ad8c5d0a1777743c43c982f746c8b6ec45aa`
(4,819 data sectors, profiling disabled). All 50 fast checks, ten CC artwork
fixtures, eight save/Continue checks, player/audio/world regressions and sound
diagnostics pass. PPZ Acts 1–3 have 11,909 gameplay intervals with zero late
refreshes; Past ring-loss stress matches 5,208 states with zero late refreshes.
The four CC1 routes reach Act 2 with zero respawns/late refreshes over 71,992
gameplay intervals. `build/cc1/pocket-final-route-proof.json` verifies the Bad
Future route's 125 stationary pocket observations and automatic upward launch
at (8832,904), while holding only Right. `build/cc1/pocket-validation.json`
indexes the preserved reports and development build; this is not physical
hardware acceptance or the final CC1 release.

This implements pockets and their own score popups. Enemy score-popup spawning,
explosion-to-flower behavior, the other missing actors, terrain animation,
background raster, ordinary travel/Good Future/campaign-save acceptance and the
final hardware-test package remain part of the full goal.

## Research inputs

- Pinned original PC reconstruction: `.deps/soniccd/src/R3/`, with source commit
  in `sources.lock.json`. `ACT31A.C` and `ACT31B.C` resolve the same record IDs
  differently (notably checkpoints and the opening Amy sequence).
- Extracted Sega CD programs and layouts: `build/auto-extract/3/` and
  `build/retail/sonic.iso`. The existing harvest cross-checks layouts with PC data.
- `tools/inventory_cc1.py` writes a hash-bound per-era placement audit to
  `build/cc1/inventory.json`. Counts measure imported placements, not completeness.
- Object artwork must come from the Sega CD program's initialized mapping and
  loaded VRAM, via `tools/zone_object_source.py`; PC sprite IDs are not tile offsets.
- `SCR31A–D.C` describe the era-specific raster behavior; `COL3A–D.C` describe
  palette cycles. The current port uses a flat background and static tile frames.

## Initial gaps

`bobin`, `frip`, `harir3`, `frdr3`, `trapdr3`, `for3`, `getdair3`, `gandair3`,
`ene_kama` (and spawned `tama_kama`), `ga`, `tentou`, `banpa`, `pocket`, `togeball`,
`hari3x`, `emie3` (and sequence children), `movie`, and the round-specific `et`
and `friend` variants. Inventory the spawned actors as well as placed records.

The first implementation covers `BOBIN.C`'s round bumpers and flippers. Preserve
flipper actor ID 30: the original shared `PLAYER.C` checks that ID for its jump
strength and standing animation. Bumper collision is original special collision
23 (8×8 half extents), not its 16×16 artwork dimensions. Its score award is
`scoreup(10)`, or 100 displayed points, limited to five awards per loaded instance.
`sub_sync(127)` is a PCM bumper sound, not FM request 127; sound extraction needs
the Collision Chaos bank. These details need independent source/target tests.

Untracked `tools/scroll/` is retained as existing research and is not modified.
V0.060 and its verified package remain the regression baseline.

## First implementation batch (`bb0f4d4`)

- Round bumpers and flippers now import through `R3/BOBIN.C`, preserving their
  source subtype, orientation, impulse, five-award score limit, motion and
  animation. Flippers keep ID 30 for the original player's jump-strength code.
  `tools/test-cc-bobin.sh` independently compiles the pinned original routines
  and their ride helpers: 115,200 bumper updates, 2,035 hitbox cases, 44,488
  flipper contact cases, with 5,729,598 assertions under ASan/UBSan.
- The original flipped flipper endpoint reads index 64 from two 64-byte tables.
  All ten Sega CD CC programs confirm the adjacent bytes are 18 and 0. Both
  the native implementation and reference fixture explicitly include these
  bytes, avoiding the reconstructed C's undefined reads.
- Era-specific original art is captured from initialized Sega CD actors. The
  asset gate now covers 50 variants / 310 frames / 765,312 source pixels over
  all supported zone families. CC1 target captures cover all 24 poses per era
  (both objects, three frames, four flips), plus uploaded VDP1 bank bytes.
  Each CC1 era uses 4,768 bytes. These are renderer fixtures, not playthroughs.
- All nine original CC palette scripts are active in Act 1. Past has no cycles.
  `tools/cc_palette_source.py` verifies the script and color bytes against the
  original Sega CD binaries. `tools/test_cc_palette.py` compares 32,772 frames
  and 2,097,408 colors with compiled `COL3A–D.C`, including repeated paused
  rendering. Integrated scene phase relative to retail still needs comparison.
- The bumper's original PCM sound is captured from `SNCBNK3B.BIN` using sound
  ID `$BA`; the native request remains 127. All 416,206 prior sample bytes are
  identical to V0.060; the bumper adds 4,932 bytes. Audit:
  `build/cc1/audio-bank-audit.json`. Sound requests now use generated IDs beside
  the sample ranges, fixing the pre-existing omitted big-ring request and
  shifted Amy/special-stage sample indexes. Japanese music remains mandatory.
- `for3` platforms now import as native type 72, with all eight original
  subtypes: fixed/sinking, horizontal and vertical acceleration cycles, and
  the three rider-triggered lifts. `src/objects_for3.inc` preserves the
  different motion/contact order and original scratch-word state. Top-only
  contact includes original terrain correction and ceiling crushing.
  `tools/test-cc-platform.sh` compiles `TRAP_R3.C` and `RIDECHK.C` independently:
  1,957,632 matching updates, 902,016 contact cases, 267,600 ridden updates,
  and 48 completed lifts across four eras and four flips under ASan/UBSan.
  Invalid subtypes are rejected before table access.
- Platform artwork comes from initialized original actor 35. The current
  four-era Saturn artwork run covers 28 pictures and 30,592 source pixels
  per era, with 5,824 bytes of verified VDP1 art per era. This includes the
  earlier bumper/flipper poses and the platform's four orientations.
  Reports: `build/cc1/platform/report.json`, `build/zone-art-qa/report.json`.

## Traps and launcher added after the first batch

- Native types 73–76 implement `harir3`, `frdr3`, `trapdr3`, and `getdair3`.
  Full solids preserve `RIDECHK.C` side/bottom contact, pushing, terrain
  correction and crushing. Retracting platforms retain top-only contact.
  Linked spikes/springs preserve after-parent allocation and signed spring
  offsets. Pool exhaustion and recursive streaming removal have explicit cases.
- `tools/test-cc-traps.sh` compiles the original trap routines, full `RIDECHK.C`
  and `COLI3.C` hitboxes independently: 107,845,563 assertions, 5,238,872
  updates and 2,453,036 contact cases under ASan/UBSan. Spring-child impulses
  use the existing shared spring implementation/gate; this trap oracle checks
  their allocation and following positions, not a second full SPRING.C oracle.
- Type 77 implements the `gandair3` base, retracting core and accelerating
  bullets, including rider launch, repeated firing, flash-off poses, pool-full
  retry and era-dependent firing suppression. Its `actwkchk` may allocate
  before the base, unlike `actwkchk2` used by the other traps.
- `tools/test-cc-gandair.sh` follows the trap gate, reusing its independently
  compiled original source: 39,451,513 assertions, 748,064 updates, 330,832
  contacts, 14,548 launches, 204,242 bullet updates and 32 completed cycles.
  The reference adapts one documented PC/console difference: the Sega CD
  animation routine copies a zero delay unchanged, while reconstructed
  `PLAYSUB.C` clamps it to one. `tools/cc_gandair_source.py` verifies the exact
  scripts, timer-reload instructions and all three launcher call sites in
  all ten original CC programs. Native bullet flashes use the console rate.
- The original Present opening section loads generic spikes at the same VRAM
  address as CC's 32-tile spike bank. Capturing there produced wrong vertical
  art and blank horizontal poses. The CC1 asset fixture now lets the original
  section loader run at camera X 2048 before injecting actors and waits for the full PLC queue to drain for two
  consecutive frames. Present required until release update 152: a 32-frame
  delay still left title-card pixels in the launcher bank. The fast asset gate
  now verifies every CC object bank against real PLC entries and Nemesis output.
  No VRAM artwork is fabricated or copied over the captured bank.
- Launcher frames 5 and 6 are genuinely empty **mapping lists** (`00`) in the
  original binary. The packer emits a transparent 8×8 cell for them; the
  asset gate still rejects nonempty mappings whose loaded pixels are blank.
- Act 2 omits the unplaced retracting-platform/launcher families; Act 3
  captures only its placed bumpers, flippers and spikes. Unused object tile
  addresses can hold other graphics in those acts. Per-era target checks
  include all CC1 families and palette DMA; the asset gate checks the original
  banks as well as composition, so matching stale VRAM cannot pass.
- The imported CC1 layout contains 527 records (per-era translated counts
  A/B/C/D: 447/442/446/446). Missing routines remain `ga`, `tentou`,
  `ene_kama`, `banpa`, `pocket`, `togeball`, `hari3x`, `emie3`, `movie`, plus
  the round-specific `friend` and `et` variants. Counts are not completeness.

## GA enemy and high-priority zone artwork

- Native type 78 implements `R3/GA3.C`: emergence, normal/damaged flight,
  directional selection, vertical reversals and the normal variant's harmless
  falling sparkles. Particle allocation may precede the parent in actor order;
  those new particles remain hidden until their first update. Failed allocation
  leaves the original movement cycle unchanged.
- `tools/test-cc-ga.sh` independently compiles `GA3.C`, `COLI3.C` enemy collision
  and `SUICIDE.C`: 119,375,155 assertions, 2,269,694 updates, 1,053,216 contact
  cases and 73,496 particle updates. It checks emergence hitboxes, reduced
  player hitboxes, attack animation, damage immunity, both power flags, score
  chains, bounce velocities, full allocation, and first-contact ordering among
  overlapping GA actors. Good Future destruction cannot repeatedly reload the
  same placement while it remains in the load window.
- GA's timed emergence scripts have no terminator. The reconstructed PC
  animation helper's sentinel scan is therefore an invalid read for these
  scripts. `tools/cc_ga_source.py` verifies all ten original programs' exact
  scripts and their calls to the Sega CD helper, which reads the timer directly.
  The independently compiled reference removes the PC scan and uses that
  console timer reload; the native code uses the same proven console semantics.
- The zone-art format now retains the original tile-priority flag per palette
  reference (bit 7; bits 0–5 select the original color). High-priority CLUT
  entries use indexed Saturn pixels and a live stage-palette copy at CRAM
  128–191. Actor priority remains independently sourced from `sprpri` (GA = 1).
  Normal/damaged/sparkle artwork comes from initialized original actors and
  verified PLC banks, including all four eras of Acts 1 and 2. The asset fixture
  explicitly disables enemy destruction after loading Good Future's artwork;
  this does not alter the port's gameplay suppression.
- The asset gate covers 50 variants / 574 frames / 936,832 source pixels /
  2,296 flips; peak use is 16,224 of 38,912 VDP1 bytes. Each CC1 era has
  42 frames / 168 flipped pictures. The target gate checks uploaded CLUT data,
  visible source pixels and all 64 live priority-palette aliases per picture.
  `build/cc1/ga-target-sheet.png` was visually inspected.
- CC1 now imports 554 records, with translated A/B/C/D counts 460/448/454/454.
  Remaining routines are `tentou`, `ene_kama`, `banpa`, `pocket`, `togeball`,
  `hari3x`, `emie3`, `movie`, and round-specific `friend` and `et`.

This is component-level evidence. GA currently uses the port's shared explosion
path; original enemy score sprites, explosion-to-flower behavior, mixed-family
collision ordering and original offscreen allocation/streaming remain to be
completed or audited before claiming full enemy fidelity. The oracle does not
claim to verify those shared effects or a complete original-console playthrough.

## Tentou enemy and bomb implementation

- Native type 79 implements `R3/TENTOU.C` in all four eras: normal/damaged
  hovering enemies, terrain following, wall climbing, edge transitions,
  periodic bomb allocation, and falling/waiting/blinking bomb states. The
  normal parent can fire; the damaged variant cannot. Children allocated into
  an earlier slot remain invisible and noncollidable until their first update.
- `tools/test-cc-tentou.sh` independently compiles the original routine,
  `COLI3.C`, `SUICIDE.C`, and the non-enemy explosion routines/scripts from
  `PLAYSUB.C`/`TBL1.C`. It passes 119,526,753 assertions across 2,218,864
  updates, 742,848 contacts, 1,034,646 bomb updates, 791,234 transitions and
  71,815 explosion observations under ASan/UBSan. Terrain cases use the actual
  four-era collision maps; pool exhaustion and allocation ordering are covered.
- `tools/cc_tentou_source.py` verifies both animation tables and their calls
  to the console animation helper in all ten original CC programs. It also
  proves the counterintuitive floor correction: falling subtracts the signed
  floor distance minus eight, while lateral movement adds it. The native code
  preserves these original instructions rather than normalizing the two paths.
- The shared GA/Tentou contact scan retains the original 16×16 Tentou body
  and 8×8 bomb collision radii. Bombs cannot be defeated by spinning or
  invincibility; damage immunity still applies. The bomb-to-explosion conversion keeps the bomb's visible pose
  and collision byte until the next actor dispatch; the next player scan can
  still hit it. The original non-enemy explosion then clears collision,
  animates through its terminal visible frame, and removes on the next update.
  Bombs suppress score sprites/flowers through the original `r_no1=1` behavior.
- Bomb art begins 43 tiles inside the larger Tentou graphics bank. The bank
  verifier now accepts contained mappings while still requiring every byte of
  the full original PLC/Nemesis bank to match captured VRAM. Normal, damaged
  and bomb poses come from initialized original actors, not substituted art.
- All ten CC Saturn artwork fixtures pass on the Tentou build. Each CC1 era
  checks 200 pictures, 99,452 visible original pixels and 19,808 VDP1 bytes,
  including all 64 live priority-palette aliases. Across all zone families,
  the source gate covers 50 variants, 638 frames, 990,080 exact pixels and
  2,552 flips. `build/cc1/tentou-target-sheet.png` was visually inspected.
- CC1 imports 577 records, including 23 Tentou placements. Translated A/B/C/D
  counts are 468/457/460/460. Remaining routines are `ene_kama`, `banpa`,
  `pocket`, `togeball`, `hari3x`, `emie3`, `movie`, and round-specific
  `friend`/`et` variants. These counts do not prove gameplay completeness.

Enemy score sprites, enemy explosion-to-flower behavior, complete mixed-family
collision ordering and original offscreen lifecycle still require work. The
bomb explosion comparison does not prove those separate enemy-death effects.

## Mantis, blades and rectangular bumpers

- Native types 80/81 implement `R3/KAMA.C`'s normal/damaged mantis and its
  two delayed blades. The blades retain their parent's slot while waiting,
  disappear if that parent disappears before launch, and continue independently
  after launch. Rolling or invincible Sonic can deflect them within the original
  half-open 56×56 region; their damage radius is only 6×6. Failed allocation,
  one available slot, and allocation before the parent are explicitly checked.
- Type 82 implements `R3/BANPA.C`: vertical/horizontal one-pixel movement,
  the four subtype combinations, 160/192-update reversal periods, and original
  side/vertical/diagonal contact responses. Contact is processed before motion
  through the shared ordered CC scan with GA, Tentou and mantis/blades.
- `tools/cc_kama_source.py` verifies the exact animation tables and helper
  calls in all ten original CC programs. It also proves differences from the
  reconstructed PC code: mantis attacks require `|dx| < 96` and `|dy| < 32`;
  its floor correction accepts -7; turn entry writes animation **word** 3;
  rectangular bumpers set tile attributes `$435e` and move immediately during
  initialization. Both native code and independent reference preserve those
  console instructions. Deflected blades use the original zero-delay script.
- `tools/test-cc-kama.sh` independently compiles KAMA/BANPA, COLI3 collision,
  SUICIDE, and ACTION's viewport checks. Its console-adapted reference passes
  129,429,696 assertions, 2,245,627 updates, 683,616 contacts, 518,204 blade
  updates, 41,728 direction changes, 76,304 deflection observations and 193,120
  bumper contact cases under ASan/UBSan. It compares actor/player state and
  audio requests. The new actors update visibility using the actual previous
  camera view and original 320×224 bounds, including vertical wrapping.
- The audio comparison exposed an existing shared issue: losing only a shield
  incorrectly requested the ring-loss sound. That request now occurs with ring
  loss. Original COLI3 code and the console hurt tail support the silent shield
  case. Request 185's original FM blade sound adds 5,425 bytes; all preceding
  421,138 effect bytes remain identical. Japanese music remains selected.
- The art capture gives a blade its real parent's signed low-word address;
  otherwise the original routine correctly removes the orphan before capture.
  All artwork comes from original mapping/VRAM captures with complete PLC-bank
  checks. The source gate now covers 50 variants, 822 frames, 1,187,712 exact
  source pixels and 3,288 flipped cases. Each CC1 era has 73 poses and uses
  28,864 of 38,912 VDP1 bytes. The frame-table bound is now 256, matching the
  probe's eight-bit frame index; texture and file bounds remain checked.
- CC1's serialized artwork exceeded its low-work-RAM slot when storing all
  eras separately. The packer now shares only byte-identical complete era
  records and texture streams. Present and Past share a copy, with their live
  stage palettes remaining separate. `ZART31.BIN` falls from 111,138 to 83,356
  bytes without dropping poses or changing pixels; every era is independently
  checked against its original source capture.
- CC1 imports 600 records (17 mantis and six rectangular-bumper placements
  added), with translated A/B/C/D counts 481/468/468/468. Act 2 also places
  these families and receives their art; Act 3 places neither. Remaining
  routines are `pocket`, `togeball`, `hari3x`, `emie3`, `movie`, and the
  round-specific `friend`/`et` variants.

This still does not complete original offscreen streaming, sprite-queue
saturation, enemy score/flower effects, or collision ordering with every other
object family. The viewport comparison is not a claim that all older actors
now use the same lifecycle.

## Rotating spike-ball chains

`src/objects_togeball.inc` implements original `TOGEBL3A/B/D.C` as native type
83: three balls in Present, two in Past, and four in both Futures, at radii
16/32/48/64 pixels. Nonzero positive subtypes reverse the orbit. Child actors
allocate strictly after the parent, retain its actor link and consume its
fixed-point orbit positions in the same update. Failed partial allocation
removes the parent; each allocated child then removes itself when it observes
the missing parent. Balls use original 8×8 hazard contact bounds and remain
hazards in Good Future.

`tools/cc_togeball_source.py` verifies the exact console allocation blocks,
child-count variants, parent lookup, orbit instructions and 320-entry sine
table in all ten CC programs. The successful Sega CD initializer immediately
executes movement, unlike the reconstructed PC initializer. The independent
reference adds only that verified initial call, maps actor links into the host
fixture, and expresses signed shifts without C undefined behavior.

`tools/test-cc-togeball.sh` passes 212,267,396 assertions over 1,707,314 updates,
320,128 contact cases, 5,515,367 ball updates, 34 allocation-boundary cases and
16,392 lifecycle cases under ASan/UBSan. Coverage includes all positive subtype
bytes and flips, every 16-bit phase in both directions with nonzero parent
fractions, damage/control/invulnerability bounds, and camera-based removal.
Contact scenarios compare audio; allocation fixtures use native ring pickups
to arrange free slots and do not compare those ring sounds against this oracle,
which does not execute original RING.C.

The parent uses the original camera-aligned 128-pixel frameout blocks after
DrawObject. The generic placement-loading window, travel cleanup and sprite
queue saturation still need the shared lifecycle audit; the new component
comparison does not certify those other systems.

Two CC1 hub placements and three CC2 hubs now import. CC1 has 602 translated
records, with A/B/C/D counts 483/470/470/470. The R6 spike-ball family remains
excluded as an unported clone. Artwork is captured from original initialized
hub/child mappings and full PLC banks; the capture fixture leaves free actor
slots after the injected parents for ordered child allocation. Each CC1 era
now checks 75 poses / 300 pictures, 141,072 source pixels and 29,184 VDP1 bytes;
CC2 checks 67 poses / 268 pictures and 26,752 bytes. Act 3 has no hub placements.
`build/cc1/togeball-target-sheet.png` was inspected after the ten target artwork
fixtures passed. The complete source-art gate checks 50 variants, 838 frames,
1,191,808 pixels and 3,352 flips.

## Controller-route investigation

`tools/probe_cc_route.py` uses ordinary Left/Right/Jump after level select,
without gameplay memory writes. With the trap and launcher batch, Present
reaches X 12287 and enters Act 2 with zero respawns and zero late gameplay
intervals over 10,500 observed updates. The route rides types 30, 72, 74, 75
and 77; `for3` accounts for 70 ridden updates. Loading the next act is logged
separately from gameplay pacing. This is still an exploratory level-select
route, not proof of final enemy fidelity or normal-progression autosaving.

On the GA build, all four eras were probed again. Present still reaches Act 2
in the 10,500-update observation window. Bad Future was still advancing at that
limit, so its probe was extended to 18,000 updates: it now enters Act 2, with no
respawns or late gameplay intervals. The 10,500-update Bad Future evidence is
preserved in `build/cc1/ga-route-D-10500/`. Current Past stalls near X 2229 and
Good Future reaches X 1789 but does not finish. Screenshots in
`build/cc1/ga-route-ends.png` show the stalled/unfinished positions; the Bad
Future screenshot there precedes its successful extended run.

Reports in `build/cc1/route-target-{A,B,C,D}-60/report.json` bind observations to
the BIN, input harness, native handlers and translated layout. A probe finishing
its observation window is not itself a gameplay completion result. Past's pad
strategy only retreats after grounded stalls and can remain against a wall
while airborne; investigate that controller limitation and missing objects
without changing collision behavior merely to make the route pass.

On the Tentou build, Present reaches X 11698 at 10,500 updates and reaches
Act 2 within an extended 18,000-update observation window. Bad Future also
reaches Act 2 within 18,000 updates. Both have zero respawns and zero late
gameplay intervals. These are still level-select routes.

The old driver counted every position behind its maximum X as a stall, even
when moving normally after a retreat. `--strategy local` measures current
movement and allows a short rightward approach after retreating. Its first
Good Future run reaches X 6747; adding the observed `--jump-at 6620` takeoff
reaches X 9716. Past's `--retreat 100 --backjump-at 2229` jumps back toward the
nearby ledge and gets past the first wall to X 2485. Neither era finishes in
18,000 updates. Both retain zero respawns and late intervals. The options
send ordinary Left/Right/Jump; they do not change player state or collision.

The more aggressive generic retreat experiment performed worse (Past X 1589,
Good Future X 4053). Its reports are preserved in
`build/cc1/route-target-{B,C}-60-local-v2/`; the first local-movement runs are
in `-local-v1/`. Do not mistake a probe's successful observation exit for a
completed route. Current best incomplete routes are
`build/cc1/route-target-B-100-local-jump2229/report.json` and
`build/cc1/route-target-C-60-local-takeoff6620/report.json`.

## Four-era controller completion on the mantis build

The later route pass completes all four eras on the same BIN
`8c8b16810533606127aa45dd78c12db4622dcf225b9fa1184c0cb8e0c2d87dea`.
Only the controller harness changed. Past needed a backward jump at the second
ledge near X 2485 as well as X 2229. Good Future needed ground jumps near
X 9650 and X 9900 to clear the horizontal springs, in addition to X 6620.
The harness accepts repeatable waypoint options and continues to send only
Left, Right and Jump after level selection.

All four runs observe 18,000 updates, with zero respawns and zero late gameplay
refreshes across 71,992 intervals. Act 2 entry occurs at sequence 7795 (Present),
6187 (Past), 5665 (Good Future) and 10427 (Bad Future). Each stage load takes
215 VBlanks and is recorded separately from gameplay pacing.

Reproduce each route with `python3 tools/probe_cc_route.py --updates 18000`
and these arguments:

- Present: `--era A --retreat 60 --strategy legacy`
- Past: `--era B --retreat 100 --backjump-at 2229 --backjump-at 2485`
- Good Future: `--era C --retreat 60 --jump-at 6620 --jump-at 9650 --jump-at 9900`
- Bad Future: `--era D --retreat 60 --strategy legacy`

Then run `python3 tools/check_cc_routes.py --expected-bin <BIN SHA-256>`.
The checker reads raw state/pad logs, requires the original spawn, continuous
observations, allowed pad commands, zero respawns, one correct Act 2 transition
and no missed gameplay refreshes; it rejects stale native/build/harness inputs.
The current evidence is copied into `build/cc1/kama-routes-validation/` and
indexed by `report.json`. Earlier incomplete evidence remains in the previous
implementation validation snapshots.

This proves one route through each currently imported era. Missing actors,
original-console comparisons, ordinary travel and Good Future creation,
campaign save acceptance, backgrounds/animation and hardware packaging remain
open. Future additions must rerun these routes rather than assume they remain
complete.

## Four-era controller completion with spike-ball hazards

The spike-ball BIN `911db48a838fceaa4aab4501cfaab0a08a9259321697b9104290983cf35f8804`
passes the four route checks with their new hazards included. The earlier
Present route died near the chains; its one 3-VBlank gap was the death/respawn
at sequence 4989. Past reached X 9944 but looped through the spring section.
Those failures remain in `build/cc1/togeball-routes-before/`.

Present now adds `--jump-at 7100` to its legacy route. Past adds
`--jump-at 9650 --jump-at 9900` to its two-backward-jump route. Good Future and
Bad Future keep their previously documented pad options. No native physics or
hazard behavior changed to make the routes pass.

All four runs observe 18,000 updates, zero respawns and zero late gameplay
refreshes over 71,992 intervals. Act 2 entry occurs at sequence 8969 (Present),
7935 (Past), 5551 (Good Future), and 11255 (Bad Future). The route checker and
its immutable raw-log/screenshot snapshots are recorded in
`build/cc1/togeball-routes-validation/report.json`. This remains one route
through each imported era, not the completed fidelity/travel/save goal.

## Pacing regression investigation

Adding the platform family exposed the existing tight timing margin at PPZ
Act 1 simulation 1238 (68 live objects). The first platform build matched
all three gameplay replays but missed one refresh there. Evidence is retained
in `build/cc1/platform-pacing-before/`. Lost-ring updates and ring draw views
now return before the growing gimmick dispatch chains. Their motion, terrain
bounce, pickup delay and animation stay unchanged. The host player reference
and 81,920 object-stream comparisons pass. The optimized BIN
`fc443a581fdc3c1db2f25da71f99a5bbbfb6d7f5678bc7b9224160ee04c3ab5d`
passes all three unchanged target pacing gates: zero late intervals across
11,909 checked intervals. All eight save/progression/cold-boot checks pass on
the same BIN (`build/save-progression/report.json`). The new Present route
probe and all four CC1 artwork/palette fixtures also pass again on this BIN.
All 42 fast checks pass, as do target player/rendering, Japanese audio,
world/travel/power-up regression and the 5,208-state Past ring-loss stress.
This is an intermediate development milestone, not the completed CC1 goal.

## Background research: do not blindly integrate the parked evaluator

Read-only runs of `tools/scroll/R3/extract.py` wrote full-window research to
`build/cc1/scroll31A-full.json` through `scroll31D-full.json`. Each era's vertical
scroll clamps at 536 with a transition based on camera Y 1312. Crucially, the
same background line can have different horizontal offsets depending on the
window top: Present/Good override lines 60–79 and 704–710; Past overrides 68–95,
532–559 and 704–710; Bad overrides 12–31 and 704–710. Bad Future also has an
uninitialized reconstructed-C interpolation seed, which the extractor assumes
zero. Original-machine evidence now disproves that assumption when moving left.

The existing window-independent raster API cannot express those overrides.
Implement the original window-dependent table construction, including the
foreground water distortion visible in `SCR31A.C`, and verify against original
CPU output. Also preserve the original static/dynamic row addressing from
`z31*wrttbl`, rather than simply applying parallax to every map row.

### Original CPU scroll evidence

`tools/capture_cc_scroll.py` records 68 explicit camera/player fixtures per era,
including left/stationary/right motion. Each fixture settles section-art DMA
before measuring an update; one emulated video frame can otherwise catch the
original CPU partway through `scroll()`. `tools/check_cc_scroll_capture.py`
checks every cloud/per-line accumulator against `LineSpdTbl` and the original
increments, and checks Bad Future's ten interpolation rows.

`build/cc1/scroll-retail/checked.json` records 272 fixtures / 21,964 compared
values. Bad Future retains the upper word of the sign-extended camera delta
multiplied by eight in D3. The following scroll helpers change only D3's low
byte/word. Thus the interpolation fraction is 65535 for leftward motion and
zero otherwise. Exact original instruction bytes are preserved in the report;
zero-seed output fails ten captured cases. This resolves the reconstructed C's
undefined half-word. Native backgrounds are **not implemented by this research**;
full hscroll buffers, row addressing and scene phase still need integration and
comparison.

## Latest verified rotating spike-ball development build

BIN `911db48a838fceaa4aab4501cfaab0a08a9259321697b9104290983cf35f8804`
(`build/cc1/togeball-build.log`, 4,838 data sectors) passes all 48 fast checks,
ten CC target-art fixtures, all eight save/Continue progression and cold-boot
checks, player/rendering regression, Japanese audio, world/travel/power-ups,
PPZ Acts 1–3 routes and pacing (11,909 intervals, zero late), and 5,208 Past
ring-loss stress states (zero late). The unchanged audio-source report proves
that adding these hazards did not modify the sound bank or track selection.
All four CC1 controller routes also reach Act 2, as documented above.

Reports are copied into `build/cc1/togeball-validation/reports/` and indexed
with current source hashes in `build/cc1/togeball-validation.json`; complete
raw route logs/screenshots remain in `build/cc1/togeball-routes-validation/`.
Earlier build indexes and failed controller routes remain separate. The full
CC1 fidelity/travel/save objective and final hardware-test package remain open.

## Verified mantis and bumper development build

BIN `8c8b16810533606127aa45dd78c12db4622dcf225b9fa1184c0cb8e0c2d87dea`
(`build/cc1/kama-build.log`, 4,837 data sectors) passes all 47 fast checks,
all ten CC Saturn artwork fixtures, all eight save/Continue progression and
cold-boot checks, player/rendering regression, Japanese audio, world/travel/
power-ups, PPZ Acts 1–3 routes and pacing (11,909 intervals, zero late), and
5,208 Past ring-loss stress states (zero late). The player comparison matches
16,800 states; Sonic artwork checks cover 195 pictures.

Each CC1 era checks 73 poses / 292 pictures, 139,760 visible source pixels and
28,864 VDP1 bytes. The rendered mantis, blades and bumper sheet was inspected
at `build/cc1/kama-target-sheet.png`. The original-source comparison passes
129,429,696 assertions, 2,245,627 updates, 683,616 contacts, 518,204 blade
updates, 41,728 reversals, 76,304 deflection observations and 193,120 bumper
contacts. Original instruction checks cover all ten CC programs.

Present and Bad Future still reach Act 2 in the controller probes; Past reaches
X 2485 and Good Future X 9716 without completing. All four observations run
18,000 updates with no respawns or late gameplay intervals. These are exploratory
routes, not full original-console or whole-zone acceptance.

Reports are copied into `build/cc1/kama-validation/reports/` and indexed by
hash in `build/cc1/kama-validation.json`, with raw route evidence and current
source inputs. Earlier build indexes remain separate. The full CC1 goal and
physical hardware acceptance remain open.

## Verified Tentou development build

BIN `9965474febbe89fe22f290b09b67704c7c056d36646bafe0a3cff8668a3dc216`
(`build/cc1/tentou-build.log`, 4,861 data sectors) passes all 46 fast checks,
all ten CC Saturn artwork fixtures, all eight save/Continue progression and
cold-boot checks, player/rendering regression, Japanese audio, world/travel/
power-ups, unchanged PPZ Acts 1–3 routes and pacing (11,909 intervals, zero
late), and the 5,208-state Past ring-loss stress (zero late). The player
comparison matches 16,800 states; Sonic artwork checks cover 195 pictures.

Reports are copied into `build/cc1/tentou-validation/reports/` and indexed by
hash in `build/cc1/tentou-validation.json`, together with current native/source
inputs and explicit incomplete controller-route outcomes. Earlier build indexes
remain separate. The full CC1 goal and physical hardware acceptance remain open.

## Verified GA development build

BIN `5988bac02482e73f0e811d9c582cb7a674841cf54e99b68585eccf4f3608b2e6`
(`build/cc1/ga-final-build.log`, 4,846 data sectors) is an intermediate V0.061
build, not the completed goal or a hardware-accepted release. The previous
trap/launcher BIN and its audit remain recorded in
`build/cc1/intermediate-validation.json`; this batch is indexed separately in
`build/cc1/ga-validation.json`.

- All 45 fast checks pass:
  `build/qa-loops/20260921-124017-549861/report.json`. This includes the new
  GA oracle and the final PLC-bank/priority-aware artwork gate.
- All ten CC Saturn artwork fixtures pass. Each CC1 era checks 168 pictures,
  82,800 original visible pixels and 16,224 uploaded VDP1 bytes. The target
  also verifies all 64 live high-priority palette aliases on every picture.
- Present and Bad Future enter Act 2 using ordinary controller input from
  level select. All four era probes have zero late gameplay intervals;
  Past and Good Future completion remains open.
- All eight save/progression/cold-boot checks pass on this BIN. Japanese music,
  player/rendering and world/travel/power-up regressions also pass.
- PPZ Acts 1–3 match their unchanged replays and have zero late refreshes over
  11,909 intervals. The Past ring-loss stress matches 5,208 states and 89 hurt
  ticks with zero late intervals in `build/cc1/ga-final-past-stress/`.
- Logs use `build/cc1/ga-final-{fast,target-art,save,emulator,audio,world,
  act1,act2,act3,past,route-A,route-B,route-C,route-D,route-D-extended}.log`.

## Still required for the full goal

The other routines in the initial-gap list, their children and original art;
terrain animation; correct backgrounds and foreground distortion; ordinary
routes through all four eras; travel and return; generator destruction and
Good Future creation; Act 2 progression with save/Continue; final regression
and hardware-test packaging. The parked per-round generator work only retains
the old approximate three-explosion handler and PPZ artwork, so it is useful
research but does not satisfy original CC generator behavior by itself.
