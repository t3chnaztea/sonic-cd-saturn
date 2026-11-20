# SS earned Good Future campaign

Host controller recordings are present. Saturn earned-save verification remains pending. Do not substitute fabricated saves or RAM writes.

Entry: the verified WW3 campaign backup. Run `tools/test_ss_campaign.py --act 1 --backup <earned-WW3-backup> --output <SS1>`; SS2 consumes SS1's output backup. SS3 consumes SS2's earned Good Future backup. SS3 must complete the race and Amy rescue, then cold Continue its resulting MM1 backup.

ET7 placements confirmed from original R7 source: Z71ACT.C:226 `(3824,1216)` and Z72ACT.C:67 `(752,1216)`. Both records use ID169 (masked ID41, ACT71A.C `et`) and era bits96 (Present/Past). Production R7_ET7 is155. The host search requires one natural Present-to-Past arrival, then generator destruction, then the Past tally.

Expected recordings: `ss1-good.txt`, `ss2-good.txt`. SS3 reuses the verified `../ss3C.txt` race route once its runtime host is integrated. `--prepare-only` compiles the derived host without accepting any route. No campaign result is claimed yet.

Host evidence (2026-10-16): SS1 8136 positions, arrival2216, generator3538, tally8137; SS2 11071 positions, arrival2248, generator3018, tally11072. Both perform exactly one natural Present-to-Past warp and finish in Past with Good Future set. Reports: `build/ss-campaign-search/SS1/report.json` and `SS2/report.json`. These are host-only results, not Saturn or retail campaign acceptance.

The Saturn chain requires the preceding passed campaign report from the same BIN. Its `backup_after_sha256` must match the supplied backup. The default report is `report.json` beside that backup; use `--entry-report` for a relocated archive. SS entries must retain earned WW Good Future and the expected SS act bits0,1,3. Handoffs preserve earlier zone flags. Cold Continue must reach active MM1 gameplay with the exact resulting backup unchanged.
