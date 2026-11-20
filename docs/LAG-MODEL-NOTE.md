# Retail lag: what the port does not model

Status 2026-10-24. Diagnosis and fix outline only; nothing here is implemented.

## The retail mechanism

The Sega CD runs one level update per frame when it keeps up. When an update overruns
the frame, V-INT still fires. `vintRoutine` is 0, so `VInt_Lag` runs (scddisasm
`Level/Main.asm:681-766`). These run on every V-INT, lagging or not:

- `levelVIntCounter` +1 (`Main.asm:712`).
- `RunTimeWarp`: `timeWarpTimer` +1 while a warp is armed (`Main.asm:709`, `971-979`).
- `RunBoredTimer` (`Main.asm:708`, `985-996`).
- `UpdateFMQueues` (`Main.asm:705`).
- In Tidal Tempest only, `VInt_Lag` also DMAs the (water) palette and resets the H-INT
  counter (`Main.asm:741-766`).

A lagging update therefore advances these counters by 2 or more. Retail lag is
heaviest exactly where the port's evidence is hardest: a 32-ring spill lags the Sega
CD on 10 of the 11 updates 3243-3253 in CC2C seed 24.

## What the port does

- Saturn: one update per V-BLANK. The route gates require zero late intervals, so every
  per-V-INT counter advances once per update. `level_vint` (`src/objects.c:70`) counts
  updates. `scd_world_step_vblanks` (`src/main.c:2104-2108`) uses Saturn V-BLANKs, which
  equal updates while there is no Saturn lag. This is deliberate: the port must not
  copy Sega CD slowdown.
- Host parity harnesses only: `<PREFIX>_LAG` feeds retail's V-INTs per update and
  `<PREFIX>_VINT_AT` aligns `levelVIntCounter` once at control unlock
  (`tools/retail_parity.py`). TT and QQ feed lag (`lag_sync=True`). CC does not
  (`tools/test_cc2_route.py` `retail_parity`, `lag_sync=False`).
- Not modelled anywhere: where inside a lagging update the extra V-INT lands. An
  object that runs after it in the RunObjects pass reads a counter one higher than an
  object before it. The retail probe samples `levelVIntCounter` only at the end of the
  update, so the host cannot know.

## Where it shows

| Symptom | Retail source | Evidence | Host with lag fed | Saturn |
| --- | --- | --- | --- | --- |
| Lost-ring floor check phase | `(levelVIntCounter + d7) & 3`, `Ring/Main.asm:415`; `RING.C:461` | CC2C seed 24 (`build/lostring/s24-final`): rings match updates 3239-3255; slot 82 bounces at retail row 3257 (counter 219 after a 2-V-INT update); native bounces one update early without the lag feed and misses it with the feed | Still differs (mid-pass V-INT) | Differs after any retail lag |
| Time-warp commit | `timeWarpTimer`, `Main.asm:976` | Harness feeds lag for it; `tests/routes/qq/travel/qq1AD.txt` commits on native 713 in both builds | Matches | Commits later in updates than a lagging retail run |
| TT water sway | per-V-INT water count (`tools/retail_parity.py` `lag_sync`) | TT gates pass with the lag feed | Matches | Differs after retail lag |
| QQ ring parity phase | `levelVIntCounter` phase | `QUARTZ-QUADRANT-PLAN.md`: ring parity needs phase 157:230; the harness keeps 229 (`vint_offset=1`) | Position parity passes at both | n/a |
| Idle (bored) animation start | `boredTimer`, `Main.asm:988` | Not measured | Not fed | Starts later in updates after retail lag |
| QQ1A update 601 "era sign" | listed as retail lag in `RELEASE-NOTES-V0.078.md:69` | Not reproduced on 2026-10-24: the QQ1A level-select window (time posts never change state; host and retail slots identical over updates 560-660), `qq1AD` travel (all 712 updates match), `qq1AB` travel (matches to 1858, the script's final pad) | n/a | Unknown; no route reproduces it |

## Outline of a fix (not implemented)

1. Policy first. Retail lag is slowdown, and the goal says to play better than the
   original. Recommend keeping the Saturn lag-free and treating these as accepted
   differences in the release notes. Model lag only in host parity, to separate lag
   from real logic defects.
2. Exact host model. Extend `tools/retail_probe.py` to record, for each lagging update,
   the RunObjects slot that was running when the extra V-INT fired. One option is a
   breakpoint on `VInterrupt` that reads `d7` or the current object pointer. Feed it as
   a third column of `<PREFIX>_LAG`. In the host, `scd_objects_vint_add` then runs at
   that slot inside the object pass, not after `step()`.
3. Turn on `lag_sync` for CC lost-ring evidence (`test_cc2_route.py`). Sonic-position
   parity does not need it, because Sonic runs in slot 0 before any mid-pass V-INT.
4. Gate it with a lost-ring object diff (`build/lostring/objdiff.py`) over whole
   windows that cover a hurt: CC2C seeds 24 and 28, the PPZ Past ring-loss route, QQ2A.
   Success means all lost-ring positions match from the spill to the last ring.
5. Optional, for the Saturn: an opt-in "retail pacing" mode that adds the predicted lag
   V-INTs to `level_vint` and `timeWarpTimer`. This needs a Sega CD cost model, so it
   is not exact. Leave it unbuilt unless hardware testers ask for retail timing.
