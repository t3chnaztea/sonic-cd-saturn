# PERFORMANCE history

Moved verbatim from `PERFORMANCE.md` on 2026-10-03. The subsection "Keep the
controller path identical when comparing performance" and "Still open" remain
in [PERFORMANCE.md](../../PERFORMANCE.md).

## V0.076 — frame headroom over the 40 Saturn routes

Purpose: real hardware may run slower than Beetle Saturn, so measure how close
each route comes to a missed refresh. Emulator data only; no hardware claim.

Method: `SCD_FRAME_PROFILE` 1, the 40 route tools with `--no-retail` and
`FRAME_PROFILE_ALL=1`, then `python3 tools/frame_headroom.py`. Cost is the nine
FRT phases (CPU/8 ticks) from the wake after VBlank-out to the end of
`sprite_draw`. Slack is measured: profile word 23's high half holds the FRT
from an update's end to the next VBlank-in, where libyaul commits `vdp2_sync`
and the DMA queue. The deadline (cost + slack) is 47,740-47,744 ticks on every
route. The 320-pixel mode runs the CPU at 26.85 MHz, so a whole refresh is
55,987 ticks, not 59.7k. "Over 90%" means slack under 10% of the deadline
(cost above about 42,970).

Before (V0.075 RC 2c64135 plus tooling) and after (b1ac7dc). Worst five shown.
All other routes: worst cost 30.1k-42.6k after, min slack 4.2k or more, at
most one update over 90%.

| Route | Worst before | Worst after | p99 after | Min slack after | Updates >90% before/after | Phase at worst |
|---|---|---|---|---|---|---|
| TT3C | 46,709 | 43,832 | 43,078 | 3,912 | 475 / 354 | sprites 26.7k (VDP1 wait 13.9k) |
| TT3D | 46,663 | 43,803 | 42,944 | 3,940 | 475 / 68 | sprites 20.1k |
| PPZ2B | 45,099 | 44,471 | 35,707 | 3,273 | 3 / 2 | update 20.9k |
| CC2C | 45,407 | 44,261 | 31,456 | 3,481 | 1 / 1 | update 29.8k |
| PPZ1C | 44,628 | 43,493 | 36,338 | 4,251 | 2 / 1 | update 21.3k |

TT3 C/D is the only sustained hotspot: the Act 3 capsule's 80-flower shower
holds about 43k ticks for 580 updates until the results hand-off. The others are
single-update spikes in object update. Per-window JSON:
`build/headroom/{slack-table,after}.json` (local, not in git).

Fixes, all bit-exact (player traces, 40/40 routes 0 late, retail 40/40):

- `placement_hash` in `src/objects.c`: the object hash's 631-entry placement
  loops skip zero words. A zero byte only multiplies by the FNV prime, so a run
  of k zeros multiplies by prime^k. 200,000 random states hash identically.
  About 1,500 ticks per update on every route.
- `view_class` table: `scd_objects_views` reads `tt_view_type`, `tp_type` and
  the frame-from-slot chain once per zone, not per actor. TT3 view list 5,571 ->
  4,519.
- `zone_art_part_get` in `src/zone_object_view.inc`: zone art part fields are
  decoded once per art load. Before, every flower re-read the byte records from
  low work RAM. TT3 sprite build 12,335 -> 11,664.

Two attempts on `scd_boss_hash` (about 2,100 ticks in Act 3) failed and were
reverted. Skipping all-zero slots cost 500 more ticks, because freed boss slots
keep stale data. Constant-shift byte extraction saved only 115 ticks.

TT3 capsule shower follow-up (e4c5be5):

- VDP1 load per update: 74 commands and 72,960 texture pixels (67,920 on
  screen), with a 13.9k-tick draw wait. That is about 0.19 ticks per pixel, so
  each 1,152-pixel flower costs about 220 ticks.
- 37 flowers are drawn. The others are already culled off screen.
- The flower art is already tight: the opaque bounding box equals the texture.
  Nothing can be trimmed or merged without changing pixels.
- A cheaper colour mode (colour bank instead of CLUT) would change how VDP2
  resolves colours, so it was not tried.
- The fix overlaps CPU work with the draw instead. Tidal Tempest's background
  line table and row cache (about 3.1k ticks) now run inside the VDP1 wait.
- Result: worst 43,832 -> 40,752, min slack 3,912 -> 6,987 (14.6%), updates
  over 90% 354 -> 0 (TT3C) and 68 -> 0 (TT3D).

Water split jitter: after e4c5be5, a per-frame video hash compare
(`ROUTE_FRAME_HASHES=1`) matched the whole TT3 C/D routes. TT1 and TT2 routes
still differed in 1-13 pictures, and b1ac7dc had moved them the same way.

Fixed in c45d25d. The causes were measured with `WATER_MAILBOX` and VCNT,
latched by an EXTEN read:

- The timer arms in VBLANK every frame, and the handler enters on the right
  line. The register write, though, could land after the HBLANK, which split
  the water row. The timer now fires one line early, and the handler waits for
  the HBLANK of the line above the water before it switches.
- The 13-row band at TT1A's act start was the back screen colour. libyaul writes
  that VRAM word at once, so it changed mid-frame. It is now written after
  `sync_frame`, in VBLANK.

TT1A, TT1C and TT2A now match frame for frame across three CPU loads, one of
them with a 4,000-7,000 tick busy loop per update.

