# Tidal Tempest — R4 verification gates

Scope: Acts 1–2 in all four eras, Act 3 in both futures, the R4 boss and
capsule, natural time travel, CC3 → TT → QQ Continue, and results/handoff.
The last user-confirmed console result remains V0.065, "Works, no new
defects" (`hardware-results/v0.065.json`). It does not close a TT-specific
hardware gate.

## Completion ledger — V0.074

V0.075 (2026-10-11): TT retail, routes, art and travel 10/10 and campaign
3/3 re-passed on BIN `b3fd1a04…` (`build/zone-gates/20261011-203415/report.json`).
Package `build/hardware-v0.075/`. Console pending.

Final BIN SHA-256:
`253344b446a3683055e9ceb34e0c2e754048eb75e4e48cd4b16ff139a8cf81b0`.
Fast QA passed at `build/qa-loops/20261005-134725-629409/report.json`.
Full QA passed 165/165 at
`build/qa-loops/20261005-141001-653051/report.json`.
Private V0.074 bundle preserved at `build/hardware-v0.074/`; readback
`build/release-v74-readback.json` verified 531 members and ZIP SHA-256
`66dff75e8f9c12db1fc4315f5b8691560688e253ee89ae086b36d08a6dd813c7`.
All host routes match retail for their whole compared windows. All Saturn
controller routes below have zero respawns and zero late gameplay intervals.
Console acceptance is open for the maintainer's SAROO test.

| Gate | Current result | Evidence |
| --- | --- | --- |
| Art / background | Pass, 10/10 programs | `build/zone-art-qa/tt-matrix.log`; full QA R4 scroll, palette, BGV, terrain, cache, plane and SCRCHK steps |
| Collision / actors | Pass | Full QA `test-tt-platforms.sh`, `test-tt-actors.sh` (10 act/era cases), `test-water.sh`, object stream and terrain checks |
| R4 boss / capsule | Pass, C/D | `build/tt3-boss/report.json`; full QA `test_tt3_boss_emulator.py` and `test-boss.sh` |
| Ten act/era routes | Pass, 10/10 | `build/tt{1,2,3}/controller/*/report.json`; whole retail windows: TT1 A/B/C/D 6,848/2,068/9,174/7,264; TT2 A/B/C/D 6,663/3,416/6,200/2,751; TT3 C/D 9,438/9,441 |
| Natural travel | Pass, 10/10 | `build/tt-travel/v074-final/tt*`; five era pairs per act, 300 resumed updates each, frozen matching BIN/CUE/ELF |
| Continue | Pass, 4/4 | `build/cc3/controller/continue/`, `build/tt{1,2,3}/controller/continue/`; CC3 → TT1 → TT2 → TT3 → QQ cold Continue |
| Earned Good Future campaign | Pass, 3/3 | `build/tt-campaign/v074-final/tt{1,2,3}/report.json`; generators, boss, results, QQ save and cold Continue |
| Other-zone regressions | Pass | PPZ 10/10 and QQ 10/10 direct route gates; CC routes, campaign and ring-loss stress in full QA |
| Console | Pending | `RELEASE-NOTES-V0.074.md` checklist; the maintainer tests SAROO |

The emulator and source gates establish retail parity for the ten compared TT
windows. They do not establish hardware acceptance. Only the maintainer's console run
can close that gate.
