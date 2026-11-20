# Collision Chaos completion plan

This is the second game zone (round R3), with Acts 1 and 2 in Present, Past,
Good Future and Bad Future, and Act 3 in both futures. Hardware acceptance is
reserved for the user's Saturn/SAROO test after the zone is otherwise complete.
Imported terrain, selectable stages and exploratory routes do not establish
original-game parity.

## Starting measured baseline (V0.063)

- Act 1 has four controller routes into Act 2. An earned New Game/Continue route
  also destroys the Past generator, reaches Good Future and saves in Act 2.
  Remaining unported placement routines are `hari3x` (4), `emie3` (1), `movie`
  (1) and the round-specific `friend` (124 visible record-eras).
- Act 2 has imported stage/collision/object-art packs in four eras but no
  accepted complete route. Its missing placement routines are `drumr3` (168
  visible record-eras, 42 records per era), `movie` (1) and the round-specific
  `friend` (92 visible record-eras). Four 4,000-update level-select probes have
  no respawns or late gameplay intervals but do not reach Act 3.
- Act 3 has Good/Bad Future stage and collision packs. The original layout's
  `egg3dai_l`, `egg3dai_s` and `sikake33` (two visible record-eras each) are
  dropped. Two 4,000-update controller probes stop around X=750. Its R3 boss,
  capsule and next-zone progression have no acceptance route.
- All CC background raster, foreground distortion and terrain animation need
  source-versus-native validation. Palette cycles have a compiled-original
  frame oracle. The present CC background remains flat.

The placement counts come from `python3 tools/inventory_cc1.py --act 1|2|3`;
reports are in `build/cc1`, `build/cc2` and `build/cc3`. Route reports are in
`build/cc2/route-target-*-60-local` and `build/cc3/route-target-*-60-local`.
The route controller is exploratory and cannot alone prove a defect: a route
can stop because of its input strategy.

## V0.071 private local candidate

The collected-ring overlap gate has implemented sparkle timing and art for placed and lost rings. `src/objects.c` keeps the actor for four six-update poses and deletes it after the animation terminator; `src/sprite_order.h` draws those poses at priority 1. The four original mapping frames are appended at atlas indices 394–397. Final packaged BIN SHA-256: `24c990f519a790527dbffb6d63229dc1872c66859d4bfacd77983781605840a8`. Full QA passed 165 checks (`build/qa-loops/20261003-164417-663625/report.json`); fast QA passed 131 checks on the same BIN (`build/qa-loops/20261003-180215-489763/report.json`). The final-hash calibrated natural route capture improved the sequence 418 ring/Sonic box from 1,350 to 1,410 exact pixels and sequence 419 from 1,740 to 1,800, with all 60 changed pixels matching the source (`build/cc-natural-align/ring/v071-final/report.json`). Sequence 418 retains a Sonic subpixel-Y mismatch. This is a sampled diagnostic. `build/release-v71-readback.json` verifies the private package, 529 members, ten CC routes, and ten idle and moving entry scenes. The PPZ Act 2 Past no-damage route was repaired and passed 6,342 host/Saturn states. Outstanding: broader natural-route overlap ordering and user-confirmed Saturn/SAROO play.

## V0.070 local candidate

The source-derived top-spring ride transition restores standing state before launch; a following spin tag may re-enter rolling animation. Repaired PPZ and Collision Chaos controller recordings preserve this behavior. Final packaged BIN SHA-256: `b10ef705860c8e9db4dc7091c2117bff7b562eda90530580e1fb07e98e28d221`. Full QA passed 165 checks (`build/qa-loops/20261003-073818-019708/report.json`); fast QA passed 131 checks on the same BIN (`build/qa-loops/20261003-085710-170788/report.json`). R32D spring frame 440 matched 52,680/52,800 source scene and 1,600/1,600 Sonic-region pixels; frame 450 matched 509/509 selected Sonic-color pixels. R31A actor/Sonic samples matched 900/900 EMIE3 and 772/772 HARI3X spike pixels. Selected Sonic colors match at equal player/camera states in the ten-variant constant-Right sample (`build/cc-motion-probe/actor-color-check.json`). The 30-scene motion report is diagnostic; some later raw frames diverge after gameplay timing differs. `build/release-v70-readback.json` verifies the private local package, 529 members, 10 CC routes, and 10 idle and moving entry scenes. Broader natural-route overlap ordering and user-confirmed Saturn/SAROO acceptance remain open. Natural CC2 Past route comparison identified a missing collected-ring sparkle: the original retains ring actor slot 32 at sequence 418 with mapping frame 6 and priority 1, while native collection removes the slot. The render and state evidence is in `build/cc-natural-align/ring/ring-scene-report.json`. This gate remains outstanding until sparkle lifecycle and art are implemented and retested.