## V0.057 — ring-loss scatter no longer overruns a refresh

The V0.057 title-card clock shifts the first accepted input from update 129 to
131. Every synthetic controller route is closed-loop, so Act 1 Present now takes
a different path: 3,861 updates, score 6,200, against V0.056's 8,061 and 2,800.
That new path is the first measured route on which Sonic is hit while carrying
twenty rings. `tools/test-act-emulator.sh` and `tools/test-sequence-emulator.sh`
both reported one late interval at simulation update 1,238 (x 4,559.6, y 514.6,
68 active objects). `check_sequence.py` requires zero, so the target suite
stopped there. This was a real frame overrun, not a harness artifact: two
independent emulator runs placed it at the same update.

Diagnosis used the `src/frame_profile.h` probes with the recorded pad trace, so
the instrumented build reproduced the identical 3,861 gameplay states. Update
1,237 spawns twenty scattered ring objects, taking active objects from 47 to 68.
Its frame measured 51,129 CPU/8 ticks against a measured budget of about 49,136
work-plus-idle ticks per refresh; every other frame on the route stayed at or
below 41,682. Temporary probes inside `scd_objects_hurt` attributed the spike:
`playdamagechk` 26 ticks, `soundset` 54, and the scatter loop 5,058.

Two causes, both fixed at the source:

- Upstream declares its lookup tables inside the functions that read them. At
  `-Os` the compiler copies each initializer onto the stack on every call, so
  `sinset` rebuilt 640 bytes per call and `atan_sonic` 257. The generators now
  give them static storage (`tools/prepare_player.py`, `tools/prepare_boss.py`:
  `sintable`, `atantbl`, `chk11tbl`, `egg1acttbl`, `bom_tbl`). Every use is a
  read, so behavior is unchanged. This helps every frame, not only this one:
  the scatter loop fell to 2,617 ticks and mean measured work fell by 383.
- `supported()` in `src/objects.c` compared the type against roughly forty
  values on every spawn, and the body then ran a second type chain that has no
  ring case. It is now a byte table indexed by type, and a ring returns before
  that chain. `tools/test_objects.py::test_supported_type_table` checks the
  table membership against the original list.

The ring-loss frame now measures 47,318 ticks with 2,901 ticks of idle left, and
the route records zero late intervals. Mean measured work over the route is
29,952 ticks, from 30,324. Instrumented logs, with the pre-fix pad trace that
pins the route: `build/v057-ringloss-evidence/`. Those are diagnostic builds and
are not candidate images.

`tools/check_act.py` now fails on a late interval, as `check_sequence.py`
always has. The standalone Act 1 gate had the same "Act pacing:" line in its log
and never read it, so this overrun passed there before the sequence gate caught
it. Confirmed against the pre-fix outputs: the tightened gate rejects them.

All eleven target gates pass on BIN
`064ef17c4ec6905c66f9d1ea33e923c93e691de5d2589fddc4875d12ffb4f2db`, with
sequence intervals 3,860/5,188/2,861 and standalone Act 1 3,860, all zero late.
All 34 fast host gates pass (`build/qa-loops/20260920-163735-152573/report.json`).
Reports: `dist/act-report.json`, `dist/sequence-report.json`,
`build/v057-target-qa.log`.

The Past ring-loss stress route now covers this code path again on V0.057.
Its V0.044 reference fed its first input at update 129, which the new card
masks, so the replay aborted there. `tools/shift_act_reference.py` rebuilds the
input with two held updates at the act entry, the same correction
`build/title-card-clock/v057-route-input` applied to the journey route, and a
new `SCD_ACT_PAD_RECORD` mode in `tools/emulator_test.c` re-records the states.
That mode prints its own banner and compares nothing; the strict gate was then
run against its output and reproduced all 5,208 states exactly. Damage is
unchanged from V0.044: 89 hurt ticks, score 5,100, bonus 5,000, three lives, no
ramp and no checkpoint. Zero late intervals with 87 peak active objects, more
than the Act 1 route's 68. Evidence: `build/act2-past-stress-v057-02/report.json`,
reference and recipe in `build/act2-past-stress-v057-reference/`.

That rerun exposed a host/target act-clock difference. `tools/act_test.c` starts
the title card only for Present or Act 3, so on a non-Present Act 2 debug entry
the host clock runs the 130 ticks the Saturn now holds: host elapsed 4,530,
target 4,400. The sixteen compared state words do not include the act timer, so
all 5,208 states still match. The Saturn is the internally consistent side: its
end-of-act HUD matches 1,764 original pixels against 4,400 and fails against
4,530. Whether that debug entry should run the card at all is the open item in
`TITLE-CARD-CLOCK.md`. `check_past_ring_loss.py` now asserts the 130-tick gap so
it cannot drift unnoticed.

Headroom on that update is about 6% of a refresh. Ring loss at a higher ring
count, or on a frame that also refreshes both scroll maps, is not proven safe.
The largest remaining constant cost on this route is the 224-entry background
line-scroll table at about 7,080 ticks every frame, 14% of a refresh. The Past
ring-loss stress gate (`tools/test-past-ring-loss.sh`) still needs a re-recorded
V0.057 reference before it can re-cover this code path.
No physical-console timing claim; V0.044 remains the last console test.

