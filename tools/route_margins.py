#!/usr/bin/env python3
"""Report how much margin each stored TT and QQ route keeps (evidence, not a gate).

A route that finishes with 4 air or one ring at a hit breaks on the next
retail-correct engine fix. This runs the existing route tools in their
host-only modes with the inventory diagnostics on (TT_TRACE + TT_TRACE_INVENTORY,
QQ_TRACE + QQ_TRACE_INVENTORY: rings, shield and, for TT, air per update) and
reads their logs. Nothing here re-implements a route check.

  windows   tools/test_<zone>_route.py --act N --era E --host-only: the plain
            host replay (host.log) and the retail-aligned replay that
            tools/retail_parity.py runs (native-lag.log, held unlock, retail
            V-INT lag). The retail probe is reused from its input-keyed cache
            (build/<zone><act>/controller/<era>/retail.key) or rerun.
  travel    tools/test_<zone>_travel.py --host-only per stored travel script.
  campaign  tools/test_<zone>_campaign.py --act N --host-only (no retail replay).

Per route: tally sequence (plain, aligned and the slack between them once the
aligned lead is removed), minimum air with its sequence (TT; plain and
aligned), hits (ring loss or shield loss) and the fewest rings held at a hit,
and the retail match (contiguous / compared, retail restart).

  --routes TT2D,QQ1A,TT1-campaign,TT1AB   only these (default: all)
  --kinds windows,travel,campaign
  --parse DIR    re-read a previous run's report.json instead of running

Writes build/route-margins/<YYYYmmdd-HHMMSS>/report.json and prints a table.
Emulator/host evidence only; never hardware acceptance.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
# Batch job: yield the CPU to foreground work (SCD_NICE=0 disables).
try:
    os.nice(int(os.environ.get('SCD_NICE', '20')))
except PermissionError:  # already at the lowest priority
    pass

ROOT = Path(__file__).resolve().parents[1]
ACT_ERAS = [(1, e) for e in 'ABCD'] + [(2, e) for e in 'ABCD'] + [(3, e) for e in 'CD']
TRAVEL = ('AB', 'AD', 'BA', 'CA', 'DA')
TALLY = re.compile(r'Tally complete: sequence=(\d+)(?: act=\d+ era=\d+ score=\d+)?(?: min_air=(\d+))?')
INVENTORY = re.compile(r'(?:TT|QQ) inventory: (\d+) rings=(\d+) shield=(\d+)(?: air=(-?\d+))?')
FAILED = re.compile(r'Route failed at (\d+)')


def trace_env(zone):
    z = zone.upper()
    return {f'{z}_TRACE': '0:999999', f'{z}_TRACE_INVENTORY': '1'}


def read_log(path):
    """Tally, minimum air and hits from one replay log (stderr of a host replay)."""
    res = dict(log=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))
    if not path.exists():
        return dict(res, error='missing log')
    text = path.read_text(errors='replace')
    tally, fail = TALLY.search(text), FAILED.search(text)
    res['tally'] = int(tally[1]) if tally else None
    if tally and tally[2] is not None:
        res['tally_min_air'] = int(tally[2])
    if fail:
        res['failed_at'] = int(fail[1])
    rows = [tuple(int(v) if v is not None else None for v in m.groups()) for m in INVENTORY.finditer(text)]
    if not rows:
        return dict(res, inventory=False)
    res['inventory'] = True
    hits, prev = [], None
    for seq, rings, shield, air in rows:
        if prev:
            if rings < prev[1]:
                hits.append(dict(sequence=seq, rings=prev[1], kind='rings'))
            elif shield < prev[2] and prev[2]:
                hits.append(dict(sequence=seq, rings=prev[1], kind='shield'))
        prev = (seq, rings, shield)
    res['hits'] = hits
    res['min_rings_at_hit'] = min((h['rings'] for h in hits), default=None)
    airs = [(air, seq) for seq, _, _, air in rows if air is not None]
    if airs:
        res['min_air'], res['min_air_sequence'] = min(airs)
    return res


def run(cmd, log, env):
    with open(log, 'w') as f:
        return subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, **env), stdout=f, stderr=subprocess.STDOUT).returncode


def window(zone, act, era, out):
    base = ROOT/f'build/{zone}{act}/controller'/era
    rc = run(['python3', f'tools/test_{zone}_route.py', '--act', str(act), '--era', era, '--host-only'],
             out/f'{zone.upper()}{act}{era}.log', trace_env(zone))
    rep = json.loads((base/'report.json').read_text()) if (base/'report.json').exists() else {}
    parity = rep.get('retail_parity') or {}
    res = dict(kind='window', exit_code=rc, status=rep.get('status'), script=f'tests/routes/{zone}/{zone}{act}{era}.txt',
               plain=read_log(base/'host.log'), aligned=read_log(base/'native-lag.log'))
    lead = parity.get('held_unlock', 0) - parity.get('unlock', 0) if parity else 0
    res['retail'] = {k: parity.get(k) for k in ('contiguous', 'compared', 'retail_restart', 'retail_updates')}
    res['aligned_lead'] = lead
    if res['plain'].get('tally') and res['aligned'].get('tally'):
        res['tally_slack'] = res['aligned']['tally'] - lead - res['plain']['tally']
    return res


def derived(zone, kind, name, cmd, out):
    dest = out/kind/name
    rc = run(cmd + ['--output', str(dest)], out/f'{name}.log', trace_env(zone))
    rep = json.loads((dest/'report.json').read_text()) if (dest/'report.json').exists() else {}
    return dict(kind=kind, exit_code=rc, status=rep.get('status'), script=rep.get('script_source'),
                plain=read_log(dest/'host-replay.log'))


def routes(kinds, only):
    for zone in ('tt', 'qq'):
        z = zone.upper()
        if 'windows' in kinds:
            for act, era in ACT_ERAS:
                yield f'{z}{act}{era}', lambda out, a=act, e=era, zz=zone: window(zz, a, e, out)
        if 'travel' in kinds:
            for act in (1, 2):
                for pair in TRAVEL:
                    name = f'{z}{act}{pair}'
                    cmd = ['python3', f'tools/test_{zone}_travel.py', '--act', str(act), '--era', pair[0], '--to', pair[1],
                           '--script', f'tests/routes/{zone}/travel/{zone}{act}{pair}.txt', '--host-only']
                    yield name, lambda out, n=name, c=cmd, zz=zone: derived(zz, 'travel', n, c, out)
        if 'campaign' in kinds:
            for act in (1, 2, 3):
                name = f'{z}{act}-campaign'
                cmd = ['python3', f'tools/test_{zone}_campaign.py', '--act', str(act), '--host-only']
                yield name, lambda out, n=name, c=cmd, zz=zone: derived(zz, 'campaign', n, c, out)


def fmt(v):
    return '-' if v is None else str(v)


def table(results):
    head = f'{"route":<14} {"tally":>6} {"slack":>5} {"air":>9} {"@seq":>6} {"hits":>5} {"rings@hit":>9} {"retail":>13} {"restart":>7}'
    lines = [head, '-' * len(head)]
    for name, r in results.items():
        p, a = r.get('plain', {}), r.get('aligned') or {}
        air = fmt(p.get('min_air', p.get('tally_min_air')))
        if a:
            air += '/' + fmt(a.get('min_air', a.get('tally_min_air')))
        hits = fmt(len(p['hits']) if 'hits' in p else None) + ('/' + fmt(len(a['hits']) if 'hits' in a else None) if a else '')
        rings = fmt(p.get('min_rings_at_hit')) + ('/' + fmt(a.get('min_rings_at_hit')) if a else '')
        ret = r.get('retail') or {}
        retail = f'{fmt(ret.get("contiguous"))}/{fmt(ret.get("compared"))}' if ret else '-'
        tally = (fmt(p['tally']) if p.get('tally') else 'FAIL@' + fmt(p['failed_at']) if p.get('failed_at')
                 else r.get('status') if r.get('exit_code') == 0 else 'FAIL')
        lines.append(f'{name:<14} {tally:>6} {fmt(r.get("tally_slack")):>5} {air:>9} {fmt(p.get("min_air_sequence")):>6} '
                     f'{hits:>5} {rings:>9} {retail:>13} {fmt(ret.get("retail_restart")) if ret else "-":>7}')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--routes', help='comma list of route names (default all)')
    ap.add_argument('--kinds', default='windows,travel,campaign')
    ap.add_argument('--parse', type=Path, help='print a previous run report instead of running')
    a = ap.parse_args()
    if a.parse:
        print(table(json.loads((a.parse/'report.json').read_text())['routes']))
        return 0
    only = set(a.routes.split(',')) if a.routes else None
    out = ROOT/'build/route-margins'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = dict(git_head=git, dirty=bool(subprocess.run(['git', 'status', '--porcelain', '--', 'src', 'tools', 'tests'],
                                                           cwd=ROOT, capture_output=True, text=True).stdout.strip()),
                  routes={}, hardware_tested=False)
    for name, fn in routes(a.kinds.split(','), only):
        if only and name not in only:
            continue
        report['routes'][name] = dict(status='pending')
        (out/'report.json').write_text(json.dumps(report, indent=1) + '\n')
        report['routes'][name] = fn(out)
        (out/'report.json').write_text(json.dumps(report, indent=1) + '\n')
        print(name, 'done', file=sys.stderr, flush=True)
    print(table(report['routes']))
    print(f'REPORT: {out.relative_to(ROOT)}/report.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
