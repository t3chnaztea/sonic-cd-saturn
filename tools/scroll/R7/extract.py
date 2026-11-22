#!/usr/bin/env python3
"""Retail scroll() C -> scroll IR: tools/scroll/extract.py plus the R7
extensions.  NOT the shared extractor.

    python3 tools/scroll/R7/extract.py R7/SCR71A.C [...]    print IR JSON
    python3 tools/scroll/R7/extract.py --round 7 --write   write tools/scroll/R7/ir/*.json

This is a copy of tools/scroll/extract.py (which stays untouched: other zone
stages run it at the same time).  Every departure is marked `EXT` and is one
of the following.  Each is a stated property of the data; the census counts
of how many of the 68 programs each changes are in tools/scroll/R7/ops.md.

  EXT-FILES      A callee the routine's file does not define is interpreted
                 from the one retail file that defines it (closure.py);
                 SCR71B/SCR72B call sinset() from ETC.C.
  EXT-OP-INTERP  A table word that is the high word of a 16.16 accumulator
                 seeded from layer words and stepped by a truncated quotient,
                 hi(sum a_i*L_i + M*div(sum n_j*L_j, D)), maps to the new op
                 `interp` (ops.md 1) and is re-checked numerically against the
                 routine's own symbolic word.
  EXT-BGY-SHIFTS A background Y that is a sum of right shifts of the 16-bit
                 camera Y maps to the new bg_y op `shifts` (ops.md 3), checked
                 at every camera Y 0..65535.
  EXT-WINDOW     Rule WINDOW, extended: when the routine's background Y
                 cannot take the ideal window top (it skips values), line y is
                 read from the reachable top nearest the ideal one, among the
                 tops whose 224-line window still shows y (ties: the higher
                 window).  Counted as WINDOW_REACH.  The buffer-height probe
                 uses the same substitution.
  EXT-WALK       After the buffer height is known, one window whose top lies
                 within 224 lines of the buffer end is read to see whether
                 the render wraps its row walk at the buffer end.  The result
                 is recorded under rules.row_walk; the IR's line model assumes
                 it wraps, so `wraps: false` is a render-window artefact the
                 IR does not express (listed in the program's gap file).
  EXT-WAVE       Band lines whose word is a layer plus a shifted sine-table
                 word map to the new op `wave` (ops.md 2).  The table access
                 is made symbolic by closure.py's SinsetMachine, and the
                 phase parameters are read off the routine's own index
                 expression and re-checked for every phase word 0..65535.

How the shared parts work, unchanged (from tools/scroll/extract.py):
  1. interp.py runs the routine with camera X, the camera X delta and the
     player X speed symbolic, once per render window: a window is the
     background Y the routine is handed (camera Y is made concrete so the
     routine's own index arithmetic runs).
  2. Every output line of every window is then one of
       - a copy of a table cell (the load that produced it is recorded), or
       - a value from a 16.16 accumulator the render steps line by line.
  3. The table cells become runs, the accumulator lines become bands, and
     each value is mapped onto the expression vocabulary.  Every mapped
     expression is then re-checked by evaluating the routine's own symbolic
     value and the IR formula on a grid of inputs; any difference aborts.
  4. A separate run with camera Y symbolic gives the background Y rule.

Stated rules of the shared extractor (TAIL, SEED, WINDOW) apply unchanged.
Everything else is a loud failure naming the program and the reason.
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # tools/scroll/R7
SHARED = HERE.parent                               # tools/scroll
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))

import sym as S                                        # noqa: E402
from cfront import RETAIL, programs, scroll_body, shape_key   # noqa: E402
from interp import InterpError, Program, SymbolicControl   # noqa: E402
import irc_ext as irc                                  # noqa: E402  EXT: extended validator
from closure import SinsetMachine, TABLE_ATOMS, sinset_sin, table_value   # noqa: E402  EXT-FILES, EXT-WAVE

IR_VERSION = 'scroll-ir/1'
DISPLAY = 224            # visible lines of the Mega CD screen
ROW = 8                  # lines per table entry
PERIODS = (64, 128, 256, 512, 1024, 2048)

X = ('var', 'X', 16, True)        # scra_h_posit.w.h: camera X after this frame's move
HZ = ('var', 'HZ', 16, True)      # scra_hz: this frame's camera X delta, 8.8
XS = ('var', 'XS', 16, True)      # actwk[0].xspeed.w: player X speed, 8.8
Y = ('var', 'Y', 16, True)        # scra_v_posit.w.h: camera Y
VZ = ('var', 'VZ', 16, True)      # scra_vz: camera Y delta, 8.8
PX = ('var', 'PX', 16, True)      # actwk[0].xposi.w.h: player X

# camera positions are whole pixels: their 16.16 fractions are 0
HORIZONTAL_INPUTS = [('scroll_start.w', 0), ('scra_h_posit.w.h', X), ('scra_h_posit.w.l', 0),
                     ('scra_hz', HZ), ('actwk[0].xspeed.w', XS), ('scra_v_posit.w.l', 0)]


class ExtractError(Exception):
    pass


def fail(prog, msg):
    raise ExtractError(f'{prog}: {msg}')


# ----------------------------------------------------------------- running

class Runner:
    def __init__(self, path):
        self.path = Path(path)
        self.name = f'{self.path.parent.name}/{self.path.name}'
        self.windows = {}
        self.closure_calls = set()                     # EXT-FILES

    def machine(self, extra):
        # EXT-FILES / EXT-WAVE: callees from other files, sine table symbolic
        if not hasattr(self, '_prog'):
            self._prog = Program(self.path)
        return SinsetMachine(self._prog, HORIZONTAL_INPUTS + extra,
                             {'lphscrollbuff': ('hscrollbuff', self._prog.unit.typedefs['int_union'], 1024)})

    def vertical_raw(self):
        """The routine's background Y as a symbolic value of camera Y (Y),
        its delta (VZ), player X (PX) and the previous background Y."""
        m = self.machine([('scra_v_posit.w.h', Y), ('scra_vz', VZ), ('actwk[0].xposi.w.h', PX)])
        try:
            m.call_function('scroll')
            stopped = None
        except SymbolicControl as e:
            # the render walks the table with the background Y just computed
            # and cannot run with it symbolic; vertical() checks the value
            # against complete concrete runs, so where the run stopped is moot
            stopped = str(e)
        self.bgy_raw = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
        self.bgy_stopped = stopped
        self.camera_for = None
        if ('init', 'scrb_v_posit.l') not in S.atoms(self.bgy_raw):
            # absolute background Y: find, for each background Y, the lowest
            # camera Y (player X 0) that produces it
            self.camera_for = {}
            env = _Default({('var', 'PX'): 0, ('var', 'VZ'): 0})
            for y in range(65536):
                env[('var', 'Y')] = y
                b = S.evaluate(self.bgy_raw, env) & 0xFFFF
                self.camera_for.setdefault(b, S.wrap(y, 16, True) if y < 32768 else None)
        return self.bgy_raw

    # EXT-WINDOW
    def reachable(self, top):
        if self.camera_for is None:
            return True
        return self.camera_for.get(top & 0xFFFF) is not None

    def window(self, top):
        """Run with background Y = top.  Returns (lines, machine)."""
        if top in self.windows:
            return self.windows[top]
        cam = top
        if self.camera_for is not None:
            cam = self.camera_for.get(top & 0xFFFF)
            if cam is None:
                fail(self.name, f'no camera Y in 0..32767 gives background Y {top}')
        m = self.machine([('scra_v_posit.w.h', cam), ('scra_vz', 0), ('actwk[0].xposi.w.h', 0),
                          ('scrb_v_posit.w.h', top), ('scrb_v_posit.w.l', 0)])
        try:
            m.call_function('scroll')
        except InterpError as e:                       # EXT: name the window in the failure
            fail(self.name, f'window {top}: {type(e).__name__}: {e}')
        self.closure_calls |= m.closure_calls
        bgy = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
        if bgy != top:
            fail(self.name, f'window {top}: routine set background Y to {S.fmt(bgy)}')
        lines = []
        for i in range(DISPLAY):
            lines.append(m.read('buf:hscrollbuff', 4 * i, 2))
        self.windows[top] = (lines, m)
        return self.windows[top]


def ideal_top(y):
    return max(0, (y - (DISPLAY - ROW)) & ~7)


def choose_top(runner, y):
    """EXT-WINDOW: the ideal top if the background Y can take it, else the
    reachable top nearest to it whose window still shows y."""
    t0 = ideal_top(y)
    if runner.reachable(t0):
        return t0
    cands = [t for t in range(max(0, y - (DISPLAY - 1)), y + 1) if runner.reachable(t)]
    if not cands:
        fail(runner.name, f'no reachable window shows background line {y}')
    return min(cands, key=lambda t: (abs(t - t0), t))


# ----------------------------------------------------------------- symbolic helpers

def strip16(v):
    """Drop 16-bit truncations at the top: the routine's words are 16 bits and
    the IR values are defined modulo 65536 (ir.md, 'Values')."""
    v = S.un(v)
    while isinstance(v, tuple) and v[0] == 'trunc' and v[2] == 16:
        v = S.un(v[1])
    return v


def bg_x(word):
    """The routine writes -(background X); return background X."""
    return strip16(S.neg(strip16(word)))


class Model:
    """Layers and accumulators found in a finished run."""

    def __init__(self, runner, machine):
        self.name = runner.name
        self.layers = {}       # object name -> dict(C, U, gate, final)
        self.accs = []         # (object name, byte offset, speed, set of init names)
        m = machine
        for oid, obj in m.state.objs.items():
            if not oid.startswith('g:'):
                continue
            self.scan_layer(m, oid, obj)
            self.scan_accs(m, oid, obj)

    def scan_layer(self, m, oid, obj):
        t = obj.type
        if t.size != 4 or 0 not in obj.ent:
            return
        v = m.read(oid, 0, 4)
        if not isinstance(v, (int, tuple, S.Prov)):
            return
        v = S.un(v)
        start = ('init', f'{obj.name}.l', 32, True)
        terms, c = S.lin_parts(v)
        if terms.get(start) != 1 or c or HZ not in terms:
            return
        C = terms.pop(HZ)
        terms.pop(start)
        U, gate = 0, None
        for a, k in terms.items():
            if isinstance(a, tuple) and a[0] == 'sel' and S.un(a[3]) == 0:
                inner, ic = S.lin_parts(a[2])
                if set(inner) == {XS} and not ic and inner[XS] % 256 == 0:
                    U += k * inner[XS] // 256
                    g = S.fmt(a[1])
                    if gate not in (None, g):
                        fail(self.name, f'layer {obj.name} has two ramp gates')
                    gate = g
                    continue
            fail(self.name, f'layer {obj.name} moves by a term outside C*HZ + U*XS: {S.fmt(a)}')
        self.layers[obj.name] = {'C': C, 'U': U, 'gate': gate, 'final': v}

    def scan_accs(self, m, oid, obj):
        t = obj.type
        elem = getattr(t, 'elem', None)
        if elem is None or t.size < 4:
            return
        seen = set()
        for off in sorted(obj.ent):
            base = off - off % 4
            if base in seen or base + 4 > t.size:
                continue
            seen.add(base)
            final = S.un(m.read(oid, base, 4))
            names = S.atoms(final)
            inits = [n for k, n in names if k == 'init' and n.startswith(obj.name + '[')]
            if not inits:
                continue
            # the value these bytes held before the routine ran
            if elem.size == 4:
                before = ('init', f'{obj.name}[{base // 4}]', 32, elem.signed)
            elif elem.size == 2:
                before = S.comp(('init', f'{obj.name}[{base // 2}]', 16, elem.signed),
                                ('init', f'{obj.name}[{base // 2 + 1}]', 16, elem.signed))
            else:
                continue
            d = S.un(S.sub(final, before))
            if isinstance(d, int) and d:
                cells = {f'{obj.name}[{base // elem.size + i}]' for i in range(4 // elem.size)}
                self.accs.append((obj.name, base, d, cells, elem))

    # -- classification of atoms
    def layer_of(self, atom):
        if atom == X:
            return 'camera'
        if isinstance(atom, tuple) and atom[0] == 'half' and atom[2] == 'hi':
            for name, L in self.layers.items():
                if S.un(atom[1]) == L['final']:
                    return name
        return None

    def acc_of(self, atom):
        names = {n for k, n in S.atoms(atom) if k == 'init'}
        hits = [a for a in self.accs if names and names <= a[3]]
        if len(hits) != 1:
            return None
        acc = hits[0]
        # verify: with the accumulator at (f-1)*speed the term is the high
        # word of f*speed, for many f
        name, base, speed, cells, elem = acc
        for f in (1, 2, 3, 7, 100, 255, 4096, 30000, 65535, 70000, 1 << 20):
            prev = ((f - 1) * speed) & S.M32
            env = {}
            for i, cell in enumerate(sorted(cells, key=lambda c: int(c.split('[')[1][:-1]))):
                if elem.size == 4:
                    env[('init', cell)] = prev
                else:
                    env[('init', cell)] = (prev >> (16 * i)) & 0xFFFF
            want = ((f * speed) & S.M32) >> 16
            got = S.evaluate(atom, env) & 0xFFFF
            if got != want:
                return None
        return acc


# ----------------------------------------------------------------- EXT-OP-INTERP

def interp_eval(e, vals):
    """Reference semantics of op interp (ops.md 1; mirrors evaluate_ext.c).
    vals: layer name -> the layer's value (any integer; read as 16 bits)."""
    s = {k: S.wrap(v, 16, True) for k, v in vals.items()}
    a = sum(k * s[n] for n, k in e['lin'].items())
    q = 0
    if e['num']:
        n = sum(k * s[nm] for nm, k in e['num'].items())
        q = abs(n) // e['D'] * (1 if n >= 0 else -1)          # C division, toward zero
    return (a + e['M'] * q) // 65536                            # floor


