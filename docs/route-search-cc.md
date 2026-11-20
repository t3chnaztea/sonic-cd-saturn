# Collision Chaos route search

How each tracked Collision Chaos pad script in `tests/routes/cc/` is searched,
which QA gate replays it, and the V0.073 regeneration record. A script is
"COUNT PAD" lines (our own inputs only, no game data).

## How the gates use the scripts

`tools/staged_routes.py` copies `tests/routes/cc/<name>.script` instead of
running the gate's fixed-seed host search. `SCD_STAGED_ROUTES=` (empty) makes
the gate search again with its own built-in mode, seed and iteration count.
The host replay, its tally gate and the Saturn replay always run, so a stale
script fails at the host replay ("Route failed" / "Route incomplete").

To re-search one route without changing its goals, either run the gate with
`SCD_STAGED_ROUTES=` (searches, then verifies; copy the `script.txt` it wrote
into `tests/routes/cc/`), or run the host search directly as below and then run
the gate with the default staged directory. Never hand-edit a script.

## Hosts

Build from the repo root. These match the gates' own compile lines.

```
# H1: tools/cc_campaign_search.c (test_cc2_route.py flags; the other cc_campaign_search users differ only in -O level)
clang -std=gnu11 -O1 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
  -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A tools/cc_campaign_search.c \
  src/{title_card,world,act,player,camera_v,sonic_animation,stage,boss,boss_r3,objects}.c \
  build/probe-source/{boss_1,boss_3,playsp3,interaction,player,dircol,fcol,etc,equ,movement}.c -o H1
# H3: tools/cc3_route_host.c (test_cc3_route.py)
clang -std=gnu11 -O2 <same flags and sources, tools/cc3_route_host.c in place of cc_campaign_search.c> -o H3
```

## Search commands

`H search MODE SEED ITERATIONS OUT` (H3: `H3 search ERA SEED ITERATIONS OUT`).
Mode `ACT:ERA` starts at that act's level-select spawn; `0` / `1` are the
campaign modes; `0@B` is CC1 Present with the Past generator milestone.

| Script | Command | Gate (qa-loop full) | Goal checked by the gate |
|---|---|---|---|
| cc1A / cc1B / cc1D | `H1 search 0:A 41 60000`, `0:B 41`, `0:D 41` | `test_cc2_route.py --act 1` | Act 1 tally, handoff to Act 2 Present |
| cc1C | `H1 search 0:C 42 60000` | same | same |
| cc2A / cc2B / cc2D | `H1 search 1:A 41 60000`, `1:B 41`, `1:D 41` | `test_cc2_route.py --act 2` | Act 2 tally, handoff to Act 3 Bad Future |
| cc2C | `H1 search 1:C 42 60000` | same | same |
| cc2C-seed25 | `H1 search 1:C 25 60000` | `test_cc2_route.py --act 2 --era C --seed 25 --require-ring-loss 30` | as cc2C, plus one update loses >= 30 rings |
| cc3C / cc3D | `H3 search C 1 200000`, `H3 search D 1 200000` | `test_cc3_route.py` and `--continue` | 3 boss hits, capsule, tally, Tidal Tempest Act 1 handoff |
| campaign-cc1 | `H1 search 0 23 60000` | `test_cc_campaign_act3.py`, `test_cc_campaign_generator.py --milestone continue` | Past generator, natural travel to Good Future, tally, Act 2 from Continue |
| campaign-good | `H1 search 1 31 60000` | `test_cc_campaign_act3.py` | Act 2 Past generator, Act 3 Good Future (R33C) |
| campaign-bad | `H1 search 1:A 41 60000` | `test_cc_campaign_act3.py` | Act 2 Present, Act 3 Bad Future (R33D) |
| generator | `H1 search 0@B 7 60000` | `test_cc_generator_route.py --act2` | generator destroyed, two natural warps to Good Future, tally, Act 2 |