## Previous local candidate (V0.069)

EMIE3's zone-art CLUT now follows line 1 of the live CC1 palette. Its color
values match the original video output levels. On the development BIN,
the R31A frame-360 companion region matches 925/925 original pixels at equal
player and camera (`build/cc-emie-palette/comparison-02.json`). The packaged
BIN SHA-256 is `0df57c19634d2032d6fb8373ec3398b1d4c99e92a2b326c3b144c7c5022efd26`.
Full QA passed 165 steps in `build/qa-loops/20261002-153600-349326/report.json`.
Fast QA passed 131 steps in `build/qa-loops/20261002-173603-052617/report.json`
and repeated early visual gates on that packaged BIN. The final-hash EMIE3 check
passed 925/925 companion pixels and 52,067/52,800 scene pixels in
`build/cc-emie-palette/final-report.json`. Private readback passed 529 members
in `build/release-v69-readback.json`; the ZIP SHA-256 is
`b17f78c235ec4adcd92ed5ab86d6f32a597b78e61c3524136785ac235bb18108`.
Later actor motion and sprite overlap priority remain open. Saturn acceptance
requires user-confirmed console evidence.

## Previous local candidate (V0.068)

Packaged BIN SHA-256: `e9bd5599a1b14250e9d8206524754835b8652aa1c894c380b6325fb5f1817f3e`.
Full QA passed 165 steps in `build/qa-loops/20261002-131002-876416/report.json`.
Fast QA then passed 130 steps in `build/qa-loops/20261002-143511-141346/report.json` and repeated the early visual gates on the packaged BIN. The live VDP2 and fixed-offset idle/moving scene reports now carry that final hash. Private V0.068 readback passed 526 members in `build/release-v68-readback.json`; the archive is `build/hardware-v0.068/sonic-cd-saturn-prototype.zip`. A later diagnostic in `build/cc-motion-scene/report.json` measures frames 300/360/420 across all ten variants. All positions and cameras match at frame 300. Act 1 stays aligned through frame 420; some Act 2/3 paths diverge by frame 360 or 420. R32D first differs at frame 332: original Sonic holds X=425 for one frame while Saturn advances to X=431, with both reporting X speed 1536. The original player animation and animation-art state also hold on that frame while its palette timer changes. Matching nearby source gameplay frames yields 94.1%-100% exact scene pixels across 30 captures. Three frame-420 comparisons need up to ten pixels of camera registration, which can hide defects. Later actor motion and sprite priority remain unaccepted. User-confirmed Saturn/SAROO play also remains open.

## Prior development slice (V0.067 audit)

The last packaged V0.067 BIN is `7d8587edef7fad8aa106dd3870d1b884216c17c616e804463cd3c87ff61ccfbd`.
The current local rebuild is `d72bfdbb275820d31a665752c8304d441d91f7ebc590ef8573fdb593a5352d85`;
full QA passed 164 steps in `build/qa-loops/20261002-091736-046171/report.json`.
Its early visual gates ran on the previous BIN; fast QA replayed them on the
current hash and passed 129 steps in
`build/qa-loops/20261002-103818-780212/report.json`. Future full runs now
build first. Current-hash full QA passed the CC1/CC2 four-era routes, CC3
Good/Bad boss/results/zone-exit routes, earned campaign Good/Bad Act 3 saves
and cold Continue. Current-hash fast QA passed the source-derived CC1-3 scroll,
original planes A/B, live VDP2 plane maps and line-scroll tables, CC1 palette
and CC2 tile animation.

Full scroll parity compares 3,878,560 CC1, 3,873,776 CC2 and 1,945,192 CC3
original/native line words, including 272/272/136 retail CPU captures. The CC2
terrain gate matches 2,235 original drum animation fires and 426,036 tile states
across all four eras; it also checks 49,158 Act 2/3 palette frames and proves
that Act 3 C/D have no tile cycles. `build/zone-art-qa/report.json` matches
739,124/707,096/614,568 original sprite pixels across CC1/CC2/CC3 target
captures on this BIN. These checks cover component data and sampled target art;
`build/cc-scroll-target/report.json` now verifies the live VDP2 line tables
against native WRAM across all ten variants: 11,010 frames and 4,932,480 exact
words. The same run verifies 2,785,280 cells in each VDP2 plane map against
WRAM over 680 sampled frames. `build/cc-plane/report.json` matches 358,400
cells in each original plane to the native stage and replayed foreground cache
across 40 walked-camera views; 5,596 foreground cells display stale cache
content and match. `build/cc-scene-audit/report.json` now records ten
matched-camera still diagnostics on the same BIN: 92.3%-96.5% exact scene
pixels below the HUD after each line chooses its best 0-16-pixel horizontal
registration. This can hide scroll defects; separate source/native and VDP2
scroll gates cover those. The stronger idle-entry gate in
`build/cc-entry-scene/report.json` compares the original and target with equal
player/camera and a fixed five-pixel screenshot border: 520,933/528,000 exact
scene pixels and 15,733/16,000 exact pixels in the Sonic area across all ten
variants at idle entry. After Sonic moves right, it matches 518,924/528,000
scene pixels and 15,594/16,000 Sonic-area pixels at the same world position
in all ten variants. It is part of fast QA after the live VDP2 capture. Later
actor motion, other sprite priority cases and physical Saturn presentation
remain open.
The expanded BG cache oracle passes 3,474,240 full-map comparisons across the
ten PPZ and ten CC packs (`build/qa-loops/20261002-084522-555341/112.log`).
The foreground cache oracle also passes 1,588,500 full-map/write-count checks
across the same 20 packs (`tools/test-foreground-cache.sh`).

