#!/usr/bin/env python3
"""Validate the round 8 scroll IR (tools/scroll/R8/ir/*.json).

    python3 tools/scroll/R8/validate.py            all ten documents
    python3 tools/scroll/R8/validate.py SCR83C     one

Writes only tools/scroll/R8/build/.  Exits 1 on any failure; every count is
printed.  For each document:

  1. schema      R8/irc.py validates it (the shared irc.py must reject it:
                 it uses vocabulary the shared ir.md does not have).
  2. coverage    every buffer line is exactly one of run / band / unwritten;
                 runs are contiguous from line 0 (no gap, no overlap).
  3. sweep       the C evaluator (R8/evaluate.c, via R8/check.c) over every
                 camera X in the stage's own limits and in 0..16383, every
                 line of two buffer heights, three frames: no crash, the
                 buffer wraps, no frame dependence, and every written line
                 inside [min layer - 1, max layer + 1] (camera included).
                 Out-of-range samples are counted and located, not hidden.
  4. windows     the retail routine, interpreted with camera X symbolic, for
                 every window top the stage can reach (every camera Y in its
                 own up..down limits) and for the WINDOW rule's top of every
                 buffer line; each shown line evaluated at 18 camera X values
                 against the C evaluator.
  5. trajectory  the retail routine run concretely from the stage start
                 (scr_set: scrbinit's own layer positions) for 700 frames
                 along a camera path that moves both ways over the whole
                 stage width and height; every rendered line and the
                 background Y compared with the C evaluator, every frame.
"""
import ctypes
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))

import extract as E          # noqa: E402  (R8/extract.py: same rules as the extraction)
import irc                   # noqa: E402  (R8/irc.py)
import sym as S              # noqa: E402
from cfront import RETAIL, programs   # noqa: E402

BUILD = HERE / 'build'
XS_CHECK = (0, 1, 2, 3, 7, 100, 111, 223, 224, 225, 1000, 2047, 2048, 3001, 3735, 4097, 7000, 7831)
FAILS = []


def bad(msg):
    FAILS.append(msg)
    print('  FAIL ' + msg)


def build(docs):
    BUILD.mkdir(exist_ok=True)
    irc.emit_c(docs, BUILD / 'tables.c')
    lib = BUILD / ('libr8check.dylib' if sys.platform == 'darwin' else 'libr8check.so')
    cmd = ['cc', '-std=c99', '-O2', '-Wall', '-Wno-unused-function', '-shared', '-fPIC', f'-I{HERE}',
           str(HERE / 'evaluate.c'), str(BUILD / 'tables.c'), str(HERE / 'check.c'), '-o', str(lib)]
    subprocess.run(cmd, check=True)
    L = ctypes.CDLL(str(lib))
    L.r8_layer.restype = ctypes.c_longlong
    L.r8_sweep.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_longlong)]
    return L


def slot_of(doc):
    rounds = sorted({r for r, a, e, p in programs()})
    s = doc['slot']
    return rounds.index(s['round']) * 12 + (s['act'] - 1) * 4 + 'ABCD'.index(s['era'])


def limits(runner):
    m = E._stage_machine(runner, [])
    m.call_function(E.STAGE_START)
    r = {k: E._read(m, k) for k in ('scralim_left', 'scralim_right', 'scralim_up', 'scralim_down',
                                    'scra_h_posit.w.h', 'scra_v_posit.w.h')}
    if not all(isinstance(v, int) for v in r.values()):
        raise SystemExit(f'{runner.name}: stage limits are not constants: {r}')
    return r


def layer_values(doc, runner, x):
    """Pixel positions the IR gives every layer object at camera X x (the
    objects the IR does not name get the same formula from the routine's own
    rate; they do not reach any line)."""
    model = runner.model
    out = {}
    for name, L in model.layers.items():
        d = doc['layers'].get(name, {'C': L['C'], 'U': L['U']})
        out[name] = ((d['C'] * x) >> 8) + d.get('K', 0)
    return out


