#!/usr/bin/env python3
"""CD++ preset host fuzz: random pad scripts on every zone's Act 1 Present and Act 3
(Good Future, the boss act), with all five CD++ moves (flags 31).

The scripts favour Right, spin dash revs, jumps with a second press in the air (air
roll, homing attack) and short Left runs, so time posts, springs and badniks are met
on the way. Each replay runs on the zone's route host (cc_campaign_search,
cc3_route_host, tt_route_search, qq_route_search) linked with src/player_plus.c,
under AddressSanitizer and UndefinedBehaviorSanitizer. Failures:
  crash  the host stops on a signal or a sanitizer report (any exit but 0, 1, 3)
  oob    Sonic leaves the map while alive (x outside 0..16383, y outside -512..2560)
  stall  Sonic does not move for 600 updates while the pad holds a direction
Explicitly identified deaths and natural time warps are counted, not failures.
Ambiguous route stops remain unknown; no respawn or arrival is proven here.
--classic runs the same scripts with flags 0 for comparison. Host evidence only.

  python3 tools/cdpp_fuzz.py [--runs N] [--length N] [--classic] [--windows ppz1A,...]
"""
import argparse, datetime, hashlib, json, os, random, re, subprocess, sys, tempfile, time
from pathlib import Path
from qa_limits import worker_limit
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cdpp-fuzz'
BASE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c', 'src/sonic_animation.c',
        'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/objects.c']
