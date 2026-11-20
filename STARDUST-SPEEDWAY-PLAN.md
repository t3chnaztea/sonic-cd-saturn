# Stardust Speedway — V0.077 milestone ledger

Scope: R71A–D, R72A–D, R73C/D. Match the Tidal Tempest V0.074 bar.
The five-zone V0.076 release comes first. No final-BIN SS acceptance exists.
Updated 2026-10-16. Integrated runtime builds; all ten merged-source
host/retail windows pass. No one-BIN Saturn or full six-zone acceptance exists.

| Gate | Implemented | Verified | Outstanding |
| --- | --- | --- | --- |
| Runtime actors | Unmerged `d79f60b`: production IDs, layouts and registration | 367 cases, 1,613,236,456 assertions; `build/weekend-20261016/ss-runtime-foundation/` | Merge after V0.076; code overlay and final runtime proof |
| Act 3 race and results | `boss_r7.c`, `prepare_boss_r7.py`, `boss7_test.c` scaffold | Unmerged `1789649`: source-cast comparisons 4/4, 17,278 updates per side, ASan/UBSan clean; `build/weekend-20261016/ss-boss-foundation/` | Unmerged `660fa25` connects runtime; final-BIN race/routes pending |
| Art | Integrated `393f758` packs; checker `8f24e31` | Saturn10/10 on BIN `8d8a4014…cd5cd72`; `ss-art-travel-04/` | Rebind to final six-zone release BIN |
| Retail routes | All ten scripts and runtime merged in isolated `e6823d4` | Fresh retail 10/10, nine fields, 63,416 updates, zero field splits; `build/weekend-20261016/ss-integrated-retail/summary.json` | Bind to final six-zone release matrix |
| Saturn routes | Integrated shared runner and ten controller scripts | SS1/2 all8 pass on8d8a4014; routes03 | SS3C/D209/128 late intervals; zero respawns and exact positions; profiling next |
| Natural travel | Integrated `29b4b15`: ten stored controller scripts | Saturn commitments/arrivals10/10 on BIN `8d8a4014…cd5cd72`; `ss-art-travel-04/` | Rebind to final six-zone release BIN |
| Campaign and Continue | Unmerged `be6db0e` earned-chain harness, provenance tests and two scripts | SS1/2 host generator routes: 8,136/11,071 positions; `build/weekend-20261016/ss-campaign-foundation/` | Earn Good Future across SS1/2/3, Amy/results handoff, cold Continue into MM |
| Prior-zone regression | Unmerged `ab0199e`: version-bound six-zone matrix and release audit | 18 focused tests; V0.076 217 windows / V0.077 260 windows; `build/weekend-20261016/ss-release-wiring/` | One-BIN full QA across zones 1–6 |
| Hardware | None | None | The maintainer's exact-BIN SAROO test remains open |

## Integration and acceptance

V0.076 remains frozen in main. `ss-integration-weekend` is active on
the QA volume, with isolated `ss-pacing` diagnosis. Check free space before builds/gates; keep 100 GiB free and use nice.
Original behavior comes from scddisasm/soniccd R7 and retail captures.
Use `tools/scd_addr.py`; confirm every name marked `~` before citing it.

1. SS1/2 pacing dependencies are merged; diagnose SS3C/D timing in isolation.
   Preserve the 61,440-byte texture and 512-record limits.
2. Integration through `02fe0c7` contains root routes `5fbae2f`, campaign
   `be6db0e`, travel `29b4b15`, boss `ef12be7`, scheduler `d2d2a5d`, and
   SS3 routes `18b7b2f`. The SS clock/reset/view variants are preserved.
   QA commit `dbe8548` adds camera, collision and campaign evidence checks.
   Campaign provenance passes 21 cases; release validation passes 18 cases.
   These focused checks do not establish a fast or full QA pass.
3. Integrated build `393f758` passed; fast QA reached step64 then failed on
   missing CC retail-scroll fixtures (20261016-193304-346586/report.json).
   Actor367, camera/collision/provenance and six-zone boot checks passed.
   CC/TT/QQ fixtures are now captured. Fast02 failed130 on a stale legacy
   object-stream fixture; test-only `50701da` fixes it (81920 comparisons).
   Fast03 now passes147commands, unchanged source/generated/BIN hashes.
   Evidence `ss-integrated-fast-03/`; routes03 fails SS3C/D timing only.