def env_for(doc, runner, x):
    env = E._Default({('var', 'X'): x, ('var', 'HZ'): 0, ('var', 'XS'): 0})
    for name, v in layer_values(doc, runner, x).items():
        env[('init', f'{name}.l')] = S.wrap((v & 0xFFFF) << 16, 32, True)
    return env


def check_windows(doc, runner, L, slot, lim):
    """Step 4."""
    B = doc['buffer_lines']
    tops = sorted({L.r8_bgy(slot, cy, 0) for cy in range(lim['scralim_up'], lim['scralim_down'] + 1)})
    rule_tops = sorted({max(0, (y - (E.DISPLAY - E.ROW)) & ~7) for y in range(B)})
    n = mism = 0
    first = None
    for group, top_list in (('reachable', tops), ('WINDOW', rule_tops)):
        for x in XS_CHECK:
            env = env_for(doc, runner, x)
            cache = {}
            for t in top_list:
                lines, _ = runner.window(t)
                if group == 'WINDOW':
                    idx = [y - t for y in range(t, min(t + E.DISPLAY, B)) if max(0, (y - 216) & ~7) == t]
                else:
                    idx = range(E.DISPLAY)
                for i in idx:
                    w = lines[i]
                    key = getattr(w, 'src', None)
                    if key is None or key not in cache:
                        val = (-S.evaluate(w, env)) & 0xFFFF
                        if key is not None:
                            cache[key] = val
                    else:
                        val = cache[key]
                    want = L.r8_raster(slot, x, t + i, 0, 0) & 0xFFFF
                    n += 1
                    if val != want:
                        mism += 1
                        if first is None:
                            first = (group, x, t, i, val, want)
    print(f'  windows    {len(tops)} reachable window tops (camera Y {lim["scralim_up"]}..{lim["scralim_down"]}) '
          f'+ {len(rule_tops)} WINDOW tops x {len(XS_CHECK)} camera X: {n} lines, {mism} differ')
    if mism:
        g, x, t, i, got, want = first
        bad(f'{doc["program"]}: windows: first difference ({g}) camera X {x}, window {t}, line {i}: '
            f'retail {got}, IR {want}')


