# Scroll IR, version `scroll-ir/1`

One JSON document describes one retail `scroll()` routine
(`build/audit/source/src/R<n>/SCR<n><act><era>.C`) as data. A single generic
evaluator (`evaluate.c`) turns any document into the two numbers the port asks
for: the background X of a background line (`scd_background_raster_x`) and the
background Y for a camera Y (`scd_background_y`). Nothing in the evaluator or
the IR is specific to a zone, act, era or program.

Tools in this directory:

| file | role |
|---|---|
| `extract.py` | retail C -> IR JSON (symbolic interpretation, see "How extract.py derives it") |
| `irc.py` | validates IR JSON against this document; emits C tables and the 84-slot table |
| `evaluate.h`, `evaluate.c` | the evaluator; the C semantics below are normative |
| `gate.c`, `run_gate.sh`, `patch_port.py` | compares the evaluator with the real `src/background.c` |
| `census.py` | the 68 programs, their 48 shapes, their features and extractor status |
| `cparse.py`, `sym.py`, `interp.py`, `cfront.py` | C parser, exact symbolic integers, interpreter, shape key |
| `ir/R1/*.json` | the ten Palmtree Panic documents |

## 1. What a scroll() routine is

Every frame the routine:

1. advances three layer positions, `scrz_h_posit`, `scrc_h_posit`,
   `scrb_h_posit` (32-bit 16.16), by an amount proportional to the camera X
   delta `scra_hz` (8.8), and in one program also to the player X speed;
2. advances a set of 32-bit accumulators (`linework[]` or the first words of
   `hscrollwork[]`) by constants: the drifting cloud bands;
3. writes a table `hscrollwork[base..]` of 16-bit words, one word per 8
   background lines, each word `-(background X)` of its row;
4. sets the background Y (`scrb_v_posit.w.h`), either accumulating a rate of
   the camera Y delta or assigning a function of camera Y;
5. renders 224+ screen lines into `lphscrollbuff`: line `i` of the screen shows
   background line `bgY + i`, which reads table row `((bgY + i) & mask) / 8`,
   except where the renderer instead steps a 16.16 accumulator line by line
   (a ramp toward the camera).

The IR is that routine reduced to: a buffer height, the table as ordered runs,
bands that override runs, and a background Y rule.

## 2. Document

```json
{
 "ir": "scroll-ir/1",
 "program": "R1/SCR12A.C",
 "shape": "75499d2c",
 "slot": {"round": 1, "act": 2, "era": "A"},
 "buffer_lines": 512,
 "layers": {"scrc_h_posit": {"C": 48, "U": 0}, "scrz_h_posit": {"C": 32, "U": 0}},
 "ramp_gate": null,
 "runs": [
  {"entries": 4, "expr": {"op": "cloud", "layer": "scrz_h_posit", "speed": 65536}},
  {"entries": 4, "expr": {"op": "cloud", "layer": "scrz_h_posit", "speed": 49152}},
  {"entries": 4, "expr": {"op": "cloud", "layer": "scrz_h_posit", "speed": 32768}},
  {"entries": 20, "expr": {"op": "layer", "layer": "scrz_h_posit"}},
  {"entries": 4, "expr": {"op": "layer", "layer": "scrc_h_posit"}}
 ],
 "table_end": 288,
 "beyond_table": "unwritten",
 "bands": [
  {"start": 288, "lines": 224, "tail": true,
   "expr": {"op": "ramp", "from": "scrc_h_posit", "to": "camera", "D": 256, "diff_bits": 16, "step_bits": 16}}
 ],
 "bg_y": {"op": "rate", "C": 48},
 "corrections": [],
 "rules": {"WINDOW_windows": 37, "TAIL": 1, "SEED": 0, "overridden_lines": [], "vertical_run_stopped": "..."}
}
```

