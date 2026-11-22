#!/usr/bin/env python3
"""End-to-end check of scroll-ir/1+r5 documents against the retail routine.

    python3 tools/scroll/R5/check_r5.py tools/scroll/R5/ir/*.json

1. Validates the documents (irc_r5.py), compiles them to C tables and links
   them with the generic evaluator (evaluate_r5.c) and check_r5.c.
2. For every document and variant, runs the retail scroll() through
   interp.py once per render window (the WINDOW/REACH choice of window for
   each background line, as extract.py makes it) and evaluates every line the
   window draws at 36 camera X values (including negative ones), 3 frame
   counts and 3 ramp values.  Layer positions are set to floor(C*x/256), the
   IR's own layer model.  Each retail value is compared with the compiled
   evaluator modulo 65536.
3. Compares the evaluator's background Y with the routine's at every camera
   Y 0..65535 for player X 0 and 0x7fff.
4. Checks that every value the evaluator returns for camera X 0..32767 lies
   between the smallest and largest layer position of that X (the
   plausible range), that lines retail leaves unwritten are exactly the
   document's overridden_lines, and that table rows the routine never writes
   evaluate to 0.
Any mismatch is counted, the first few are printed, and the exit status is 1.
"""
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import sym as S                   # noqa: E402
import extract as E               # noqa: E402  (R5 copy; also applies its UDIV patch)
import irc_r5                     # noqa: E402
from cfront import RETAIL         # noqa: E402

BUILD = HERE / 'build'


def compile_and_run(files):
    irs = [irc_r5.validate(json.loads(Path(f).read_text()), f) for f in files]
    BUILD.mkdir(exist_ok=True)
    tables = BUILD / 'tables_r5.c'
    irc_r5.emit_c(irs, tables)
    exe = BUILD / 'check_r5'
    cmd = ['cc', '-std=c99', '-O2', '-Wall', '-Werror', '-I', str(HERE), '-o', str(exe),
           str(HERE / 'check_r5.c'), str(HERE / 'evaluate_r5.c'), str(tables)]
    subprocess.run(cmd, check=True)
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
    raster, bgy = defaultdict(dict), defaultdict(dict)
    for line in out.splitlines():
        f = line.split()
        if f[0] == 'R':
            prog, when, x, frame, ramp = f[1], int(f[2]), int(f[3]), int(f[4]), int(f[5])
            raster[(prog, when)][(x, frame, ramp)] = list(map(int, f[6:]))
        else:
            prog, when, px = f[1], int(f[2]), int(f[3])
            bgy[(prog, when)][px] = list(map(int, f[4:]))
    return irs, raster, bgy


def top_for(R, y):
    ideal = max(0, (y - (E.DISPLAY - E.ROW)) & ~7)
    low = max(0, y - (E.DISPLAY - 1))
    for t in list(range(ideal, low - 1, -1)) + list(range(ideal + 1, y + 1)):
        if R.reachable(t):
            return t
    raise SystemExit(f'{R.name}: no reachable window shows line {y}')


def check(ir, raster, bgy):
    prog = ir['program']
    bad = defaultdict(int)
    shown_bad = []
    report = {}
    flag = ir['flag']
    for body in ir['variants']:
        when = body['when']
        key = (prog, -1 if when is None else when)
        fixed = [] if when is None else [(flag['name'], when)]
        R = E.Runner(RETAIL / prog, fixed)
        R.vertical_raw()
        _, m0 = R.window(0)
        model = E.Model(R, m0)
        overridden = {y for a, b in body['rules'].get('overridden_lines', []) for y in range(a, b + 1)}
        B = body['buffer_lines']
        n = {'compared': 0, 'unwritten_output': 0, 'unwritten_rows': 0}
        words = []
        for y in range(B):
            t = top_for(R, y)
            lines, _ = R.window(t)
            words.append(lines[y - t])
        for (x, frame, ramp), got in raster[key].items():
            env = {('var', 'X'): x, ('var', 'HZ'): 0, ('var', 'XS'): 0}
            pos = {'camera': x}
            for name, L in model.layers.items():
                p = (L['C'] * x) >> 8
                pos[name] = p
                env[('init', f'{name}.l')] = S.wrap((p & 0xFFFF) << 16, 32, True)
            lo = min(pos.values())
            hi = max(pos.values())
            for y, w in enumerate(words):
                if E.unwritten(w):
                    n['unwritten_output'] += 1
                    if y not in overridden:
                        bad['unwritten line not in overridden_lines'] += 1
                    continue
                src = getattr(w, 'src', None)
                if src is not None and S.un(w) == ('init', f'{src[0]}[{src[1] // 2}]', 16, True):
                    n['unwritten_rows'] += 1
                    if y < body['table_end'] or got[y] != 0:
                        bad['unwritten table row'] += 1
                    continue
                if y in overridden:
                    continue
                try:
                    retail = S.wrap(-S.evaluate(w, env), 16, True)
                except KeyError as e:
                    raise SystemExit(f'{prog}: line {y} depends on an input the check does not set: {e}')
                n['compared'] += 1
                if retail != S.wrap(got[y], 16, True):
                    bad['raster mismatch'] += 1
                    if len(shown_bad) < 5:
                        shown_bad.append(f'{prog} when={when} x={x} y={y}: retail {retail} IR {got[y]}')
                if 0 <= x <= 32767 and not lo <= got[y] <= hi:
                    bad['value outside the layer range'] += 1
                    if len(shown_bad) < 5:
                        shown_bad.append(f'{prog} when={when} x={x} y={y}: IR {got[y]} outside [{lo}, {hi}]')
        nb = 0
        for px, vals in bgy[key].items():
            for y in range(65536):
                env = S_Default({('var', 'Y'): y, ('var', 'PX'): px, ('var', 'VZ'): 0})
                want = S.wrap(S.evaluate(R.bgy_raw, env), 16, True)
                if want != S.wrap(vals[y], 16, True):
                    nb += 1
                    if len(shown_bad) < 5:
                        shown_bad.append(f'{prog} when={when} camera Y {y} player X {px}: retail {want} IR {vals[y]}')
        if nb:
            bad['background Y mismatch'] += nb
        n['bg_y_compared'] = 2 * 65536
        report[str(when)] = n
    return report, dict(bad), shown_bad


class S_Default(dict):
    def __missing__(self, key):
        return 0


def main():
    files = sys.argv[1:]
    if not files:
        raise SystemExit('usage: check_r5.py R5/ir/*.json')
    irs, raster, bgy = compile_and_run(files)
    failed = 0
    for ir in irs:
        report, bad, shown = check(ir, raster, bgy)
        status = 'OK' if not bad else 'FAIL'
        failed += bool(bad)
        print(f'{status} {ir["program"]}: ' + '; '.join(
            f'when {w}: {n["compared"]} raster values, {n["unwritten_output"]} unwritten output lines, '
            f'{n["unwritten_rows"]} unwritten rows, {n["bg_y_compared"]} bg Y' for w, n in report.items()))
        for k, v in bad.items():
            print(f'   {k}: {v}')
        for s in shown:
            print(f'   {s}')
    print(f'check_r5.py: {len(irs) - failed}/{len(irs)} documents match the retail routine')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
