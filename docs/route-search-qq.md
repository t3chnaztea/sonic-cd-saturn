# Quartz Quadrant route search (V0.073 regeneration)

Why: commit 6ad1372 (grounded spawn, objects lead update, monitor width,
rolling-on-monitor, air right wall, spring top, object load window) changed
player/object physics. Routes searched on the old physics no longer replay.

## Inputs the QA loop consumes outside tests/routes/{ppz,cc,tt}

`tools/qa-loop.py` (fast and full) reads no tracked route file outside
`tests/routes/{ppz,cc,tt}`. `tests/routes/qq/` held only `.gitkeep`.
Non-PPZ/CC/TT input generators in the loop:

| Consumer | Input | Physics-dependent |
| --- | --- | --- |
| `test-qq-cache-replay.sh`, `test-ww/ss/mm-cache-replay.sh` | Synthetic camera routes (8 px/frame), generated inline | No (camera only) |
| `test_qq_switch_margin.py`, `test_sequence_replay.py` | Fixture logs | No |
| `test-zones-emulator.sh` zones 3-6 | Hard-coded level-select entry in `emulator_test.c` | Yes (object spawns) |
| `test-special-*-emulator.sh`, `test-bigring-emulator.sh` | `special_route.py` / `special_retail.py` pads | Special stage: no (`special_player.c` unchanged) |
| `test-title-emulator.sh` | `title_retail.py` pads | No |

The Quartz Quadrant controller routes are candidate gates (QUARTZ-QUADRANT-PLAN.md),
run outside the loop by `tools/test_qq_route.py` and `tools/test_qq_travel.py`.

## Original searches (reconstructed)

Source: `build/qq{1,2,3}/controller/*/report.json` (`script_source: search`,
seed 51, V0.066 disc `24596e21...`), `build/overnight-20260930/travel-{17..20}/run.json`.

```
python3 tools/test_qq_route.py --act 1
python3 tools/test_qq_route.py --act 2 --era A --era C --require-r5-dispatch
python3 tools/test_qq_route.py --act 2 --era B --era D
python3 tools/test_qq_route.py --act 3
python3 tools/test_qq_travel.py --output <dir> [--script build/overnight-20260930/qq-travel-01/script.txt]
python3 tools/test_qq_travel.py --era B --output <dir>
python3 tools/test_qq_travel.py --act 2 --output <dir>
python3 tools/test_qq_travel.py --act 2 --era B --output <dir>
```

Defaults: `test_qq_route.py` seed 51, 200000 iterations, tail 300;
`test_qq_travel.py` seed 51, 100000 iterations. Gates are unchanged.

## Tool options added (defaults unchanged)

- `test_qq_route.py`: `--cue`, `--elf` (replay a frozen image), `--out` (report root).
- `test_qq_travel.py`: `--cue`, `--elf`; it also resolves the LTO-renamed
  `_bg_slave_ready.lto_priv.N` symbol (the V0.073 ELF has no plain `_bg_slave_ready`).

## V0.073 regeneration commands

The host search compiles `src/` from the working tree. Other sessions had
uncommitted `src/objects_tt_*.inc` edits, so the host must build from a
pristine HEAD snapshot to match the frozen image:

```
H=<scratch>/head
git archive HEAD src tools | tar -x -C $H   # plus generated src/*_tables.inc, *_palette.inc
cp tools/test_qq_route.py tools/test_qq_travel.py $H/tools/
# $H/assets/generated: copy; assets/private, .deps, .toolchain, build/probe-source: symlinks
cd $H; export SCD_QQ_ROUTES=""   # always search
F=<frozen v073wip dir>; C="--cue $F/sonic-cd-saturn-prototype.cue --elf $F/sonic-cd-saturn-prototype.elf"
python3 tools/test_qq_route.py --act 1 --era <A|B|C|D> $C --save-route --out <dir>
python3 tools/test_qq_route.py --act 2 --era <A|C> --require-r5-dispatch $C --save-route --out <dir>
python3 tools/test_qq_route.py --act 2 --era <B|D> $C --save-route --out <dir>
python3 tools/test_qq_route.py --act 3 --era <C|D> $C --save-route --out <dir>
python3 tools/test_qq_travel.py [--act 2] [--era B] [--script <old>] $C --output <dir>
```

One era per process gives the same search as the grouped command (seed and
iterations are per era). `--save-route` writes `tests/routes/qq/qq<act><era>.txt`
only after the Saturn replay passes; copy it from `$H` to the repo.

## Results (frozen BIN f4ac2b0c...4d4a)

Evidence: `build/qq-route-v073/{new,travel}/` (reports carry input hashes).
Host compiled from the pristine HEAD 6ad1372 tree; Saturn replay on the frozen image.

Old V0.066 scripts, host replay on HEAD: all 10 act routes desync (QQ1 A-D,
QQ2 B, QQ3 D "Route incomplete"; QQ2 A/C/D and QQ3 C die). Travel QQ1 A/B
still replay; travel QQ2 A/B desync.