## V0.056 — checkpoint clock correction retains Good Future pacing

BIN `a8a9ce0721fc977a70153b4313a16d2f8a9575cee453ac02a8437f221cecdbe9`
rounds saved-checkpoint reload time to the original whole second. The complete
Good Future route has no checkpoint death and retains every one of its 26,029
controller/state rows from V0.055. All 26,023 same-act/era intervals remain one
VBlank, with profiling disabled. Actual run: `target-good-zone-v056-01` under
`build/ppz-journey`. The release evidence directory reuses its hash-identical
raw target artifacts with a fresh identical host reference to bind packaging
tools; that refresh is not presented as an additional emulator run.

Checkpoint-specific host/source/target/HUD gates verify the intended changed
clock behavior. Broader target regression passes with all 32,916 previous main/
Bad Future sequence states unchanged. Sequence intervals 8,060/5,192/2,861,
standalone Act 1 8,060 and opening 1,800 all have zero late intervals. Reports:
`dist/sequence-report.json`, `build/act-qa/pacing-report.json`,
`build/pacing-v056-qa/report.json`. Packaging status: NEXT-SESSION.md. No all-route
or physical-console timing claim; V0.044 remains the last console test.

## V0.055 — natural Good Future journey and arrival hitches

Final uninstrumented BIN
`b6951d679663e352b94c1b1c49085c1cb87946e72efd254ff4b20e90dc92b378`.
The new normal-controller Good Future route completes both Past generators,
all three acts, the boss, capsule, results and return to title. V0.054 exposed
three 3-VBlank gaps immediately after time travel (rows 1,288 / 14,992 / 19,949).
The loader warmed the era spawn view rather than the saved destination view.
Prewarming the actual projected/clamped destination while display is off removes
two gaps and shortens the third; the remaining crowded Act 2 arrival also pays
for repeated slot/ownership scans in object streaming.

The stream now builds a temporary placement-ownership bitset after removals
and reuses the first-free search position while adding slots. Initialization,
placement order, slot selection, break-on-failure and gameplay remain unchanged.
81,920 sanitized exact old/new private-state comparisons cover ten packs,
fragmented/full pools, children, reversals and persistent/deferred records.
The diagnostic first-arrival simulation phase falls from 38,390 to 24,163
CPU/8 ticks; all recorded state words still match. Diagnostic reports:
`build/ppz-journey/target-arrival-v055-{profile,stream-profile}-01`.

Final acceptance of this **measured route** uses profiling disabled:
`build/ppz-journey/target-good-zone-v055-03`. All 26,029 controller/state rows
are byte-identical to V0.054; 416,464 state words and 26,029 six-field progression
snapshots match the sanitized/shared-native reference. All **26,023** measured
same-act/era intervals have gap 1. Load/era transition gaps are excluded and
not represented as instantaneous. All 32 fast gates pass. Broader V0.055
regressions also pass: unchanged 32,916 main/sequence gameplay states; zero late
intervals in the Bad Future sequence (8,060/5,192/2,861), standalone Act 1
(8,060) and opening (1,800). Packaging is tracked in NEXT-SESSION.md; no hardware or
all-route/original-console timing acceptance is implied.

## V0.054 — checkpoint protection retains measured pacing

BIN `0df96d901b284a1622f89b4bac41c5462ddca7eb9aea943ef02dd2b9cd850f24`
adds the missing original checkpoint protection timer. All 32,916 unrelated
main/three-act states and inputs match V0.053, as does standalone Act 1.
The changed checkpoint route has its own source/negative/countdown evidence.

Sequence intervals 8,060 / 5,192 / 2,861, standalone Act 1 8,060 and opening
1,800 all have zero late intervals, maximum gap 1. Reports:
`dist/sequence-report.json`, `build/act-qa/pacing-report.json`,
`build/pacing-v054-qa/report.json` and `dist/checkpoint-regression-report.json`.
All 30 host and focused target gates pass. No all-route/original-console or
physical-console performance claim; V0.044 remains the last console test.

## V0.053 — source arrival/protection correction retains measured pacing

BIN `df0e79f8d93b0061f25bca6111827dc7c7bcf243fa8fc8e0663e927f699f7bbd`
corrects the state restored through travel and the captured hurt-flash decision.
The unrelated main/three-act comparison retains all 32,916 gameplay states and
inputs versus V0.052; standalone Act 1 also matches V0.052 exactly.

Sequence intervals 8,060 / 5,192 / 2,861, standalone Act 1 8,060 and opening
1,800 all have zero late intervals (maximum gap 1). Evidence:
`build/*-v053.log`, `build/act-qa/pacing-report.json`,
`build/pacing-v053-qa/report.json`, `dist/sequence-report.json`.
All 29 fast and focused target gates pass; audio/CD code matches V0.040.
No claim of all-route, original-console or physical-console timing is made.

## V0.052 — original effects retain measured pacing

BIN `963f403847bc276f594b7eb89ea9429b3e44fc401f0edd4daa3a71dd272ea048`
adds the original nine effect actors and pre-object player presentation samples.
No gameplay or audio rules change. The exact main/three-act comparison retains
all 32,916 gameplay states/inputs. Standalone Act 1 also matches V0.051 exactly.