### Completion ledger — affected gates

| Gate | Implemented | Verified evidence | Outstanding |
| --- | --- | --- | --- |
| CC1 terrain and actor palette | Static tile/block packs; COL3A-D palette cycles (Past has no cycle); EMIE3 live zone-art CLUT | `build/cc1/palette/report.json`: 32,772 original/native frames; `build/zone-art-qa/report.json`: R31A-D, 1,756 target captures and 739,124 original sprite pixels; `build/cc-plane/report.json`: 143,360 cells in each original plane; target plane maps and scroll transfer in `build/cc-scroll-target/report.json`; `build/cc-entry-scene/report.json` checks entry scenes; `build/cc-emie-palette/final-report.json` matches 925/925 EMIE3 pixels on V0.070 | Later rendered motion/sprite priority and physical Saturn acceptance remain separate |
| CC2/CC3 visual components | Source-derived SCR32A-D/SCR33C-D line scroll, CC2 drum tiles and Act 2/3 palettes; static Act 3 tiles | V0.068 full QA: 3,873,776/1,945,192 original/native CC2/CC3 line words; `build/cc2/terrain/report.json`: 2,235 original drum fires, 426,036 tile states and 49,158 palette frames; `build/zone-art-qa/report.json`: 1,640/544 target captures with 707,096/614,568 original sprite pixels; `build/cc-plane/report.json`: 215,040 cells in each original plane; `build/cc-scroll-target/report.json`: all ten variants, 11,010 live VDP2 frames, 4,932,480 exact scroll words and 2,785,280 exact cells in each plane map; fixed-offset idle-entry scene in `build/cc-entry-scene/report.json` | Later rendered motion/sprite priority; Saturn acceptance |
| CC2 drum ride contacts | Native `drum_ride` calls shared `cc_ride` | `tools/test-cc-drum.sh` compiles original `drumr3` + `RIDECHK.C`: 5,447,880 contact updates, three player X speeds, zero/up/down Y speed, four eras | None |
| CC1/CC2 level-select routes | Four eras each, fixed-seed host search (`tools/cc_campaign_search.c`) | V0.068 full QA: `tools/test_cc2_route.py --act 1|2` matches every position with zero respawns and late intervals; CC2 C ring-loss stress route passes | Hardware acceptance |
| CC3 routes and zone exit | Boss, `sikake33`, both `egg3dai`, capsule, Tidal Tempest handoff | V0.068 full QA: `tools/test_cc3_route.py` and `--continue` pass both futures from level select and earned CC3-entry saves, with zero respawns and late intervals | Hardware acceptance |
| Earned campaign and saves | PPZ → CC1 Good Future → CC2 (Good/Bad) → CC3 entry, cold Continue | V0.068 `build/cc2/campaign/report.json` passes earned Good/Bad Act 3 saves and cold Continue | Hardware acceptance, including power-cycle Continue |
| Later rendered motion and priority | Source-derived R32D top-spring transition; 30 constant-Right scenes and two actor/Sonic overlap probes | V0.070 final-hash R32D t440: 52,680/52,800 scene and 1,600/1,600 Sonic-region pixels; t450: 509/509 selected Sonic colors. R31A t360 EMIE3: 900/900 overlap pixels; t420 HARI3X: 772/772 spike pixels. Equal-state selected Sonic-color samples in all ten variants: `build/cc-motion-probe/actor-color-check.json`. Original/source and native captures have input hashes in `build/cc-motion-scene/report.json`, `build/cc-overlap-priority/report.json`, and `build/cc-motion-probe/R32D-final-hash/scene-comparison.json`. Natural-route draw order (`tools/check_cc_draw_order.py`, `build/cc-draw-order/report.json`): retail queue read without perturbing the run, along all ten native CC controller routes; 68,769 gameplay frames and 558,383 submissions have 0 priority levels out of slot order, so native Sonic-first slot-order submission matches; Sonic shares its level with actors in 26,636 frames. Defect fixed: native drew Sonic at a fixed priority 2, but retail queues `actwk[0].sprpri` (0 when dying, COLI3.C:556). The retail run has 202 dying frames, 36 of them within 32 px of a priority 0/1 actor. `src/main.c` now uses `player.priority`. Dying plane priority (V0.072): `playdieset` sets `sproffset` bit 15 (COLI3.C:555) and `actionsub` makes it the sprite priority bit (ACTION.C:322); native Sonic now takes a PR=1 palette-code LUT while the bit is set (`src/sonic_view.inc` SONIC_HIGH_LUT, `src/main.c`). `tools/test_dying_priority.py` (`build/dying-priority/report.json`, BIN `ed89c145…2785`): 48 dying pictures, 461/461 Sonic pixels over high-priority cells show Sonic; with the fix disabled, 461/461 showed the cell. Full QA 165 checks on that BIN (`build/qa-loops/20261003-205753-821666/report.json`). | Native slot allocation parity with retail (SPRITE-ORDER.md); dying test is one PPZ fixture death, no CC natural death capture; Saturn hardware acceptance. |
| Collected-ring overlap (V0.071) | Placed and lost rings retain four six-update sparkle poses; original frames 4–7 draw at priority 1 | Final-hash `build/cc-natural-align/ring/v071-final/report.json`: sequence 419 ring/Sonic box 1,800/1,800 original pixels; all 60 changed pixels in each sampled frame match the source. Full QA passes object timing, art, composition, and final-hash CC routes | Sequence 418 Sonic subpixel-Y difference; broader natural-route overlap ordering; Saturn hardware acceptance |
| Zone-wide release gate (V0.073 local candidate) | Private local package at final BIN hash `5879a195c031588a504db8fa7125266f94599b4cde58907b367d2a05e54ccf25`, ZIP `41af1d6d…d2b5` (`build/hardware-v0.073/`) | Full QA 165 checks (`build/qa-loops/20261004-163735-999328/report.json`); CC scroll-target, entry-scene and EMIE3 rerun on the final BIN; readback `build/release-v73-readback.json` (529 members). V0.072 (`ed89c145…`) was never console-tested | User-confirmed Saturn/SAROO results |
| Zone-wide release gate (V0.071 local candidate) | Private local package preserved at final BIN hash `24c990f519a790527dbffb6d63229dc1872c66859d4bfacd77983781605840a8` | Full QA 165 checks; fast QA 131 checks on the same BIN; `build/release-v71-readback.json` verifies 529 members, 10 CC routes, and 10 idle and moving scenes | User-confirmed Saturn/SAROO results |
| Zone-wide release gate (V0.070 local candidate) | Final packaged BIN hash above; private local package preserved | Full QA passes 165 steps including final-hash routes, campaign and zone art; fast QA passes 131 early gates on the same BIN, including live VDP2, fixed-offset scenes and EMIE3; `build/release-v70-readback.json` verifies 529 members, 10 CC routes, and 10 idle and moving scenes | Broader natural-route overlap ordering and user-confirmed Saturn/SAROO results |

