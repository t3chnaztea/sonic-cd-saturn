# Quartz Quadrant — V0.066 acceptance gates

Scope: Acts 1–2 in all four eras, Act 3 in both futures, the boss and capsule,
Classic-default saves, TT → QQ → WW Continue, and R5 background redraws.
Hardware acceptance requires user-confirmed Saturn/SAROO evidence.

## Completion ledger

Full QA passed 161 gates with zero failures in
`build/qa-loops/20261001-030504-286740/report.json`. Full-12's guardian passed
with unchanged inputs. Profile-02 passed all six actual redraws with source
restored. The final QQ batch passed under `qq-final-13/run.json` with unchanged inputs.
All final candidate gates passed. Local bundling/readback passed; remaining-time
ring-loss/cold-boot stress passed under `stress-15/run.json`. Natural travel
passed four controller-only routes under travel-17 through travel-20:
QQ1 A→D/B→A and QQ2 A→B/B→A, 5,966 matched positions and 300 resumed
slave-ready updates per arrival. Travel-16 failed before gameplay; the runner
then received its missing replay-enable setting. Final fast QA passed 126 gates
under fast-21. `build/overnight-20260930/final-audit.json` passed the closing
package, source-change and stress-evidence audit. No overnight work remains live.
The stress-only tool edit postdates frozen QA/package input hashes. Hardware acceptance remains pending.
The absolute deadline is October 1 at 08:00 Central. Revalidate the live process
before starting any other build/emulator command. Resolved save/art verifier
failures remain in the handoff archive and their preserved evidence folders.

| Gate | Implemented | Verified evidence | Outstanding |
| --- | --- | --- | --- |
| R5 switch-frame hold and N+1 redraw | `src/background_r5.c` retains the pending event until the display snapshot; `src/main.c` divides eligible full redraws between both SH-2s | Final `build/qq2/controller/{A,C}/report.json` on `24596e211c97f164bf0b9ce87a82476b86ceb7cb9c1eddc894f4ca9f4757af7c`: 2 A and 4 C changes, holds, redraws and slave completions; zero fallback/unavailable events | Console ownership transitions |
| Background fidelity and cache | R5 scroll, palette, terrain and row-fill code | Overnight full-run logs `build/qa-loops/20261001-030504-286740/{63,65,68}.log`: 81,528,832 original/native line words, 10-pack cache replay, 573,440 retail plane cells matched; comparison exclusions remain in the logs | Full QA passed; visual acceptance on Saturn |
| All act/era routes and boss | `tools/test_qq_route.py`; `tools/test_qq3_boss_emulator.py` | Final `build/qq1/`, `build/qq2/`, `build/qq3/controller/` reports: all ten routes, 78,467 matched positions, zero respawns/late intervals; `build/qq3-boss/report.json`: C and D passed on current `24596e...57af7c` | Console acceptance; whole-act retail parity remains unproved |
| Continue and cold save | TT3 → QQ1 → QQ2 → QQ3 → WW; original v2 save flags preserve `curSpecStage` | Final `build/{tt,qq}{1,2,3}/controller/continue/` reports: earned TT1–3 → QQ1–3 → WW chain; exact backup hashes join all six links; QQ3 cold WW Continue passed | Twelve repeated cold boots passed in `qq-stress-01/report.json`; console power-cycle remains pending |
| Redraw timing | Actual hold/redraw/slave markers in profile word 30; checker requires adjacent target VBlanks and work ≤47,355 ticks | `build/overnight-20260930/profile-02/report.json`: 2 A redraws (max 21,969 ticks), 4 C redraws (max 19,376); adjacent target VBlanks and completed slave work; normal executable/disc identity restored apart from ISO dates. Prior threshold-based 12,164-tick claim withdrawn | Final full-QA/route content identity verified in `full-12/identity-after-rebuild.json`; hardware timing remains open |
| QQ slave transitions | Era reload, game-over/title and special-stage return fixtures | `build/qq-lifecycle/report.json`: all three pass on final `24596e211c97f164bf0b9ce87a82476b86ceb7cb9c1eddc894f4ca9f4757af7c`; eight era reloads, advancing title, 120 resumed QQ updates | Four natural controller-only era warps passed in `qq-travel-{02,1B,2A,2B}/report.json`; console results remain pending |
| Retail slot model and ring parity (2026-10-18) | `qq-slot-weekend`: checkpoint ball companion slot (`src/boss.c`), `tp_actwkchk` slot at the call, lost rings and placed rings through `qq_enemy_scan` (all gated `objects_zone==3`) | QQ2A host vs retail object dumps: every slot matches, updates 149-3029. Ring counts: 3 updates differ (was 1118), each a hurt where `flyringinit` clears `plring` one update later. `build/zone-gates/20261018-005346/report.json`: QQ retail/routes/art/travel 10/10 each, 0 late intervals | Ring parity needs host V-INT phase 157:230; the harness keeps `vint_offset=1` (229) because position parity passes at both and cached results stay valid. Known gaps (retail lag, as the warp timer): lost-ring floor phase after a lag frame on Saturn; QQ1A 601 era sign |
| V0.066 release | Version/date set in `Makefile`; release notes finalized; normal BIN rebuilt by full-12 `24596e211c97f164bf0b9ce87a82476b86ceb7cb9c1eddc894f4ca9f4757af7c` built | Full-12 passed 161 gates; qq-final-13 passed all candidate gates with unchanged inputs; 83 evidence files staged; local ZIP readback passed 525 members (`build/release-v66-readback.json`) | User-confirmed console result |

## Next commands

1. Local bundle/readback passed. Keep the preserved package immutable; no SD changes.
2. All planned overnight checks passed. Optional read-only evidence recheck:
   `python3 build/overnight-20260930/final-audit.py`.
3. Next acceptance step: user-confirmed Saturn/SAROO test. Card copy remains a
   separate task. The overnight goal ended before October 1 at 08:00 Central.

Full QA alone does not close the QQ candidate gates; the separate final QQ
batch and `dist/qq-acceptance.json` provide their current evidence.
