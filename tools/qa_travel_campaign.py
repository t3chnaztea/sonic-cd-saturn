#!/usr/bin/env python3
"""Seeded natural-travel controller mutations, seven zones and both presets.

Reuses existing travel search adapters without changing gameplay. A committed
natural warp is observed, not a successful arrival. No hardware acceptance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import qa_campaign as q

ROOT = q.ROOT


def compile_host(zone, flags, out):
    module = importlib.import_module(f'test_{zone}_travel')
    source = module.host_source(1)
    kind = 'cc' if zone in ('ppz', 'cc') else zone
    _, native, original, extra = q.hosts.HOSTS[kind]
    folder = out / f'{zone}-{flags}'
    folder.mkdir()
    generated = folder / 'host.c'
    generated.write_text(q.instrument(source))
    exe = folder / 'host'
    cmd = ['nice', '-n', '20', 'clang', '-std=gnu11', '-O1', '-fsigned-char', '-fwrapv',
           '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
           '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
           '-Isrc', '-Itools', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
           f'-DSCD_PLUS_HOST_FLAGS={flags}', *extra, str(generated), *native,
           'src/player_plus.c', *[f'build/probe-source/{n}.c' for n in q.hosts.CORE + original], '-o', str(exe)]
    with (folder / 'compile.log').open('w') as log:
        subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=log, check=True, timeout=300)
    return (zone, flags), dict(path=str(exe), sha256=q.digest(exe), command=cmd,
                              observer_source_sha256=q.digest(generated))


def run_case(zone, flags, seed, args, out, executables):
    folder = out / f'{zone}-{flags}' / str(seed)
    folder.mkdir()
    original = ROOT / f'tests/routes/{zone}/travel/{zone}1AB.txt'
    pads = q.load_pad(original)
    mutated, mutation = q.mutate(pads[:min(len(pads), 1200)], seed, args.span)
    changed = mutated + pads[len(mutated):]
    pad = folder / 'pad.txt'
    q.write_pad(pad, changed)
    rows = folder / 'rows.txt'
    command = ['nice', '-n', '20', executables[(zone, flags)]['path'], 'replay',
               'p0:A' if zone == 'ppz' else '0:A', str(pad),
               '40000' if zone in ('ppz', 'cc') else '46000', str(rows)]
    prefix = 'PPZ_ROUTE' if zone == 'ppz' else 'CC_ROUTE' if zone == 'cc' else 'TT_ROUTE' if zone == 'tt' else 'QQ_ROUTE'
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SCD_', 'CC_', 'PPZ_', 'TT_', 'QQ_'))}
    env.update({prefix + '_TRACE': '1', 'ASAN_OPTIONS': 'detect_leaks=0', 'SCD_CAMPAIGN_RELOADS': '1'})
    report = dict(status='pending', zone=zone, flags=flags, seed=seed, mutation=mutation,
                  command=command, original=str(original.relative_to(ROOT)),
                  original_sha256=q.digest(original), pad_sha256=q.digest(pad))
    q.save(folder / 'report.json', report)
    try:
        with (folder / 'host.log').open('w') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=log, timeout=120)
        text = (folder / 'host.log').read_text()
        report.update(q.classify(result.returncode, text, [Path(str(rows) + '.reload-0')]))
        report['rc'] = result.returncode
        report['natural_warp_commit'] = result.returncode == 0 and 'natural travel:' in text and 'destination=1' in text
        observed = max(0, report['executed_updates'] - 2)
        report['mutation']['changed_inputs_after_controller_delay'] = sum(a != b for a, b in zip(pads[:observed], changed[:observed]))
        report['status'] = 'failed' if report['failures'] else 'passed'
    except subprocess.TimeoutExpired:
        report.update(status='failed', failures=['timeout'])
    except BaseException:
        report.update(status='interrupted')
        raise
    finally:
        q.save(folder / 'report.json', report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--zones', default=','.join(q.ZONES))
    ap.add_argument('--seeds', type=int, default=10)
    ap.add_argument('--seed-start', type=int, default=9200)
    ap.add_argument('--span', type=int, default=12)
    ap.add_argument('--jobs', type=int, choices=range(1, 5), default=3)
    args = ap.parse_args()
    zones = args.zones.split(',')
    if any(z not in q.ZONES for z in zones) or min(args.seeds, args.span) < 1:
        ap.error('invalid zones/limits')
    if shutil.disk_usage(ROOT).free < 100 * 1024**3:
        ap.error('100 GiB reserve unavailable')
    out = ROOT / 'build/qa-campaign' / ('travel-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir()
    report = dict(status='pending', scope='mutated controller natural warp commitment; arrival unproven',
                  hardware_accepted=False, args=vars(args), runs=[], inputs={})
    for base in ('src', 'tools', 'tests/routes', 'assets/generated', 'build/probe-source'):
        for p in sorted((ROOT / base).rglob('*')):
            if p.is_file() and p.suffix.lower() in ('.c', '.h', '.inc', '.py', '.bin', '.txt', '.script', '.pads'):
                report['inputs'][str(p.relative_to(ROOT))] = q.digest(p)
    report['bin_sha256'] = q.digest(ROOT / 'dist/sonic-cd-saturn-prototype.bin')
    report['compiler'] = subprocess.check_output(['clang', '--version'], text=True)
    q.save(out / 'report.json', report)
    print(f'Travel campaign: {out}', flush=True)
    keys = [(z, f) for z in zones for f in (0, 31)]
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            executables = dict(pool.map(lambda k: compile_host(*k, out), keys))
        report['executables'] = {f'{z}-{f}': entry for (z, f), entry in executables.items()}
        tasks = [(z, f, s) for z, f in keys for s in range(args.seed_start, args.seed_start + args.seeds)]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for r in pool.map(lambda t: run_case(*t, args, out, executables), tasks):
                report['runs'].append(r)
                q.save(out / 'report.json', report)
        report['natural_warp_coverage'] = {f'{z}/{f}': sum(r.get('natural_warp_commit', False) and
            r['mutation'].get('changed_inputs_after_controller_delay', 0) > 0
            for r in report['runs'] if r['zone'] == z and r['flags'] == f) for z, f in keys}
        report['coverage_complete'] = all(report['natural_warp_coverage'].values())
        report['changed_inputs'] = [p for p, h in report['inputs'].items() if q.digest(ROOT / p) != h]
        report['status'] = 'failed' if report['changed_inputs'] or any(r['status'] != 'passed' for r in report['runs']) else 'passed'
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc))
        raise
    finally:
        q.save(out / 'report.json', report)
    print(f'{"PASS" if report["status"] == "passed" else "FAIL"}: travel campaign: '
          f'{len(report["runs"])} runs; natural-warp coverage {sum(v > 0 for v in report["natural_warp_coverage"].values())}/{len(keys)}')
    return report['status'] != 'passed'


if __name__ == '__main__':
    raise SystemExit(main())
