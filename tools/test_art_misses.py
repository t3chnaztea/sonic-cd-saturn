#!/usr/bin/env python3
"""Art-miss gate: object draws with no art of their own (emulator evidence only).

Runs every stored route window (acts 1 and 2 in four eras, act 3 in both
Futures) on the Saturn build with SCD_ZONE_ROUTE_ART_MISS. src/main.c records
each draw that reaches the common atlas's default pose (any type but spikes and
the boulder: a zone object whose zone-art lookup missed, drawn as a PPZ rock)
and each zone-art record miss (Metallic Madness). tools/emulator_test.c prints
each new (type, subtype, pose) with the route update that first drew it, and
every 300 updates the draw counts.

Usage: python3 tools/test_art_misses.py [--zones ppz,cc,tt,qq,ww,ss,mm] [--jobs 2]
Writes build/art-misses/report.json. PASS needs every window to finish its route
and record no miss. Not a hardware result.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from qa_limits import worker_limit, emulator_limit

ROOT = Path(__file__).resolve().parents[1]
ZONES = ('ppz', 'cc', 'tt', 'qq', 'ww', 'ss', 'mm')
WINDOWS = [(a, e) for a in (1, 2) for e in 'ABCD'] + [(3, 'C'), (3, 'D')]


def runner(zone, act):
    if zone == 'tt':
        return ['tools/test_tt_route.py', '--act', str(act)], f'build/tt{act}/controller'
    if zone in ('qq', 'ww', 'ss', 'mm'):
        return ['tools/test_qq_route.py', *([] if zone == 'qq' else ['--' + zone]), '--act', str(act)], f'build/{zone}{act}/controller'
    if zone == 'ppz':
        return ['tools/test_ppz_route.py', '--act', str(act)], f'build/ppz{act}/controller'
    if act < 3:
        return ['tools/test_cc2_route.py', '--act', str(act)], f'build/cc{act}/controller'
    return ['tools/test_cc3_route.py'], 'build/cc3/controller'


def symbols():
    listing = subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm', ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    table = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    return table['_scd_art_miss_mailbox'], table['_scd_art_miss_counts']


def window(zone, act, era, mailbox):
    cmd, base = runner(zone, act)
    env = dict(os.environ, SCD_ZONE_ROUTE_ART_MISS=','.join(mailbox))
    start = time.time()
    proc = subprocess.run(['nice', '-n', '20', sys.executable, *cmd, '--era', era, '--no-retail'], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    status = (proc.stdout.strip().splitlines() or [''])[-1]
    if not status:  # the tool died before printing: keep its error
        status = 'no output; ' + ' | '.join(proc.stderr.strip().splitlines()[-2:])
    log = ROOT/base/era/'results.log'
    # A log from an earlier run (another gate, or a route tool that stopped early) is not evidence.
    if log.exists() and log.stat().st_mtime < start - 1:
        return {'window': f'{zone.upper()}{act}{era}', 'route_passed': False,
                'status': ('stale ' + str(log.relative_to(ROOT)) + '; ' + status)[:300], 'misses': [], 'overflow': False}
    first, counts, overflow, rows = {}, {}, False, 0
    if log.exists():
        for line in log.read_text(errors='replace').splitlines():
            if line.startswith('Art miss new: '):
                seq, key = line.split()[3:5]
                first.setdefault(int(key, 16), int(seq))
            elif line.startswith('Art miss counts: '):
                rows += 1
                parts = line.split()[3:]
                overflow = overflow or bool(int(parts[1]) & 256)
                counts = {int(k, 16): int(c) for k, c in (p.split(':') for p in parts[2:])}
    misses = [{'type': k >> 16, 'subtype': k >> 8 & 255, 'pose': k & 255, 'first_update': first.get(k),
               'draws': counts.get(k, 1)} for k in sorted(set(first) | set(counts))]
    # No count rows means the recorder was not read (an old build or runner): not a pass.
    if not rows:
        status = 'no art-miss rows in ' + str(log.relative_to(ROOT)) + '; ' + status
    return {'window': f'{zone.upper()}{act}{era}', 'route_passed': proc.returncode == 0 and status.startswith('PASS') and rows > 0,
            'status': status[:300], 'misses': misses, 'overflow': overflow}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--zones', default=','.join(ZONES))
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    try:
        args.jobs = emulator_limit(worker_limit(args.jobs))
    except ValueError as error:
        parser.error(str(error))
    zones = [z for z in args.zones.split(',') if z]
    assert all(z in ZONES for z in zones), zones
    mailbox = symbols()
    # Windows of one act share the route tool's build folder (its compiled host and
    # emulator, and each era's results.log): run them one after another, and only
    # different folders in parallel.
    groups = {}
    for z in zones:
        for a, e in WINDOWS:
            groups.setdefault(runner(z, a)[1], []).append((z, a, e))
    with ThreadPoolExecutor(args.jobs) as pool:
        done = dict(zip(groups, pool.map(lambda g: [window(*j, mailbox) for j in groups[g]], groups)))
    results = [r for g in groups for r in done[g]]
    out = ROOT/'build/art-misses'
    out.mkdir(parents=True, exist_ok=True)
    disc = ROOT/'dist/sonic-cd-saturn-prototype.bin'
    import hashlib
    report = {'disc_sha256': hashlib.sha256(disc.read_bytes()).hexdigest(), 'hardware_tested': False, 'windows': results}
    bad = [r for r in results if r['misses'] or r['overflow'] or not r['route_passed']]
    report['passed'] = not bad
    (out/'report.json').write_text(json.dumps(report, indent=1) + '\n')
    for r in results:
        line = ' '.join(f"{m['type']}/{m['subtype']}/{m['pose']}@{m['first_update']}x{m['draws']}" for m in r['misses'])
        flag = '' if r['route_passed'] else ' (route did not pass: ' + r['status'][:80] + ')'
        print(f"{r['window']}: {len(r['misses'])} misses{' (overflow)' if r['overflow'] else ''}{flag} {line}".rstrip())
    total = sum(len(r['misses']) for r in results)
    print(('PASS' if not bad else 'FAIL') + f': art misses {total} in {len(results)} windows, {out/"report.json"}')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