def interp_expr(model, v, what):
    """Map hi(A), A = sum a_i*L_i + M*div(sum n_j*L_j, D) over layer words,
    onto op interp.  None when v does not have that form (the caller then
    fails loudly as the shared extractor does)."""
    v = S.un(v)
    if not (isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi'):
        return None
    terms, c = S.lin_parts(S.un(v[1]))
    if c:
        return None
    lin, num, D, M = {}, {}, 1, 0
    atoms = {}
    for a, k in terms.items():
        L = model.layer_of(a)
        if L is not None:
            lin[L] = lin.get(L, 0) + k
            atoms[L] = a
            continue
        a = S.un(a)
        if isinstance(a, tuple) and a[0] == 'div' and a[3] and not num:
            nt, nc = S.lin_parts(S.un(a[1]))
            if nc:
                return None
            for na, nk in nt.items():
                NL = model.layer_of(na)
                if NL is None:
                    return None
                num[NL] = num.get(NL, 0) + nk
                atoms[NL] = na
            D, M = a[2], k
            continue
        return None
    lin = {k: c for k, c in lin.items() if c}
    num = {k: c for k, c in num.items() if c}
    if not num:
        D, M = 1, 0
    if not lin and not num:
        return {'op': 'zero'}
    if list(lin.values()) == [65536] and not num:
        return {'op': 'layer', 'layer': next(iter(lin))}
    e = {'op': 'interp', 'lin': dict(sorted(lin.items())), 'num': dict(sorted(num.items())), 'D': D, 'M': M}
    # re-check against the routine's own word, every layer read as a 16-bit
    # word: edges and 600 random points
    names = sorted(atoms)
    rng = random.Random(7)
    edges = [0, 1, -1, 2, 255, 256, 4095, 11927, 16023, 32767, -32768, -32767, 12345, -12345]
    pts = [{n: edges[(i + j * 5) % len(edges)] for j, n in enumerate(names)} for i in range(len(edges) * 3)]
    pts += [{n: rng.randint(-32768, 32767) for n in names} for _ in range(600)]
    for p in pts:
        env = _layer_env(model, {atoms[n]: val for n, val in p.items()})
        got = S.evaluate(v, env) & 0xFFFF
        want = interp_eval(e, p) & 0xFFFF
        if got != want:
            fail(model.name, f'{what}: interp {e} does not reproduce the routine at {p}: routine {got}, IR {want}')
    return e


def to_expr(model, v, what):
    """Map background X (symbolic) onto the IR vocabulary: one layer, plus at
    most one accumulator term (everything that is not a layer is taken
    together and must be exactly the high word of one accumulator)."""
    e = interp_expr(model, v, what)                  # EXT-OP-INTERP
    if e is not None:
        return e
    terms, c = S.lin_parts(v)
    layers, rest = [], {}
    for a, k in terms.items():
        L = model.layer_of(a)
        if L is not None and k == 1:
            layers.append(L)
        else:
            rest[a] = k
    remainder = S.make_lin(rest, c)
    clouds = []
    if S.un(remainder) != 0:
        acc = model.acc_of(remainder)
        if acc is None:
            fail(model.name, f'{what}: {S.fmt(remainder)} is neither a layer nor one accumulator '
                             f'(in {S.fmt(v)})')
        clouds.append(acc)
    if not layers and not clouds:
        return {'op': 'zero'}
    if len(layers) == 1 and not clouds:
        return {'op': 'layer', 'layer': layers[0]}
    if len(layers) == 1 and len(clouds) == 1 and layers[0] != 'camera':
        return {'op': 'cloud', 'layer': layers[0], 'speed': clouds[0][2]}
    fail(model.name, f'{what}: combination outside the vocabulary: {S.fmt(v)}')


# ----------------------------------------------------------------- ramps

def ramp_params(model, q, what):
    """q is the per-line step (in 1/256 pixel) of an accumulator band.
    Returns (to, from, D, diff_bits, step_bits) with
        q == [s16]( trunc( 256*[s16](to - from) / D ) )."""
    step_bits = 32
    inner = S.un(q)
    if isinstance(inner, tuple) and inner[0] == 'trunc' and inner[2] == 16 and inner[3]:
        step_bits = 16
        inner = S.un(inner[1])
    D = 256
    diff = None
    if isinstance(inner, tuple) and inner[0] == 'div':
        if not inner[3]:
            fail(model.name, f'{what}: unsigned ramp division')
        D = inner[2]
        num = S.un(inner[1])
        t, c = S.lin_parts(num)
        if c or len(t) != 1:
            fail(model.name, f'{what}: ramp numerator is not 256*difference: {S.fmt(num)}')
        (a, k), = t.items()
        if k != 256:
            fail(model.name, f'{what}: ramp numerator scale {k}, expected 256')
        diff = a
    else:
        diff = inner
    diff_bits = 32
    d = S.un(diff)
    if isinstance(d, tuple) and d[0] == 'trunc' and d[2] == 16 and d[3]:
        diff_bits = 16
        d = S.un(d[1])
    elif D == 256 and step_bits == 16:
        diff_bits = 16
    t, c = S.lin_parts(d)
    if D == 256 and not c and len(t) == 2 and sorted(t.values()) != [-1, 1]:
        # 256*d/D folded to m*d when D divides 256 exactly
        m = max(t.values())
        if sorted(t.values()) == [-m, m] and 256 % m == 0:
            D = 256 // m
            t = {a: k // m for a, k in t.items()}
    if c or len(t) != 2 or sorted(t.values()) != [-1, 1]:
        fail(model.name, f'{what}: ramp difference is not (to - from): {S.fmt(d)}')
    to = [a for a, k in t.items() if k == 1][0]
    frm = [a for a, k in t.items() if k == -1][0]
    to_l, from_l = model.layer_of(to), model.layer_of(frm)
    if to_l is None or from_l is None:
        fail(model.name, f'{what}: ramp ends are not layers: {S.fmt(d)}')
    # re-check the parameterisation numerically
    rng = random.Random(1)
    for _ in range(400):
        tv, fv = rng.randint(-32768, 32767), rng.randint(-32768, 32767)
        env_q = S.evaluate(q, _layer_env(model, {to: tv, frm: fv}))
        if env_q != ramp_step(tv, fv, D, diff_bits, step_bits):
            fail(model.name, f'{what}: ramp parameters do not reproduce the step at to={tv} from={fv}')
    return to_l, from_l, D, diff_bits, step_bits, frm


def _layer_env(model, values):
    """Environment giving layer atoms the given 16-bit values."""
    env = {('var', 'X'): 0, ('var', 'HZ'): 0, ('var', 'XS'): 0}
    for atom, val in values.items():
        if atom == X:
            env[('var', 'X')] = val
            continue
        name = model.layer_of(atom)
        env[('init', f'{name}.l')] = (val & 0xFFFF) << 16
    # layer gates read other inputs; give every remaining leaf a value of 0
    return _Default(env)


class _Default(dict):
    def __missing__(self, key):
        if key[0] == 'var' and key[1] in TABLE_ATOMS:       # EXT-WAVE: table atoms
            return table_value(key[1], self)
        return 0

    def __contains__(self, key):
        return True


def ramp_step(to, frm, D, diff_bits, step_bits):
    d = to - frm
    if diff_bits == 16:
        d = S.wrap(d, 16, True)
    q = S.div(S.wrap(256 * d, 32, True), D, True)
    if step_bits == 16:
        q = S.wrap(q, 16, True)
    return q


# ----------------------------------------------------------------- EXT-WAVE

def wave_eval(e, layer_value, frame, k):
    """Reference semantics of op wave (ops.md 2; mirrors evaluate_ext.c)."""
    table = sinset_sin()
    word = (e['phase_speed'] * frame) & 0xFFFF
    p = ((word >> 8) + e['phase_step'] * k) & 255
    return layer_value + (table[p] >> e['shift'])


def wave_line(model, runner, v, what):
    """A band line layer + (u16(SIN[p]) >> s), SIN the symbolic sine word the
    SinsetMachine returned for index expression p.  Returns
    (layer, shift, index expression) or None."""
    terms, c = S.lin_parts(v)
    if c:
        return None
    layer, rest = None, []
    for a, k in terms.items():
        L = model.layer_of(a)
        if L is not None and k == 1 and layer is None and L != 'camera':
            layer = L
        else:
            rest.append((a, k))
    if layer is None or len(rest) != 1 or rest[0][1] != 1:
        return None
    a = strip16(rest[0][0])
    if not (isinstance(a, tuple) and a[0] == 'shr'):
        return None
    inner = S.un(a[1])
    if isinstance(inner, tuple) and inner[0] == 'trunc' and inner[2] == 16 and not inner[3]:
        inner = S.un(inner[1])
    k = S.kind(inner)
    if not k or k[1] or k[0] > 16:
        return None                  # the shifted word must be an unsigned 16-bit table word
    idx = SinsetMachine.index_of(inner)
    if idx is None:
        return None
    return layer, a[2], idx, inner


def wave_params(model, runner, lines, what):
    """lines: [(k, (layer, shift, index expression))] for consecutive band
    lines.  Reads phase_speed from the phase word's per-call add and
    phase_step from consecutive index expressions, then re-checks every line
    for every phase word 0..65535."""
    layers = {ln[1][0] for ln in lines}
    shifts = {ln[1][1] for ln in lines}
    if len(layers) != 1 or len(shifts) != 1:
        fail(model.name, f'{what}: wave lines ride different layers or shifts: {layers} {shifts}')
    words = SinsetMachine.phase_words(lines[0][1][2])
    if len(words) != 1:
        fail(model.name, f'{what}: the sine index reads {len(words)} memory words, expected one phase word')
    word, = words
    speed = runner.phase_add.get(word)
    if not speed:
        fail(model.name, f'{what}: the phase word {word} is not advanced by a constant each call')
    # the index at line 0 with the phase word at 0 after the add; step from line 1
    idx0 = lines[0][1][2]
    step = None
    for (k0, a), (k1, b) in zip(lines, lines[1:]):
        d = S.sub(b[2], a[2])
        d = S.un(S.trunc(d, 8, False))
        if not isinstance(d, int):
            fail(model.name, f'{what}: sine index step between lines {k0} and {k1} is not constant: {S.fmt(d)}')
        if step is None:
            step = d
        elif d != step:
            fail(model.name, f'{what}: sine index step changes between lines {k0} and {k1}')
    e = {'op': 'wave', 'layer': layers.pop(), 'table': 'sinset_sin', 'phase_speed': speed,
         'phase_step': step if step is not None else 0, 'shift': shifts.pop()}
    # the table the routine indexes must be the op's table: sinset's sine
    # words for kakudo 0..255 (closure.sinset_sin interprets sinset itself)
    for k, ln in lines:
        where, values, _ = SinsetMachine.table_of(ln[3])
        if tuple(values[:256]) != sinset_sin():
            fail(model.name, f'{what}: line {k} reads {where}, whose first 256 words are not sinset\'s sine words')
    # re-check: for every phase word the routine held before the call, the
    # routine's own table index at each line equals the IR's phase for
    # frame f, phase word (f*speed) after the add; the index must lie in the
    # sine part of the table (0..255)
    init_name = ('init', word)
    for k, ln in lines:
        idx = ln[2]
        for before in range(0, 65536):
            after = (before + speed) & 0xFFFF
            got = S.evaluate(idx, _Default({init_name: before}))
            want = ((after >> 8) + e['phase_step'] * k) & 255
            if got != want:
                fail(model.name, f'{what}: wave phase differs at line {k}, phase word {before}: routine {got}, IR {want}')
    return e


def wave_recheck(model, v, e, k, word, what):
    """EXT-WAVE: the line's whole value against wave_eval, numerically, for
    layer values and phase words on a grid."""
    speed = e['phase_speed']
    atoms = [a for a in S.lin_parts(v)[0] if model.layer_of(a) == e['layer']]
    if len(atoms) != 1:
        fail(model.name, f'{what}: wave layer atom not found')
    rng = random.Random(11)
    for i in range(300):
        lv = rng.randint(-32768, 32767) if i else 0
        before = rng.randint(0, 65535) if i % 3 else (i * 997) & 0xFFFF
        env = _layer_env(model, {atoms[0]: lv})
        env[('init', word)] = before
        got = S.evaluate(v, env) & 0xFFFF
        f_after = (before + speed) & 0xFFFF             # the phase word after the add
        want = (lv + (sinset_sin()[((f_after >> 8) + e['phase_step'] * k) & 255] >> e['shift'])) & 0xFFFF
        if got != want:
            fail(model.name, f'{what}: wave value differs at layer {lv}, phase word {before}: routine {got}, IR {want}')


# ----------------------------------------------------------------- vertical

def shifts_of(v):
    """EXT-BGY-SHIFTS: [k...] when v is sum((u16)Y >> k), else None."""
    v = strip16(v)
    terms, c = S.lin_parts(v)
    if c or not terms:
        return None
    ks = []
    for a, k in terms.items():
        a = S.un(a)
        if k != 1:
            return None
        if isinstance(a, tuple) and a[0] == 'shr' and strip16(a[1]) == Y and \
                S.un(a[1]) == ('trunc', Y, 16, False):
            ks.append(a[2])
        elif a == ('trunc', Y, 16, False):
            ks.append(0)
        else:
            return None
    if not any(ks):
        return None               # plain camera Y: the shared `camera` op
    return sorted(ks)


def vertical(runner, rules):
    v, stopped = runner.bgy_raw, runner.bgy_stopped
    start = ('init', 'scrb_v_posit.l', 32, True)
    terms, c = S.lin_parts(v if not (isinstance(v, tuple) and v[0] == 'half') else S.un(v[1]))
    ks = shifts_of(v)
    if isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi' and terms.get(start) == 1 and not c \
            and set(terms) == {start, VZ}:
        out = {'op': 'rate', 'C': terms[VZ]}
    elif ks is not None:                             # EXT-BGY-SHIFTS
        out = {'op': 'shifts', 'shifts': ks}
        for yv in range(65536):
            for pv in (0, 0x800, 0x7FFF):
                env = {('var', 'Y'): yv, ('var', 'PX'): pv}
                if S.wrap(S.evaluate(v, env), 16, True) != S.wrap(bg_y_eval(out, yv, pv), 16, True):
                    fail(runner.name, f'background Y rule {out} differs at Y={yv} PX={pv}')
    else:
        leaves = S.atoms(v)
        if not leaves <= {('var', 'Y'), ('var', 'PX')} or ('var', 'Y') not in leaves:
            fail(runner.name, f'background Y is outside the vocabulary: {S.fmt(v)}')
        out = {'op': 'camera'}
        fold = find_fold(v)
        if fold:
            out['fold'] = fold
        for yv in range(0, 4096, 1):
            for pv in (0, 1, 0x7FF, 0x800, 0x801, 0x1000, 0x2000, 0x3000, 0x7FFF):
                env = {('var', 'Y'): yv, ('var', 'PX'): pv}
                if S.wrap(S.evaluate(v, env), 16, True) != S.wrap(bg_y_eval(out, yv, pv), 16, True):
                    fail(runner.name, f'background Y rule {out} differs at Y={yv} PX={pv}')
    # completeness: concrete runs must land on the same value
    for yv, pv, a, d in ((0, 0, 0, 0), (480, 0x800, 3, 2), (1000, 0x900, 100, -5),
                         (1808, 0x100, 7, 16), (481, 0x2000, 60, 1), (37, 0, 1, -16)):
        cm = runner.machine([('scra_v_posit.w.h', yv), ('scra_vz', d << 8), ('actwk[0].xposi.w.h', pv),
                             ('scrb_v_posit.w.h', a), ('scrb_v_posit.w.l', 0)])
        try:
            cm.call_function('scroll')
        except InterpError as e:
            fail(runner.name, f'concrete background Y run at camera Y {yv}: {type(e).__name__}: {e}')
        got = S.un(cm.load(cm.lvalue(cm.parse_expr('scrb_v_posit.w.h')))[0])
        env = _Default({('var', 'Y'): yv, ('var', 'PX'): pv, ('var', 'VZ'): d << 8,
                        ('init', 'scrb_v_posit.l'): a << 16})
        if got != S.wrap(S.evaluate(v, env), 16, True):
            fail(runner.name, f'background Y from the symbolic run ({S.fmt(v)}) differs from a concrete run')
    rules['vertical_run_stopped'] = stopped
    return out


def find_fold(v):
    """Constants of `if (player X >= P && Y >= Y0) Y = (Y - Y0)/K + Y0`."""
    found = {'px': set(), 'y': set(), 'div': set()}

    def walk(x):
        x = S.un(x)
        if not isinstance(x, tuple):
            return
        if x[0] == 'cmp' and x[1] == '>=' and isinstance(S.un(x[3]), int):
            leaves = S.atoms(x[2])
            if leaves == {('var', 'PX')}:
                found['px'].add(S.un(x[3]))
            elif leaves == {('var', 'Y')}:
                found['y'].add(S.un(x[3]))
        if x[0] == 'div':
            found['div'].add(x[2])
        for p in S.children(x):
            walk(p)
    walk(v)
    if not any(found.values()):
        return None
    if any(len(s) != 1 for s in found.values()):
        raise ExtractError(f'background Y fold constants are ambiguous: {found}')
    return {'player_x_min': found['px'].pop(), 'y_min': found['y'].pop(), 'div': found['div'].pop()}


def bg_y_eval(rule, y, player_x):
    """Reference semantics of the bg_y vocabulary (mirrors evaluate_ext.c)."""
    if rule['op'] == 'rate':
        return (rule['C'] * y) >> 8
    if rule['op'] == 'shifts':                       # EXT-BGY-SHIFTS
        return sum((y & 0xFFFF) >> k for k in rule['shifts'])
    if rule['op'] == 'camera':
        f = rule.get('fold')
        if f and (player_x & 0xFFFF) >= f['player_x_min'] and (y & 0xFFFF) >= f['y_min']:
            return S.div(y - f['y_min'], f['div'], True) + f['y_min']
        return y
    raise ExtractError(f'unknown bg_y op {rule}')


# ----------------------------------------------------------------- derivation

def derive(path):
    R = Runner(path)
    name = R.name
    rules = {'WINDOW': 0, 'TAIL': 0, 'SEED': 0}
    R.vertical_raw()

    lines0, m0 = R.window(0)
    src0 = getattr(lines0[0], 'src', None)
    if src0 is None:
        fail(name, 'line 0 of window 0 is not a table cell')
    table_obj, base_off = src0
    tobj = next(o for o in m0.state.objs.values() if o.name == table_obj)
    esize = tobj.type.elem.size
    if esize != 2:
        fail(name, f'table {table_obj} has {esize}-byte entries, expected 2')
    base = base_off // esize

    def row_of(word):
        src = getattr(word, 'src', None)
        if src is None or src[0] != table_obj:
            return None
        return src[1] // esize - base

    # EXT-WINDOW: probe P + t0 with both tops reachable
    buffer_lines = None
    for P in PERIODS:
        t0 = next((t for t in range(ROW) if R.reachable(t) and R.reachable(P + t)), None)
        if t0 is None:
            fail(name, f'no reachable window pair (t, {P} + t) with t < {ROW} to probe a {P}-line buffer')
        lt, _ = R.window(t0)
        lp, _ = R.window(P + t0)
        if row_of(lt[0]) is None:
            fail(name, f'line 0 of window {t0} is not a table cell')
        if row_of(lp[0]) == row_of(lt[0]):
            buffer_lines = P
            break
    if buffer_lines is None:
        fail(name, f'no window up to {PERIODS[-1]} shows table row 0 again: cannot read the buffer height')

    model = Model(R, m0)
    if not model.layers:
        fail(name, 'no layer positions found')
    # EXT-WAVE: per-call adds of words the sine index reads
    R.phase_add = {}
    for oid, obj in m0.state.objs.items():
        if oid.startswith('g:') and obj.type.size == 2 and 0 in obj.ent:
            fin = S.un(m0.read(oid, 0, 2))
            d = S.un(S.trunc(S.sub(fin, ('init', f'{obj.name}.w', 16, True)), 16, False))
            if isinstance(d, int) and d:
                R.phase_add[f'{obj.name}.w'] = d

    # table cells written by the routine
    def cell_value(i):
        return S.un(m0.read(f'g:{table_obj}', 2 * i, 2))

    def written(i):
        return cell_value(i) != ('init', f'{table_obj}[{i}]', 16, True)

    rows = buffer_lines // ROW
    if base + rows > tobj.type.n:
        fail(name, f'table base {base} + {rows} rows passes the end of {table_obj}')
    n_written = 0
    while n_written < rows and written(base + n_written):
        n_written += 1
    if any(written(base + i) for i in range(n_written, rows)):
        fail(name, 'table has a hole: an unwritten row followed by written rows')
    table_end = n_written * ROW

    # stitched lines (rule WINDOW, EXT-WINDOW)
    stitched, tops, reach_lines = [], set(), 0
    for y in range(buffer_lines):
        top = choose_top(R, y)
        tops.add(top)
        reach_lines += top != ideal_top(y)
        lines, _ = R.window(top)
        stitched.append(lines[y - top])
    rules['WINDOW'] = len(tops)
    rules['WINDOW_REACH'] = reach_lines

    band_lines, wave_lines = {}, {}
    for y, word in enumerate(stitched):
        src = getattr(word, 'src', None)
        if src is not None and src[0] == table_obj:
            row = src[1] // 2 - base
            if row != y // ROW:
                fail(name, f'line {y} shows table row {row}, expected {y // ROW}')
            continue
        v = bg_x(word)
        if S.poisoned(v):
            fail(name, f'line {y}: {v[1]}')
        w = wave_line(model, R, v, f'line {y}')      # EXT-WAVE
        if w is not None:
            wave_lines[y] = w + (v,)
            continue
        # an accumulator line shows hi(A); a line equal to a layer is the
        # accumulator's first line, A = 65536*layer
        if isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi' and model.layer_of(v) is None:
            band_lines[y] = S.un(v[1])
        else:
            band_lines[y] = S.mulc(v, 65536)

    # runs
    runs = []
    for i in range(n_written):
        e = to_expr(model, bg_x(cell_value(base + i)), f'table row {i}')
        if runs and runs[-1]['expr'] == e:
            runs[-1]['entries'] += 1
        else:
            runs.append({'entries': 1, 'expr': e})

    # bands
    bands, corrections, overridden = [], [], []
    ys = sorted(band_lines)
    i = 0
    tail_region = None
    while i < len(ys):
        y0 = ys[i]
        if tail_region is not None and y0 >= tail_region[0]:
            i += 1
            continue
        A0 = band_lines[y0]
        t0, c0 = S.lin_parts(A0)
        if c0 % 65536 or any(k % 65536 for k in t0.values()):
            fail(name, f'line {y0} is an accumulator line whose band does not start there: {S.fmt(A0)}')
        seed = S.make_lin({a: k // 65536 for a, k in t0.items()}, c0 // 65536)
        j = i + 1
        delta = None
        while j < len(ys) and ys[j] == ys[j - 1] + 1:
            d = S.sub(band_lines[ys[j]], band_lines[ys[j - 1]])
            if delta is None:
                delta = d
            elif d != delta:
                break
            j += 1
        n = j - i
        if delta is None:
            fail(name, f'band at line {y0} is one line long')
        dt, dc = S.lin_parts(delta)
        if dc % 256 or any(k % 256 for k in dt.values()):
            fail(name, f'band at line {y0}: step {S.fmt(delta)} is not a multiple of 1/256 pixel')
        q = S.make_lin({a: k // 256 for a, k in dt.items()}, dc // 256)
        to_l, from_l, D, diff_bits, step_bits, from_atom = ramp_params(model, q, f'band at line {y0}')
        seed_l = model.layer_of(seed) if isinstance(seed, tuple) else None
        expr = {'op': 'ramp', 'from': from_l, 'to': to_l, 'D': D,
                'diff_bits': diff_bits, 'step_bits': step_bits}
        if seed_l != from_l:
            rules['SEED'] += 1
            corrections.append({'rule': 'SEED', 'band_start': y0, 'literal_first_line': S.fmt(seed),
                                'taken': from_l})
        band = {'start': y0, 'lines': n, 'expr': expr}
        if y0 == table_end:
            rules['TAIL'] += 1
            band['lines'] = buffer_lines - y0
            band['tail'] = True
            tail_region = (y0, buffer_lines)
            for y in range(y0 + n, buffer_lines):
                want = S.add(S.mulc(seed, 65536), S.mulc(delta, y - y0))
                if band_lines.get(y) != want:
                    overridden.append(y)
        bands.append(band)
        i = j

    # EXT-WAVE: one band per run of consecutive wave lines whose index
    # expression steps by a constant; it runs to the buffer end when the
    # windows that show the rest of the buffer restart its phase (a
    # render-window artefact, listed in overridden_lines like TAIL's)
    wys = sorted(wave_lines)
    if wys:
        y0 = wys[0]
        if y0 in band_lines or any(b['start'] <= y0 < b['start'] + b['lines'] for b in bands):
            fail(name, f'wave band at line {y0} overlaps another band')
        run = [y0]
        for y in wys[1:]:
            if y != run[-1] + 1:
                break
            run.append(y)
        # the phase is anchored where the band starts; windows whose top lies
        # below the band start restart it one row later
        anchored = [y for y in run if choose_top(R, y) < y0]
        if len(anchored) < 2:
            fail(name, f'wave band at line {y0}: fewer than two lines drawn from a window above it')
        e = wave_params(model, R, [(y - y0, wave_lines[y]) for y in anchored], f'wave band at line {y0}')
        word, = SinsetMachine.phase_words(wave_lines[y0][2])
        for y in anchored:
            wave_recheck(model, wave_lines[y][4], e, y - y0, word, f'wave line {y}')
        rest = [y for y in range(y0, buffer_lines) if y not in anchored]
        for y in rest:
            if y in band_lines or y < table_end:
                fail(name, f'wave band at line {y0}: line {y} below it is not a wave line')
        for y in wys:
            if y not in anchored:
                overridden.append(y)
        for y in range(anchored[-1] + 1, buffer_lines):
            if y not in wave_lines:
                fail(name, f'wave band at line {y0}: line {y} is not a wave line')
        bands.append({'start': y0, 'lines': buffer_lines - y0, 'expr': e})
        rules['WAVE'] = 1
        rules['WAVE_anchored_lines'] = [anchored[0], anchored[-1]]
    bands.sort(key=lambda b: b['start'])

    covered = set()
    for b in bands:
        covered.update(range(b['start'], b['start'] + b['lines']))
    stray = [y for y in band_lines if y not in covered]
    if stray:
        fail(name, f'accumulator lines outside any band: {stray[:8]}')
    for b in bands:
        for y in range(b['start'], b['start'] + b['lines']):
            if y < table_end and b['start'] >= table_end:
                fail(name, 'band overlaps the table')

    # EXT-WALK: does the render wrap its row walk at the buffer end?
    walk = row_walk(R, buffer_lines, row_of)

    bgy = vertical(R, rules)

    # background Y layers used
    used = set()
    for r in runs:
        used |= irc.expr_layers(r['expr'])
    for b in bands:
        used |= irc.expr_layers(b['expr'])
    used.discard('camera')
    layers = {k: {'C': model.layers[k]['C'], 'U': model.layers[k]['U']} for k in sorted(used)}
    gates = {model.layers[k]['gate'] for k in used if model.layers[k]['U']}
    if len(gates) > 1:
        fail(name, f'layers use different ramp gates: {gates}')

    rnd, act, era = int(Path(path).name[3]), int(Path(path).name[4]), Path(path).name[5]
    _, _, body = scroll_body(Path(path))
    ir = {
        'ir': IR_VERSION,
        'program': name,
        'shape': shape_key(body),
        'slot': {'round': rnd, 'act': act, 'era': era},
        'buffer_lines': buffer_lines,
        'layers': layers,
        'ramp_gate': gates.pop() if gates else None,
        'runs': runs,
        'table_end': table_end,
        'beyond_table': 'unwritten',
        'bands': bands,
        'bg_y': bgy,
        'corrections': corrections,
        'rules': {'WINDOW_windows': rules['WINDOW'], 'TAIL': rules['TAIL'], 'SEED': rules['SEED'],
                  'overridden_lines': ranges(overridden),
                  'vertical_run_stopped': rules['vertical_run_stopped'],
                  # EXT rules
                  'WINDOW_REACH_lines': rules['WINDOW_REACH'],
                  'FILES': sorted(f'{fn} from {src}' for fn, src in R.closure_calls),
                  'WAVE': rules.get('WAVE', 0),
                  'row_walk': walk},
    }
    if 'WAVE_anchored_lines' in rules:
        ir['rules']['WAVE_anchored_lines'] = rules['WAVE_anchored_lines']
    irc.validate(ir)
    ext = irc.ext_ops_used(ir)
    if ext:
        ir['notes'] = ('DRAFT: uses extension ops ' + ', '.join(ext) +
                       ' (tools/scroll/R7/ops.md); does not conform to tools/scroll/ir.md until they are merged')
    return ir


def row_walk(R, B, row_of):
    """EXT-WALK.  Read a window whose top lies within 224 lines of the buffer
    end and report whether the render's row walk wraps there."""
    tops = [t for t in range(B - ROW, B - DISPLAY, -1) if R.reachable(t)]
    if not tops:
        fail(R.name, f'no reachable window within {DISPLAY} lines of the buffer end {B}')
    t = tops[0]
    lines, _ = R.window(t)
    verdict, rows = None, []
    for i, word in enumerate(lines):
        y = t + i
        if y < B:
            continue
        r = row_of(word)
        if r is None:
            continue                     # not a table copy (a band line): no verdict from it
        rows.append(r)
        wraps = r == (y & (B - 1)) // ROW
        straight = r == y // ROW
        if wraps == straight:
            fail(R.name, f'window {t} line {i}: row {r} is neither the wrapped row nor the next row')
        if verdict not in (None, wraps):
            fail(R.name, f'window {t}: the row walk both wraps and does not')
        verdict = wraps
    out = {'probe_top': t, 'wraps': verdict}
    if verdict is False:
        out['rows_read_past_buffer'] = [min(rows), max(rows)]
        out['affected_window_tops_mod_buffer'] = [B - DISPLAY + 1, B - 1]
    return out


def ranges(ys):
    out = []
    for y in sorted(ys):
        if out and out[-1][1] == y - 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return out


# ----------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', help='retail files, e.g. R7/SCR71A.C')
    ap.add_argument('--round', type=int, help='every SCR program of this round')
    ap.add_argument('--write', action='store_true', help='write tools/scroll/R7/ir/<name>.json')
    args = ap.parse_args(argv)
    paths = [RETAIL / f for f in args.files]
    if args.round is not None:
        paths += [p for r, a, e, p in programs() if r == args.round]
    if not paths:
        ap.error('no programs given')
    failed = 0
    for p in paths:
        try:
            ir = derive(p)
        except (ExtractError, irc.IRError) as e:
            failed += 1
            print(f'extract.py: FAIL {e}', file=sys.stderr)
            continue
        text = json.dumps(ir, indent=1)
        if args.write:
            dest = HERE / 'ir' / (p.stem + '.json')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text + '\n')
            print(f'wrote {dest.relative_to(HERE.parents[2])}  ext={irc.ext_ops_used(ir) or "none"}')
        else:
            print(text)
    if failed:
        print(f'extract.py: {failed} of {len(paths)} programs failed', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
