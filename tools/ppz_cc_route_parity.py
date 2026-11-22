#!/usr/bin/env python3
"""Whole-route retail parity for the PPZ and CC campaign and travel routes.

The zone gates compare ten level-select windows per zone with the retail act
program (tools/retail_parity.py). This diagnostic runs the same comparison on
the routes the gates do not cover: the PPZ journey legs (pJ0, pJ1), the CC
campaign scripts (campaign-cc1, generator, campaign-good, campaign-bad) and
the natural-travel scripts (tests/routes/{ppz,cc}/travel). Host:
tools/cc_campaign_search.c in each route's own mode. Retail:
tools/retail_probe.py --round 1|3 from level-select entry of the route's start
act and era.

The retail probe follows one era program only: rows stop when the level
program hands off (time warp or tally), so a journey route is compared up to
its first warp. Travel routes end at the warp commit and are compared whole.
Evidence, not a pass gate; writes build/route-parity/<route>/report.json and
one summary line per route.

usage: ppz_cc_route_parity.py [ROUTE ...]   (default: all; names as below)
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import retail_parity as rp  # noqa: E402
from test_ppz_route import NATIVE, ORIGINAL  # noqa: E402

OUT = ROOT / 'build/route-parity'
# name: (script, host mode, env prefix, round, 1-based act, start era)
ROUTES = {
    'pJ0': ('tests/routes/ppz/pJ0.txt', 'pJ0', 'PPZ_ROUTE', 1, 1, 'A'),
    'pJ1': ('tests/routes/ppz/pJ1.txt', 'pJ1', 'PPZ_ROUTE', 1, 2, 'A'),
    'campaign-cc1': ('tests/routes/cc/campaign-cc1.script', '0', 'CC_ROUTE', 3, 1, 'A'),
    'generator': ('tests/routes/cc/generator.script', '0@B', 'CC_ROUTE', 3, 1, 'B'),
    'campaign-good': ('tests/routes/cc/campaign-good.script', '1', 'CC_ROUTE', 3, 2, 'A'),
    'campaign-bad': ('tests/routes/cc/campaign-bad.script', '1:A', 'CC_ROUTE', 3, 2, 'A'),
}
for _a in (1, 2):
    for _pair in ('AB', 'AD', 'BA', 'CA', 'DA'):
        ROUTES[f'ppz{_a}{_pair}'] = (f'tests/routes/ppz/travel/ppz{_a}{_pair}.txt', f'p{_a - 1}:{_pair[0]}', 'PPZ_ROUTE', 1, _a, _pair[0])
        ROUTES[f'cc{_a}{_pair}'] = (f'tests/routes/cc/travel/cc{_a}{_pair}.txt', f'{_a - 1}:{_pair[0]}', 'CC_ROUTE', 3, _a, _pair[0])


def main():
    names = sys.argv[1:] or list(ROUTES)
    OUT.mkdir(parents=True, exist_ok=True)
    host = OUT / 'cc_campaign_search'
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source',
                    '-DR1', '-DR11A', 'tools/cc_campaign_search.c', *NATIVE,
                    *[f'build/probe-source/{n}.c' for n in ORIGINAL], '-o', host], cwd=ROOT, check=True)
    env = {k: v for k, v in os.environ.items() if k != 'PPZ_DIRECT_ENTRY'}
    os.environ.clear()
    os.environ.update(env)
    for name in names:
        script, mode, prefix, round_no, act, era = ROUTES[name]
        out = OUT / name
        out.mkdir(parents=True, exist_ok=True)
        copy = out / 'script.txt'
        copy.write_text((ROOT / script).read_text())
        updates = sum(int(l.split()[0]) for l in copy.read_text().splitlines() if l.strip())
        report = dict(route=name, script=script, mode=mode, round=round_no, act=act, era=era,
                      script_sha256=rp.sha(copy), status='pending')
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        try:
            parity = rp.retail_parity(host, lambda h, s, rows, m=mode: [h, 'replay', m, s, '40000', rows], prefix,
                                      round_no, act, era, copy, out, updates, lag_sync=True, vint_offset=-1)
            report.update(status='measured', retail_parity=parity)
        except Exception as e:  # noqa: BLE001 - evidence run: record and continue
            report.update(status='failed', error=repr(e))
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        p = report.get('retail_parity', {})
        d = p.get('first_divergence') or {}
        f = p.get('first_field_divergence') or {}
        print(f"{name}: {report['status']} contiguous {p.get('contiguous')}/{p.get('compared')} "
              f"all-fields {p.get('contiguous_all_fields')} retail_rows {p.get('retail_updates')} "
              f"first_xy seq {d.get('sequence')} first_field seq {f.get('sequence')} {f.get('fields')}"
              + (f" error {report.get('error')}" if report['status'] == 'failed' else ''), flush=True)


if __name__ == '__main__':
    main()
