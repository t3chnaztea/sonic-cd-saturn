# Palmtree Panic route search

How each tracked PPZ pad route in `tests/routes/ppz/` is searched, which gate
replays it, and the V0.073 regeneration record. Never hand-edit a route; search
again with the command below and verify with the listed gate.

Two formats:

- `*.txt`: "COUNT PAD" lines, pad bits 128 Right, 64 Left, 32 Down, 16 Up,
  1 Jump. Host: `tools/cc_campaign_search.c` PPZ modes (`p<act>:<era>`, `pJ0`,
  `pJ1`; `pS`/`pJ` are chained, not searched).
- `natural-*.pads`: one pad per line, bits 8 Right, 4 Left, 2 Down, 1 Up,
  16 Jump, from NEW GAME. Host: `tools/ppz_journey.c` (NEW GAME journey model).

## Hosts

Build from the repo root.

```
# H: tools/cc_campaign_search.c (the gates build the same file as build/ppz_route_host)
clang -std=gnu11 -O2 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
  -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A tools/cc_campaign_search.c \
  src/{title_card,world,act,player,camera_v,sonic_animation,stage,boss,boss_r3,objects}.c \
  build/probe-source/{boss_1,boss_3,playsp3,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/ppz_route_host
# J: journey explorer libraries and the journey search
bash tools/build-ppz-journey.sh          # build/ppz-journey/native.dylib + sanitized
bash tools/build-ppz-journey-search.sh   # build/ppz-journey/search
```

`H search MODE SEED ITERATIONS OUT` is deterministic for one source tree: the
search stops at the first finished route, so a larger ITERATIONS value finds
the same route. Search options are environment variables:

- `PPZ_DIRECT_ENTRY=1`: Act 2 debug entry (no card in the Futures, input masked
  until update 128 C / 117 D). Used by gates that run `tools/run-act2-era-script.sh`
  for eras 2 and 3. Era 0/1 entry is the same with or without it.
- `PPZ_NO_DAMAGE=1`: a hit ends the branch.
- `PPZ_REQUIRE_CHECKPOINT=1`: an Act 1/2 Present tally only counts after a checkpoint.
- `PPZ_RING_LOSS=N`: the tally only counts after one update lost N+ rings
  (added V0.073 for the ring-loss stress route).

## Controller routes (`*.txt`)

Each gate's checker adds constraints the host search does not enforce. The
"filter" column lists them; the V0.073 seed is the first seed that met them.

| Route | Search (V0.073) | Filter | Gate(s) |
|---|---|---|---|
| `p0A.txt` | `H search p0:A 1 100000 OUT` | — | `test_ppz_route.py --act 1`; leg of `pS` |
| `p0A.seq.txt` | `PPZ_REQUIRE_CHECKPOINT=1 PPZ_NO_DAMAGE=1 H search p0:A 1 100000 OUT` | Act 1 score < 50000 | `test-sequence-emulator.sh` (full QA) |
| `p0B.txt` | `H search p0:B 1 100000 OUT` | — | `test_ppz_route.py --act 1` |
| `p0C.txt` | `H search p0:C 1 100000 OUT` | — | `test_ppz_route.py --act 1` |
| `p0D.txt` | `H search p0:D 1 100000 OUT` | — | `test_ppz_route.py --act 1` |
| `p1A.txt` | `PPZ_REQUIRE_CHECKPOINT=1 H search p1:A 1 100000 OUT` | checkpoint > 0 | `test-act2-emulator.sh`, `test-sequence-emulator.sh`, `test_save_progression.py`, `test_ppz_route.py --act 2`; leg of `pS` |
| `p1B.txt` | `PPZ_RING_LOSS=30 H search p1:B 11 100000 OUT` | host tally ≤ 8400 (the `act2` emulator mode stops at frame 9000); R2: seed 10 gave 8505 | `test-past-ring-loss.sh` (full QA), `test_ppz_route.py --act 2` |
| `p1B.nohit.txt` | `PPZ_DIRECT_ENTRY=1 PPZ_NO_DAMAGE=1 H search p1:B 2 100000 OUT` | lives 3, tally ≤ 8400 (R2: seed 1 gave 8976) | `test-act2-era-emulator.sh 1` |
| `p1C.txt` | `H search p1:C 1 100000 OUT` | — | `test_ppz_route.py --act 2` |
| `p1C.era.txt` | `PPZ_DIRECT_ENTRY=1 PPZ_NO_DAMAGE=1 H search p1:C 1 100000 OUT` | lives 3, tally ≤ 8400 | `test-act2-era-emulator.sh 2` |
| `p1D.txt` | `H search p1:D 1 100000 OUT` | — | `test_ppz_route.py --act 2` |
| `p1D.era.txt` | `PPZ_DIRECT_ENTRY=1 H search p1:D 3 100000 OUT` | lives 3, tally ≤ 8400, host and Saturn clocks in one time-bonus tier (R2: seed 2 ended at 1:30) | `test-act2-era-emulator.sh 3` |
| `p2C.txt` | `H search p2:C 5 100000 OUT` | seeds 1–4 stall | `test_ppz_route.py --act 3`; leg of `pJ` |
| `p2D.found.txt` | `H search p2:D 1 100000 OUT` | — | `test-sequence-emulator.sh`, `test_ppz_route.py --act 3`; leg of `pS` |
| `pJ0.txt` | `H search pJ0 1 100000 OUT` | — | leg of `pJ` |
| `pJ1.txt` | `H search pJ1 1 100000 OUT` | — | leg of `pJ` |
| `pS.txt`, `pJ.txt` | `python3 tools/ppz_chain_scripts.py` (then `--check`) | — | chained legs, padded to each host tally |

