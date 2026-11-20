# Full Sonic CD homebrew port — acceptance roadmap

The active user Goal now expands beyond the former PPZ-only boundary: a complete
fan-made Saturn port, a Classic / CD++-style setting, the remaining levels,
and a better-than-original experience. This is unfinished.
Palmtree Panic remains the first quality milestone, not the final scope.

## Completion ledger

Updated 2026-10-28: V0.081 BIN `49a576b3…` passed clean full QA 202/202, matrix 347/347, fast QA 160/160 and all 21 CD++ cases; final source/BIN audit complete. Hardware remains unproven. Updated 2026-10-24 (V0.080 docs at main 6094c92; V0.080 full QA 201/201): rows 3 CC/TT/WW/SS/MM, 4, 5, 7 and a source row. Earlier on 2026-10-24: rows 4-5 for V0.079 (front end, credits, CD++); V0.079 full QA pending; console test pending (Monday). Earlier text from 2026-10-18: V0.078 (all seven zones and special stages 1–8) passed full QA 187/187 and is packaged privately; see NEXT-SESSION.md for its hash and package. V0.076, V0.077 and V0.078 console tests are open. V0.075 evidence is historical; its package is lost and must not be rebuilt without the maintainer. Last user-confirmed console build: V0.065.

| Milestone | Implemented | Verified | Outstanding | Evidence |
| --- | --- | --- | --- | --- |
| 1 Visual (V0.044 reports) | Title timing, monitor compositor, draw sync fixes | Focused emulator/source checks | Console retest PPZ-GFX-003–006 | [PPZ plan](PALMTREE-PANIC-PLAN.md) |
| 2 Palmtree Panic | Ten act/era routes, natural travel, Good/Bad Future, SS1 return (V0.067) | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 10/10, travel 10/10, campaign 3/3 | Emulator gates complete; the maintainer's SAROO console test | [PPZ plan](PALMTREE-PANIC-PLAN.md) |
| 3 Collision Chaos | Ten variants: art, scroll, routes, CC3 exit, campaign, ring sparkle (V0.071), dying Sonic draw priority (V0.072); V0.080: spike touch in Sonic's update, retail lost-ring pickup box, one spill timer (e2c635c), hari3x mask (a294920); V0.080 full QA 201/201 | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 10/10, travel 10/10, campaign 5/5 | Emulator gates complete; the maintainer's SAROO console test | [CC plan](COLLISION-CHAOS-PLAN.md) |
| 3 Tidal Tempest | Ten routes, R4 boss, Continue chain, natural travel, earned Good Future campaign, retail parity fixes (V0.074); V0.080: Acts 1-2 water splash and flowers (99e7be2, d84f798); V0.080 full QA 201/201 | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 10/10, travel 10/10, campaign 3/3 | Emulator gates complete; the maintainer's SAROO console test | [TT plan](TIDAL-TEMPEST-PLAN.md) |
| 3 Quartz Quadrant | Ten routes, boss, R5 redraw, Continue (V0.066) | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 10/10, travel 10/10, campaign 3/3 | Emulator gates complete; the maintainer's SAROO console test | [QQ plan](QUARTZ-QUADRANT-PLAN.md) |
| 3 Wacky Workbench | Ten routes, original actors/art/boss and earned campaign; V0.080: WW1 Past flower (d84f798), animated tiles restart on death (adeb9f2); V0.080 full QA 201/201 | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 10/10, travel 10/10, campaign 3/3 | Emulator gates complete; the maintainer's SAROO console test | [WW plan](WACKY-WORKBENCH-PLAN.md) |
| 3 Stardust Speedway | Runtime, art, ten routes, travel and earned campaign (V0.077); V0.080: retail searchlight masks, level timer clears on warp (cc1d3a1); V0.080 full QA 201/201 | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 10/10, travel 10/10, campaign 3/3 | Emulator gates complete; the maintainer's SAROO console test | [SS plan](STARDUST-SPEEDWAY-PLAN.md) |
| 3 Metallic Madness | Ten routes, actors, shrink form, R8 bosses, Amy/ending, natural travel and earned Good Future campaign to the good ending (V0.078) | Full QA 187/187 and seven-zone gates on V0.078 BIN `11b16221…`: retail 10/10, routes 10/10, art 12/12, travel 10/10, campaign 3/3 | V0.080 (a6d1df3; V0.080 full QA 201/201): radius audit closed (only BEAM differed), R82A attract 2006/2006 retail. MM2A ET8 art packed and checked against retail VRAM (790fe2e, merged d24e978). Open: SAROO | [MM plan](METALLIC-MADNESS-PLAN.md) |
| 4 Complete-game flow | Special stages 1–8, save v2, New Game/Continue/RAM Data/Time Attack menu, seven-zone Continue, both endings; V0.079: D.A. Garden (61af0ad, ceef0d9), Visual Mode (e502dc4), pencil-test FMV (9c1cc1f, f0cfdcd), credits, end screens, SEGA card, Thank You and SS8 credits (fd6ae25, 1203ff3, 8888069, 3ea505f) | Special gates 42/42 on V0.078 BIN `11b16221…`; save matrix (2f932ad). V0.079: retail oracles and emulator routes per feature ([credits audit](docs/CREDITS-AUDIT.md); 212d7d3, 36e25d1, 367878f); QA evidence pending V0.079 full QA | V0.079 full QA PASS 197/197. V0.080 (V0.080 full QA 201/201): secret sound-test pictures 1-5 exact vs retail (9d74001); save safety: RESDISA around backup writes, Time Attack A/B pairs, unread slots never overwritten (df557ee). Open: US-stream good-ending card +7 frames (control only); SAROO | [Party 1](docs/PARTY1-PLAN.md), [Party 2](docs/PARTY2-INVENTORY.md), [Credits audit](docs/CREDITS-AUDIT.md) |
| 5 CD++ preset | Five moves, persisted Classic/CD++ toggle, separate Time Attack records; SS3 order cache + claim invalidation; exact object/boss hash acceleration | Current uninstrumented BIN `49a576b3…`: all 21 CD++ cases PASS, 139648 matched positions, zero late/respawns ([verification](tests/routes/cdpp/completion/verification.json)); Classic/CD++ MM3/SS3 C/D native states and hashes match pinned original object/boss code ([run binder](build/final-bin/20261028-183233/report.json)) | Clean full QA PASS 202/202, matrix 347/347, fast 160/160; all 1195 inputs and BIN rechecked unchanged. Automated goal achieved. CD++ readme terms (spec §8) remain open; SAROO remains unproven | [CD++ spec](docs/CDPP-PRESET-SPEC.md) |
| 6 Recurring QA loop | Manual fast/full QA plus local seeded exploration/repair campaign | Historical reported counts: 210 mutations, 280 lifecycle fixture cycles, 14 emulator prefixes. Current A3 [native traces/order/restart](build/qa-campaign/validation-resume-20261106-202400/native-order-restart-current-checkpoint.json) passed; [current fast171](build/qa-campaign/validation-resume-20261106-223759/fast-recovery-current-pass.json) passed with159 verified reused checks and12 reruns;full215 remains open | Current acceptance: 210 retained mutations; 280 lifecycle cycles; 14 native/Saturn prefix pairs; 23 supplements; 2 resource cases; 7 CD++ arrivals; 8 Saturn death/warp cases; coverage audit and independent review. TA full-storage policy settled: preserve records and report failure. Current storage-recovery acceptance pending. Scheduled job not installed | [QA campaign](docs/QA-CAMPAIGN-PLAN.md) |
| 7 Release package | tools/release.py source-only package; V0.080: `tools/export-public.py` single-commit public export with audit (fd7c843) | release.py forbidden-file tests pass; export audit clean; two fresh clones at different paths gave one BIN on 2026-10-24 (pre-V0.080 tree; V0.080 full QA 201/201) | Box art dropped by the maintainer 2026-10-18; history rewrite for the public repo is the maintainer's call | 936a23d, fd7c843 |
| 7a Reproducible source | Retail code read from the disc by SHA-256 (c65112c); fixed ISO dates and harvest check (633c048); fresh-clone build fixes and libyaul path patch (fd7c843) | Fresh-clone BIN equals a checkout build with the patched toolchain; main's shared toolchain still embeds the build path until bootstrap at the V0.080 integration point | Bootstrap main's toolchain; disc-only build (113 scddisasm manifest files unmapped) | [V0.080 notes](RELEASE-NOTES-V0.080.md) |

