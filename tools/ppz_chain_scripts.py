#!/usr/bin/env python3
"""Regenerate the chained PPZ route scripts tests/routes/ppz/pS.txt and pJ.txt
from their per-act legs.

pS = p0A + p1A + p2D.found (sequence: Act 1 A, Act 2 A, Act 3 D)
pJ = pJ0 + pJ1 + p2C       (journey: Good Future in all three acts)

A standalone replay treats pads past a script's end as neutral, so a leg may
end before its act does. Each leg is therefore padded with neutral pads to the
pads its act consumes on the current host (tally sequence - 1), measured by a
host replay (tools/cc_campaign_search.c PPZ mode), and the legs are then
concatenated as "COUNT PAD" runs.

usage: tools/ppz_chain_scripts.py [--check] [--host PATH]
  --check  exit 1 if the committed pS/pJ differ from the regenerated output.
  --host   use this cc_campaign_search binary instead of building one.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / 'tests/routes/ppz'
CHAINS = {'pS': [('p0:A', 'p0A'), ('p1:A', 'p1A'), ('p2:D', 'p2D.found')],
          'pJ': [('pJ0', 'pJ0'), ('pJ1', 'pJ1'), ('p2:C', 'p2C')]}


def build_host():
    host = ROOT / 'build/ppz_route_host'
    host.parent.mkdir(exist_ok=True)
    native = [f'src/{n}.c' for n in ('title_card', 'world', 'act', 'player', 'camera_v', 'sonic_animation',
                                      'stage', 'boss', 'boss_r3', 'objects')]
    original = [f'build/probe-source/{n}.c' for n in ('boss_1', 'boss_3', 'playsp3', 'interaction', 'player',
                                                      'dircol', 'fcol', 'etc', 'equ', 'movement')]
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source',
                    '-DR1', '-DR11A', 'tools/cc_campaign_search.c', *native, *original, '-o', host],
                   cwd=ROOT, check=True)
    return host


def pads(path):
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            count, pad = map(int, line.split())
            out += [pad] * count
    return out


def leg(host, mode, name):
    script = ROUTES / f'{name}.txt'
    # Level-select entry (the chains start acts as src/main.c's act change does).
    env = {k: v for k, v in os.environ.items() if k != 'PPZ_DIRECT_ENTRY'}
    log = subprocess.run([host, 'replay', mode, script, '40000', '/dev/null'], cwd=ROOT, env=env,
                         capture_output=True, text=True).stderr
    tally = re.search(r'Tally complete: sequence=(\d+)', log)
    if not tally:
        sys.exit(f'{name}: leg does not reach the tally on this host')
    used = int(tally[1]) - 1
    legpads = pads(script)
    # Pads after the tally update are never read; the chain drops them.
    return legpads[:used] + [0] * (used - len(legpads))


def render(allpads):
    runs, i = [], 0
    while i < len(allpads):
        j = i
        while j < len(allpads) and allpads[j] == allpads[i]:
            j += 1
        runs.append(f'{j - i} {allpads[i]}')
        i = j
    return '\n'.join(runs) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', type=Path)
    args = parser.parse_args()
    host = args.host or build_host()
    stale = []
    for name, legs in CHAINS.items():
        text = render(sum((leg(host, mode, n) for mode, n in legs), []))
        path = ROUTES / f'{name}.txt'
        if args.check:
            if path.read_text() != text:
                stale.append(name)
        else:
            path.write_text(text)
    if args.check:
        if stale:
            sys.exit('FAIL: stale chained scripts: ' + ', '.join(stale) + ' (run tools/ppz_chain_scripts.py)')
        print('PASS: pS and pJ equal their regenerated legs')
    else:
        print('wrote ' + ', '.join(f'{n}.txt' for n in CHAINS))


if __name__ == '__main__':
    main()