Check a filter on the host: `H replay MODE OUT 40000 /dev/null` (with the same
environment) prints `Tally complete: sequence=… lives=…`.

## Natural journey routes (`natural-*.pads`)

`J/search GOALS SEED ITERATIONS OUT [PREFIX]` (see the file header for the
goal letters). Later routes extend earlier ones as prefixes, so search in this
order. `c1`, `c2`, `c3` are intermediate prefixes, not tracked.

| Output | Command (V0.073) |
|---|---|
| `natural-act1-return.pads` | `search W1,W0 1 30000 OUT` |
| c1 (Act 1 Past generator, tally) | `search W1,G,T 1 30000 c1.pads` |
| c2 (Act 2 Past arrival) | `search W1,G,T,W1 1 30000 c2.pads c1.pads` |
| `natural-past-return.pads` | `search W1,G,T,W1,W0 1 30000 OUT c2.pads` |
| `natural-present-future.pads` | `search W1,G,T,W1,W0,W3 1 30000 OUT natural-past-return.pads` |
| `natural-future-return.pads` | `search W1,G,T,W1,W0,W3,W0 1 30000 OUT natural-present-future.pads` |
| c3 (Act 2 Past generator) | `search W1,G,T,W1,G 7 30000 c3.pads c2.pads` |
| `natural-good-results.pads` | `search W1,G,T,W1,G,T,R 5 40000 OUT c3.pads` (seeds 1-4 stall at the boss) |
| `natural-special-entry.pads` | `search W1,G,T,W1,G,B 1 30000 OUT c3.pads` |

Verify each (the ledger rows in `PALMTREE-PANIC-PLAN.md`):

```
python3 tools/ppz_journey.py --label <ref> --prefix tests/routes/ppz/<name>.pads --steps <lines> [--until-zone-results]
# natural-special-entry: --steps <lines - 1> (the last pad touches the big ring; states.bin holds pre-entry rows only)
bash tools/test-ppz-journey.sh build/ppz-journey/<ref> build/ppz-journey/<target>
# natural-special-entry: SCD_JOURNEY_SPECIAL=1 (needs build/special-retail/{timeout,win}.pad)
```

## V0.073 regeneration record (2026-10-04)

Sources: commit 6ad1372. Saturn image: frozen V0.073 WIP BIN
`f4ac2b0c…4d4a` (not `dist/`). Results:

Every route below was searched with the command in the tables, replayed on
the host, then replayed on the Saturn emulator against that BIN:

| Gate | Result |
|---|---|
| `test-act2-emulator.sh` (p1A) | Complete Act 2 Present passed: 8767 matched states, score 6900 |
| `test-act2-era-emulator.sh 1` (p1B.nohit) | Act 2 Past passed: 7744 states, score 9500 |
| `test-act2-era-emulator.sh 2` (p1C.era) | Act 2 Good Future passed: 6787 states, score 7100 |
| `test-act2-era-emulator.sh 3` (p1D.era) | Act 2 Bad Future passed: 6966 states, score 8400 |
| `test-sequence-emulator.sh` (p0A.seq, p1A, p2D.found) | Zone sequence passed: scores 7600 / 14500 / 28600, lives 3, entered CC Act 1 |
| `test-past-ring-loss.sh` (p1B) | 7756 exact states; 96 hurt ticks; 53 rings lost in one update; 0 late |
| `test_ppz_route.py --act 1/2/3` | PASS all ten eras, 0 respawns, 0 late intervals |
| `test_save_progression.py` | Save progression and cold-boot persistence passed |
| `ppz_chain_scripts.py --check` | PASS: pS and pJ equal their regenerated legs |
| `test-ppz-journey.sh`, six natural routes | all verified (3840 / 10226 / 12376 / 16042 / 18796 / 19074 states); special: SS1 won, Act 3 Good Future, stone 1, lives 3 |

Open: the five natural routes that share prefix c2 show one late interval
(2 VBlanks) at row 8061, two updates after the Act 2 Past arrival at x~1853.
`check_ppz_journey.py` passes; it is a Saturn pacing fact at that arrival, not
a desync. The V0.067 routes arrived elsewhere and had zero.

