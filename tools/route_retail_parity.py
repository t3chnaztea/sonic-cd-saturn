#!/usr/bin/env python3
"""Whole-route retail parity for the TT and QQ campaign and travel routes.

The gate windows (tests/routes/<zone>/<zone><act><era>.txt) are compared with
the retail act programs by tools/test_tt_route.py and tools/test_qq_route.py.
This driver runs the same comparison (tools/retail_parity.py, retail program
through tools/retail_probe.py) over the routes those gates do not cover:

  tests/routes/<zone>/campaign/<zone><act>-good.txt  (Present start, era A)
  tests/routes/<zone>/travel/<zone><act><from><to>.txt

Evidence, not a pass gate. Writes build/route-parity/<zone>/<route>/ with the
retail_parity result in report.json and prints one line per route.

usage: route_retail_parity.py [--zone tt|qq] [ROUTE-NAME ...]
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import retail_parity as rp  # noqa: E402

ZONES = {
    'tt': dict(round=4, prefix='TT_ROUTE', source='tools/tt_route_search.c', test='test_tt_route'),
    'qq': dict(round=5, prefix='QQ_ROUTE', source='tools/qq_route_search.c', test='test_qq_route'),
}


def build_host(zone, out):
    spec = ZONES[zone]
    test = __import__(spec['test'])
    host = out / f'{zone}_route_search'
    original = [f'build/probe-source/{n}.c' for n in test.ORIGINAL]
    subprocess.run(['clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                    '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated',
                    '-Ibuild/probe-source', '-DR1', '-DR11A', spec['source'], *test.NATIVE, *original,
                    '-o', host], cwd=ROOT, check=True)
    return host


def routes(zone):
    base = ROOT / 'tests/routes' / zone
    for path in sorted((base / 'campaign').glob('*.txt')):
        yield path.stem, int(path.stem[2]), 'A', path
    for path in sorted((base / 'travel').glob('*.txt')):
        yield path.stem, int(path.stem[2]), path.stem[3], path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--zone', choices=sorted(ZONES), action='append')
    parser.add_argument('names', nargs='*')
    args = parser.parse_args()
    for zone in args.zone or sorted(ZONES, reverse=True):
        spec = ZONES[zone]
        base = ROOT / 'build/route-parity' / zone
        base.mkdir(parents=True, exist_ok=True)
        host = build_host(zone, base)
        for name, act, era, script in routes(zone):
            if args.names and name not in args.names:
                continue
            out = base / name
            out.mkdir(parents=True, exist_ok=True)
            updates = sum(int(line.split()[0]) for line in script.read_text().splitlines() if line.strip())
            report = dict(status='pending', zone=zone, route=str(script.relative_to(ROOT)), act=act, era=era,
                          script_sha256=rp.sha(script), host_sha256=rp.sha(host))
            (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            try:
                result = rp.retail_parity(host, lambda h, s, rows: [h, 'replay', f'{act - 1}:{era}', s, '46000', rows],
                                          spec['prefix'], spec['round'], act, era, script, out, updates + 200)
                report.update(status='done', retail_parity=result)
            except Exception as error:  # evidence run: record and continue
                report.update(status='failed', error=repr(error)[:1000])
            (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            p = report.get('retail_parity', {})
            first = p.get('first_field_divergence')
            print(f'{name}: contiguous {p.get("contiguous_all_fields")}/{p.get("compared")} xy {p.get("contiguous")} '
                  f'first {first and (first["sequence"], first["fields"])} native_end {p.get("native_end")} '
                  f'{report["status"]}', flush=True)


if __name__ == '__main__':
    main()
