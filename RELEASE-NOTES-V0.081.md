# V0.081: review fixes and CD++ pacing

Release date label: `20261025` (same day as V0.080).
This is a private Saturn/SAROO test build. The last user-confirmed console
build is V0.065. Keep the BIN/CUE local. They contain assets from the owner's
Sonic CD disc.

## Scope

Fix the 7 findings of the V0.080 code review. No gameplay, physics or art
change. V0.080 stays the fallback.

## Implemented changes

- Finding 1, Time Attack store with almost full backup RAM: the initial
  implementation (1b99e9a) allowed an in-place fallback. The maintainer selected record
  preservation on 2026-10-30 after a 16-byte torn-write reproducer showed
  loss of the sole record. The working candidate now returns BIOS code 4
  when the companion file cannot fit. It preserves the verified record.
  Native regression: 5,536 preservation cases and 8 space-recovery retries.
  Independent review and fresh BIOS preservation passed; full-suite validation pending.
- Finding 2, SMPC collision (a4baa99): the VBlank INTBACK (`input_poll`) is
  now off from RESDISA to RESENAB around every backup write, verify, delete
  and the BIOS init in `src/save_saturn.c`, through the new
  `scd_input_ready_set` (`src/main.c`). Every other SMPC command already did
  this.
- Finding 3, interrupted zone re-harvest (3e9e249):
  `tools/install_zone_packs.py` records the re-extracted rounds in
  `build/zone-packs-pending.json` before the extract and clears it after the
  install. An interrupted run no longer blocks the next build.
- Finding 4, secret picture music (fb98ddd): each picture's music starts
  after its SECRET file loads, as SPX.asm does. The Saturn CD block cannot
  play CD-DA and read data at the same time.
- Finding 5, zone slot sizes (58e27cf): `tools/extract_zone_auto.py` reads
  the per-slot sizes from `src/stage_packs.h` (PPZ0 0x18000, PPZ1/PPZ2
  0x16800, PPZ3 0x17000, COL0-3 0x2800) instead of one 0x18000 constant.
  All 210 harvest files are byte-identical to the V0.080 extractor's.
- Finding 6, public export message (d1f7f51): the default commit message of
  `tools/export-public.py` takes the version from `IP_VERSION`.
- Finding 7, record buffers (3cfc364): the 3 Time Attack file buffers
  (3 x 692 B) move from resident `.bss` to the R0 overlay data. `.bss` goes
  from 221168 B to 219088 B (-2080). `.zone_R0` grows by 2048 B and stays
  below R5.

- CD++ pacing: SS3 actor selection uses the retail-order cache with claim
  invalidation. Object and boss hashes retain every original field and its
  order while avoiding temporary arrays and repeated hashing of cleared slots.
  Native Classic/CD++ MM3 and SS3 C/D states and hashes match the original code.

## Candidate evidence

BIN SHA-256: `49a576b36675853df69417c489cf2068a0702cc56696ca67626b901d3cbb023a`
Source: main `d0f1c85` plus the uncommitted SS3 cache, claim invalidation and exact hash optimizations. Makefile remains V0.081 / `20261025`.
Fast QA: `PASS: build/qa-loops/20261028-183639-569451/report.json` (160/160).
Full QA: `PASS: build/qa-loops/20261028-191222-830737/report.json` (202/202, clean full run).
Seven-zone and special-stage matrix: 347/347 windows, zero failed gates (`build/zone-gates/20261028-211916/report.json`).
CD++ completion: 21/21 cases, 139648 matched positions, zero respawns or late gameplay intervals (`build/cdpp-completion/20261028-191905-011884/report.json`).
Final audit: `build/final-bin/20261028-183233/completion-audit.json`; BIN and all 1195 recorded inputs rechecked unchanged.

The findings below retain the original targeted evidence. The former V0.081 BIN `2ebb18e2…` is historical; it does not identify this candidate.

| Finding | Check | Result |
| --- | --- | --- |
| 1 | `bash tools/test-time-attack.sh` | PASS, includes "one-file backup RAM"; 3 FAIL lines without the fix |
| 1 | `tools/test_ta_full_emulator.py` (real BIOS, backup RAM nearly full) | `PASS: ta-full: free_blocks=6, record_blocks=13, generation=2->4` |
| 2 | Bracket check of `src/save_saturn.c`; `guarded_write` disassembly | 6 SMPC commands, 0 unguarded |
| 2 | `test_frontend_emulator.py ta-unlock ta-run ta-pair` | PASS: input works after the stores |
| 3 | Interrupt after re-extract, then `bash tools/build.sh` | Exit 0; `test_install_zone_packs.py` 12 cases PASS |
| 4 | `test_frontend_emulator.py sound-test-images` | PASS: music stopped during each load, slots 8/30/37/34/2 playing after |
| 5 | Parsed sizes against `stage_packs.h`; harvest compare | Match; 210/210 files identical |
| 6 | `tools/export-public.py --help` | Default "Sonic CD Saturn V0.080 source" before the bump; now V0.081 |
| 7 | `build/unknown-program.map` | `.bss` 0x357d0 (219088 B); buffers in `.zone_R0` |
| All | `bash tools/test-player.sh` | PASS: 16800 frames, desktop reference matches |

## Known gaps

- All V0.080 known gaps carry over (RELEASE-NOTES-V0.080.md).
- The main checkout's harvest and its 6 installed Metallic Madness act 2/3
  packs (Sep 20) are older than the current extractor (111 chunks against
  109). This was present before V0.081 and is not changed by it.
- Automated full QA and all 21 CD++ cases now pass on the hash above. Console acceptance remains pending.

## Hardware

No V0.081 content has run on hardware. Findings 1 and 2 stay pending until a
console test. Emulator results do not close the console gate.

## Console checklist

1. Confirm the BIN SHA-256 above. Cold boot V0.081 twice.
2. Fill backup RAM until fewer than 2 Time Attack files fit (about 13 free
   blocks). Set a Time Attack record. Power off, boot, and check the record.
3. Set a Time Attack record. Check the pad works at once after the save and
   that RESET during the save does not cut it.
4. In the Sound Test, enter each of the five secret codes. Check that each
   picture shows and its music plays.
5. Repeat the V0.080 console checklist.

Only the maintainer's exact-BIN SAROO evidence closes the console gate.