Uninstrumented sequence intervals 8,060 / 5,192 / 2,861, standalone Act 1 8,060
and opening 1,800 all have zero late intervals, maximum gap 1. Evidence:
`build/*-v052.log`, `build/act-qa/pacing-report.json`,
`build/pacing-v052-qa/report.json`, and `dist/sequence-report.json`.
The focused title/world/effect-source-pixel/audio/transition gates also pass.
These measured routes do not establish worst-case all-era or console timing.

## V0.051 — merged actor priority retains measured pacing

BIN `8e21f5b6346d74a6d6a05936e132f6c42b279fa825f4e55c4e4fe11207e15209`
uses an eight-bucket index queue instead of separate hard-coded actor groups.
All 32,916 main/sequence gameplay states and controller inputs match V0.050
exactly, including animation. `dist/sprite-order-regression-report.json` binds
the old/new traces and six rejected pre-fix overlap photographs.

The uninstrumented sequence has zero late intervals over 8,060 / 5,192 / 2,861.
Standalone Act 1 has zero over 8,060 and opening zero over 1,800. All focused
world/source-pixel, main replay, title, audio/diagnostic and special-return gates
pass. Evidence: `build/*-v051.log`, `build/act-qa/pacing-report.json`,
`build/pacing-v051-qa/report.json` and the sequence report/raw traces.
These measured routes do not establish all-zone or physical-console timing.

## V0.050 — original descending selection preserves measured pacing

BIN `1fda1a9804bb02808cd100aa945e4fd66871e6f49795dc934bdf4e0b4c8a13f8`
restores a missing pre-movement animation selection, without changing physics.
All 16,116 sequence inputs and non-animation state bits match V0.049; 152 Act 2
animation bytes change as documented in AIR-ANIMATION.md. Act 1/3 states are
unchanged. `dist/air-regression-report.json` binds both old/new traces.

The sequence has zero late intervals over 8,060 / 5,192 / 2,861 updates.
Standalone Act 1 retains all 8,061 historical states and has zero late intervals
over 8,060; opening has zero over 1,800. Profiling is disabled. All focused
world/camera, replay/source-pixel, title, audio and transition checks pass on
this BIN. Evidence: `build/*-v050.log`, `build/act-qa/pacing-report.json`,
`build/pacing-v050/report.json` and the packaged sequence reports/raw traces.
These measured routes do not establish whole-zone or physical-console timing.

## V0.049 — original animation without runtime DPLC stalls

The first integrated runtime source decoder (`a2c95e003d3cdc13a4a911823bbf47c9bf45c34d072ae1b311592c7e6e74d1c4`)
misses 40/1,800 opening intervals, maximum gap 2. Preserve
`build/v049-runtime-dplc` and `build/pacing-v049-native` as the failed baseline.
Do not call its matching physics/pictures a performance pass.

Build-time composition of all 198 original poses, independently verified pixel
for pixel, creates a 96,578-byte lossless word-RLE pack. The same eight-slot
texture cache now expands these frames instead of composing DPLC pieces in
gameplay. First compressed BIN
`6d3ba238b804cd70248022c08901b8d771fb9163ffbecc28e317484ff752e5ae`
has zero late intervals / 1,800 (maximum gap 1), recorded in
`build/pacing-v049-rle`. No art or animation variants were dropped.
Final uninstrumented BIN
`e505d621b79ae2c374fdb5d3498efcc594ce5597f43beb6e883a0d0b3c8653a4`
includes the disc/heart priority corrections and passes all focused emulator
gates. Its exact recorded three-act sequence has zero late intervals over
8,060 / 5,192 / 2,861 updates. The 16,116 gameplay states remain byte-identical
to the previous candidate. Standalone Act 1 retains zero misses over 8,060
intervals and opening pacing zero over 1,800 (maximum gap 1 throughout).
Evidence: `build/*-v049-final.log`, `build/sequence-qa`,
`build/act-qa/pacing-report.json`, `build/pacing-v049-final/report.json`.
All four audio/CD implementation files still match the hardware-confirmed
V0.040 candidate. This is route-specific emulator evidence, not complete-zone,
original-console timing or physical-console acceptance.

## V0.048 — sprite correction preserves the measured pacing

BIN `95224d40113a0fe4730e6faab86674050c17867c5d4c838b4dd94d1a43bb3eaf`
corrects source-art composition; gameplay/audio logic and the V0.047 camera
pipeline remain unchanged. The three exact sequence traces are byte-identical
to V0.047 (16,116 states) and each act retains zero late intervals over
8,060 / 5,192 / 2,861 updates. Standalone Act 1 (8,060 intervals) and opening
pacing (1,800) also have zero misses. All focused same-BIN checks pass; see
SPRITE-COMPOSITION.md and `build/*-v048.log`. This is not complete-zone or
original/physical-console timing acceptance.

## V0.047 dense Act 2 follow-up — focused same-BIN gates pass

