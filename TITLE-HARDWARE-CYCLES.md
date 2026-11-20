# V0.046 title hardware-fetch correction

Status: documented VDP2 timing violations corrected and target register state
verified; **the user's physical-console cloud stripes are not yet confirmed
fixed**. No screen-width, cloud-animation, palette or reference-pixel tolerance
was changed. The V0.045 monitor correction is retained.

## Evidence and cause

Sega's VDP2 manual, tables 3.2–3.4, requires one pattern-name access per cycle
at 1x reduction allowance; using two-word pattern names does not double this.
At normal resolution, NBG1 name fetches at T2/T3 cannot feed a character fetch
at T5. The old title scheduled exactly those invalid pairs, plus duplicate
name fetches. The pinned SDK's `vdp2/vram.h` also explicitly documents one
access for either one- or two-word names.

Primary reference: [Sega VDP2 VRAM access rules](https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p03_31.htm).

| A0 cycle | T0 | T1 | T2 | T3 | T4 | T5 | T6 | T7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V0.045 | NBG0 name | NBG0 name | NBG1 name | NBG1 name | NBG0 character | NBG1 character | idle | idle |
| V0.046 | NBG0 name | NBG1 name | idle | idle | NBG0 character | NBG1 character | idle | idle |

`src/title_vram.h` defines the legal schedule, used by `title_view.inc`.
The title explicitly selects 1x reduction allowance while preserving the
205/256 source step that expands the original 256-pixel picture to 320 pixels.
Unrelated gameplay cycle schedules are not changed by this correction.

## Why old emulator picture tests did not catch it

A fresh V0.045 title run passed all 823 V-INT states and all 1,196 picture
comparisons. Its captured VDP2 state nevertheless contains five validator
findings (duplicate name counts and illegal fetch pairs). Thus an emulator
picture pass alone is demonstrably insufficient to establish a legal hardware
schedule. This does not by itself prove that the user's observed stripes have
only this cause.

Before evidence: `build/pre-v046-qa/title-v045-cycle-baseline/`, including
`title-v120.state` and `title-report-v045.json`. Original BIN remains in
`build/visual-checkpoint-v0.045-01`.

After evidence: `build/title-qa/title-v120.state`, `dist/title-report.json`,
`build/title-v046.log`. The emulator's actual serialized VDP2 registers show
A0 `01FF 45FF`, all documented timing checks pass, and all 1,196 retail-derived
pictures remain exact. The state, checker/source and core hashes are recorded.
The parser reads bounded named state sections, not a byte-pattern search or
an assumed private emulator-memory address. It checks the mode, palette size,
cell format, VRAM partitioning, reduction allowance and horizontal sampling
before applying this profile's timing rules.

Five host regression tests include the old failing schedule, missing/duplicate
fetches, the T2→T5 forbidden pairing, a legal alternative and malformed states.
The fast suite now includes this additional gate. Hardware packaging rejects
missing, stale or failing title-cycle evidence and preserves the state capture.

Current V0.046 BIN SHA-256:
`68621e29aae1a1a7e3e1ced139162243216fc1865dd3d34ed7fd3ff43c4d62cf`.
All 20 fast gates, 16,800-state replay, audio/music and isolated probes, and
222 world captures pass on this BIN. Full Act 1 matches 8,061 states; all 8,060
measured intervals use one refresh, as do the 1,800 opening pacing intervals.
This is focused candidate evidence, not full-zone or physical-console acceptance.

## Remaining title investigation

Retest cloud motion on Saturn, including cold boot and return from game over.
If stripes persist, inspect SH-2 cache coherency and cloud-buffer publication,
VDP2 write timing and exact stripe location. Keep hardware symptoms open until
observed; do not paper over them with looser pixel comparisons.
