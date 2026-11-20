# Hardware-readiness gate audit — 2026-09-19

Scope: the active request to fix real-hardware audio, investigate slowdown,
correct title coverage/glitches, and restore original gameplay HUD. Do not
substitute complete-zone feature work or the later scheduled QA phase for this
gate. The preceding goal turn made concrete progress: V0.044 fixed the HUD
ring-color state and added independently verified native-renderer coverage.

Current candidate: `build/hardware-candidate-v0.044-01`, BIN
`fd18db44c07bc9c296f675049dcc9bbd2e543fac5620231cd5ce918f6129c55c`.
All 34 archived payload hashes and all 41 recorded current-source hashes were
rechecked. Archived reports refer to that BIN, not just a matching version name.

| Requirement | Authoritative evidence | Status / remaining limit |
| --- | --- | --- |
| Research the hardware sound path and compare other ports | Pinned Sega/Yaul sources and PoneSound, SRL, Mimas and Sonic Z-Treme comparisons in `HARDWARE-ACCEPTANCE.md`; project-local CD command override and exhaustive status tests | Implemented and validated; do not speculate about firmware/electrical fixes |
| Obtain audible real-Saturn/SAROO sound confirmation | `hardware-results/v0.040.json`, deployment receipt and preserved V0.040 BIN; user's “IT WORKED!! SOUND WORKS PERFECTLY!!” | Functional sound gate passed on V0.040; no fabricated per-track/repeated-boot observations |
| Preserve working audio in the new candidate | V0.044 audio/CD/sound-memory source hashes equal V0.040; same-BIN audio and isolated-probe reports pass | Code/emulator regression passes; V0.044 itself has not been run on the console |
| Test the reported slowdown | V0.037 opening route: 60 late intervals/1,800; V0.040: 51; V0.044: zero. Complete Act 1, dense Act 2 and damage-stress timing reports retain exact inputs/states and zero misses | Tested and avoidable measured stalls corrected; console responsiveness and video-mode timing remain unverified |
| Fix title blank side strips and possible cloud glitches | Exact source-derived full-width title comparison: 823 V-INTs, 1,196 pictures, zero mismatched pixels; cold-reveal prewarm and sanitizer regressions | Code/emulator coverage and cadence pass; real-console edges/clouds have no post-fix observation yet |
| Restore original gameplay HUD | Original mappings/art/counters/life/time-post presentation; 1,088 actual native renderer cases, retail 68000 ring-state oracle, full opaque/transparency comparison; target HUD pixel checks | Code/source/target checks pass; hardware presentation and absolute cross-console startup phase are not independently confirmed |
| Validate and preserve candidate | 19 fast gates, same-BIN title/gameplay/audio/act reports; immutable package and verified hashes | Focused candidate validated, not a whole-zone or hardware acceptance claim |
| No further level development during this gate | V0.041–044 work is rendering performance, title/HUD presentation and test/evidence support | No new level content in this gate; remaining zone functionality is a separate task |

## Required next observation

Run this candidate on the user's Saturn/SAROO and report title edges/clouds,
HUD, responsiveness and continuing sound. The current environment cannot
provide that physical-console observation. The previously used card volume is
absent from `/Volumes`; no other mounted volume should be treated as that card.
Do not install to backup disks, delete unrelated folders, or relabel an emulator
pass as hardware evidence.

`docs/archive/HARDWARE-TEST-V0.044.md` is the short handoff checklist. The user's deferred
glitch footage is not required for this test. No cron/recurring job has been
activated: the user requested that after Palmtree Panic functional completion.

The verified BIN/CUE and checklist have been copied into the newly created
Desktop folder named `Sonic CD Saturn v0.044` after approval. All three
destination hashes match the source files; `build/desktop-deployment-v044.json`
records the handoff. No older build or card folder was removed or overwritten.

The overall hardware-readiness acceptance remains pending this external
observation. Rebuilding an unchanged candidate or repeating identical passing
tests cannot resolve it. The broader unidentified zone-glitch report remains
open, but is not permission to expand this active gate into unrelated level
development.

## Subsequent card handoff

The user remounted the card. Its UUID matched the recorded SAROO volume.
V0.040 was moved off the card into `build/card-removed-v040-for-v044` before
installing V0.044; all 15 old payloads and its manifest were verified in recovery.
The new BIN/CUE/checklist passed readback hashing, and the names/types/sizes/
modification times of all 173 unrelated ISO entries were unchanged. The card
was safely ejected. Receipt: `build/card-deployment-v044.json`. The card-absence
part of the earlier handoff blocker is resolved; the actual console-test result
is still pending.

## Subsequent V0.044 hardware result — 2026-09-19

The user has now tested the deployed candidate and remounted the card. They
report it is "Hugely improved" with no noticed gameplay-affecting problems on
their route. See `hardware-results/v0.044.json`; the earlier pending-observation
statements above describe the pre-test state and are superseded by this record.

Acceptance is still incomplete: title clouds show vertical lines; monitor
contents appear black; small brick platforms appear only when stood upon;
sprites may drift during vertical scrolling. `PALMTREE-BUGS.md` tracks each
separately. The report does not establish exact console timing, every audio
event, HUD flash-phase accuracy or whole-zone completion. Preserve the V0.044
archive and working audio baseline. No card write occurred with this report.
