# Palmtree Panic performance evidence

## Quick reference

Purpose: Palmtree Panic frame-pacing evidence and the method for measuring it.
`tools/package-hardware-candidate.py` ships this file with a candidate when a
pacing report exists. Entries run through V0.057. Later pacing results live in
`NEXT-SESSION.md`, the zone ledgers and release notes.

Binding rules:

- Gates require zero late intervals. `tools/check_sequence.py` and
  `tools/check_act.py` fail on any late interval. The packager rejects a pacing
  report with `late` above zero or marked instrumented.
- Compare performance only on an identical controller path (section below).
  Reactive routes change inputs when render timing changes (PPZ-QA-002).
- Profile with `src/frame_profile.h`: set `SCD_FRAME_PROFILE` to 1, rebuild,
  resolve `_scd_frame_profile` from that ELF and pass the address as the
  `SCD_FRAME_PROFILE` environment variable to `tools/test-pacing.sh`. Restore 0
  and rebuild before acceptance tests. Never ship a profiling build.
- 16-bit phase timers can wrap. Ignore loading/fade frames when reading them.
- Fix overruns at the source without changing physics or gameplay states.
  No locked-60 Hz or console-timing claim from emulator data.

Commands:

- Opening route: `bash tools/test-pacing.sh <absolute-cue> <out-dir>`.
- Recorded route check: `tools/act_pacing.py` (example below).
- Malformed-input gate: `tools/test-act-pacing.sh` (fast QA).
- Cache gates: `bash tools/test-background-cache.sh`, `bash tools/test-foreground-cache.sh`.

Open items:

- V0.057 ring-loss update headroom is about 6% of a refresh. Higher ring counts,
  or ring loss on a frame that refreshes both scroll maps, are not proven safe.
- The 224-entry background line-scroll table costs about 7,080 CPU/8 ticks every
  frame (14% of a refresh).
- Whole-zone, original-console cadence and hardware timing remain open (below).
- V0.076 headroom over all 40 PPZ/CC/TT/QQ routes (`tools/frame_headroom.py`,
  measured VBlank-in deadline 47,740 ticks): TT3 C/D capsule flowers keep
  7.0k ticks of slack (14.6%) after e4c5be5, none above 90%. Table in the history.

Per-version measurements (V0.041–V0.057) moved verbatim to
[docs/archive/PERFORMANCE-HISTORY.md](docs/archive/PERFORMANCE-HISTORY.md).

## Keep the controller path identical when comparing performance

The first attempt with the old reactive driver failed the Past no-damage requirement and could not finish Good Future. Failures remain preserved at `build/act2-past-v042-reactive-failed` and `build/act2-good-v042-reactive-failed`; they were not relabeled as passes. Some jump/dash/wait counters advance per **emulator refresh**, so renderer speed changes the input history. The Past first input difference is update 795; the first state difference is update 1,244. That different route also exposes one late interval at update 3,384 near ring loss, X=7,172.609375/Y=595.51953125, with 79 objects. Keep this additional stress case open.

`SCD_ACT_PAD_TRACE` optionally supplies a previous complete target trace through the **normal controller interface**. It never writes game memory or skips to checkpoints. Pads are scheduled by simulation update with the measured one-update SMPC polling lead. Every consumed input and every one of 16 gameplay words must match the reference, with immediate failure on any difference. A lead-zero negative run fails at the first input transition (update 129). The general reactive driver is still useful for exploration but is not yet simulation-clocked; replay mode does not repair that driver.

`tools/act_pacing.py` reconciles each VBlank record, coordinates and object count with the complete trace, checks all interval arithmetic, requires a successful same-BIN route report, and verifies reference input/state equality. `tools/test-act-pacing.sh` checks malformed/truncated/oversized input rejection under ASan/UBSan and rejects missing/duplicated/mismatched timing records. It is an additional fast QA gate; the entire updated fast suite was **not** rerun at this checkpoint. Act 2 Present also retains its separate travel regression; Act 3 retains boss/capsule/results/end/title-return checks.

Example reproduction (preserve existing output directories first):

```sh
SCD_ACT_PAD_TRACE="$PWD/build/expanded-pacing-v042-01/act2-past-qa/reference-trace.txt" bash tools/test-act2-era-emulator.sh 1
python3 tools/act_pacing.py build/act2-past-qa --cue dist/sonic-cd-saturn-prototype.cue --expected-bin 50651bef6a17afbab06600ef4b5f19a586cb9e1f74a665db5a95d026b04d12bf --route-report build/act2-past-qa/report.json --reference-trace build/expanded-pacing-v042-01/act2-past-qa/reference-trace.txt
```

Use era 2/3 and the corresponding archived reference for Good/Bad Future; use `tools/test-act2-emulator.sh` or `tools/test-act3-emulator.sh` for Present/boss. Run sequentially: existing scripts share their compiled harness path. Recorded input is for same-route comparisons, not a substitute for original-source fidelity checks when gameplay legitimately changes.

## Still open

- V0.041's two late intervals at updates 1,723 and 1,728 are resolved on the tested route by V0.042's foreground optimization. This does not close performance acceptance for unmeasured scenes or hardware.
- Measure other routes, all eras, transitions and worst-case object/effect loads. The measured routes do not establish whole-zone speed.
- Establish original-console cadence for matching scenes and confirm responsiveness on real Saturn/SAROO. Do not claim locked 60 Hz or close the user's slowdown report on emulator evidence alone.
- No conclusion about the user's unspecified graphical glitches follows from these timing results. Those remain open in `PALMTREE-BUGS.md`.
