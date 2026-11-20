# Targeted QA reruns

After a full run fails or is interrupted, use its `build/qa-loops/*/report.json`:

```sh
python3 tools/qa-loop.py targeted --from-report build/qa-loops/<run>/report.json --list
python3 tools/qa-loop.py targeted --from-report build/qa-loops/<run>/report.json
```

The selector starts at the failed check, or the first unfinished check after an interruption. It runs every later command in the full suite. This conservative suffix includes downstream consumers of files created by earlier checks. If a targeted run fails, use its report as the source for another targeted run after the fix. The command prefix must match the current runner. A changed disc hash is rejected when the source report records one.

The new report has `mode: targeted`, `passed: false`, `release_eligible: false`, and `partial_passed: true` only after all selected commands pass. Targeted mode never writes `dist/qa-report.json`. It is a diagnostic rerun, not cumulative proof from earlier checks. Once inputs are stable, run `python3 tools/qa-loop.py full` from the start. Hardware packaging requires that clean full report and its final BIN hash.