| key | meaning |
|---|---|
| `ir` | always `"scroll-ir/1"` |
| `program` | `R<n>/SCR<n><act><era>.C`; `slot` must agree with it |
| `shape` | md5-8 shape key of the scroll() body (`cfront.shape_key`; informational) |
| `buffer_lines` | background lines before the table index wraps. The render indexes the table with `bgY & M`; `buffer_lines = M + 8` (`& 504` -> 512, `& 1016` -> 1024, `& 2040` -> 2048). Power of two, 8..2048 |
| `layers` | every layer an expression names, `{C, U}` (section 3). `camera` is implicit and never listed |
| `ramp_gate` | required when any `U != 0`: the retail condition under which the player speed accumulates (text; the port's `scd_background_step` implements it) |
| `runs` | the table from background line 0 down, in order. `entries` table words, each 8 lines. Adjacent runs never have equal expressions (merge them) |
| `table_end` | `8 * sum(entries)`: first line the routine never writes |
| `beyond_table` | always `"unwritten"`: lines from `table_end` to `buffer_lines`, where no band applies, evaluate to 0 (section 4) |
| `bands` | line ranges that override runs, each `{start, lines, expr[, tail]}`; non-overlapping, inside the buffer. `tail: true` marks rule TAIL |
| `bg_y` | the background Y rule (section 5) |
| `corrections` | every place the IR departs from a literal reading of the C, with the rule that justifies it (section 7) |
| `rules` | counts of the stated derivation rules that fired (section 7); informational |

`irc.py` enforces all of the above and rejects unknown keys and unknown ops.

## 3. Values and layers

Inputs to the evaluator: camera X `x` (pixels), background line `y`, frame
count `f` (scroll() calls since the accumulators were cleared), and `ramp` (the
gated sum of the player X speed in 8.8, `scd_background_scroll.ramp` in the
port).

A layer `{C, U}` is a position that advances by `C * scra_hz + U * (xspeed << 8)`
per frame in 16.16. `scra_hz` is the camera delta shifted left by 8, so after
the camera has moved `x` pixels from 0 and the gated speed has summed to
`ramp`, the layer's pixel position is

    layer(L) = floor((C*x + U*ramp) / 256)

`camera` is the layer `{256, 0}`: `layer(camera) = x`.

**Values.** Retail holds every position and table word in 16 bits and the
hardware uses the low 9 bits. The IR's arithmetic is exact integer arithmetic
on the formulas below, not reduced to 16 bits, which is what the port's
functions return. The two agree modulo 65536 by construction.

`C` is read from the argument of the position helper (`scrollz_h(scra_hz << 5)`
gives 32; `(scra_hz << 4) * 3` gives 48). `U` is the coefficient of the player
speed term in the same argument (only R1/SCR11A has one: z 1, c 2, b 1).

## 4. Expression vocabulary (closed)

| op | fields | background X |
|---|---|---|
| `zero` | | `0` |
| `layer` | `layer` | `layer(L)` |
| `cloud` | `layer`, `speed` | `layer(L) + (((uint32)(f * speed)) >> 16)` |
| `ramp` | `from`, `to`, `D`, `diff_bits`, `step_bits` | see below; bands only |

`cloud`: the accumulator is a 32-bit word advanced by `speed` once per frame
from 0; the routine adds its high half. `layer` may not be `camera`.

`ramp` (the renderer's 16.16 accumulator, seeded with `from` and stepped once
per line), for the line `k = y - band.start`:

    B = layer(from);  T = layer(to)
    d = T - B;                     if diff_bits == 16: d = (int16)d
    q = (256 * d) / D;             C division, toward zero
                                   if step_bits == 16: q = (int16)q
    value = B + floor(k * q / 256)

`diff_bits`/`step_bits` record where the routine narrows to 16 bits
(`(short)(scra - scrb)`, a quotient stored through `.w.l`). They change nothing
until `|T - B|` passes 32767 or `|q|` does. The floor is the accumulator's: its
integer half is the high word of `65536*B + k*256*q`, which rounds down for
negative steps. (The port's C division rounds toward zero there; that is one of
the two port differences the gate reports.)

Line lookup, normative (evaluate.c):

    line = y & (buffer_lines - 1)
    if line is inside a band:            band expr with k = line - start
    else if line < table_end:            expr of the run covering line (k unused)
    else:                                0          ("unwritten")

"Unwritten" is not a retail value: retail leaves whatever `hscrollwork` held.
0 is the stated convention (BSS starts zeroed; the port also returns 0).

## 5. Background Y

| op | fields | background Y |
|---|---|---|
| `rate` | `C` | `floor(C * camera_y / 256)`: the routine adds `C * scra_vz` to `scrb_v_posit` each frame (`scrollb_hv(.., (scra_vz << 4) * 2)` gives 32 = y/8) |
| `camera` | optional `fold {player_x_min, y_min, div}` | `camera_y`; with a fold, when `(uint16)player_x >= player_x_min` and `(uint16)camera_y >= y_min`: `(camera_y - y_min)/div + y_min` (C division) |

## 6. Emitting IR by hand from a routine you are reading

1. Find the index mask in the render (`scrb_v_posit.w.h & M`): `buffer_lines = M + 8`.
2. Find the table base: the `hscrollwork` word the render reads for background
   line 0 (`&hscrollwork[row] + 8` means base 8). Accumulators live below it.
3. Walk the table writes in execution order from the base. Loops run as
   written: a descending loop `for (i = N-1; i >= 0; --i)` that reads a count
   table `cnt[i]` while a pointer walks the accumulators forward pairs
   accumulator k with `cnt[N-1-k]`; `for (j = cnt; j >= 0; --j)` writes
   `cnt + 1` words. Each word is `-(layer)` or `-(accumulator high half +
   layer)`: emit `layer` or `cloud` with the accumulator's per-frame add as
   `speed`. Merge equal neighbours into one run.
4. A render loop that seeds a 16.16 accumulator and adds
   `(scra - scrX) * 256 / D * 256` per line is a `ramp` from `scrX` to
   `camera` with that `D`. If it starts where the table ends it is a tail band
   (`start = table_end`, `lines = buffer_lines - table_end`, `tail: true`); if
   a table of `(start, length)` pairs places it, emit one band per pair.
5. Background Y: `scrollb_hv(h, (scra_vz << a) * b)` is `rate` with
   `C = b << a`; `scrollb_v(scra_v_posit.w.h)` is `camera`, plus a fold if the
   routine folds it.
6. Run `python3 tools/scroll/irc.py your.json`. Better: run `extract.py` on the
   file; if it fails, its message names the first construct outside this
   vocabulary.

Anything that does not fit is a new op (section 9), never an approximation.

## 7. How extract.py derives it, and its stated rules

`interp.py` executes the routine exactly as written (loops, pointer walks,
union views, helper calls) with symbolic inputs: camera X `X`, delta `HZ`,
player speed `XS`, and memory as it was before the call. An `if` on a symbolic
value runs both arms and merges them into selections; a loop, pointer or return
that depends on a symbol stops the run (`SymbolicControl`). The camera tracking
functions `scrchk`, `scroll_h`, `scroll_v` are not run: the camera is the input.
A routine that tracked the camera under another name would reach the model as a
selection over player state and fail, never pass.

The routine runs once per render window (a concrete background Y). Each output
line is either a copy of a table word (the load is tracked to its cell) or the
high word of a linear 16.16 value that the render steps line by line. Every
mapped expression is re-verified: accumulators by evaluating the routine's term
against the high word of `f*speed` for eleven frame counts; ramps by comparing
the routine's step with the IR formula at 400 random layer values; the
background Y by comparing at every camera Y 0..4095 for nine player X values
and against six fully concrete runs.

Stated rules; each fires as counted, on R1:

| rule | statement | fires on (of the 10 R1 programs) |
|---|---|---|
| WINDOW | line `y` is read from the window whose top is `max(0, (y - 216) & ~7)`, the highest window that still shows `y` on a 224-line screen, so the render reaches `y` walking down from above, as in play | all 10 (37 windows each for 512-line buffers, 229 for SCR11A) |
| TAIL | a band that begins exactly at `table_end` runs to `buffer_lines`. Retail shows at most 224 lines of it; lines the chosen windows show differently are listed in `rules.overridden_lines` | 4: SCR11C (232..511 overridden), SCR12A (none), SCR12C and SCR13C (480..511) |
| SEED | a band's first line is the layer its step subtracts (`step = (T - L)*256/D`, first line `L`); when the routine seeds the accumulator from something else the IR takes `L` and records the literal seed in `corrections` | 1: SCR11C |

SEED, in full: SCR11C.C:377-383 seeds the water ramp with `lD3.w.h = wD0`,
the table word of the last drawn row (`-scrc`), and writes `-(unsigned
short)lD3.w.h`, so the literal C starts the water at `-scrc` and jumps 2*scrc
at line 224. SCR12A, SCR12C and SCR13C seed with `scrc_h_posit` directly, and
the Mega CD disassembly of the same routine
(`.deps/scddisasm/src/Level/Palmtree Panic/Scroll (Act 1 Good Future).asm`,
`.ScrollWater`) seeds with `cameraBg2X` (`move.w d0,d3` after
`move.w cameraBg2X.w,d0`). The decompiler dropped the reload. SCR11C's render
loop count is garbled the same way (`wD3 = (wD0 < 2) ^ 1` where the 68k has
`sub.w d3,d1; bcs`), which is what TAIL overrides for lines 232..511.

Mutation check (copies of the retail files in a scratch directory, never the
tree): SCR12D `z12d_cnttbl {0,4,3,3}` -> `{1,4,3,2}` moved the cloud runs from
4,4,5,1 to 3,4,5,2 entries (the descending loop read in reverse); SCR11A band
length 224 -> 160, divisor 224 -> 200 and fold 480 -> 400 all moved in the IR;
SCR11C `* 256 / 256 * 256` -> `/ 128` gave `D: 128`. Changing only the fold's
comparison (400) but not its offset (480) failed loudly: the fold rule no
longer reproduced the routine.

Acts with no program: act 3 has no Present or Past `scroll()` in any round
(14 of 84 slots), and R4 has no SCR42B/SCR42D file (2 slots, both shipped
stages). `irc.py` marks all 16 as "no program file"; nothing is aliased in the
IR. (The gate compares ids 8 and 9 against act 1 of the same era and says so.)

## 8. Invariants (irc.py)

- keys and ops exactly as in sections 2, 4, 5; every named layer declared and used
- `table_end == 8 * sum(entries) <= buffer_lines`; `buffer_lines` a power of two, 8..2048
- bands sorted non-overlapping inside the buffer; a `tail` band spans `table_end..buffer_lines`
- `ramp` only in bands; `cloud` never on `camera`; `speed` 1..2^31-1; `D > 0`; widths 16 or 32
- a layer with `U != 0` requires `ramp_gate`

## 9. Extending the vocabulary

A routine that needs something new gets a new op, added in the same change to
this file (exact integer semantics), `evaluate.c`, `irc.py`, `extract.py`
(mapping plus a numeric re-check against the routine's own symbolic value) and
`census.py` output, with the count of programs that use it. Never widen an
existing op's meaning, never fit numbers, never branch on a program or round.

The census (`python3 tools/scroll/census.py --extract`) names the first blocker
of each of the 58 programs the extractor does not yet cover. Grouped:

| blocker (first loud failure) | programs | what it needs |
|---|---|---|
| table rows are interpolations `hi(65536*L + m*div(k*(T - L), D))`; SCR61B/SCR62B add a `radwk` (sine) term, R8 rows carry `u16(-X)` in the low half | SCR53C, SCR61B, SCR62B, SCR73C, SCR73D, SCR81A-D, SCR82A-D, SCR83C (and SCR71A's rows, once it gets past the window search) | a row-interpolation op with the exact carry of the 32-bit sum |
| rows chosen by the event flag `enkeino & 1` (two layouts; window 0 line 0 is a selection) | SCR51A-D, SCR52A-D, SCR53D | the flag as an input: one IR per layout, or a selector |
| table index depends on `waterdirec` (a water phase) | SCR31A-D, SCR32A-D, SCR33C/D, SCR41B-D, SCR42A/C, SCR43C/D | the water phase as an input and a sine-table op |
| `sinset()` is defined in another file | SCR61A/C/D, SCR62A/C/D, SCR63C/D | interpret the defining file too (closure over files) |
| background Y `(Y>>2)+(Y>>3)` skips values (128, 512), so no window has those tops | SCR71A-D, SCR72A-D | WINDOW taking the nearest reachable top above the ideal one |
| background Y depends on camera X (`X >= 640 ? 512 : 0`) | SCR41A | a bg_y op with a camera X term |
| background Y is a shifted camera Y (`scrollb_v` of `Y >> k`) | SCR83D | a bg_y op for shifted and summed camera Y (R5 and R7 need it too) |

## 10. The gate

`sh tools/scroll/run_gate.sh` extracts R1, compiles the IR, and links the
evaluator against three builds of the port: `src/background.c` as it is, a copy
with the era 1/2/3 branch wrapping at 512 lines, and a copy that also floors the
era 0 ramps. Grid per id: background Y 0..2047 x camera X {0, 0x400, 0x800,
0x1000, 0x1800, 0x2000, 0x2800, 0x3000, 0x3c00} x 10 frames x 11 ramps
(2,027,520 raster samples) and camera Y 0..4095 x 8 player X (32,768 background
Y samples). Result on this tree: literal 6/12, with wrap 10/12, with wrap and
floor 11/12 (the 10 ids that have a retail program: 6/10, 9/10, 10/10).

- ids 1, 2, 3, 9, literal only: every mismatch is at background line >= 512.
  SCR11B/C/D index with `& 504`; the port's era 1/2/3 branch never wraps.
- ids 0 and 8, literal and wrap: 13,960 mismatches, all at camera X 0 with
  ramp > 0, all inside SCR11A's two ramp bands. There the layer `scrb` (x/2 +
  ramp/256) is ahead of the camera, the step is negative, and the port's
  `(...)*(y-640)/256` rounds toward zero where the retail accumulator rounds
  down. The floor copy removes all of them.
- id 8, every build: 32,760 background Y mismatches. Act 3 Present has no
  program; the gate compares it with SCR11A (camera Y with a fold) and the port
  returns y/8 for it. Nothing in the retail source decides this id.
- Outside the grid (camera X not a multiple of 256, printed as a diagnostic):
  ids 0 and 8 also differ where the port adds `x/2` and `ramp>>8` separately
  and retail floors their sum once (e.g. x=1, ramp=255: port 0, retail 1).