## Work order and completion gates

1. **Act 1 fidelity.** Port the remaining R3 actor families and children,
   including their source art, score/flower lifecycle and mixed-object allocation
   order. Implement era-specific background raster, foreground distortion and
   terrain animation from `SCR31A-D.C` and `COL3A-D.C` evidence. Require
   source/native state fixtures, visual captures and all four existing routes
   with no gameplay pacing regression. Keep the earned generator/Good Future/
   cold-Continue campaign path green.
2. **Act 2 coverage.** Finish `drumr3` ride-contact parity and port `movie`
   and `friend` variants with source comparisons. Validate animation, terrain, backgrounds,
   collision and music for A/B/C/D. Build controller-only routes from ordinary
   Act 2 entry through results to Act 3, then repeat from the earned Act 1
   campaign save. Verify natural time travel, future flags, score, rings, time
   stones and cold Continue at the handoff.
3. **Act 3 and zone exit.** Port R3 `sikake33`, both `egg3dai` platforms, boss
   behavior, art and sound from the original program. Prove separate Good and
   Bad Future controller routes through boss defeat, capsule, results and the
   natural handoff into Tidal Tempest. Check save/Continue and good-zone flags.
4. **Zone-wide release gate.** Run independent original visual/state/audio
   comparisons, all ten variant asset fixtures, stress and campaign routes,
   `python3 tools/qa-loop.py fast` and `full`. Make a new versioned, private,
   readback-verified package with release notes. Hand it to the user for the
   Saturn test; only user-confirmed hardware results can close that gate.

No zone-completion claim follows from an emulator pass alone. Palmtree Panic's
separate quality milestone and the remaining six zones stay under
`PORT-ROADMAP.md`.
