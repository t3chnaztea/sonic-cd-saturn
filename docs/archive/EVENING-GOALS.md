# Evening goals — 2026-09-21

Starting point: `f72104a`, Japanese soundtrack candidate
`112d86227977407b0544a6cde19f8d10b30bf03a4202dcf97d5e675a0d31b1c5`.
The visual baseline and focused Japanese audio checks are recorded in
`NEXT-SESSION.md`. The active thread goal asks to establish and achieve
concrete evening goals after that validation pass.

## Required outcome

Integrate the queued first group of zone objects: Tidal Tempest wall1,
Stardust Speedway wall7/wall73, Quartz Quadrant dair5 platforms, Metallic
Madness Act 1 konbea conveyors, and Metallic Madness pistons. Complete their
source-backed art, frame selection and collision behavior. Retain the
draw-priority hang fix and staged-CD dependency fix. Produce a locally
verified Japanese-music BIN/CUE and a reproducible record of its checks.

## Acceptance evidence

- Original-source behavior tests for all four object families, with
  sanitizer checks, pass against the integrated implementation.
- All supported act/era variants of those objects have original graphics,
  correct offsets, palette indices and animation-frame selection. Source
  pixel comparisons and actual Saturn renderer evidence are required;
  merely loading a zone or reusing the boulder sprite is insufficient.
- Every zone enters through the level select and sustains simulation without
  a renderer abort. Exercise the new object families on the target, including
  types absent from a zone's Act 1 start.
- The existing fast checks and complete Palmtree Panic target regression
  suite pass on the candidate. Japanese audio, effects and title behavior
  remain verified. Check that data-only changes rebuild the disc.
- Save the final package hashes, test results, remaining limitations and
  next steps in the handoff. Preserve prior accepted hardware baselines.

Later bosses, additional object batches, full parallax, animated terrain,
per-zone music routing and hardware acceptance remain separate full-port
work. This evening's goal does not claim those are finished.

## Completed outcome

V0.058 meets the above local acceptance requirements. All 38 fast gates and
the full configured Saturn suite pass on BIN
`98adf3b88d084fb49b2d92fafd458b4bb7d33ab7dbc2766ea414bfdb1ee89b23`.
The aggregate is `build/evening-final-qa/report.json`; it retains the two
failed checker attempts and their corrections (expanded priority-case count,
and automatic next-zone entry replacing the retired prototype end screen).
Neither correction changed the binary, controller routes or timing thresholds.

The artwork matrix passes all 40 variants, 1,000 frame/flip captures and
2,606,256 source pixels. All seven zone smoke routes pass. Original behavior
and sanitizer gates, Japanese audio, PPZ regressions and the staged-CD rebuild
proof pass. The Past ring-loss stress route matches 5,208 states with zero
missed refreshes. See `build/evening-v0.058-01/candidate-manifest.json` for the
preserved package and file readback hashes. No hardware acceptance is claimed.