Search-tool changes in V0.073: `PPZ_RING_LOSS` in `tools/cc_campaign_search.c`
(no effect unless set); new `tools/ppz_journey_search.c` and
`tools/build-ppz-journey-search.sh`.

## V0.073 R2 regeneration (2026-10-04)

Every controller route and natural journey failed the host replay after the R2
shared fixes; all were re-searched with the commands above (seed changes noted
in the table). Saturn: test_ppz_route acts 1-3, act2/era 1-3 emulators,
sequence, past ring loss (45 rings, 0 late), save progression, chain check,
six natural journeys (0 late intervals; the row-8061 late interval is gone):
PASS.

## TT parity branch refresh (2026-10-05)

On BIN `60475c30…da24f40adb6`, renewed p0A.seq (seed 1), p0B (seed 1), p0D (seed 1), p1A (seed 1), p1B (seed 11), p2C (seed 5), pJ0 (seed 1), and pJ1 (seed 1) with the same filters. Regenerated pS and pJ from those legs. `test_ppz_route.py --act 1|2|3` passed all routes with zero respawns and late intervals. The p1B stress route lost 44 rings in one update.

## PPZ parity round 3 (2026-10-10)

Retail-parity tail searches keep the old route as a byte-identical prefix and
search under retail-aligned timing: the prefix gets `held - unlock` neutral pads
in front, `PPZ_ROUTE_UNLOCK_AT=held` and `PPZ_ROUTE_VINT_AT` as
`tools/retail_parity.py` sets them, then the lead is stripped. A result counts
only if it also finishes on the plain host (`H replay`). `PPZ_WARP_LIMIT=N`
(default off) ends a plain-route branch at N warp ticks: retail lag frames reach
the 230-tick warp while the host is near 190 (150 used; 205 for 2D). The search
macro now crouches one update before Down + jump (retail has no spin-dash buffer).

| Route | Search | Result |
|---|---|---|
| `p0C.txt` | aligned tail, whole old route, seed 1 | 7988/7988, tally (both timings) |
| `p1C.txt` | aligned tail, whole old route, seed 1 | 9123/9123, tally |
| `p1D.txt` | aligned tail, whole old route, seed 1, `PPZ_WARP_LIMIT=205` | 10555/10555, tally |
| `p0A.txt`, `p0D.txt` | aligned tail, seed 1 | 1A 9975 contiguous; 1D 13370/13370, plain host stalls |
| `p0B.txt` | aligned tail before update 1575 | 7429/7429; plain host diverges by update 1000 (no tail fix) |
| `p0A.seq.txt` | plain tail, cut 3200, seed 1, checkpoint + no damage | score 7000; `test-sequence-emulator.sh` passed |
| `p1A.txt` | plain tail, cut 4100, seed 2, checkpoint | tally at update 8577 |

Open: pJ0, pJ1, p1B, p1B.nohit, p1C.era, p1D.era no longer finish on the host;
pS and pJ are not regenerated.

## PPZ parity round 4 (2026-10-11)

Aligned tail searches (`route_tail_search.py --aligned PPZ_ROUTE_UNLOCK_AT:held:held-unlock`,
`PPZ_ROUTE_VINT_AT` as `retail_parity.py` sets it, seed 1) after the round 4
object/boss fixes. KEEP counts script pads; pad i reaches native sequence about
i + 26, so cut a few dozen pads before the divergence. Each result tallies on
the plain host (`H replay`).

| Route | Keep | Result |
|---|---|---|
| `p0A.txt` | 13813 (whole old route) | 1A 15482/15482, tally 15693 |
| `p1A.txt` | 5780 | 2A 9766/9766, tally 9925 (checkpoint kept); act2 emulator cap now 15000 frames |
| `p1B.txt` | 5640 | 2B 13088/13088 after the Anton placement fix, tally 13355 |
| `p2C.txt` | 1360 | 3C 3390/3390 |
| `p2D.found.txt` | 2000 | 3D 3067/3067 (old tail pressed Down + jump from a roll stop) |

## PPZ1 campaign repair (2026-10-12)

After the warp-out merge at `4e4ae49`, `pJ0.txt` reached the Present sign before
its Good Future warp and died at sequence 12935. Kept its first 12000 pads and
searched a new tail with seed 1 and 100000 iterations using
`tools/route_tail_search.py` in mode `pJ0`. The search finished at iteration
6489. Regenerated `pJ.txt` with `tools/ppz_chain_scripts.py`.

On BIN `bac1cfe0f37a`, the earned campaign emulator passed PPZ1 (17373 host
positions, generator 7813), PPZ2 from PPZ1's backup (13494), and PPZ3 from
PPZ2's backup (3533). Each run had zero respawns and zero late intervals. PPZ3
saved Collision Chaos and passed cold Continue. This is emulator evidence;
the SAROO console gate remains open.