Seeds and iteration counts come from the gates: `SEEDS`/`ITERATIONS` in
`tools/test_cc2_route.py`, `SEEDS`/`SEARCH_ITERATIONS` in
`tools/test_cc3_route.py`, `SEARCH` in `tools/test_cc_campaign_act3.py`,
`SEARCH_SEED` in `tools/test_cc_campaign_generator.py`, and the literal
`0@B 7 60000` in `tools/test_cc_generator_route.py`. cc2A and campaign-bad use
the same mode and seed, so they are the same script.

## V0.073 regeneration (2026-10-04)

Commit 6ad1372 changed player/object physics. All 15 scripts above failed the
host replay on the new sources (for example cc1B "Route failed at 7530",
cc3D "Route died at 3671", generator "Route incomplete: milestone=1"). Each
was re-searched with the command above, unchanged seed and goals. Every search
finished on its first seed.

Verified against frozen BIN `f4ac2b0c…4d4a` (ELF identical to
`build/saturn/`), staged scripts, every host position matched on Saturn:

- `test_cc2_route.py --act 1`: PASS, A 9087, B 9400, C 8090, D 8649 positions, 0 respawns, 0 late.
- `test_cc2_route.py --act 2`: PASS, A 7749, B 7766, C 9068, D 7976 positions, 0 respawns, 0 late.
- seed 15 ring-loss stress: PASS, 7167 positions, largest ring loss 35.
- `test_cc3_route.py`: PASS, C 3801 / D 2998 positions, 3 boss hits each, Tidal Tempest handoff.
- `test_cc_generator_route.py --act2`: FAIL. Host replay and positions match,
  but the Saturn shows 2 late gameplay intervals: sequence 5634->5635 and
  6484->6485, 2 VBlanks each. Both are the first update after a time-warp
  arrival (era 1->0, then 0->2). The Sep 21 `--travel` report (BIN `70f545ac…`) had
  none. Suspected cause: 6ad1372 calls `scd_player_objects_lead()` in
  `load_era` (`src/main.c:849`), so the first update after any load also runs
  `scd_objects_step` a second time (`src/player.c:385`). Not patched; `src/` is
  out of scope for route work. Any route with a warp will show it, so a new
  seed would not help.
- Campaign chain (`prepare_cc_campaign_checkpoint.py`, `test_cc_campaign_act3.py`,
  `test_cc3_route.py --continue`, `test_cc_campaign_generator.py --milestone continue`):
  not run on Saturn. The checkpoint step plays the PPZ sequence first, and
  `tests/routes/ppz/p0A.seq.txt` fails its host replay ("Route incomplete:
  milestone=0"). The three campaign scripts replay to their host tally
  (cc1 sequence 14354, warps 3, good_future 1; good 9369; bad 7750). campaign-cc1
  includes warps, so expect the same late-interval failure once the
  checkpoint exists.

## V0.073 R2 regeneration (2026-10-04)

Shared physics changed again (Object Solid.asm floor sensors and push bits,
ObjSonic_LevelBound boss limit, SlopeResistRoll asr). All 15 scripts failed the
host replay and were re-searched with the commands above. Seed 15 now loses
26 rings (needs 30); seeds 16, 18, 19, 21 also fall short; seed 17 passes
(qa-loop and the table use 17). Saturn: cc2 act 1/2, cc3, generator (9476
positions, 2 warps, zero late intervals), seed 17 ring loss: PASS.

## TT parity branch refresh (2026-10-05)

Current BIN `60475c30…da24f40adb6`: renewed cc1A (seed 41), cc2A (seed 41), cc2D (seed 41), campaign-cc1 (seed 23), campaign-bad (seed 41), and generator (seed 7) after the TT slot-order changes. CC1 and CC2 A–D and generator pass their Saturn controller gates with zero respawns and late intervals. Seed 17 now loses only 27 rings. Seed 25 loses 39 in one update; `test_cc2_route.py --act 2 --era C --seed 25 --require-ring-loss 30` passes 7,612 matched positions with zero respawns and late intervals.