Uninstrumented follow-up BIN:
`8e50d87b961be55f37ed3c5ed74f4a69899eb35aca737df1247a2ab1698e6825`.
The original failed checkpoint below remains immutable. `src/frame_profile.h`
is restored to 0. All 21 fast gates pass. The same-BIN uninstrumented sequence
passes all three sanitized host replays, with zero missed refreshes over
8,060 / 5,192 / 2,861 intervals. Its three trace files are byte-identical to
the failed checkpoint's originals: 16,116 states / 257,856 semantic words.
The other focused same-BIN regressions also pass: world/source pixels and
camera coherence, the 16,800-state main replay, four-era and isolated audio,
823 title V-INTs / 1,196 exact pictures, full Act 1, special-stage win/return
and opening pacing. Standalone Act 1 has zero late intervals over 8,060;
opening has zero over 1,800. The camera check retains all 16 pictures / 3,451
spring pixels / 92,064 terrain pixels / 107,520 clear pixels. These are focused
host/emulator gates, not complete-zone coverage or hardware acceptance.
Evidence: `dist/sequence-report.json`,
`build/sequence-v047-margin-final.log`, `build/sequence-qa`, and
`build/qa-loops/20260920-002748-365549/report.json`.

`tools/replay-sequence.sh` adds exact recorded controller input across all
three acts, including carried progress, through the normal input interface.
It checks every input and all 16 semantic state words. The unchanged original
BIN freshly reproduces its single Act 2 miss in
`build/sequence-v047-exact-baseline`, with 16,116 matching states. The parser
now resets safely between stage files and validates all three before boot.
Sanitized parser tests and four additional sequence-report negative controls
protect against malformed input, state changes, incomplete runs and changed
builds. The measurement report deliberately is not a release acceptance gate.

The offending interval follows simulation 3,675, where ring loss creates a
large sprite list. Temporary probes separate sprite construction, clear wait,
list transfer and actual draw completion. The early clear is already finished;
the spike is simulation plus ring rendering, not a late software clear.

| Instrumented exact-route variant | Simulation ticks at 3,675 | Raster ticks | Sum of nine phases | Act 2 missed refreshes |
| --- | ---: | ---: | ---: | ---: |
| Camera-fixed baseline | 32,190 | 2,934 | 51,243 | 1 / 5,192 |
| Batched flat raster bands only | 32,173 | 613 | 48,930 | 1 / 5,192 |
| Raster plus ring allocation | 28,633 | 613 | 45,391 | 0 / 5,192 |

Ticks are SH-2 FRT CPU/8 diagnostic measurements, not wall-clock microseconds
or complete frame durations; loading/wrapped intervals are not interpreted.
Evidence, BIN/CUE and source snapshots: `build/sequence-v047-profile-before`,
`build/sequence-v047-profile-raster`, `build/sequence-v047-profile-ring`.
All three retain the complete recorded route and 16,116 matching states.
The final instrumented sequence has zero misses in all three acts, not just
the dense interval. The uninstrumented confirmation above now passes too.

Changes preserve output and gameplay:

- `scd_background_lines` computes Act 2 Present's constant 32-line bands once,
  retaining per-line slopes and all source wrapping. 189,056 complete-table
  comparisons across ten layouts match the untouched scalar calculation,
  including guard words, zero/partial lengths, boundaries and negative/wrapped
  coordinates. Existing 1,737,120 full-map cache comparisons also pass.
- Ring scatter remembers the last slot allocated within its own batch.
  Nothing frees slots during that batch, so subsequent lowest-free-slot
  searches can skip the known occupied prefix. Ordinary spawning, validation,
  slot order, ring counts, velocities and full-pool failure behavior are
  unchanged. 1,358 sanitized dense/fragmented/full-pool cases pass against both
  the old and new implementations, with byte-identical host test output.

Operational note: the raster-only shell wrapper was edited while its emulator
child ran, causing a shell seek/parse failure after the complete capture.
The captured run was not rerun or relabeled silently: every originally recorded
input hash was manually rechecked and the independent sequence checker then
validated all three completed acts. That variant still correctly reports one
late interval. Later wrappers are left unchanged while running.

## Historical V0.047 camera checkpoint — dense-scene margin failed

Development BIN `d7096389e77352f3ccc3b24944e3cab522c8924e6ea5e1d236a969a6626fa10d`
uses explicit drawing/manual swaps and an early software clear overlapped with
CPU work. The camera motion/source-pixel gate passes; see
[CAMERA-PRESENTATION.md](CAMERA-PRESENTATION.md) for rejected alternatives and
exact evidence. This is not yet a hardware-ready candidate.

Opening (1,800 intervals), complete Act 1 (8,060), and sequence Act 3 Bad Future
(2,861) have zero missed refreshes. Uninterrupted sequence Act 2 has one
two-refresh interval out of 5,192: simulation 3,676, X=7996.5390625/Y=552.40625,
80 active objects. All three functional routes and sanitized host replays pass,
but the new sequence pacing assertion fails. The failure report replaces the
earlier functional-only green report; hardware packaging rejects it. Profile
this exact dense route next, without changing inputs/physics or weakening the
camera/clear checks. Preserve `build/visual-checkpoint-v0.047-01` first.

Older measurements below remain historical, not current-BIN certifications.

## V0.044 — original HUD ring-flash state, no measured route regression

BIN `fd18db44c07bc9c296f675049dcc9bbd2e543fac5620231cd5ce918f6129c55c`, built with profiling disabled (`build/build-v044.log`). The only gameplay presentation change is the source-backed RINGS palette-state correction described in [HUD-FIDELITY.md](HUD-FIDELITY.md). Audio, counters and physics are unchanged. V0.040's `audio.c`, `audio.h`, `sound_bus.h` and `cd_status.h` hashes still match exactly.

