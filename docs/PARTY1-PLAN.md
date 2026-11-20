# Party 1 plan after QQ (planner inventory, 2026-09-26)

Goal: one-to-one Sega CD match. Order: QQ V0.066, WW V0.067, SS, MM, then non-zone items.

## Overlay budget
The region equals the largest ZTR. ZTR5 is 104,424 B, ZTR6 31,372 B (rodata only), and ZTR8 46,484 B. No ZTR7 exists yet.
Estimates: WW about 73 KB, SS 55-65 KB, MM about 95 KB. MM is close to the region; gate it.

## WW slices (mirror QQ)
1. Stream window test, a copy of test_tt_stream.py.
2. Boss link. boss_r6.c has host parity. Open: test-boss.sh R5/R6, the scd_boss6_fade reader, and native flashout.
3. Overlay: .text.z6_*, zone_r6_names.h, ww_zone_ops, and background_r6 behind SCD_ZONE_R6. This touches busy files, so run it after QQ.
4. Art matrix: add round (6,4) to zone_object_assets.py:198 for ZART6x, and a run-ww-art-matrix.sh.
5. Background/terrain: DEV6 tiles and the PLAYER6 bfloor/sibi hooks. Re-verify the SCR61B/62B plane A mismatches.
6. Routes: WW1-3 x A-D, found by host search.
7. QA and release V0.067.
Also: 8 of 24 WW routines are unfinished in test-ww-actors.sh.

## SS (R7)
Needs .zone_R7, the test_zone_code R7 prefix, and ZONE_TABLES R7. Open: the hotaru7 renderer, the gametimer tick, and the prio_flag reader.

## MM (R8)
Needs player.c hooks: chibi_flag, HAGURUMA actfree[14], shoot_s swdata, KAITEN layer, SHUT block_wrt. koma8 is deferred. 4 retail capture fixtures freeze.

## Non-zone
- Special stages: audit time stones and good futures against main.c:157-181.
- Title/menus: audit TA, BESTTIME, SOUNDTST, STAGETST, and VISUALMD, plus D.A. Garden.
- Warp cutscene: WARP/WARP.C.
- Intro/ending FMV: a Saturn playback design is needed.
- Credits: TITLE/THANKS, a host port.

## Completion ledger
| Gate | State | Evidence |
|---|---|---|
| V0.065 hardware | passed (user report) | hardware-results/v0.065.json |
| Zone code overlays R3/R4 | verified | 4081c1d, margin 67,897 B |
| R5/R1 overlays, QQ3 boss (S2) | verified | 0dfdce3, boss_retail_capture PASS |
| Stream window TT/QQ/WW (S1) | verified | b5bc519 |
| Special stages 1-7 + save v2 | verified | 6b2f8b1, a0a8d3f |
| QQ S5 CLUT cycling | uncommitted, gates interrupted | src/main.c:991 |
| QQ routes 10/10 | 6/10 on main; 8/10 with 0bdf64a; 1D/2D freeze | NEXT-SESSION.md |
| QQ V0.066 release | open | |
