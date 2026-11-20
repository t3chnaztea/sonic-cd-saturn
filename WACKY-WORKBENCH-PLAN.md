# Wacky Workbench — active milestone ledger

Scope: R61A–D, R62A–D, R63C/D; art, collision, actors, routes, boss,
progression and console acceptance. The Sega CD source under
`build/audit/source/src/R6/` and retail CPU captures are the reference.
This ledger describes the development tree, not the frozen V0.074 package.

Current V0.076 runtime is `6b8bd72`; last pre-warp-fix profile0 BIN
`87ddaea236b61447271efc4ab20a150f8cd128b05ab3649845c6566c96ce8bc0`.
Full run06 passed165 commands, then was interrupted before a known campaign
failure: the stored WW2 earned route dies at update5727, x3468/y1709.
Both main and SS source snapshots reproduce it; retail also dies before warp.
Replacement040f55d passes native/Saturn but is held for a shared warp-contact
ordering correction: native starts the timer one update before original.
Matched retail VBlank history confirms that error;14 extra retailVINTs explain
the larger unlagged arrival difference. The VBlank-based clock remains unchanged.
Corrected source matches exact retail saved/arrival state with matched VINTs;
728 boundary cases and player traces pass. Fourteen other campaign host routes
pass. Natural travel47/50 passes; WW2AB/BA/DA require classification/repair.
Evidence: `build/weekend-20261016/six-zone-campaign-01/`; active diagnosis is
in the integration worktree's `build/weekend-20261016/ww2-campaign-diagnosis/`.
Earlier ten-window host parity and predecessor-BIN gates below remain historical.
No final one-BIN campaign, complete regression or console acceptance exists.

| Gate | Implemented | Current evidence | Outstanding |
| --- | --- | --- | --- |
| Background art | R6 scroll, COL6 palettes, animated tiles and plane B; WW3 camera-bottom and floor rules; R61/R63 object clocks and R62A/B/C palette and object phase fixes | `PASS: WW zone-art matrix, 10 programs, bin 98604e03c82a331b`; `build/ww-art-v0076-9860.log`; R62C phase fix merged as `51d89f2` | R62D retail phase comparison, Saturn display inspection |
| Object art | R6 pattern extraction and zone-art records; Minomusi normal poses; R63C/D boss and PLC 19 art | `PASS: WW3 PLC 19 entry sprites match every retail tile write in both futures` on `efe1b4f`; R6 art matrix 10/10 on predecessor BIN `98604e03`; 2,300,928 R63C and 2,279,424 R63D exact sprite pixels | Live beam, toge and explosion visuals on hardware |
| Collision | Native `COLI6.C` pcol and terrain; WW spark blocks; rolling launch flags; Sega CD falloff at speed 640; time-warp timer by VBlanks; original rotating pole; WW hanging bar, beam and spark recoil, bounce-platform rider lifetime | WW1 A–D, WW2 A–D, WW3 C/D whole-window nine-field host parity passed 10/10 on source-equivalent isolated tree; reports `build/ww2-fullfixture-c767-evidence/` and `build/ww2-minomusi-508c-evidence/` | Final-source BIN routes and hardware |
| Actors | 24 R6 actor routines; R63C/D boss, six doors and three meca; original Snake Block child timing, PISTON6 wall order, WW retail-ordered placement stream and ring visibility | Main `508cf3b` WW actor gate passed 320 cases and 1,155,902,722 assertions; `build/ww-actors-main-508c.log`. WW stream passed 1,551 placements on prior source. | Final-source stream and hardware |
| Routes and progression | QQ3 can hand off to WW1; controller-only WW1 A–D, WW2 A–D, WW3C/D reach next acts; earned WW1/WW2 Good Future and WW3C→SS1 cold Continue; PPZ→CC earned-save bridge merged | WW1 A–D and WW3 C/D Saturn routes, earned PPZ1→WW3, and SS1 cold Continue passed on predecessor BINs. WW2D Saturn route passed 5,660/5,660 retail rows with zero respawns/late intervals on interim BIN `307e2239`; `build/ww2d-interim-saturn-307e/report.json`. | Repair WW2 earned-route death; final-BIN routes/campaign and hardware |
| Natural travel | All five Act 1 and five Act 2 pairs use only controller input and the normal warp handoff | Saturn emulator passed 10/10 on predecessor BIN `98604e03`; `build/ww-travel-v0076-9860/`, refreshed routes `50f530b` | Repair WW2AB/BA/DA host paths, then final-BIN rerun; hardware |

All ten WW whole-window host retail routes pass on one source. The WW1C
flower-slot regression and WW2 actor timing gaps are closed. Resume with one
clean full QA run on the five-zone matrix, then verify the final BIN and
package it for console testing. Console acceptance still needs a user test.

## R63 boss art extraction findings (2026-10-07)

The retail inputs are `R63C__.MMD` SHA-256
`9708c99810fa001eb5593497f8e96d1008391f73348e672c94354c804e4d0c13`
and `R63D__.MMD` SHA-256
`e3799bdd69c593996af6ad245e1b3d354d3ba4cedcc49503389f19e730fe7173`.
Scanning the 64-entry ObjectIndex and each BOSS_6.C actor routine's first
`patbase` write gives these retail mapping counts in both futures:

| Actor | Mapping poses | C address | D address |
| --- | ---: | ---: | ---: |
| 52 egg6boss | 17 | `20f986` | `20fa4e` |
| 53 egg6meca0 | 2 | `20fb1e` | `20fbe6` |
| 54 egg6meca1 | 4 | `20fb72` | `20fc3a` |
| 55 egg6meca2 | 4 | `20fba0` | `20fc68` |
| 56 egg6toge | 1 | `20fbc0` | `20fc88` |
| 57 egg6gareki | 2 | `20fc58` | `20fd20` |
| 61 egg6yuka | 1 | `20fc88` | `20fd50` |
| 62 egg6door | 2 | `20fc28` | `20fcf0` |
| 63 egg6bakuha | 8 | `20fbde` | `20fca6` |
| 64 egg6beam | 5 | `20fcaa` | `20fd72` |

The routine scan also finds a 2-pose beamer table at `20fc18`/`20fce0` and a
4-pose debris table at `20fc68`/`20fd30` (C/D). Live retail traces confirm
their actor use. The retail beam retains one mapping table while cycling three
uncompressed MMD art blocks at `$233c0c`/`$233d0c`/`$233e0c` in both futures.
R63C PLC 1 loads stage art
at tiles `$360`–`$7ae`; PLC 2 replaces overlapping tiles `$330`–`$458`.
The egg6boss mapping reads tiles `$3ec`–`$47b`, so extraction needs the
fight's actual PLC state. The current pack uses PLC 1, 2 and 19 fight art.
The R63C/D zone-art target pictures pass. Retail frames 300–910 match nine
sampled boss kinds in both futures. The three extracted beam art states equal
retail VRAM when actor 64 is live. Entry PLC 1/2 poses for kinds 240–243
match all sampled retail VRAM tiles at frame 145 in C/D
(`build/ww-entry-live-art.json`). PLC 19 writes three complete tiles per
update, separately in banks `$300` (C age 22), `$3ec` (C age 101) and `$440`
(C age 129). D reaches each bank one update earlier. The generated patch
stream updates all 22 mutable VDP1 entry records through C age 106/D age
105. Retail VRAM matches the derived schedule at 303 sampled frames, and
the native emulator matches each mutable bitmap hash at all 211 update ages
(`build/ww-plc-art-test-2.log`, `build/ww-plc-runtime-2.log`). Toge, explosion,
native beam kind cycling and full fight art parity remain open.