## Ordered milestones

1. Visual correctness: resolve the four V0.044 hardware reports, audit shared
   sprite composition, and preserve working music/effects and gameplay pacing.
2. Finish and accept Palmtree Panic: all ten act/era variants, natural travel,
   routes/objects, animation, boss, results and special-stage boundaries. The
   detailed `PALMTREE-PANIC-PLAN.md` remains this milestone's test specification.
3. Generalize the proven stage pipeline; inventory and port Collision Chaos,
   Tidal Tempest, Quartz Quadrant, Wacky Workbench, Stardust Speedway and Metallic
   Madness. Each requires its own all-era art/collision/object/boss/progression
   matrix, source comparisons, deterministic routes, stress and hardware tests.
   `COLLISION-CHAOS-PLAN.md` tracks the current Collision Chaos slice and gates.
   `QUARTZ-QUADRANT-PLAN.md` tracks the V0.066 Quartz Quadrant candidate gates.
4. Finish the complete-game flow: all special stages and time stones, title and
   menus, intro/ending presentation, saves/options, credits and supported modes.
   Audit original content and current implementation before claiming coverage;
   imported files or a selectable stage are not completion evidence.
5. Add an optional, documented CD++-style preset. Verify the intended hack's
   behavior and attribution, implement moves natively, and test both presets
   against collision, travel, boss and completion routes. Keep Classic default
   and independently protected; do not claim binary compatibility with a hack.
6. Run the requested recurring, non-overlapping QA/repair loop with durable
   coverage, seed/input logs, independent visual comparisons, audio/pacing
   checks, failure retention and verified launches. Never substitute repeated
   passing smoke tests for complete-game coverage or actual hardware results.
7. Create a source-only versioned release package, instructions, changelog
   and credits. Keep original retail assets user-supplied; no unauthorized
   distribution of a complete copyrighted game disc. Box art: dropped by the maintainer
   on 2026-10-18; do not reintroduce.

## What "better than the original" must establish

Classic behavior/presentation must be faithful rather than changed accidentally.
Enhanced play must offer the requested optional improvements without breaking
original routes. Measure responsiveness/frame pacing and loading, retain stable
audio, and resolve known visual defects. Final acceptance includes full-game
completion and the user's Saturn/SAROO sign-off, not a claim of objectively
superior taste or mathematically bug-free software.

## Known Classic deviations

- Down+Jump spin-dash buffer (`src/player.c` `charge_buffer`): retail has none.
  the maintainer kept it in Classic on 2026-10-11; revisit after the zones 1–4 work.
  Route searches crouch one update first so retail parity is unaffected.

## Safeguards

Preserve immutable V0.040 audio and V0.044 hardware baselines; never overwrite
other games, auto-deploy an unverified candidate, purchase credits, weaken tests,
or bypass permissions. Record each candidate's actual evidence and leave
untested requirements open.