def check_trajectory(doc, runner, L, slot, lim, frames=700):
    """Step 5."""
    m = E._stage_machine(runner, [])
    m.call_function(E.STAGE_START)
    x, cy = lim['scra_h_posit.w.h'], lim['scra_v_posit.w.h']
    left, right, up, down = lim['scralim_left'], lim['scralim_right'], lim['scralim_up'], lim['scralim_down']
    rng = random.Random(slot)
    span = right - left
    vx = max(1, span // (frames // 2))             # there and back
    lines_n = mism = bgy_mism = 0
    first = None
    xs_seen = set()

    def put(text, value):
        lv = m.lvalue(m.parse_expr(text))
        m.store(lv, value, lv.type)

    put('scroll_start.w', 0)
    for f in range(frames):
        forward = f < frames // 2
        dx = rng.randint(0, 2 * vx) * (1 if forward else -1) + rng.randint(-3, 3)
        nx = min(right, max(left, x + dx))
        ny = min(down, max(up, cy + rng.randint(-12, 12)))
        dx, dy = nx - x, ny - cy
        x, cy = nx, ny
        xs_seen.add(x)
        for text, value in (('scra_h_posit.w.h', x), ('scra_h_posit.w.l', 0), ('scra_hz', dx << 8),
                            ('scra_v_posit.w.h', cy), ('scra_v_posit.w.l', 0), ('scra_vz', dy << 8),
                            ('actwk[0].xspeed.w', 0), ('actwk[0].xposi.w.h', x + 160)):
            put(text, value)
        m.call_function('scroll')
        env = E._Default({})
        bgy = S.evaluate(E._read(m, 'scrb_v_posit.w.h'), env)
        if (bgy - L.r8_bgy(slot, cy, x + 160)) & 0xFFFF:
            bgy_mism += 1
        for i in range(E.DISPLAY):
            w = m.read('buf:hscrollbuff', 4 * i, 2)
            got = (-S.evaluate(w, env)) & 0xFFFF
            want = L.r8_raster(slot, x, bgy + i, f, 0) & 0xFFFF
            lines_n += 1
            if got != want:
                mism += 1
                if first is None:
                    first = (f, x, cy, bgy, i, got, want)
    print(f'  trajectory {frames} frames from the stage start, camera X {left}..{right} ({len(xs_seen)} distinct), '
          f'Y {up}..{down}: {lines_n} lines, {mism} differ; background Y {bgy_mism} of {frames} differ')
    if mism or bgy_mism:
        bad(f'{doc["program"]}: trajectory: first difference {first}')


def main(argv):
    names = argv or [p.stem for r, a, e, p in programs() if r == 8]
    docs, paths = [], []
    for n in names:
        path = HERE / 'ir' / f'{n}.json'
        doc = json.loads(path.read_text())
        irc.validate(doc, str(path))
        docs.append(doc)
        paths.append(path)
    L = build(docs)
    shared = subprocess.run([sys.executable, str(SHARED / 'irc.py')] + [str(p) for p in paths],
                            capture_output=True, text=True)
    print(f'shared irc.py on these documents: exit {shared.returncode} '
          f'({(shared.stdout + shared.stderr).strip().splitlines()[-1][:120]})')
    if shared.returncode == 0:
        bad('the shared irc.py accepted a document that uses R8 extensions')
    for doc in docs:
        slot = slot_of(doc)
        print(f'{doc["program"]} (background id {slot}, extensions {doc.get("extensions")})')
        if not L.r8_present(slot):
            bad(f'{doc["program"]}: not in the emitted slot table')
            continue
        # 2. coverage
        B = doc['buffer_lines']
        classes = [L.r8_line_class(slot, y) for y in range(B)]
        end = doc['table_end']
        gap = [y for y in range(end) if classes[y] == 2]
        overlap = [y for y in range(B) if classes[y] == -1]
        counts = {c: classes.count(k) for c, k in (('run', 0), ('band', 1), ('unwritten', 2))}
        print(f'  coverage   buffer {B}: {counts}, table_end {end}, gaps {len(gap)}, overlaps {len(overlap)}')
        if gap or overlap or sum(r['entries'] for r in doc['runs']) * 8 != end:
            bad(f'{doc["program"]}: coverage gaps {gap[:4]} overlaps {overlap[:4]}')
        runner = E.Runner(RETAIL / doc['program'])
        runner.vertical_raw()
        lines0, m0 = runner.window(0)
        runner.model = E.Model(runner, m0)
        lim = limits(runner)
        # 3. sweep
        for lo, hi, label in ((lim['scralim_left'], lim['scralim_right'], 'stage limits'), (0, 16383, '0..16383')):
            out = (ctypes.c_longlong * 10)()
            L.r8_sweep(slot, lo, hi, out)
            o = list(out)
            where = (f'; out of range at camera X {o[5]}..{o[6]}, lines {o[7]}..{o[8]}, up to {o[9]} px outside'
                     if o[1] else '')
            print(f'  sweep      camera X {lo}..{hi} ({label}): {o[0]} samples, {o[1]} outside the layer range, '
                  f'{o[2]} wrap, {o[3]} frame, {o[4]} unwritten{where}')
            if o[2] or o[3]:
                bad(f'{doc["program"]}: sweep wrap/frame failures {o[2]}/{o[3]}')
            if o[1]:
                doc.setdefault('_range', []).append((label, o))
        # 4, 5
        check_windows(doc, runner, L, slot, lim)
        check_trajectory(doc, runner, L, slot, lim)
    print()
    print(f'validate.py (R8): {len(docs)} documents, {len(FAILS)} failures')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
