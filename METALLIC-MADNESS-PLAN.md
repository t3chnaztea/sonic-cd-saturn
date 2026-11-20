# Metallic Madness — V0.078 milestone ledger

Phase 3 follows the private V0.076 and V0.077 releases. Inventory dated
2026-10-16 began with read-only source inspection. Branch `mm-integration-weekend`
(from SS tip `f3e7e14`) merges both foundations and wires MM into production.
All ten MM windows load, run and draw original art on the Saturn build; MM3
plays through the boss and EMIE8's ending. No full MM gate or hardware
acceptance exists. Evidence: `build/weekend-20261016/mm-integration/`.

| Gate | Implemented | Verified | Outstanding |
| --- | --- | --- | --- |
| Actors | Merged `155059f`. Production ids 157-188, R8 layouts, R8 code overlay, `mm_zone_ops` as zone 6, borrowed score-slot sync; `mm_view_table` pattern views; GAME.C stage resets (shut/chibi/prio flags); scarab item script 10 from retail | Smoke 10/10 load and run; no live art misses in six sampled windows (`miss-check.sh`); actors 420 cases, 811,768,137 assertions (oracle carries the port's 8 retail fixes, fbce6d8); monitors/time posts on the player's layer (0ba4c90, ITEM.C/COLI8.C) | Score popups: objects.c skips SCD_OBJ_SCORE from the draw list in every zone and main.c has no score art |
| Player/camera | Shared player code; main.c SCRCHK8 (1808/784, 268 under bossflag); zone-6 rules from retail: st_metalDataChk layer chunks (R83C $2011B2), MM gametimer, up-spring mspeed, goal-post (mosugu) left bound on every load; shrink form: mini animator (retail .MiniAnims/.MiniSonicRun curl, RollMini/PushMini), chibi_flag checkpoint restore, stage-start clear, RIDECHK.C 10/5 landing | MM3C/D Saturn positions match host to the game end; host/retail all nine fields: MM1A 8340/8340, MM1B 9835/9835, MM1D 10285/10285, MM3D 8416/8416 (`build/weekend-20261017/mm-parity/p-1A`, `p-1B`, `p-1D`, `p-3D`); `test-player.sh` PASS; other six zones retail PASS (`build/zone-gates/20261017-090939`); mini animator matches retail R81A/R83C on 175,808 states (27,388 curls); `test-mm-chibi.sh` host PASS | None for shrink: stored MM2A-D routes shrink at x ~7036 and grow back at ~6576; host/retail matches every update to the tally (10,863 small updates, `build/polish/p2/` in mm-polish). Mini Sonic was invisible on Saturn (SONFRM frames 111-126 empty); per-round Sonic packs (7548e5c) fix it: MM2A 5000/5500/6000 pixel-exact vs retail below the HUD (`build/polish/s2b`, `r2shots`) |
| Boss/results | Production BOSS_8/COLI8/COL8C-D and EMIE8 (z8 overlay); retail LoadPLC(4)/(5) restored; EMIE8 swdata control and game end; room/boss/Amy palettes; final-boss track 25 (cue 10, CD track 36) | `test-boss8.py` 6,601 updates per future on production; MM3C/D host routes end the game (7,957/7,448); Saturn MM3C/D match every position, 0 respawns | Late intervals fixed on BIN d27b6580 (ee0ef81 vslot_sync, 6782a3d MM BG during VDP1 draw): Saturn MM1A/1B/3C/3D 0 late, MM1 earned campaign 17149/17149 0 late (`mm-chibi/final-d27b`, `campaign-MM1c`); EMIE8 flash fixed (ddf19c1): the explosion actor's atlas CLUTs follow line 0, MM3D 8670 100% white like retail row 8671; MM3 boss-room death reloads the stage art (966da72) |
| Art | Retail captures for every R8 family (`r8_specs`), flowers, springs; boss 240-248 and Amy 249 from PLC 4/5; ZAR4 shared arenas; Act 3 fight/Amy banks in era slots A/B; R8 COL8 cycles in sprite CLUTs | Saturn art 14/14: ten windows plus fight and Amy banks (`final4/art/`); host art 64 variants | Fight bank 96 B under the VDP1 arena; heap margin 857 B on BIN 9a660e22 (mm-polish); Sonic poses per round: SONFRMB/4/8 (7548e5c, round 4 omits poses only other rounds set) |
| Retail/routes | `test_qq_route.py --mm` Acts 1-3 (Act 3: room, boss, Amy, game end), MM V-INT alignment -1; stored `tests/routes/mm/` for all ten windows; search-only knobs QQ_ROUTE_MM_TOP, QQ_ROUTE_BONUS, QQ_ROUTE_BEST (74d3a3d). Zone-6 fixes: springs act only on screen (228878d), DANGO8 hit roll sign-extends (f60c0fb), time posts in COLI8 pcol's scan (c9dde7c), no native y -256 clamp (e0906b5) | On 1cac0d7 (07f1ffd merged), all ten: host tally, Saturn 0 respawns/0 late, host/retail every update to the tally: MM1A 8340, MM1B 9835, MM1C 7088, MM1D 10285, MM2A 10189, MM2B 10882, MM2C 9808, MM2D 11006, MM3C 8832, MM3D 8416. The MM2C door (TOBIRA 6560,208) is one-way in retail; the route takes the lower door. MM2D exit -11 searches were bigbom's unset pAct1 (86475c8). Evidence `build/weekend-20261017/mm-routes2/` (`r8/`, `r9/n2B`, `r9/n2C`) | MM3 pacing |
| Travel | `tools/test_mm_travel.py`; ten stored pairs `tests/routes/mm/travel/` (48f1cee) | Saturn 10/10 on BIN `4546aee4` (`build/zone-gates/20261017-191124`) | Rerun on the release BIN |
| Campaign | `tools/test_mm_campaign.py`; `mm1-good.txt`, `mm2-good.txt` (lower door), MM3 on `mm3C.txt`; game end checks completed save, ALL ZONES CLEAR, title, cold Continue | WW2 no longer blocks: earned PPZ→MM1 Saturn pass, MM1 17,149 positions, 0 late (`4546aee4`). MM3 diagnostic from MM2's save: 9,083 positions, seven good zones, completed, end screen, title, cold Continue (`build/mm-campaign-search/c275/MM3-diag2`) | MM2 Saturn: one late interval 12347 (5301,1377, beside BIGBOM; mm-pacing); then linked MM2→MM3 |
| Regression/release | V0.078 audit (seven zones + 36 special/front-end cases), packaging, qa-loop MM steps, draft `RELEASE-NOTES-V0.078.md`; package counts 403/394 | Seven-zone dry run 303/305 on `4546aee4` (only MM2/MM3 campaign fail); special BIGRING×7 + SAVE 8/8 on `c04f3db4` (`20261017-183556`); fast QA PASS on `92b01a9c` | Release BIN: full QA with sp cases; SP8 timeout/hazard pending |
| Hardware | None | None | The maintainer tests exact private SAROO candidate |

Source entry points: original R8 `ACT81A.C`, `ACT82A.C`, `ACT83.C` identify
actor dispatch. `tools/mm_host_objects.py` names 32 provisional families;
production IDs must avoid SS IDs136–156. Inspect `tools/test-mm-actors.sh`
before the first baseline. Existing palette/terrain/scroll/cache tests cover
backgrounds only. The source inventory has no retail address citations.
Use `tools/scd_addr.py` for addresses and confirm every name marked `~`.

Do not treat imported art, selectable stages or host scaffolds as completion.
Record exact input hashes, BIN hash and reports for each gate. Keep build and
emulator output on the QA volume, check free space before each run, use nice, and
retain at least100 GiB free. The console gate requires user evidence.

Boss evidence: `build/weekend-20261016/mm-boss-foundation/`. The gate runs
actual original BOSS_8/COLI8/COL8C-D/EMIE8 behind explicit standalone hooks.
It does not exercise production dispatch or the Saturn ending frontend.
Commit `91043b2` is retained; its worktree and build output were removed
after compact evidence preservation. Follow-up `301b823` adds EMIE8 control
outputs (`swdata`, `plautoflag`, Sonic `patcnt`, all seven `clchgtim` bytes)
and assertions. Evidence: `mm-boss-ending-outputs/` under the same weekend
folder. Independent re-review confirms those outputs are covered. Ending
playback and control consumption remain untested.

Actor evidence: `build/weekend-20261016/mm-actor-foundation/final/`. Original
SCARAB, BIGBOM8, GATER8 and ANAR8 fixtures add27 cases to the repaired393-case
baseline. Initial SS/MM helper-name collisions are fixed only in MM helpers.
Preserve the active main handoff when cherry-picking `b594183`. Its isolated
worktree/build were removed. No full fast QA or Saturn proof exists.

Actor review found an independent-lifetime gap: the existing MM oracle
skips original explosion execution and follows native deletion. The four new
wrappers and pointer alias repair match original contracts, but child lifetime
and slot reuse were not verified by that earlier run. Follow-up `155059f`
executes original child routines independently:25,621 explosion,19,766 flower
and16,737 score calls;24 kill replays and7,052 slot reuses. Evidence is in
`build/weekend-20261016/mm-lifecycle-foundation/`. SS actor regression passes.
MM flower and score drawing remain suppressed. Actor fixtures count R8 views
only; add child-view checks and repair rendering during art integration.

Independent review of `155059f` found no blocking lifecycle defect. Earlier-zone
predicates preserve behavior; retained retail instructions support ET8 correction.
Production gap: score spawning checks pool occupancy, but MM does not yet
synchronize its borrowed retail slot immediately. Standalone actor fixtures
cannot prove boss-slot safety or global update order. Test those at integration.

## Integration (mm-integration-weekend)

Evidence is under `build/weekend-20261016/mm-integration/`. Ids 157-188
avoid the SS range; `object_layouts.py` asserts it. R8 records now keep
retail order and the saved-flag bit, like rounds 3-7. Shared-code changes are
zone-6 gated, except two. `boss_zone.h` gains a `colorset2` hook, which is NULL
for other rounds. Missing-art lookups no longer abort in zone 6 only.
The R8 overlay is 95,536 B; the heap margin is 345 B. COL8C/D palette tables,
`boss8_col1` and COLI8 `colitbl` moved into the overlay to fit. BOSS_8.C
pattern data now sits in the overlay (`r8_b8_*`); KONBEA.C followed (`mm_zone_ops.konbea`).
Integration BIN: `c24c32492d64a73858cef78f4bca771c6cb75a56ba6de823552f52a38d5f8e44`.
On it: fast QA PASS (zones 0-5), MM actors 420 cases / 811,767,066
assertions, boss8 6,601 updates per future, MM smoke 10/10 (`final/`).