4. Rebind all ten host/retail windows, Saturn routes, art, travel, earned
   campaign and Continue to one V0.077 BIN. Earlier five zones must pass too.
5. After V0.076 is preserved, merge verified SS work into main, run clean full
   six-zone QA, fill release/hardware docs and preserve V0.077 privately.
   Only the maintainer's exact-BIN SAROO test can close console acceptance.

## Preserved evidence and limits

All evidence folders below are under `build/weekend-20261016/`.
`final-ss12-regression/`: eight Act 1/2 windows match all nine retail fields:
SS1 A/B/C/D 4,846 / 6,726 / 5,959 / 6,118 comparisons;
SS2 A/B/C/D 6,399 / 6,429 / 5,506 / 4,673 comparisons.
QQ1A 10,841, CC2D 9,213 and WW1B 6,578 also match all fields.
Ten cold host travel commitments pass. Retail-prefix diagnostics are five
complete matches, two sampled-perfect incomplete windows and three phase
bound differences. None proves Saturn arrival. All 570 inputs stayed fixed.

`ss-lifecycle-combined/`: 1,614,971,389 actor assertions, 367 cases; actual
original explosion, flower and score child functions execute in the oracle.
`camera-death-regression/`: 29,568 original SCRCHK comparisons, 1,008 dead
camera cases, player traces 16,800 frames / 268,800 words. This death-only
camera change follows the route batch; final integration needs fresh gates.
`ss3-retail-parity/`: C/D 8,107 / 8,653 all-field comparisons through race,
Amy/results and tally. Boss 4/4, player and QQ1A checks pass in that tree.
`ss-campaign-foundation/`: SS1/2 each warp A→B, destroy the generator and
finish in the Past. `ss-campaign-evidence/`: 21 predecessor-proof cases pass.
`ss-actor-art/` and `ss-boss-art/`: host captures only; SS flower capture and
final Saturn art gates remain in integration work. No hardware result exists.

`ss-integrated-retail/`: all ten windows rerun on final merged flower/clock
source `e6823d4`; 63,416 complete sampled updates match all nine fields.
Both SS3 race contracts pass. Inputs stayed unchanged. Mid-update V-INT
samples are excluded by the existing oracle. No Saturn result is implied.

Art/travel02: integration `build/zone-gates/20261016-202302/report.json`.
Travel10/10; art initially9/10 due missing R7 palette cycles in checker.
BIN `3ab4c73ffd581d7b5df4d9ec40e69fe37f674a6d6cd71f8cfc58cec98fdcb88f`
and source hashes stayed fixed. Checker `8f24e31` adds source-verified cycles
and one whole-capture palette timestamp. Fresh `ss-art-03/` passes10/10 on
the same BIN. Wrong-color and mixed-timestamp negatives fail as required.
Independent palette timer-phase QA remains required. No full release pass exists.

SS2A pacing `80a1990`: profile0 route6722 matched positions, zero late/respawns;
source actors367/1615034951 assertions and actual allocator48 cases pass.
Independent review found no blocking defect; virtual exhaustion is not covered
by the fixture. Evidence `ss2a-pacing/spring-fix/`. Integrated build03 passes.
Current SS BIN: `8d8a40149af0b263a1fb0aa6cf1e265780a0a8d312b8f81bf99e7af6bcd5cd72`.
Fast03 PASS: `build/qa-loops/20261016-203324-642232/report.json` in integration.

Integrated art/travel04 passes20/20 windows on BIN8d8a4014 with unchanged
inputs. Six-zone earned campaign01 is active from PPZ newgame through SS.

Unmerged SS3 scheduler fix `43f30e5` passes profile0 C/D8311/8827 positions
with zero late/respawns and MM1 handoffs. Source actors367/1615034951assertions
and boss parity/results adapter pass. Actual old/new scheduler fixture passes
35 selector cases,10 mutation scenarios,95 callbacks,2 deletion/reuse cases;
both negative controls fail as intended. Independent review clear. Profile1
C retains one late interval; paired profile0 C/D pass unchanged runtime.
Evidence `ss3-pacing/`; isolated worktree removed. Merge after WW2 diagnosis.

Six-zone campaign01:15/20 pass. WW2 stored route dies at5727 before warp on
both V0.076 and SS source. Retail also dies; nine fields match through5725.
WW3 and SS1–3 are blocked by missing fresh WW2 backup. Route regeneration
is in progress; no campaign acceptance. Evidence `six-zone-campaign-01/`.
