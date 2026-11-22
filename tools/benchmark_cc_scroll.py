#!/usr/bin/env python3
"""Benchmark the CC1 R3 line evaluator after its source/native parity gate.

Host time is useful for comparing evaluator revisions on the same machine; it
is not a Saturn frame-budget measurement.  The JSON report records source and
compiler identities so results with different inputs are not compared.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [
    Path('src/background_r3.c'),
    Path('src/background_r3.h'),
    Path('src/background_r3_tables.inc'),
    Path('tools/cc_scroll_benchmark.c'),
    Path('tools/benchmark_cc_scroll.py'),
    Path('tools/test_cc_scroll.py'),
]
RESULT = re.compile(
    r'^calls=(\d+) elapsed_ns=(\d+) ns_per_call=([0-9.]+) '
    r'fingerprint=([0-9a-f]+) sink=([0-9a-f]+)$'
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=int, default=20000)
    parser.add_argument('--samples', type=int, default=7)
    parser.add_argument('--skip-correctness', action='store_true',
                        help='skip test_cc_scroll.py when it already passed for identical inputs')
    args = parser.parse_args()
    if args.iterations <= 0 or args.samples < 3:
        parser.error('iterations must be positive and samples must be at least 3')

    correctness = None
    if not args.skip_correctness:
        checked = subprocess.run(
            [sys.executable, 'tools/test_cc_scroll.py'], cwd=ROOT,
            check=True, text=True, capture_output=True)
        correctness = checked.stdout.strip()
        print(correctness)

    out = ROOT/'build/cc1/scroll-benchmark'
    out.mkdir(parents=True, exist_ok=True)
    executable = out/'benchmark'
    compile_command = [
        'clang', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror',
        '-Isrc', 'tools/cc_scroll_benchmark.c', 'src/background_r3.c',
        '-o', str(executable),
    ]
    subprocess.run(compile_command, cwd=ROOT, check=True)
    compiler = subprocess.check_output(['clang', '--version'], text=True).splitlines()[0]

    samples = []
    fingerprint = None
    for _ in range(args.samples):
        line = subprocess.check_output(
            [executable, str(args.iterations)], cwd=ROOT, text=True).strip()
        match = RESULT.fullmatch(line)
        if not match:
            raise AssertionError(('unexpected benchmark output', line))
        calls, elapsed, per_call, current_fingerprint, sink = match.groups()
        if fingerprint is None:
            fingerprint = current_fingerprint
        assert current_fingerprint == fingerprint, 'output fingerprint changed between samples'
        samples.append({
            'calls': int(calls), 'elapsed_ns': int(elapsed),
            'ns_per_call': float(per_call), 'sink': sink,
        })

    timings = [sample['ns_per_call'] for sample in samples]
    report = {
        'passed': True,
        'correctness_gate': correctness,
        'iterations_per_sample': args.iterations,
        'sample_count': args.samples,
        'median_ns_per_call': statistics.median(timings),
        'minimum_ns_per_call': min(timings),
        'maximum_ns_per_call': max(timings),
        'output_fingerprint': fingerprint,
        'compiler': compiler,
        'compile_command': compile_command,
        'input_sha256': {str(path): sha256(ROOT/path) for path in INPUTS},
        'samples': samples,
        'limits': ('Host comparison benchmark only; use Saturn frame profiles for '
                   'hardware timing and test_cc_scroll.py for behavioral parity.'),
    }
    report_path = out/'report.json'
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'CC1 scroll benchmark: median {report["median_ns_per_call"]:.3f} ns/call '
          f'across {args.samples}x{args.iterations}; fingerprint {fingerprint}; '
          f'report {report_path}')


if __name__ == '__main__':
    main()
