#!/usr/bin/env python3
"""Bounded, hash-bound host exploration. Host evidence, never hardware acceptance.

Mutates controller recordings; observes checkpoints, death/warp and actor counts
before the existing hosts terminate. Same-process reloads test deterministic
cleanup. Missing lifecycle coverage remains explicit in the report.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import time

import cdpp_fuzz as hosts

ROOT = Path(__file__).resolve().parents[1]
ZONES = ('ppz', 'cc', 'tt', 'qq', 'ww', 'ss', 'mm')
CASES = [f'{z}{a}{e}' for z in ZONES for a, e in ((1, 'A'), (3, 'C'), (3, 'D'))]
OBSERVER = r'''{scd_checkpoint cp=scd_player_checkpoint();scd_world_state w=scd_world_get();
 unsigned alive=0;for(unsigned q=1;q<128;q++)alive+=actwk[q].actno!=0;
 if(sequence%120==0 || cp.id || dead || done)
 fprintf(stderr,"CAMPAIGN %u %u %u %u %u %u %d %u %u %u\n",sequence,
 (unsigned)cp.id,(unsigned)p.routine,(unsigned)p.resets,(unsigned)p.lives,w.era,w.destination,alive,dead,done);
 }
 '''
WRAPPER = r'''
int main(int argc,char **argv){
 const char *v=getenv("SCD_CAMPAIGN_RELOADS");unsigned n=v?(unsigned)atoi(v):1;
 if(!n || n>100 || argc<6)return 2;
 char *original=argv[5],path[4096];int rc=0;
 for(unsigned k=0;k<n;k++){
  if(snprintf(path,sizeof(path),"%s.reload-%u",original,k)>=(int)sizeof(path))return 2;
  argv[5]=path;fprintf(stderr,"CAMPAIGN_RELOAD %u\n",k);
  rc=campaign_original_main(argc,argv);if(rc!=0 && rc!=1 && rc!=3)break;
 }
 argv[5]=original;return rc;
}
'''


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, report):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, indent=2) + '\n')
    tmp.replace(path)


def load_pad(path):
    pads = []
    for line in path.read_text().splitlines():
        count, pad = map(int, line.split())
        if not 0 < count <= 48000 or pad & ~0xF1:
            raise ValueError(f'invalid controller row: {line}')
        pads.extend([pad] * count)
        if len(pads) > 48000:
            raise ValueError('recording too long')
    if not pads:
        raise ValueError('empty recording')
    return pads


def mutate(pads, seed, span=90):
    """Change one contiguous interval after title lock; retain route context."""
    rng = random.Random(seed)
    at = rng.randrange(min(180, len(pads) - 1), len(pads))
    end = min(len(pads), at + rng.randint(1, span))
    result = list(pads)
    for i in range(at, end):
        # One chosen legal action held for short intervals, including reversal.
        if i == at or (i - at) % 15 == 0:
            action = rng.choice([v for v in (0, 128, 129, 64, 65, 32, 33, 16, 17, 1) if v != pads[i]])
        result[i] = action
    return result, dict(start=at, end=end, changed=result != pads)


def write_pad(path, pads):
    rows = []
    for pad in pads:
        if rows and rows[-1][1] == pad:
            rows[-1][0] += 1
        else:
            rows.append([1, pad])
    path.write_text(''.join(f'{n} {p}\n' for n, p in rows))


def instrument(source):
    needle = 'if(dead){fprintf(stderr,"Route'
    if source.count(needle) != 1 or source.count('int main(int argc,char **argv)') != 1:
        raise ValueError('route host layout changed; observer needs review')
    source = source.replace(needle, OBSERVER + needle, 1)
    source = source.replace('int main(int argc,char **argv)',
                            'int campaign_original_main(int argc,char **argv)', 1)
    return source + WRAPPER


def compile_host(key, out):
    kind, flags = key
    source, native, original, extra = hosts.HOSTS[kind]
    generated = out / f'{kind}-{flags}.c'
    generated.write_text(instrument((ROOT / source).read_text()))
    exe = out / f'{kind}-{flags}'
    command = ['nice', '-n', '20', 'clang', '-std=gnu11', '-O1', '-fsigned-char',
               '-fwrapv', '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
               '-Isrc', '-Itools', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
               f'-DSCD_PLUS_HOST_FLAGS={flags}', *extra, str(generated), *native,
               'src/player_plus.c', *[f'build/probe-source/{n}.c' for n in hosts.CORE + original],
               '-o', str(exe)]
    with exe.with_suffix('.compile.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True, timeout=300)
    return key, dict(path=str(exe), sha256=digest(exe), command=command,
                     observer_sha256=digest(generated))


def classify(rc, log, traces):
    failures = []
    if rc not in (0, 1, 3):
        failures.append('host_exit')
    if re.search(r'AddressSanitizer|runtime error:|LeakSanitizer', log):
        failures.append('sanitizer')
    if not traces or any(not p.exists() for p in traces):
        failures.append('missing_trace')
    hashes = [digest(p) for p in traces if p.exists()]
    if hashes and len(set(hashes)) != 1:
        failures.append('reload_divergence')
    samples = []
    try:
        samples = [list(map(int, line.split()[1:])) for line in log.splitlines()
                   if line.startswith('CAMPAIGN ')]
        if not samples or any(len(row) != 10 for row in samples):
            failures.append('missing_or_invalid_observer')
            samples = [row for row in samples if len(row) == 10]
    except ValueError:
        failures.append('invalid_observer')
        samples = []
    rows = []
    for path in traces:
        if not path.exists():
            continue
        try:
            parsed = [[int(v) for v in line.split()] for line in path.read_text().splitlines()]
            if not parsed or any(len(row) != 13 for row in parsed):
                raise ValueError('expected nonempty 13-column trace')
            if any(b[0] != a[0] + 1 for a, b in zip(parsed, parsed[1:])):
                raise ValueError('nonconsecutive sequence')
            if any(not (0 <= row[2] <= 16383 and -512 <= row[3] <= 2560) for row in parsed):
                failures.append('bounds_candidate')
            rows = parsed
        except (OSError, ValueError):
            failures.append('invalid_trace')
    return dict(failures=failures, checkpoints=sorted({r[1] for r in samples if r[1]}),
                death_observed=any(r[2] >= 6 or r[3] for r in samples),
                warp_terminal=any(r[8] == 2 for r in samples),
                eras=sorted({r[5] for r in samples}),
                peak_actor_slots=max((r[7] for r in samples), default=0),
                tally='Tally complete:' in log, observations=len(samples), trace_hashes=hashes, executed_updates=len(rows))


def run_case(case, flags, seed, args, out, executables):
    folder = out / f'{case}-{flags}-{seed}'
    folder.mkdir()
    original = ROOT / 'tests/routes/cdpp/completion' / f'{case}.txt'
    if flags == 0:
        zone, act, era = case[:-2], int(case[-2]) - 1, case[-1]
        name = f'p{act}{era}.txt' if zone == 'ppz' else f'{case}.script' if zone == 'cc' else f'{case}.txt'
        if case == 'ppz3D':
            name = 'p2D.found.txt'
        original = ROOT / 'tests/routes' / zone / name
    original_pads = load_pad(original)
    reachable = min(len(original_pads), args.updates)
    chosen = original_pads[:min(reachable, args.mutation_before)]
    prefix, mutation = mutate(chosen, seed, args.span)
    pads = prefix + original_pads[len(prefix):reachable]
    script = folder / 'pad.txt'
    write_pad(script, pads)
    zone, act, era = case[:-2], int(case[-2]) - 1, case[-1]
    kind = zone if zone not in ('ppz', 'cc') else 'cc3' if zone == 'cc' and act == 2 else 'cc'
    pre = [] if kind == 'cc3' else [f'{"p" if zone == "ppz" else ""}{act}:{era}']
    post = [era] if kind == 'cc3' else []
    rows = folder / 'rows.txt'
    limit = min(args.updates, 40000 if kind in ('cc', 'cc3') else 46000)
    command = ['nice', '-n', '20', executables[(kind, flags)]['path'], 'replay',
               *pre, str(script), *post, str(limit), str(rows)]
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SCD_', 'CC_', 'PPZ_', 'TT_', 'QQ_'))}
    prefix = 'CC_ROUTE' if zone == 'cc' else 'PPZ_ROUTE' if zone == 'ppz' else 'TT_ROUTE' if zone == 'tt' else 'QQ_ROUTE'
    env.update({prefix + '_TRACE': '1', 'ASAN_OPTIONS': 'detect_leaks=0',
                'SCD_CAMPAIGN_RELOADS': str(args.reload_cycles)})
    result = dict(case=case, flags=flags, seed=seed, status='pending', mutation=mutation,
                  original_recording=str(original.relative_to(ROOT)), original_sha256=digest(original), pad_sha256=digest(script), command=command)
    # Persist only controlled overrides, never the inherited environment.
    result['environment'] = {k: env[k] for k in (prefix + '_TRACE', 'ASAN_OPTIONS', 'SCD_CAMPAIGN_RELOADS')}
    save(folder / 'report.json', result)
    start = time.monotonic()
    try:
        with (folder / 'host.log').open('w') as log:
            rc = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=log,
                                timeout=args.timeout).returncode
        result.update(classify(rc, (folder / 'host.log').read_text(),
                               [Path(str(rows) + f'.reload-{i}') for i in range(args.reload_cycles)]))
        # Hosts sample controller input two updates before player consumption.
        observed = max(0, result['executed_updates'] - 2)
        applied = sum(a != b for a, b in zip(original_pads[:observed], pads[:observed]))
        result['mutation']['changed_inputs_after_controller_delay'] = applied
        result.update(rc=rc, status='failed' if result['failures'] else 'passed')
    except subprocess.TimeoutExpired:
        result.update(status='failed', failures=['timeout'])
    except BaseException:
        result.update(status='interrupted')
        save(folder / 'report.json', result)
        raise
    result['seconds'] = round(time.monotonic() - start, 3)
    save(folder / 'report.json', result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases', default=','.join(CASES))
    ap.add_argument('--seeds', type=int, default=3)
    ap.add_argument('--seed-start', type=int, default=8100)
    ap.add_argument('--mutation-before', type=int, default=2500)
    ap.add_argument('--span', type=int, default=90)
    ap.add_argument('--updates', type=int, default=20000)
    ap.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    ap.add_argument('--reload-cycles', type=int, choices=(1,), default=1, help='reload gate pending a reset-safe lifecycle harness')
    ap.add_argument('--timeout', type=int, default=120)
    args = ap.parse_args()
    cases = args.cases.split(',')
    if any(c not in CASES for c in cases) or min(args.seeds, args.span, args.timeout, args.mutation_before) < 1 or not 10 <= args.updates <= 46000:
        ap.error('invalid cases or limits')
    if shutil.disk_usage(ROOT).free < 100 * 1024**3:
        ap.error('100 GiB reserve unavailable')
    out = ROOT / 'build/qa-campaign' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True)
    report = dict(status='pending', scope='instrumented host only', hardware_accepted=False,
                  args=vars(args), runs=[], source_hashes={}, coverage_complete=False)
    for base in ('src', 'tools', 'tests/routes', 'assets/generated', 'build/probe-source'):
        for p in sorted((ROOT / base).rglob('*')):
            if p.is_file() and p.suffix.lower() in ('.c', '.h', '.inc', '.py', '.bin', '.txt', '.script', '.pads'):
                report['source_hashes'][str(p.relative_to(ROOT))] = digest(p)
    binfile = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
    report['bin_sha256'] = digest(binfile) if binfile.exists() else None
    report['compiler'] = subprocess.check_output(['clang', '--version'], text=True)
    save(out / 'report.json', report)
    print(f'Campaign: {out}', flush=True)
    try:
        keys = set()
        for case in cases:
            z = case[:-2]
            kind = z if z not in ('ppz', 'cc') else 'cc3' if case == 'cc3C' or case == 'cc3D' else 'cc'
            keys.update((kind, f) for f in (0, 31))
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            executables = dict(pool.map(lambda k: compile_host(k, out), sorted(keys)))
        report['executables'] = {f'{k[0]}-{k[1]}': v for k, v in executables.items()}
        save(out / 'report.json', report)
        tasks = [(c, f, s) for c in cases for f in (0, 31)
                 for s in range(args.seed_start, args.seed_start + args.seeds)]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for result in pool.map(lambda t: run_case(*t, args, out, executables), tasks):
                report['runs'].append(result)
                save(out / 'report.json', report)
        report['mutation_coverage'] = {
            f'{case}/{flags}': sum(r['mutation'].get('changed_inputs_after_controller_delay', 0) > 0
                                 for r in report['runs'] if r['case'] == case and r['flags'] == flags)
            for case in cases for flags in (0, 31)}
        report['mutation_coverage_complete'] = all(report['mutation_coverage'].values())
        report['changed_inputs'] = [p for p, h in report['source_hashes'].items() if digest(ROOT / p) != h]
        report['status'] = 'failed' if report['changed_inputs'] or any(r['status'] != 'passed' for r in report['runs']) else 'passed'
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc))
        raise
    finally:
        save(out / 'report.json', report)
    failed = sum(r['status'] != 'passed' for r in report['runs'])
    print(f'{"PASS" if report["status"] == "passed" else "FAIL"}: QA campaign host batch: '
          f'{len(report["runs"])} runs, {failed} findings; lifecycle coverage requires review')
    return report['status'] != 'passed'


if __name__ == '__main__':
    raise SystemExit(main())