| Uninstrumented V0.044 route | Update intervals | Missed-refresh intervals |
| --- | ---: | ---: |
| Opening Act 1 | 1,800 | 0 |
| Complete Act 1 | 8,060 | 0 |
| Recorded Act 2 Present | 5,188 | 0 |
| Separate Past ring-loss stress | 5,205 | 0 |

The complete routes preserve every recorded controller input and all 16 gameplay words. Act 1 retains 8,061 states, score 2,800, bonus 2,100 and three lives. Act 2 retains 5,189 states, score 4,400 and bonus 4,300; its separate Past-travel gate passes too. The stress case retains all 5,206 states, 89 expected hurt ticks and three lives; it is not a replacement for the no-damage Past route. Matching target HUD checks cover 1,805 / 1,727 / 1,772 original pixels respectively.

All 19 fast gates pass: `build/qa-loops/20260919-202621-605852/report.json`. Same-BIN focused checks pass for emulator/player (16,800 states / 268,800 words), title (823 original V-INTs and all 1,196 pictures), music/effects/pause/resume/loops and the three isolated audio probes. The new actual-native-HUD composition gate verifies 1,088 cases and 2,265,705 opaque pixels plus transparency against original mappings and retail ring-state execution. Final title/HUD captures were also visually inspected.

Evidence: `build/pacing-v044-qa/report.json`, `build/act-qa/pacing-report.json`, `build/act2-qa/pacing-report.json`, `build/act2-past-stress-v044/report.json`; focused logs are `build/{emulator,title,act,act2,audio,audio-diagnostics}-v044.log`. The versioned candidate preserves the corresponding reports, route logs/traces and HUD regression inputs/commands. Previous working QA directories were moved recoverably to `build/pre-v044-qa`; older immutable candidates were not changed.

No V0.044 whole-zone, every-era or hardware pass is claimed. V0.043's broader world/sequence/special-stage evidence remains historical. The current card is unmounted and unchanged. Original absolute gameplay clock phase, hardware performance and the unidentified graphical report remain open; no recurring QA job has been activated.

## V0.043 — snapshot reuse, loading prewarm and title reveal margin

Current uninstrumented test BIN: `7495f8471bf2ab8f6019994c502636fa3deacd7454429c98413c2b03cb4d5b63`. **Focused regression validation passes; this is not hardware or full-zone acceptance.** The working audio implementation and all object/player behavior are unchanged. The versioned local candidate is `build/hardware-candidate-v0.043-01`; it has not been copied to the card.

The Act 2 Present profile identified an avoidable duplicate computation of the full object diagnostics. `scd_replay_words_snapshot` still computes every hash/counter and publishes all 16 trace words, but returns the complete snapshot for `main.c` to reuse later in that same update. Paused, loading and diagnostic branches take a fresh snapshot instead. No hash, object or diagnostic field is omitted. The sanitized act replay independently compares the returned structure with a fresh `scd_objects_get()` on every update.

Over updates 3,664–3,672, the diagnostic-mailbox phase drops from **4,724.2 to 328.6 CPU/8 ticks** on average; total measured work drops from 36,316.7 to 31,907.3 ticks. The instrumented exact-recorded Present route goes from one missed refresh to zero. Source/BIN hashes before and after each diagnostic run are checked in `build/profile-act2-present-{before,snapshot}/input-hashes.txt` and `hash-check.log`; phase records are in their `results.log`. These diagnostic builds are not hardware candidates.

The Future loading gaps have a separate cause. The first simulation update previously constructed the complete foreground and background ring maps after stage loading. `load_era` now fills those maps and commits their DMA while the display is off, then waits for a fresh VBlank-out before returning to gameplay. The work remains part of loading; no simulation/animation update is dropped or advanced. Prewarming alone reduced the observed gap from three refreshes to two; aligning the first update removed the remainder. See `build/profile-act2-good-{before,prewarm,aligned}/` for the diagnostic experiments. Loading time must not be confused with steady-state frame rate.

The first uninstrumented V0.043 build exposed an additional **title reveal stall**, despite the title source being unchanged at that point. It expanded 22 new Sonic/arm textures at V-INT 82 and missed one refresh; the strict original-picture comparison failed rather than accepting the shifted sequence. That BIN (`16c5e7e4809a086256840eaeb67741dcccfbd0a27269a5ab02ec391e8b806394`), failure report, captures and source snapshots remain in `build/title-v043-failed-01`. It is not the final candidate.

`title_prewarm_mapping` now prepares Sonic frame 4 and arm frame 9 alongside the banner during title loading. These are the exact original mapping keys/positions; their art is already available and lies beyond the emblem reload. `tools/title_prewarm_test.c` checks **3,116 complete texture comparisons** through the reveal and requires all 38 warmed keys to occur in the source program's sprite table. ASan/UBSan and the existing 32,768 sampling cases pass. In the final BIN, uploads stay at 102 across V-INTs 80–83 rather than rising by 22 at 82, and the original title gate again passes **all 823 V-INT states/cadences and all 1,196 full-width pictures** (`build/title-v043-warm.log`). No tolerance or reference timing was changed.