CORE = ['interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
HOSTS = {
    'cc': ('tools/cc_campaign_search.c', BASE, ['boss_1', 'boss_3', 'playsp3'], []),
    'cc3': ('tools/cc3_route_host.c', BASE, ['boss_1', 'boss_3', 'playsp3'], []),
    'tt': ('tools/tt_route_search.c', BASE + ['src/boss_r4.c', 'src/water.c'], ['boss_1', 'boss_3', 'boss_4', 'playsp3'], []),
    'qq': ('tools/qq_route_search.c', BASE + ['src/boss_r4.c', 'src/boss_r5.c', 'src/water.c'],
           ['boss_1', 'boss_3', 'boss_4', 'boss_5', 'playsp3'], []),
}
for name, define, native, original in (('ww', 'ROUTE_WW', ['src/boss_r6.c', 'src/background_r6.c'], ['boss_6']),
                                       ('ss', 'ROUTE_SS', ['src/boss_r7.c'], ['boss_7']),
                                       ('mm', 'ROUTE_MM', ['src/boss_r8.c'], ['boss_8', 'ending_8'])):
    src, base, orig, _ = HOSTS['qq']
    HOSTS[name] = (src, base + native, orig + original, [f'-D{define}'])
# window: (host, replay argv before the script, argv after it, env prefix)
WINDOWS = {
    'ppz1A': ('cc', ['p0:A'], [], 'PPZ_ROUTE'), 'ppz3C': ('cc', ['p2:C'], [], 'PPZ_ROUTE'),
    'cc1A': ('cc', ['0:A'], [], 'CC_ROUTE'), 'cc3C': ('cc3', [], ['C'], 'CC_ROUTE'),
    'tt1A': ('tt', ['0:A'], [], 'TT_ROUTE'), 'tt3C': ('tt', ['2:C'], [], 'TT_ROUTE'),
    'qq1A': ('qq', ['0:A'], [], 'QQ_ROUTE'), 'qq3C': ('qq', ['2:C'], [], 'QQ_ROUTE'),
    'ww1A': ('ww', ['0:A'], [], 'QQ_ROUTE'), 'ww3C': ('ww', ['2:C'], [], 'QQ_ROUTE'),
    'ss1A': ('ss', ['0:A'], [], 'QQ_ROUTE'), 'ss3C': ('ss', ['2:C'], [], 'QQ_ROUTE'),
    'mm1A': ('mm', ['0:A'], [], 'QQ_ROUTE'), 'mm3C': ('mm', ['2:C'], [], 'QQ_ROUTE'),
}
R, L, D, U, J = 128, 64, 32, 16, 1
BUILD_FLAGS = ['-std=gnu11', '-O1', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
               '-Wno-parentheses', '-Wno-unused-value', '-w', '-fsanitize=address,undefined',
               '-fno-sanitize-recover=all', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A']
FAILURES = ('crash', 'timeout', 'trace_error', 'oob', 'stall')


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def build_manifest(sources, flags, extra):
    # Conservative transitive text-input inventory. Runtime binary assets are
    # outside this compiler cache; generated headers and included .inc files are not.
    inputs = {ROOT / source for source in sources}
    for directory in ('src', 'assets/generated', 'build/probe-source'):
        inputs.update(p for p in (ROOT / directory).rglob('*')
                      if p.is_file() and p.suffix.lower() in ('.c', '.h', '.inc'))
    inputs.update((ROOT / 'tools').glob('*.h'))
    compiler = subprocess.check_output(['clang', '--version'], text=True)
    return dict(compiler=compiler, flags=[*BUILD_FLAGS, f'-DSCD_PLUS_HOST_FLAGS={flags}', *extra],
                sources=sources, inputs={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in sorted(inputs)})


def host(name, flags):
    src, native, original, extra = HOSTS[name]
    sources = [src, *native, 'src/player_plus.c', *[f'build/probe-source/{n}.c' for n in CORE + original]]
    exe = OUT / 'hosts' / f'{name}-{flags}'
    exe.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(sources, flags, extra)
    stamp = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    mark = exe.with_suffix('.sha')
    if not (exe.exists() and mark.exists() and mark.read_text() == stamp):
        subprocess.run(['nice', '-n', '20', 'clang', *manifest['flags'], *sources, '-o', str(exe)],
                       cwd=ROOT, check=True, timeout=600)
        mark.write_text(stamp)
        save_json(exe.with_suffix('.inputs.json'), manifest)
    return exe


def script(rng, length):
    rows = [[160, 0]]
    while sum(n for n, _ in rows) < length:
        k = rng.random()
        if k < 0.2:    # spin dash: crouch, revs, release running
            rows += [[rng.randint(5, 15), D]] + [[1, D | J], [1, D]] * rng.randint(1, 5) + [[rng.randint(40, 120), R]]
        elif k < 0.5:  # jump, then a press in the air (air roll / homing attack)
            rows += [[rng.randint(1, 6), R | J], [rng.randint(4, 25), R], [1, R | J], [rng.randint(10, 50), R]]
        elif k < 0.65:
            rows += [[rng.randint(30, 120), R]]
        elif k < 0.75:  # a short run left, with a jump
            rows += [[rng.randint(10, 40), L], [1, L | J], [rng.randint(10, 30), L]]
        elif k < 0.85:  # up: a look, or the super peel-out with a press
            rows += [[rng.randint(5, 20), U], [1, U | J], [rng.randint(5, 30), U], [rng.randint(20, 60), R]]
        else:
            rows += [[rng.randint(5, 60), rng.choice([0, R, R | J, J, R | D])]]
    return rows


def terminal_kind(returncode, stderr):
    if returncode == 0:
        return 'complete'
    if returncode == 1:
        return 'limit'
    if returncode == 3:
        if re.search(r'\bdead=2\b', stderr):
            return 'warp'
        if re.search(r'\bdead=1\b|\bRoute died at\b', stderr):
            return 'death'
        # CC/PPZ use rc=3 for death, travel and rejected route conditions.
        # CC3 prints "warped" for both dead=2 and failed music checks (dead=3).
        return 'unknown_stop'
    return 'crash'


def run(window, flags, seed, length, output_root=None):
    name, pre, post, prefix = WINDOWS[window]
    root = output_root
    if root is None:
        OUT.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='case-', dir=OUT))
    folder = root / window / f'{seed}-{flags}'
    folder.mkdir(parents=True, exist_ok=False)
    pad = folder / 'pad.txt'
    pad.write_text(''.join(f'{n} {p}\n' for n, p in script(random.Random(seed), length)))
    rows_path = folder / 'trace.rows'
    result = dict(status='pending', passed=False, window=window, flags=flags, seed=seed,
                  length=length, updates=0, death=False, warp=False, artifacts=str(folder))
    save_json(folder / 'report.json', result)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SCD_', 'PPZ_', 'CC_', 'TT_', 'QQ_'))}
    env.update({f'{prefix}_TRACE': '1', 'ASAN_OPTIONS': 'detect_leaks=0'})
    try:
        argv = [str(host(name, flags)), 'replay', *pre, str(pad), *post, str(length), str(rows_path)]
        result.update(command=argv, pad_sha256=hashlib.sha256(pad.read_bytes()).hexdigest(),
                      host_sha256=hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest())
        r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        stdout, stderr = r.stdout, r.stderr
        result.update(rc=r.returncode, terminal=terminal_kind(r.returncode, stderr))
        if result['terminal'] == 'crash' or 'runtime error' in stderr or 'AddressSanitizer' in stderr:
            result['crash'] = (stderr.strip().splitlines() or ['unexpected exit'])[-1][:200]
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or '', exc.stderr or ''
        result.update(rc=None, terminal='timeout', timeout=600)
    except BaseException as exc:
        result.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                      error=f'{type(exc).__name__}: {exc}')
        save_json(folder / 'report.json', result)
        raise
    stdout = stdout.decode(errors='replace') if isinstance(stdout, bytes) else stdout
    stderr = stderr.decode(errors='replace') if isinstance(stderr, bytes) else stderr
    (folder / 'stdout.log').write_text(stdout)
    (folder / 'stderr.log').write_text(stderr)
    result['warp'] = result['terminal'] == 'warp'
    result['death'] = result['terminal'] == 'death'
    try:
        rows = [[int(v) for v in line.split()] for line in rows_path.read_text().splitlines()]
        if any(len(row) not in (4, 13) for row in rows):
            raise ValueError('expected 4 or 13 trace columns')
        if not rows and result['terminal'] in ('complete', 'limit'):
            raise ValueError('successful replay wrote no states')
        result['updates'] = len(rows)
        still = 0
        previous = None
        for row in rows:
            x, y = row[2:4]
            if not (0 <= x <= 16383 and -512 <= y <= 2560):
                result['oob'] = (row[0], x, y)
                break
            still = still + 1 if previous and previous[2:4] == row[2:4] and row[1] & (R | L) else 0
            if still == 600:
                result['stall'] = (row[0], x, y)
                break
            previous = row
    except (OSError, ValueError) as exc:
        result['trace_error'] = str(exc)
    result.update(status='failed' if any(k in result for k in FAILURES) else 'passed')
    result['passed'] = result['status'] == 'passed'
    save_json(folder / 'report.json', result)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--length', type=int, default=2000)
    ap.add_argument('--classic', action='store_true')
    ap.add_argument('--windows')
    ap.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    ap.add_argument('--seed-start', type=int, default=7000)
    args = ap.parse_args(argv)
    try:
        args.jobs = worker_limit(args.jobs)
    except ValueError as error:
        ap.error(str(error))
    windows = args.windows.split(',') if args.windows else list(WINDOWS)
    if args.runs < 1 or not 10 <= args.length <= 40000 or any(w not in WINDOWS for w in windows):
        ap.error('require runs >= 1, length 10..40000 and known windows')
    windows = list(dict.fromkeys(windows))
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=OUT))
    report = dict(status='pending', passed=False, hardware_tested=False, runs=args.runs,
                  length=args.length, seed_start=args.seed_start, jobs=args.jobs, windows=windows,
                  modes=[31, 0] if args.classic else [31], results=[], summary={}, failures={})
    save_json(output / 'report.json', report)
    # Build the hosts in parallel first (each is cached by its source hash).
    from concurrent.futures import ThreadPoolExecutor
    needed = sorted({(WINDOWS[w][0], f) for w in windows for f in ([31, 0] if args.classic else [31])})
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(lambda nf: host(*nf), needed))
        for flags in report['modes']:
            for w in windows:
                for i in range(args.runs):
                    report['results'].append(run(w, flags, args.seed_start + i, args.length, output))
                    save_json(output / 'report.json', report)
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                      error=f'{type(exc).__name__}: {exc}', seconds=round(time.time() - start, 1))
        save_json(output / 'report.json', report)
        raise
    results = report['results']
    summary = {}
    for res in results:
        s = summary.setdefault(f"{res['window']}/{res['flags']}",
                               dict(runs=0, deaths=0, warps=0, unknown_stops=0, **{k: [] for k in FAILURES}))
        s['runs'] += 1
        s['deaths'] += res['death']
        s['warps'] += res['warp']
        s['unknown_stops'] += res.get('terminal') == 'unknown_stop'
        for k in FAILURES:
            if k in res:
                s[k].append((res['seed'], res[k]))
    bad = {k: {f: v[f] for f in FAILURES if v[f]} for k, v in summary.items() if any(v[f] for f in FAILURES)}
    report.update(status='failed' if bad else 'passed', passed=not bad,
                  seconds=round(time.time() - start, 1), summary=summary, failures=bad)
    save_json(output / 'report.json', report)
    if bad:
        print(f'FAIL: CD++ fuzz: {json.dumps(bad)[:600]}; report={output / "report.json"}')
        return 1
    print(f'PASS: CD++ fuzz: {len(windows)} windows x {args.runs} runs x {args.length} updates; '
          f'modes={report["modes"]}; 0 crashes, 0 out-of-bounds, 0 stalls; '
          f'{sum(r["death"] for r in results)} deaths, {sum(r["warp"] for r in results)} time warps; '
          f'report={output / "report.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
