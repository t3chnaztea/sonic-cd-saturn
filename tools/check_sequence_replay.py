"""Measure a recorded sequence without treating diagnostic pacing as acceptance."""
import hashlib
import json
import re
import sys
from pathlib import Path
from act_pacing import measure


def check(folder, reference):
    log = (folder / 'results.log').read_text()
    ends = list(re.finditer(r'^Act pacing:.*$', log, re.M))
    assert len(ends) == 3, 'three completed acts required'
    assert 'Act 3 end: prototype screen shown, Start returned to the title screen' in log
    hashes = {}
    # Paths written before the run include the actual disc, executable, code
    # and all three input oracles. Verify again before binding the report.
    for row in (folder / 'input-hashes.txt').read_text().splitlines():
        expected, name = row.split('  ', 1)
        actual = hashlib.sha256(Path(name).read_bytes()).hexdigest()
        assert actual == expected, ('input changed', name)
        hashes[name] = actual
    pacing = {}; start = 0
    for act, (end, name) in enumerate(zip(ends, (
            'player-target-trace.txt', 'act2-target-trace.txt', 'act3-target-trace.txt')), 1):
        trace = (folder / name).read_text()
        source = (reference / name).read_text()
        assert [row.split()[1:] for row in trace.splitlines()] == [
            row.split()[1:] for row in source.splitlines()], ('route mismatch', act)
        pacing[str(act)] = measure(log[start:end.end()], trace)
        start = end.end()
    report = dict(measurement_complete=True, exact_inputs_and_states=True, pacing=pacing,
                  zero_missed_refreshes=all(p['late'] == 0 for p in pacing.values()),
                  instrumented_frame_profile='Frame profile:' in log, input_hashes=hashes,
                  log_sha256=hashlib.sha256((folder / 'results.log').read_bytes()).hexdigest(),
                  hardware_tested=False, release_gate=False)
    (folder / 'pacing-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Exact sequence replay:', ', '.join(
        f"Act {act}: {p['late']} late / {p['intervals']} intervals" for act, p in pacing.items()))


if __name__ == '__main__':
    check(Path(sys.argv[1]), Path(sys.argv[2]))