The final BIN's 1,800-interval opening route, full 8,060-interval Act 1 route, and 5,205-interval Past ring-loss stress route have no missed refreshes. The stress route is deliberately separate from the no-damage Past acceptance route: its 5,206 states exactly retain the earlier failed exploratory run's inputs, 89 hurt ticks, three lives and results. The original no-damage requirement remains intact. Evidence: `build/pacing-v043-final-qa/report.json`, `build/act-qa/results.log`, `build/act2-past-stress-v043-final/report.json`.

All five expanded recorded routes also have **zero missed refreshes**: Act 2 Present 5,188 intervals, Past 4,816, Good Future 5,392, Bad Future 6,710, and Act 3 Bad Future 2,861. Their 24,972 gameplay states still match the previous recordings exactly and retain all original HUD checks. The Act 1 trace is also byte-for-byte identical to V0.042. Supplemental route evidence is `build/expanded-pacing-v043-01`; previous V0.042 measurements remain intact.

Final same-BIN checks: **18 fast gates**, including the new title-prewarm test (`build/qa-loops/20260919-200331-363359/report.json`); 16,800-state player replay; 21 scene captures; four-era music, silent pause/fixed disc position, resume/looping and isolated tone/ring/music probes; exact title pictures/states; full Act 1; all four Act 2 eras; Act 3 Bad Future; and **28,638-frame world regression / 122 captures**. The uninterrupted Act 1→2→3 controller route passes with exact host replay and zero missed-refresh intervals in each act (8,060 / 5,192 / 2,861). Its reactive input path differs from older runs, yielding scores 2,800→7,300→18,500; this is not presented as an identical-input performance comparison. The big-ring path also wins Special Stage 1 and returns correctly to Act 2 with score 84,000, four lives and time stone 1.

Final build log: `build/build-v043-title-warm.log`. The older `build/build-v043-final.log` belongs to the preserved title-failing intermediate BIN, not this candidate. No full-release QA report, hardware responsiveness pass, original-console gameplay cadence proof or closure of the unidentified graphical glitches is claimed. The general reactive driver and provisional gameplay Sonic animation remain separate open findings.

## V0.042 expanded timing/HUD audit — remaining gaps found

The **unchanged** final V0.042 BIN (`50651bef6a17afbab06600ef4b5f19a586cb9e1f74a665db5a95d026b04d12bf`) now has five additional full-route measurements. **24,972 states / 399,552 semantic words** match both sanitized host replay and the inputs/states of earlier successful target recordings. The routes retain their original no-damage/lives/result requirements; no assertion was relaxed. Evidence is preserved in `build/expanded-pacing-v042-01/manifest.json` (94 readback-hash-verified files). This supplemental archive does not modify the immutable hardware candidate.

| Recorded route | Update intervals | VBlanks | Late intervals | Largest gap | Original HUD pixels |
| --- | ---: | ---: | ---: | ---: | ---: |
| Act 2 Present | 5,188 | 5,189 | 1 | 2 | 1,727 |
| Act 2 Past | 4,816 | 4,816 | 0 | 1 | 1,876 |
| Act 2 Good Future | 5,392 | 5,394 | 1 | 3 | 1,831 |
| Act 2 Bad Future | 6,710 | 6,712 | 1 | 3 | 1,764 |
| Act 3 Bad Future | 2,861 | 2,861 | 0 | 1 | 1,796 |

The Present gap is at simulation update **3,670**, X=7,993.328125/Y=548.5, with **80 active objects** (route maximum 86). Both Future gaps occur at **update 2**, immediately after debug era loading. They remain in the totals, not excluded as warm-up. These are reproducible profiling targets; their root causes are not yet established. No original-console timing or real Saturn performance conclusion follows from these measurements.

The additional HUD checks compare rendered score, time, rings, labels and era-specific life icons against original mappings/art at the completed tally. All five captures contain rings, so ring labels are checked too. The common verifier now counts only actually checked pixels if another test explicitly excludes the zero-ring flashing label. These endpoint checks do not establish every flash, time-post or transition frame.

## V0.042 development checkpoint — direct foreground edge updates

The normal, **uninstrumented** final build records zero missed refreshes on both the 1,800-interval opening route and the full 8,060-interval Act 1 route. All 8,061 full-act gameplay states still match the sanitized host replay, with the same score, bonus, lives and checkpoint. BIN SHA-256: `50651bef6a17afbab06600ef4b5f19a586cb9e1f74a665db5a95d026b04d12bf`. Evidence: `build/pacing-v042-final-qa/report.json`, `build/act-qa/results.log`, `dist/act-report.json`. This is not whole-zone, original-console cadence or hardware acceptance.

All 16 fast gates pass (`build/qa-loops/20260919-190030-859081/report.json`). The six focused emulator/player/audio/audio-diagnostic/act/title reports match that same BIN. All 21 scene capture hashes and all seven full-act capture hashes are unchanged from V0.041; the independent title check still matches 1,196 pictures and 823 V-INT states/cadences. These selected captures are regression evidence, not complete motion/retail fidelity. The known provisional Sonic animation and the user's unidentified graphical glitches remain open.

The additional world regression passes 28,506 emulator frames and 122 captures, including its existing source-pixel checks, travel, platforms, checkpoint/death, monitors, doors/springs, tunnels, discs, scenery, projector/animals and Amy. Its report is also bound to the final BIN. This rerun exposed and fixed a diagnostic fixture-publication race (PPZ-QA-001); the failed initial BIN and captures remain in `build/world-v042-failed-01`. No visual tolerance was changed. The first audio comparison also encountered mixed-build recordings while the new gameplay run was pending; `check_audio.py` now requires matching BIN and gameplay-recording hashes. Rechecking the completed matching recordings passes (`build/audio-check-v042-final.log`).