| Route | Command (plus `$C --save-route --out`) | Result |
| --- | --- | --- |
| qq1A-D | `--act 1 --era E` (seed 51) | PASS: 7250 / 8985 / 8769 / 8126 positions, 0 respawns, 0 late |
| qq2C | `--act 2 --era C --require-r5-dispatch` | PASS: 8347 positions |
| qq2D | `--act 2 --era D` | PASS: 8200 positions |
| qq3C, qq3D | `--act 3 --era E` | PASS: 6948 / 7617 positions |
| qq2A | seed 51: host passes; Saturn fails `lost R5 change/hold/redraw` [4 changes, 4 holds, 3 redraws; last change at tick 9440, the update before the handoff] | Re-searched `--seed 52`: PASS, 6615 positions, 2/2/2 change/hold/redraw. Saved route is seed 52. |
| qq2B | `--act 2 --era B` (seed 51) | FAIL on Saturn: `CC pad mismatch: sequence=1 actual=64,364 expected=64,364`. Not saved. |
| travel 1A, 1B (old scripts) | `--script <old>` | PASS: arrival era 3 / era 0, 300 slave-ready updates |
| travel 2A | `--act 2` (re-searched) | PASS: arrival era 1 |
| travel 2B | `--act 2 --era B` (re-searched) | FAIL: same `sequence=1` mismatch as qq2B |

Zones level-select entry (`test-zones-emulator.sh` command, frozen image),
zones 3-6: all loaded (QQ 42 objects, WW 21, SS 55, MM 12). Cache replays,
fixture tests, special-stage and title pads were not rerun: 6ad1372 does not
touch the code they drive.

## Open problems

1. QQ2 era B start (suspected regression, not a route problem). On the frozen
   image the harness sees gameplay sequence 1 at the first `SCD2` frame;
   V0.066 first showed sequence 2 (`build/qq2/controller/B/results.log`).
   Two independent routes fail before any pad input is used. Candidate cause:
   the new level-start objects lead update (`scd_player_objects_lead`) making
   update 1 visible on the slower era-B load. Needs a src or harness decision.
2. QQ2 A seed 51: an enkeichg on the last update before the act handoff is held
   but never redrawn. The check is unchanged; seed 52 avoids the edge. Decide
   whether a held change at act exit should count as lost.
3. Working-tree `src/objects_tt_*.inc` edits change QQ host searches (QQ2 C
   gave 7529 positions dirty, 8347 pristine). Any route search must use a
   tree that matches the image under test.

## V0.073 R2 regeneration (2026-10-04)

All ten act routes re-searched on the working tree with
`SCD_QQ_ROUTES="" python3 tools/test_qq_route.py --act N --era X [--require-r5-dispatch] --save-route`
(seed 51) and passed on the R2 image, including QQ2 B (the sequence=1 start
failure is fixed: the level-start object lead update now runs during loading,
src/main.c load_era). Travel routes not rerun.

## TT parity branch refresh (2026-10-05)

On BIN `ea91e968…035726`, renewed QQ1 B/C, QQ2 D, and QQ3 C/D with seed 51 and the same search/tally gates. QQ1 A–D, QQ2 A–D (including A/C R5 redraw dispatch), and QQ3 C/D pass on Saturn with zero respawns and late intervals.

## Tail re-search for retail parity (V0.075)

Use when the native host matches retail up to where a stored route dies or
stalls. Only the tail is searched; the matched prefix stays pad-identical.

1. Measure: `python3 tools/test_qq_route.py --act N --era E --host-only`.
   Read `build/qqN/controller/E/report.json`: `retail_parity.first_divergence`
   (parity sequence) and `host.log` (host sequence of the death or "Route
   incomplete"). Host sequence ~= pad index; parity sequence = host sequence +
   (`held_unlock` - `unlock`).
2. Pick KEEP = (earlier of the death and the first divergence, as a host
   sequence) - 100..150 pads.
3. `python3 tools/route_tail_search.py build/qqN/controller/qq_route_search
   <N-1>:E tests/routes/qq/qqNE.txt KEEP <scratch>/tailNE.txt` (seed 51,
   200000 iterations; the tool checks that the first KEEP pads are unchanged).
   Copy the host binary first when several searches run at once.
   Add `--aligned QQ_ROUTE_UNLOCK_AT:<held_unlock>:<held_unlock - unlock>` so
   the tail is searched under the retail-aligned timing tools/retail_parity.py
   replays (the lead neutral pads are stripped from the output).
4. Copy the result to `tests/routes/qq/qqNE.txt` (search output, never edited)
   and rerun `python3 tools/zone-gates.py --zones qq --gates retail`. A window
   passes only when the route finishes the tally on the host and under the
   aligned replay (`retail_parity.native_end` reads "Tally complete"), retail
   has no death or restart inside the window, and contiguous == compared.
5. The QQ search leads a Down + jump pad with two Down pads: native buffers a
   standstill Down + jump into a spin dash; retail needs a crouch first.
