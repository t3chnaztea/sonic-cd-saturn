"""Validate every interval against a completed, independently replayed act trace.

This measures one route; a measurement can be valid while a gameplay gate fails.
It never converts a failed route gate into an accepted build.
"""
import re


def measure(log, trace):
    timing = [tuple(map(int, row)) for row in re.findall(
        r'^Act timing: sequence=(\d+) simulation=(\d+) vblank=(\d+) x=(\d+) y=(\d+) objects=(\d+)$', log, re.M)]
    rows = []
    for line in trace.splitlines():
        fields = line.split()
        assert len(fields) == 18, 'invalid trace row'
        rows.append([int(v, 10 if i < 2 else 16) for i, v in enumerate(fields)])
    assert len(rows) == len(timing) and len(rows) > 1, 'missing per-state timing'
    summary = re.findall(r'^Act pacing: intervals=(\d+) vblanks=(\d+) late=(\d+) max_gap=(\d+)$', log, re.M)
    assert len(summary) == 1, 'one completed act required'
    gaps = []
    for i, ((seq, sim, tick, x, y, objects), row) in enumerate(zip(timing, rows)):
        assert (seq, sim, x, y, objects) == (row[0], row[8], row[2], row[3], row[14] >> 16), 'timing/trace mismatch'
        assert sim == i + 1, 'simulation update skipped or duplicated'
        if i:
            assert seq == timing[i-1][0] + 1, 'trace sequence skipped or duplicated'
            delta = tick - timing[i-1][2]
            assert delta > 0, 'multiple updates per VBlank or decreasing timer'
            if delta > 1:
                signed = lambda value: value if value < 0x80000000 else value - 0x100000000
                gaps.append(dict(simulation=sim, vblanks=delta, x=signed(x)/65536,
                                 y=signed(y)/65536, active_objects=objects))
    intervals = len(rows)-1
    blanks = timing[-1][2]-timing[0][2]
    peak = max([1] + [gap['vblanks'] for gap in gaps])
    assert tuple(map(int, summary[0])) == (intervals, blanks, len(gaps), peak), 'pacing summary differs from trace'
    assert blanks == intervals + sum(gap['vblanks']-1 for gap in gaps)
    return dict(states=len(rows), intervals=intervals, vblanks=blanks, late=len(gaps),
                max_gap=peak, gaps=gaps, max_active_objects=max(row[5] for row in timing))


if __name__ == '__main__':
    import argparse
    import hashlib
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--cue', type=Path, required=True)
    parser.add_argument('--expected-bin', required=True, help='BIN hash recorded before the run')
    parser.add_argument('--route-report', type=Path, required=True)
    parser.add_argument('--reference-trace', type=Path)
    args = parser.parse_args()
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    cue = args.cue.resolve()
    bins = re.findall(r'^FILE "([^"]+)" BINARY$', cue.read_text(), re.M)
    assert len(bins) == 1
    disc = cue.parent / bins[0]
    assert sha(disc) == args.expected_bin, 'disc changed since measurement began'
    log_path = args.folder / 'results.log'
    trace_path = args.folder / 'player-target-trace.txt'
    report = measure(log_path.read_text(), trace_path.read_text())
    route = json.loads(args.route_report.read_text())
    assert route['passed'] and route['disc_sha256'] == args.expected_bin, 'route did not pass on this disc'
    assert route['states'] == report['states'] and route['trace_sha256'] == sha(trace_path)
    report.update(measurement_complete=True, route_gate_passed=True,
                  disc_sha256=args.expected_bin, cue_sha256=sha(cue),
                  log_sha256=sha(log_path), trace_sha256=sha(trace_path),
                  route_report_sha256=sha(args.route_report),
                  instrumented_frame_profile='Frame profile:' in log_path.read_text(),
                  reference_trace_sha256=None, hardware_tested=False,
                  limits='One complete controller route; not whole-zone acceptance, original-console timing, or hardware performance.')
    root = Path(__file__).resolve().parents[1]
    report['checked_tool_sha256'] = {name: sha(root/'tools'/name) for name in
                                    ['emulator_test.c', 'act_pad_replay.h', 'act_pacing.py']}
    report['harness_binary_sha256'] = sha(root/'build/emulator_test')
    if args.reference_trace:
        # Absolute diagnostic sequence IDs differ with loading/title duration.
        # Controller inputs and all 16 semantic words must remain identical.
        data = lambda path: [row.split()[1:] for row in path.read_text().splitlines()]
        assert data(args.reference_trace) == data(trace_path), 'recorded route differs in inputs or gameplay state'
        report['reference_trace_sha256'] = sha(args.reference_trace)
    (args.folder / 'pacing-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f"Act pacing: {report['late']} late / {report['intervals']} intervals; peak {report['max_gap']}")