Diagnosis: temporary CPU/8 timer probes separate controls, audio, simulation, foreground, background, raster, palette, diagnostics and sprite submission. Over updates 1,715–1,730, the foreground phase averaged 5,932.9 timer ticks before and 3,202.2 after the change (46.0% less); total measured work fell from 46,342.3 to 43,444.1 ticks. Other major phases were substantially unchanged. Instrumented logs are `build/profile-v041-qa/results.log` and `build/profile-foreground-qa/results.log`; instrumented BIN hashes are recorded in their reports, distinct from candidate images. Ignore loading/fade frames when interpreting the 16-bit phase timers, which can wrap.

The old foreground code scanned all 42×30 viewport cells to identify exposed tiles. `src/foreground_cache.h` directly selects the newly exposed edge range on each row. It performs exactly the same tile writes, not fewer visible updates; simulation, sprite lists and audio are unchanged. ASan/UBSan passes **794,250** full-map/write-count comparisons over ten packs, including every overlap-boundary delta, ring wrapping, reversing, diagonal scrolling, teleports and deterministic randomized sequences. Run `bash tools/test-foreground-cache.sh`; it is in the fast QA suite alongside the existing background-cache gate.

The optional probes live in `src/frame_profile.h`, with `SCD_FRAME_PROFILE` set to **0**. To diagnose a future issue, change it to 1, rebuild, resolve `_scd_frame_profile` from that build's ELF and pass the address as the `SCD_FRAME_PROFILE` environment variable to `tools/test-pacing.sh`. Restore 0 and rebuild before acceptance tests. The candidate packager refuses an ELF containing the profiling mailbox or a pacing report marked instrumented. Its rejection was tested on the diagnostic build. Do not distribute that diagnostic build as V0.041 or V0.042 hardware acceptance evidence.

| Same-route comparison | V0.040 | V0.041 | V0.042 |
| --- | --- | --- | --- |
| Opening route missed-refresh intervals | 51 / 1,800 | 2 / 1,800 | 0 / 1,800 |
| Full Act 1 missed-refresh intervals | 51 / 8,060 | 2 / 8,060 | 0 / 8,060 |

## V0.041 development checkpoint — incremental background rows

V0.040 remains the user-confirmed Saturn/SAROO audio baseline. V0.041 is a development build, not hardware-accepted or a full-zone QA release.

The renderer previously decoded all 64 tiles in a background row whenever its horizontal tile origin changed. Adjacent origins share 63 tiles. `src/background_cache.h` now decodes only newly exposed columns, preserving the entire 64-tile ring map. It rebuilds the complete row after a vertical ring-slot change or a horizontal jump of 64 or more tiles. Leftward scrolling, static rows and resets retain the same behavior. DMA submission and simulation/physics are unchanged.

The independent test rebuilds whole rows using the old algorithm, then compares **all 4,096 map cells after every operation**. ASan/UBSan passed 1,737,120 comparisons over all ten act/era packs, including tile/row wrap, reversal, large jumps, source bounds, cloud animation and changing raster regions. Single-tile shifts must perform one decode; new world rows must perform 64. Run `bash tools/test-background-cache.sh`; it is part of the fast QA suite.

| Measurement | V0.040 | V0.041 |
| --- | --- | --- |
| Opening route, 1,800 update intervals | 1,851 refreshes; 51 late intervals | 1,802 refreshes; 2 late intervals |
| Full Act 1, 8,060 update intervals | 8,111 refreshes; 51 late intervals | 8,062 refreshes; 2 late intervals |
| Largest interval on these routes | 2 refreshes | 2 refreshes |

The opening-route baseline was freshly rerun from the immutable V0.040 archive, not rebuilt from new source. Its BIN SHA-256 is `32e461959d053be26661675c222169d3b558280a0c72aa1666d9242a9ea79fe8`. V0.041's is `99dc45f33f60ad7dc6cfee8d6451187322da353f9c8d9b44375883d8120d49b7`. Hash-bound measurements: `build/pacing-v040-baseline-qa/report.json` and `build/pacing-v041-qa/report.json`.

Reproduce with `bash tools/test-pacing.sh <absolute-path-to-cue> <output-directory>`. This is a measurement, not a passing whole-zone performance gate.

The complete Act 1 target/host replay retains 8,061 matching states (128,976 semantic words), score 2,800, bonus 2,100, three lives and checkpoint 2. Evidence: `build/act-v041.log`, `build/act-qa/results.log`, `dist/act-report.json`. The host shares native behavior code: this proves replay consistency, not independent retail physics fidelity. The full-width title still independently matches 823 original V-INT states/cadences and all 1,196 pictures (`dist/title-report.json`).

Focused regression completion: all 15 fast gates pass (`build/qa-loops/20260919-185002-297349/report.json`). The emulator/player/audio/audio-diagnostic/act/title reports all match the V0.041 BIN hash above. The wider player replay matches 16,800 states/268,800 words; isolated tone/ring/music, four-era music, silent pause, resume and looping pass. These are focused checks, not the full-zone suite. No card deployment was performed.
