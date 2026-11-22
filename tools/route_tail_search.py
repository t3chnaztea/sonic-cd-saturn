#!/usr/bin/env python3
"""Re-search only the tail of a stored pad route, keeping its prefix.

usage: route_tail_search.py HOST ACT:ERA SCRIPT KEEP OUT [--seed N] [--iterations N]

HOST is a route host built by the zone's route tool (for Quartz Quadrant
build/qq<act>/controller/qq_route_search, built by tools/test_qq_route.py).
Its ``search`` mode takes a prefix script: it steps the prefix, then runs the
fixed-seed Go-Explore search from there. KEEP is the number of pads (script
updates, not native sequences) kept from SCRIPT. The found script is checked to
start with exactly those KEEP pads (a run that continues across the cut is
merged into one ``COUNT PAD`` line, which is the same pad sequence) and written
to OUT. Exit status: the host's (0 found a finishing route, 1 best effort, 2
prefix died) or 3 when the prefix check fails.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
# Batch job: yield the CPU to foreground work (SCD_NICE=0 disables).
try:
    os.nice(int(os.environ.get('SCD_NICE', '20')))
except PermissionError:  # already at the lowest priority
    pass


def pads(path):
    out = []
    for line in Path(path).read_text().split('\n'):
        if line.strip():
            n, pad = map(int, line.split())
            out += [pad] * n
    return out


def write(path, seq):
    lines, i = [], 0
    while i < len(seq):
        j = i
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        lines.append(f'{j - i} {seq[i]}')
        i = j
    Path(path).write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('host'); ap.add_argument('window'); ap.add_argument('script')
    ap.add_argument('keep', type=int); ap.add_argument('out')
    ap.add_argument('--seed', type=int, default=51)
    ap.add_argument('--iterations', type=int, default=200000)
    ap.add_argument('--aligned', metavar='ENV:HELD:LEAD',
                    help='search under retail-aligned timing, as tools/retail_parity.py replays: '
                         'set ENV (e.g. QQ_ROUTE_UNLOCK_AT) to HELD and lead the prefix with LEAD '
                         'neutral pads (held_unlock - unlock); the lead is stripped from OUT')
    a = ap.parse_args()
    old = pads(a.script)
    assert 0 < a.keep <= len(old), (a.keep, len(old))
    env, lead = dict(os.environ), 0
    if a.aligned:
        name, held, lead = a.aligned.split(':')
        env[name] = held
        lead = int(lead)
    prefix = Path(a.out).with_suffix('.prefix.txt')
    write(prefix, [0] * lead + old[:a.keep])
    rc = subprocess.run([a.host, 'search', a.window, str(a.seed), str(a.iterations), a.out, str(prefix)], env=env).returncode
    if Path(a.out).exists() and lead:
        found = pads(a.out)
        assert found[:lead] == [0] * lead
        write(a.out, found[lead:])
    if Path(a.out).exists() and pads(a.out)[:a.keep] != old[:a.keep]:
        print('prefix changed', file=sys.stderr)
        return 3
    return rc


if __name__ == '__main__':
    sys.exit(main())
