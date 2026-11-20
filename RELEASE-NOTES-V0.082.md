# V0.082: candidate ready for the maintainer's hardware test

Software regression passed on 2026-11-19 at 05:43:44 CST. Hardware acceptance remains open.
Build label: `V0.082 / 20261117`.
Tested source commit: `49bfd89643b2a77962964a988e87b75a46e9b7a6`.
Local baseline commit: `0afbcd62c02fce4a919aa0ee6e40b740daa0aa15`.

## Result

| Gate | Result |
| --- | --- |
| Full regression | 215/215 passed; 214 completed checks retained from the original run |
| Zone and special-stage matrix | 347/347 passed; 161 saved windows reused; 186 new windows passed |
| Missing-art scan | 70 route/era cases passed; 0 art misses |
| Source18 disc-dependency repair | Passed in this full regression at step171 |
| Owned processes | All 5 retired; coordinator, main, caffeinate, watcher and observer exited0 |
| Hardware acceptance | Open; the maintainer will test Saturn/SAROO |

Exact terminal output:

```text
PASS: final full gate; hardware acceptance remains open
PASS: <repo>/build/qa-loops/20261118-233511-837399/report.json
```

This is a finite software regression result. Full-game path coverage percentage remains unverified. The retained coverage gaps remain in `docs/BACKLOG.md`.

## Committed changes

Commit `0afbcd6` preserves the accumulated game, test, route and QA-control baseline. It includes Stage Select and Coming support, Staff Times entry and presentation, CD-DA support and firmware preparation, Time Attack record preservation, CD++ state and pacing changes, object/checkpoint/era handling, and guarded QA recovery. This describes committed code; it does not close every game milestone.

The Source18 failure came from the disc-dependency test's two `gmake -q` probes. Both now exclude the always-run `prepare-sound-driver` validator with `-o prepare-sound-driver`. The actual build, staged-data invalidation and restoration assertions remain intact. The affected component passed before the commit. It also passed in the completed V0.082 full run.

Commit `49bfd89` adds V0.082 to the seven-zone and special-stage release-evidence version sets. The original startup attempt failed with `AssertionError: Unsupported release evidence scope` before any check or build ran. That zero-check failure remains recorded separately. The full 215 command inventory and complete matrix scope remain unchanged.

## Recovery record

The actual full run started on 2026-11-17 at 21:23 CST. The maintainer stopped it on 2026-11-18 at 07:45 CST after 214 top-level passes and 161 matrix passes. The later continuation used matching source, image, runtime, logs, producer outputs, 24,328 immutable dependency hashes and 310 generated asset hashes. Every original top-level row remains intact, including its original cache-completeness markers.

The first continuation unexpectedly reran TT1 successfully because the generic cache chose the wrong earned parent. A TT2 attempt was interrupted. This breached the requested no-repeat policy. The original161 accepted windows and their artifacts were restored. Duplicate outputs remain preserved. See V082-002 in `docs/BACKLOG.md` and the prior continuation's `recovery-restoration.json`.

The corrected continuation uses TT1's actual CC3/C earned backup. It retains the backup-hash equality check. It stops before archive, preparation or execution if a saved passing window cannot be reused. All 161 saved windows were consumed without another saved-window execution in that corrected continuation. No game source or candidate image changed during recovery.

The saved report retains the actual private matrix argv. The unchanged release audit received an explicitly bound copy that differs only at `steps[214].command`. All 347 window, artifact and campaign assertions ran. The audit sidecar was published after the audit succeeded. Standard downstream auditing of this continuation needs that bound view. General reader support remains backlogged.

Two identity-hook read-access outages left the existing QA process running. The independent first-failure observer remained active. Both outages recovered without a new QA launch.

## Evidence

`D = build/qa-campaign/final-regression-full-v0082-continue2-20261118/`

- `D/release-outcome.json`: exact result, commit, artifacts, raw exits and evidence hashes.
- `D/final-full-report.frozen.json`: completed215-check report.
- `D/final-matrix-report.frozen.json`: completed347-window matrix.
- `D/final-audit-view.frozen.json`: exact audit view; only the bound matrix argv differs from the truthful report.
- `D/final-retirement.json`: fresh native identity proof for all5 retired processes.
- `D/saved-consumption161.json`: retained214-row and161-window consumption proof.

Live result paths are `build/qa-loops/20261118-233511-837399/report.json` and `build/zone-gates/20261118-033850/report.json`. The stored bound view is `D/bound-matrix-audit-view.json`.

## Hardware and artifacts

The maintainer will perform the console test. At the2026-11-19 QA close, the earlier SAROO transfer receipt predated this release commit. No new image was written during that QA session. No push or SEGA asset sharing occurred.

The following hashes were captured after all owned processes retired and the required cooling interval elapsed. They match the images from the original V0.082 build.

| Artifact | SHA-256 |
| --- | --- |
| `dist/sonic-cd-saturn-prototype.bin` | `cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66` |
| `build/saturn/sonic-cd-saturn-prototype.elf` | `b28df036848c55d20394e2a812af4703ef037497b1ef0e1476a54b26288d1e45` |
| `dist/iso/sonic-cd-saturn-prototype.iso` | `f4274072fada7d47dd9d3f3e18e73e32f8756a9855032719e896d5f310586f35` |
| `dist/sonic-cd-saturn-prototype.cue` | `10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337` |
| `dist/iso/sonic-cd-saturn-prototype.cue` | `b08368e7743787ec3045e778f46761a0e1133e076977e7453be888b3eac41f5e` |

## 2026-11-20 local delivery

The exact BIN/CUE above were copied to `/Volumes/Untitled/SAROO/ISO/Sonic CD Saturn v0.082`. Writes were flushed. Both card readback hashes matched. Existing folders were preserved. The transfer receipt is `build/release-deployment-v0082-20261120/sd-transfer.json`.

The local browser patcher in commit `81e3fb8` also produced matching downloaded BIN/CUE files in desktop Chrome. Its bundle stays private because it contains converted game data. No game rebuild or new game QA campaign ran. No push, remote deployment or visibility change occurred. See [the release handoff](docs/RELEASE-HANDOFF-V0.082.md) for test receipts and publication limits.
