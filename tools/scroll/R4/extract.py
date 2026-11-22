#!/usr/bin/env python3
"""Retail scroll() C -> scroll IR (tools/scroll/ir.md).

    python3 tools/scroll/extract.py R1/SCR11A.C [...]      print IR JSON
    python3 tools/scroll/extract.py --round 1 --write     write ir/R1/*.json
    python3 tools/scroll/irc.py tools/scroll/ir/R1/*.json -o F   C tables for evaluate.c

How it works (no program is named anywhere in this file):
  1. interp.py runs the routine with camera X, the camera X delta and the
     player X speed symbolic, once per render window: a window is the
     background Y the routine is handed (camera Y is made concrete so the
     routine's own index arithmetic runs).
  2. Every output line of every window is then one of
       - a copy of a table cell (the load that produced it is recorded), or
       - a value from a 16.16 accumulator the render steps line by line.
  3. The table cells become runs, the accumulator lines become bands, and
     each value is mapped onto the closed expression vocabulary.  Every
     mapped expression is then re-checked by evaluating the routine's own
     symbolic value and the IR formula on a grid of inputs; any difference
     aborts.
  4. A separate run with camera Y symbolic gives the background Y rule.

Stated rules, each counted in the output (`rules` in the JSON):
  WINDOW   Line y is read from the window whose top is the lowest multiple of
           8 that still shows y at the bottom of a 224-line screen, i.e.
           top = max(0, (y - 216) & ~7).  That window reaches y by walking
           down from above, as play does.
  TAIL     An accumulator band that begins exactly where the table ends runs
           to the end of the buffer.  Retail only ever shows the first 224
           lines of it; lines the chosen windows show differently beyond
           that point are listed under `overridden`.
  SEED     A band's first line is the layer its step subtracts
           (step = (T - L)*256/D, first line = L).  Where the routine seeds
           the accumulator from something else the IR takes L and records
           the literal seed under `corrections`.
Everything else is a loud failure naming the program and the reason.

R4 EXTENSIONS (this copy only; tools/scroll/extract.py is unchanged).  Each
is stated, counted in `rules`, and re-verified against the routine's own
value.  Documents that use none of them are byte-identical to the shared
extractor's (checked on all ten R1 documents by R4/check.py).
  PROVENANCE  A 32-bit read whose low half is one 2-byte cell and whose high
           half was never written as a unit (byte placeholders only) returns
           comp(low, high), so the low half keeps the table cell it was loaded
           from.  Same value as the shared read.  Needed where the render
           copies a table word through a union whose other half the
           decompiled C never sets (R4 zonescrsetsub0: hsw.w.h).
  XBRANCH  A symbolic branch whose condition's only input is camera X is
           decided in window runs, once per representative camera X on each
           side of every such constant.  A window keeps the representatives
           whose run produces its background Y; there must be one, their
           lines must agree, and the table cells must agree across all
           representatives.  (SCR41A: background Y is 512 when camera X >= 640.)
  WATER    Routines that read the water surface `waterposi` or the phase word
           `waterdirec` get them as inputs.  Windows run dry (surface 32767,
           which no 16-bit line passes; phase 0).  A separate set of wet runs
           then maps every line below the surface onto the `water` record
           (R4/ir.md) and re-verifies it line by line.
  INTERP   A table row hi(65536*L + m*div(k*(T - L), D)) with L, T layers is
           the op `interp` {from L, to T, k, D, m}.  Re-checked at 400 random
           layer values.
  PIECES   A background Y that is an absolute function of camera Y with
           conditions on camera X or camera Y (unsigned 16-bit compares) is
           the op `pieces`: ordered pieces {if, mul, add, shift}.  Verified
           at every camera Y 0..65535 for eleven camera X values.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/scroll/R4
SHARED = HERE.parent                             # tools/scroll
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))

import sym as S                                        # noqa: E402
from cfront import RETAIL, programs, scroll_body, shape_key, functions   # noqa: E402
from interp import InterpError, Machine, Pointer, Program, SymbolicControl, CAMERA_TRACKING   # noqa: E402
import irc                                             # noqa: E402
import irx                                             # noqa: E402

IR_VERSION = 'scroll-ir/1'
IRX_VERSION = irx.IR_VERSION     # the extended format, R4/ir.md
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

# EXT WATER: the water surface and the water phase word.  Dry windows put the
# surface at 32767, which `avp > waterposi` (signed 16-bit) never passes, and
# the phase word at 0.
WATER_SURFACE = 'waterposi'
WATER_PHASE = 'waterdirec'
DRY = [(WATER_SURFACE, 32767), (WATER_PHASE + '.w', 0)]


def reached_text(path):
    """Text of scroll() and every file-local function it reaches (camera
    tracking excluded), as census.py computes it."""
    text, funcs, _ = scroll_body(path)
    seen, todo = set(), ['scroll']
    while todo:
        f = todo.pop()
        if f in seen or f not in funcs or f in CAMERA_TRACKING:
            continue
        seen.add(f)
        todo.extend(re.findall(r'\b([A-Za-z_]\w*)\s*\(', funcs[f][1]))
    return ' '.join(funcs[f][1] for f in seen)


class XMachine(Machine):
    """Machine with the PROVENANCE read and the XBRANCH decision."""

    def __init__(self, program, inputs, buffers, decide_x=None):
        self.decide_x = decide_x
        self.decided = []
        self.provenance_reads = 0
        super().__init__(program, inputs, buffers)

    def read(self, oid, off, size):
        obj = self.state.objs[oid]
        if size == 4 and off >= 0 and (not obj.type.size or off + 4 <= obj.type.size):
            self.ensure(obj, off, 4)
            e, e2, e3 = obj.ent.get(off), obj.ent.get(off + 2), obj.ent.get(off + 3)
            if e is not None and e[0] == 2 and not isinstance(e[1], Pointer) \
                    and e2 is not None and e2[0] == 1 and e3 is not None and e3[0] == 1:
                lo = Machine.read(self, oid, off, 2)
                hi = Machine.read(self, oid, off + 2, 2)
                if not isinstance(lo, Pointer) and not isinstance(hi, Pointer):
                    self.provenance_reads += 1
                    return S.comp(lo, S.un(hi))
        return Machine.read(self, oid, off, size)

    def fork(self, code, then_pc, else_pc, join, cond, line):
        if self.decide_x is not None and S.atoms(cond) == {('var', 'X')}:
            d = S.evaluate(cond, {('var', 'X'): self.decide_x})
            self.decided.append((line, S.fmt(cond), d))
            if self.run(code, then_pc if d else else_pc, join)[0] != 'stop':
                raise SymbolicControl(f'{self.p.name}:{line}: decided branch does not rejoin')
            return
        return Machine.fork(self, code, then_pc, else_pc, join, cond, line)


class Runner:
    def __init__(self, path):
        self.path = Path(path)
        self.prog = Program(self.path)
        self.name = f'{self.path.parent.name}/{self.path.name}'
        self.int_union = self.prog.unit.typedefs['int_union']
        self.windows = {}
        self.rep_runs = {}
        code = reached_text(self.path)
        self.water = bool(re.search(rf'\b({WATER_SURFACE}|{WATER_PHASE})\b', code))
        self.x_reps = [None]
        self.provenance_windows = 0
        self.xbranch_windows = 0

    def machine(self, extra, decide_x=None):
        return XMachine(self.prog, HORIZONTAL_INPUTS + (DRY if self.water else []) + extra,
                        {'lphscrollbuff': ('hscrollbuff', self.int_union, 1024)}, decide_x)

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
        # XBRANCH: one representative camera X per truth assignment of the
        # conditions on camera X alone
        conds = [c for c in conditions(self.bgy_raw) if c[0] == 'camera_x']
        if conds:
            by_truth = {}
            for c in conds:
                for xv in (0, c[2] - 1, c[2], c[2] + 1):
                    xv = S.wrap(xv, 16, True)
                    key = tuple(cond_holds(d, {'camera_x': xv}) for d in conds)
                    by_truth.setdefault(key, xv)
            self.x_reps = [by_truth[k] for k in sorted(by_truth)]
        return self.bgy_raw

    def window(self, top):
        """Run with background Y = top.  Returns (lines, machine)."""
        if top in self.windows:
            return self.windows[top]
        cam = top
        if self.camera_for is not None:
            cam = self.camera_for.get(top & 0xFFFF)
            if cam is None:
                fail(self.name, f'no camera Y in 0..32767 gives background Y {top}')
        kept, runs, bgys = [], [], []
        for rep in self.x_reps:
            m = self.machine([('scra_v_posit.w.h', cam), ('scra_vz', 0), ('actwk[0].xposi.w.h', 0),
                              ('scrb_v_posit.w.h', top), ('scrb_v_posit.w.l', 0)], rep)
            m.call_function('scroll')
            bgy = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
            runs.append((rep, m))
            bgys.append(S.fmt(bgy))
            if bgy == top:
                kept.append((rep, m, [m.read('buf:hscrollbuff', 4 * i, 2) for i in range(DISPLAY)]))
        if not kept:
            fail(self.name, f'window {top}: routine set background Y to {" / ".join(bgys)}')
        rep, m, lines = kept[0]
        for rep2, m2, lines2 in kept[1:]:
            for i, (a, b) in enumerate(zip(lines, lines2)):
                if S.un(a) != S.un(b) or getattr(a, 'src', None) != getattr(b, 'src', None):
                    fail(self.name, f'window {top} line {i}: camera X {rep} and {rep2} render differently')
        if any(mm.decided for _, mm in runs):
            self.xbranch_windows += 1
        if any(mm.provenance_reads for _, mm in runs):
            self.provenance_windows += 1
        self.rep_runs[top] = runs
        self.windows[top] = (lines, m, rep)
        return self.windows[top]


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


def to_expr(model, v, what):
    """Map background X (symbolic) onto the IR vocabulary: one layer, plus at
    most one accumulator term (everything that is not a layer is taken
    together and must be exactly the high word of one accumulator)."""
    ie = interp_expr(model, v, what)          # EXT INTERP
    if ie is not None:
        return ie
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


# ----------------------------------------------------------------- EXT INTERP

def interp_expr(model, v, what):
    """v == hi(65536*L + m*div(k*(T - L), D)) with L, T layers (T may be the
    camera): the op `interp` (R4/ir.md).  None when v does not have that
    form; a loud failure when it has it but the parameters do not reproduce
    the routine's value."""
    v = S.un(v)
    if not (isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi'):
        return None
    terms, c = S.lin_parts(v[1])
    if c or len(terms) != 2:
        return None
    base = [a for a, k in terms.items() if k == 65536 and model.layer_of(a) not in (None, 'camera')]
    divs = [(a, k) for a, k in terms.items() if isinstance(a, tuple) and a[0] == 'div']
    if len(base) != 1 or len(divs) != 1:
        return None
    L = base[0]
    (dv, m), = divs
    num, D, signed = S.un(dv[1]), dv[2], dv[3]
    if not signed:
        fail(model.name, f'{what}: unsigned interpolation division')
    diff_bits = 32
    nt, nc = S.lin_parts(num)
    if not nc and len(nt) == 1:
        # k * s16(T - L)
        (a, k), = nt.items()
        a = S.un(a)
        if isinstance(a, tuple) and a[0] == 'trunc' and a[2] == 16 and a[3]:
            diff_bits = 16
            nt, nc = S.lin_parts(S.mulc(S.un(a[1]), k))
    if nc or len(nt) != 2 or L not in nt:
        fail(model.name, f'{what}: interpolation numerator is not k*(T - L): {S.fmt(num)}')
    k = -nt[L]
    (T, kt), = [(a, kk) for a, kk in nt.items() if a != L]
    if kt != k or k <= 0:
        fail(model.name, f'{what}: interpolation numerator is not k*(T - L): {S.fmt(num)}')
    to_l, from_l = model.layer_of(T), model.layer_of(L)
    if to_l is None:
        fail(model.name, f'{what}: interpolation target is not a layer: {S.fmt(T)}')
    e = {'op': 'interp', 'from': from_l, 'to': to_l, 'k': k, 'D': D, 'm': m, 'diff_bits': diff_bits}
    rng = random.Random(2)
    for _ in range(400):
        tv, fv = rng.randint(-32768, 32767), rng.randint(-32768, 32767)
        got = S.wrap(S.evaluate(v, _layer_env(model, {T: tv, L: fv})), 16, True)
        if got != S.wrap(interp_value(e, fv, tv), 16, True):
            fail(model.name, f'{what}: interp parameters {e} do not reproduce the row at to={tv} from={fv}')
    return e


def interp_value(e, frm, to):
    """Reference semantics of `interp` (mirrors R4/evaluate_x.c)."""
    d = to - frm
    if e['diff_bits'] == 16:
        d = S.wrap(d, 16, True)
    q = S.div(e['k'] * d, e['D'], True)
    return frm + ((e['m'] * q) >> 16)


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


# ----------------------------------------------------------------- vertical

def unclamp(v, rules):
    """CLAMP0: hi(A < 0 ? 0 : A) with A the accumulated background Y is hi(A)
    wherever A >= 0.  A is 65536 * C * camera Y / 256 for a rate, so the
    clamp can fire only for a camera Y < 0, which no stage reaches (every
    stage's top limit is >= 0, src/scroll_limits.h).  Recorded in
    corrections; verified at 2000 random A >= 0."""
    if not (isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi'):
        return v
    inner = S.un(v[1])
    if not (isinstance(inner, tuple) and inner[0] == 'sel' and S.un(inner[2]) == 0):
        return v
    c = S.un(inner[1])
    a = S.un(inner[3])
    if not (isinstance(c, tuple) and c[0] == 'cmp' and c[1] == '<' and S.un(c[3]) == 0 and not c[4]
            and S.un(c[2]) == a):
        return v
    out = S.half(a, 'hi')
    rng = random.Random(4)
    leaves = sorted(S.atoms(a))
    for _ in range(2000):
        env = {k: rng.randrange(-1 << 31, 1 << 31) for k in leaves}
        if S.evaluate(a, env) < 0:
            continue
        if S.evaluate(v, env) != S.evaluate(out, env):
            raise ExtractError(f'CLAMP0: {S.fmt(v)} differs from {S.fmt(out)} at a non-negative sum')
    rules['CLAMP0'] = {'rule': 'CLAMP0', 'literal': S.fmt(v), 'taken': S.fmt(out),
                       'why': 'the clamp fires only when the accumulated background Y is negative, '
                              'i.e. for a camera Y < 0, which no stage reaches'}
    return out


def vertical(runner, rules):
    v, stopped = unclamp(runner.bgy_raw, rules), runner.bgy_stopped
    start = ('init', 'scrb_v_posit.l', 32, True)
    terms, c = S.lin_parts(v if not (isinstance(v, tuple) and v[0] == 'half') else S.un(v[1]))
    if isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi' and terms.get(start) == 1 and not c \
            and set(terms) == {start, VZ}:
        out = {'op': 'rate', 'C': terms[VZ]}
    elif ('var', 'X') in S.atoms(v) and S.atoms(v) <= {('var', 'Y'), ('var', 'PX'), ('var', 'X')}:
        out = pieces(runner, v, rules)          # EXT PIECES
        rules['vertical_run_stopped'] = stopped
        return out
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
        cm.call_function('scroll')
        got = S.un(cm.load(cm.lvalue(cm.parse_expr('scrb_v_posit.w.h')))[0])
        env = _Default({('var', 'Y'): yv, ('var', 'PX'): pv, ('var', 'VZ'): d << 8,
                        ('init', 'scrb_v_posit.l'): a << 16})
        raw = runner.bgy_raw          # the routine's own value, before any mapping rule
        if got != S.wrap(S.evaluate(raw, env), 16, True):
            fail(runner.name, f'background Y from the symbolic run ({S.fmt(raw)}) differs from a concrete run')
    rules['vertical_run_stopped'] = stopped
    return out


# ----------------------------------------------------------------- EXT PIECES

COND_VARS = {('var', 'X'): 'camera_x', ('var', 'Y'): 'camera_y', ('var', 'PX'): 'player_x'}
FLIP = {'<': '>', '>': '<', '<=': '>=', '>=': '<=', '==': '==', '!=': '!='}
NEGATE = {'<': '>=', '>=': '<', '>': '<=', '<=': '>', '==': '!=', '!=': '=='}


def input_name(x):
    x = S.un(x)
    if isinstance(x, tuple) and x[0] == 'var' and x[2] == 16 and x[3]:
        return COND_VARS.get((x[0], x[1]))
    return None


def cond_leaf(x):
    """(var name, unsigned) when x is one 16-bit input, as-is or as u16."""
    x = S.un(x)
    if input_name(x):
        return input_name(x), False
    if isinstance(x, tuple) and x[0] == 'trunc' and x[2] == 16 and not x[3] and input_name(x[1]):
        return input_name(x[1]), True
    return None


def conditions(v):
    """Every comparison of one input with a constant inside v:
    [(var, op, value, unsigned, node)], var in camera_x/camera_y/player_x."""
    found = {}

    def walk(x):
        x = S.un(x)
        if not isinstance(x, tuple):
            return
        if x[0] == 'cmp' and not x[4]:
            a, b = S.un(x[2]), S.un(x[3])
            if isinstance(b, int) and cond_leaf(a):
                var, uns = cond_leaf(a)
                found[x] = (var, x[1], b, uns, x)
            elif isinstance(a, int) and cond_leaf(b):
                var, uns = cond_leaf(b)
                found[x] = (var, FLIP[x[1]], a, uns, x)
        for p in S.children(x):
            walk(p)
    walk(v)
    return list(found.values())


def cond_holds(c, values):
    var, op, k, uns = c[0], c[1], c[2], c[3]
    x = values[var] & 0xFFFF if uns else S.wrap(values[var], 16, True)
    return {'<': x < k, '>': x > k, '<=': x <= k, '>=': x >= k, '==': x == k, '!=': x != k}[op]


REBUILD = {
    'half': lambda x, f: S.half(f(x[1]), x[2]),
    'comp': lambda x, f: S.comp(f(x[1]), f(x[2])),
    'trunc': lambda x, f: S.trunc(f(x[1]), x[2], x[3]),
    'div': lambda x, f: S.div(f(x[1]), x[2], x[3]),
    'mod': lambda x, f: S.mod(f(x[1]), x[2], x[3]),
    'shr': lambda x, f: S.shr(f(x[1]), x[2], x[3]),
    'mul': lambda x, f: S.mul(f(x[1]), f(x[2])),
    'band': lambda x, f: S.band(f(x[1]), f(x[2])),
    'bor': lambda x, f: S.bor(f(x[1]), f(x[2])),
    'bxor': lambda x, f: S.bxor(f(x[1]), f(x[2])),
    'bnot': lambda x, f: S.bnot(f(x[1])),
    'cmp': lambda x, f: S.cmp(x[1], f(x[2]), f(x[3]), x[4]),
    'lnot': lambda x, f: S.lnot(f(x[1])),
    'land': lambda x, f: S.land(f(x[1]), f(x[2])),
    'lor': lambda x, f: S.lor(f(x[1]), f(x[2])),
    'sel': lambda x, f: S.sel(f(x[1]), f(x[2]), f(x[3])),
    'byte': lambda x, f: S.byte(f(x[1]), x[2]),
}


def subst(x, table):
    """x with every node in `table` replaced by its value, rebuilt through
    sym.py so that decided selections collapse (identities only)."""
    x = S.un(x)
    if x in table:
        return table[x]
    if not isinstance(x, tuple) or x[0] in ('var', 'init', 'poison'):
        return x
    f = lambda y: subst(y, table)     # noqa: E731
    if x[0] == 'lin':
        out = x[2]
        for a, k in x[1]:
            out = S.add(out, S.mulc(f(a), k))
        return out
    return REBUILD[x[0]](x, f)


def u16_parts(x):
    """256*byte(w, 1) + u8(w) is u16(w): the two low bytes of a word that the
    interpreter merged byte by byte (a union written two ways in two arms)."""
    x = S.un(x)
    while isinstance(x, tuple) and x[0] == 'trunc' and x[2] == 16:
        inner = u16_parts(x[1])
        if inner is S.un(x[1]):
            break
        return S.trunc(inner, 16, x[3])
    t, c = S.lin_parts(x)
    if c or len(t) != 2 or not isinstance(x, tuple) or x[0] != 'lin':
        return x
    hi = [a for a, k in t.items() if k == 256 and isinstance(a, tuple) and a[0] == 'byte' and a[2] == 1]
    lo = [a for a, k in t.items() if k == 1 and isinstance(a, tuple) and a[0] == 'trunc' and a[2] == 8 and not a[3]]
    if len(hi) == 1 and len(lo) == 1 and \
            S.trunc(S.un(hi[0][1]), 16, False) == S.trunc(S.un(lo[0][1]), 16, False):
        return S.trunc(S.un(hi[0][1]), 16, False)
    return x


def strip_truncs(x):
    x = S.un(x)
    while isinstance(x, tuple) and x[0] == 'trunc':
        x = S.un(x[1])
    if isinstance(x, tuple) and x[0] == 'lin':
        out = x[2]
        for a, k in x[1]:
            out = S.add(out, S.mulc(strip_truncs(a), k))
        return S.un(out)
    return x


def affine_of(name, e):
    """{mul, add, shift} with e == (mul*u16(Y) + add) >> shift: read from e,
    verified by the caller at every camera Y."""
    e = u16_parts(S.un(e))
    if isinstance(e, int):
        return {'mul': 0, 'add': e, 'shift': 0}
    if cond_leaf(e) == ('camera_y', True) or cond_leaf(strip_truncs(e)) == ('camera_y', False):
        return {'mul': 1, 'add': 0, 'shift': 0}
    inner = e
    while isinstance(inner, tuple) and inner[0] == 'trunc' and inner[2] >= 16:
        inner = S.un(inner[1])
    if isinstance(inner, tuple) and inner[0] == 'half' and inner[2] == 'hi':
        t, c = S.lin_parts(strip_truncs(inner[1]))
        if set(t) == {('var', 'Y', 16, True)}:
            return {'mul': t[('var', 'Y', 16, True)], 'add': c, 'shift': 16}
    fail(name, f'background Y piece is not (mul*Y + add) >> shift: {S.fmt(e)}')


def piece_value(p, y):
    return (p['mul'] * (y & 0xFFFF) + p['add']) >> p['shift']


def bg_y_pieces_eval(rule, camera_x, camera_y, player_x):
    """Reference semantics of `pieces` (mirrors R4/evaluate_x.c)."""
    vals = {'camera_x': camera_x, 'camera_y': camera_y, 'player_x': player_x}
    hit = [p for p in rule['pieces']
           if all(cond_holds((c['var'], c['op'], c['value'], c['unsigned']), vals) for c in p['if'])]
    if len(hit) != 1:
        raise ExtractError(f'pieces: {len(hit)} pieces hold at X={camera_x} Y={camera_y} PX={player_x}')
    return piece_value(hit[0], camera_y)


def pieces(runner, v, rules):
    name = runner.name
    conds = conditions(v)
    if not conds or len(conds) > 6:
        fail(name, f'background Y depends on camera X outside a comparison: {S.fmt(v)}')
    regions = []
    for bits in range(1 << len(conds)):
        truth = [(bits >> i) & 1 for i in range(len(conds))]
        e = subst(v, {c[4]: tv for c, tv in zip(conds, truth)})
        if S.atoms(e) - {('var', 'Y')}:
            fail(name, f'background Y piece still depends on {S.atoms(e) - {("var", "Y")}}: {S.fmt(e)}')
        regions.append(({i: tv for i, tv in enumerate(truth)}, affine_of(name, e)))
    # merge regions that differ in one condition and share the formula
    merged = True
    while merged:
        merged = False
        for a in range(len(regions)):
            for b in range(a + 1, len(regions)):
                (ta, fa), (tb, fb) = regions[a], regions[b]
                if fa != fb or set(ta) != set(tb):
                    continue
                diff = [i for i in ta if ta[i] != tb[i]]
                if len(diff) == 1:
                    regions[a] = ({i: tv for i, tv in ta.items() if i != diff[0]}, fa)
                    del regions[b]
                    merged = True
                    break
            if merged:
                break
    out_pieces = []
    for truth, f in regions:
        conds_out = []
        for i in sorted(truth):
            var, op, k, uns = conds[i][:4]
            conds_out.append({'var': var, 'op': op if truth[i] else NEGATE[op], 'value': k, 'unsigned': uns})
        out_pieces.append({'if': conds_out, **f})
    out = {'op': 'pieces', 'pieces': out_pieces}
    # every camera Y, eleven camera X, three player X
    xs = sorted({0, 1, 0x7FFF, 0x8000, 0xFFFF, 16064} |
                {S.wrap(c[2] + d, 16, False) for c in conds if c[0] == 'camera_x' for d in (-1, 0, 1)})
    pxs = sorted({0, 0x800, 0xFFFF} |
                 {S.wrap(c[2] + d, 16, False) for c in conds if c[0] == 'player_x' for d in (-1, 0, 1)})
    for xv in xs:
        for pv in pxs:
            env = {('var', 'X'): xv, ('var', 'PX'): pv}
            for yv in range(65536):
                env[('var', 'Y')] = yv
                if S.evaluate(v, env) & 0xFFFF != bg_y_pieces_eval(out, xv, yv, pv) & 0xFFFF:
                    fail(name, f'background Y rule {out} differs at X={xv} Y={yv} PX={pv}')
    # completeness: concrete runs (camera X concrete too) land on the same value
    for yv, xv, pv in ((0, 0, 0), (511, 639, 0), (511, 640, 0), (512, 0, 0), (513, 700, 0x800),
                       (1296, 5000, 0), (37, 0x7FFF, 0), (2047, 1, 0)):
        cm = runner.machine([('scra_v_posit.w.h', yv), ('scra_vz', 0), ('actwk[0].xposi.w.h', pv),
                             ('scra_h_posit.w.h', xv), ('scrb_v_posit.w.h', 0), ('scrb_v_posit.w.l', 0)])
        try:
            cm.call_function('scroll')
        except SymbolicControl:
            pass            # the render may stop; the background Y is already set
        got = S.un(cm.load(cm.lvalue(cm.parse_expr('scrb_v_posit.w.h')))[0])
        if not isinstance(got, int) or got & 0xFFFF != bg_y_pieces_eval(out, xv, yv, pv) & 0xFFFF:
            fail(name, f'background Y of a concrete run at X={xv} Y={yv} ({S.fmt(got)}) differs from {out}')
    rules['PIECES'] = 1
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
    """Reference semantics of the bg_y vocabulary (mirrors evaluate.c)."""
    if rule['op'] == 'rate':
        return (rule['C'] * y) >> 8
    if rule['op'] == 'camera':
        f = rule.get('fold')
        if f and (player_x & 0xFFFF) >= f['player_x_min'] and (y & 0xFFFF) >= f['y_min']:
            return S.div(y - f['y_min'], f['div'], True) + f['y_min']
        return y
    raise ExtractError(f'unknown bg_y op {rule}')


# ----------------------------------------------------------------- EXT WATER

SURFACE_TRIALS = (0, 1, 7, 8, 9, 100, 223, 224, 300)
PHASE_WORDS = (0x0000, 0x0180, 0x2500, 0x807F, 0xFFFF, 0x7F00)


def table_definition(name):
    """Values of the unique initialised definition of `name` in the retail
    tree (the render reads it through an extern declaration)."""
    from cfront import strip_comments
    pat = re.compile(r'\b(unsigned\s+char|signed\s+char|char)\s+' + re.escape(name) +
                     r'\s*\[\s*(\d*)\s*\]\s*=\s*\{([^}]*)\}')
    hits = []
    for f in sorted(RETAIL.rglob('*.C')):
        text = f.read_text(errors='replace')
        if name not in text:
            continue
        for m in pat.finditer(strip_comments(text)):
            hits.append((f, m))
    if len(hits) != 1:
        raise ExtractError(f'{name}: {len(hits)} initialised definitions in the retail tree, expected 1: '
                           f'{[str(f.relative_to(RETAIL)) for f, _ in hits]}')
    f, m = hits[0]
    vals = [int(v, 0) for v in re.findall(r'-?(?:0[xX][0-9a-fA-F]+|\d+)', m.group(3))]
    if m.group(2) and int(m.group(2)) != len(vals):
        raise ExtractError(f'{name}: {len(vals)} initialisers for [{m.group(2)}]')
    return str(f.relative_to(RETAIL)), m.group(1), vals


def surface_line(cam, surface):
    """First screen line i with (int16)(cam + i) > (int16)surface, or None
    (normative semantics of the `water` record, R4/ir.md)."""
    for i in range(1 << 17):
        if S.wrap(cam + i, 16, True) > S.wrap(surface, 16, True):
            return i
        if S.wrap(cam + i, 16, True) == 32767:
            return None
    return None


def water(R, table_obj, base, buffer_lines, rules):
    """Map the lines below the water surface onto the `water` record and
    re-verify it on every line of every wet run."""
    name = R.name
    tops = []
    for top in (0, 8, 136, 256, 504, 512, 1000, buffer_lines - 232, buffer_lines - 8):
        if not 0 <= top < buffer_lines or top in tops:
            continue
        if R.camera_for is not None and R.camera_for.get(top) is None:
            continue
        lines, _, _ = R.window(top)
        if any(S.poisoned(S.un(w)) for w in lines):
            continue          # the render walks past the table there
        tops.append(top)
    if len(tops) < 5:
        fail(name, f'water: only {len(tops)} usable windows')
    table = None
    sign = None
    step = None
    n_runs = n_wet = 0
    rng = random.Random(3)
    for top in tops:
        dry, _, rep = R.window(top)
        cams = [top, 777, 32760] if R.camera_for is None else [R.camera_for[top]]
        for cam in cams:
            trials = [(cam, S.wrap(cam + s - 1, 16, True)) for s in SURFACE_TRIALS]
            trials += [(cam, 32767), (cam, -32768)]
            if cam == 32760:
                trials.append((cam, 32765))          # the line counter wraps below the surface
            for n, (cam_, surface) in enumerate(trials):
                word = PHASE_WORDS[(n + len(tops) + cam) % len(PHASE_WORDS)]
                P = word >> 8
                m = R.machine([('scra_v_posit.w.h', cam_), ('scra_vz', 0), ('actwk[0].xposi.w.h', 0),
                               ('scrb_v_posit.w.h', top), ('scrb_v_posit.w.l', 0),
                               (WATER_SURFACE, surface), (WATER_PHASE + '.w', word)], rep)
                m.call_function('scroll')
                n_runs += 1
                bgy = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
                if bgy != top:
                    fail(name, f'water: camera Y {cam_} gives background Y {S.fmt(bgy)}, not {top}')
                after = S.un(m.load(m.lvalue(m.parse_expr(WATER_PHASE + '.w')))[0])
                if not isinstance(after, int):
                    fail(name, f'water: the phase word ends as {S.fmt(after)}')
                st = (after - word) & 0xFFFF
                if step is None:
                    step = st
                elif st != step:
                    fail(name, f'water: phase step {st} after {step}')
                i0 = surface_line(cam_, surface)
                for i in range(DISPLAY):
                    wet = m.read('buf:hscrollbuff', 4 * i, 2)
                    d = dry[i]
                    if i0 is None or i < i0:
                        if S.un(wet) != S.un(d) or getattr(wet, 'src', None) != getattr(d, 'src', None):
                            fail(name, f'water: window {top} camera Y {cam_} surface {surface} line {i} '
                                       f'(above the surface) differs from the dry render')
                        continue
                    n_wet += 1
                    extra = S.atoms(wet) - S.atoms(d)
                    cells = [a for a in extra if a[0] == 'init' and re.fullmatch(r'\w+\[\d+\]', a[1])]
                    if len(cells) != 1 or len(extra) != 1:
                        fail(name, f'water: line {i} below the surface adds {sorted(extra)}, not one table cell')
                    tname, idx = cells[0][1][:-1].split('[')
                    idx = int(idx)
                    want_idx = (P + top + i) & 255
                    if idx != want_idx:
                        fail(name, f'water: window {top} line {i} phase {P} reads {tname}[{idx}], '
                                   f'expected [(phase + line) & 255] = [{want_idx}]')
                    if table is None:
                        table = tname
                    elif table != tname:
                        fail(name, f'water: two tables {table} and {tname}')
                    atoms = S.atoms(wet) | S.atoms(d)
                    for tv in (0x00, 0x7F, 0x80, 0xFF, rng.randrange(256)):
                        env = {a: rng.randrange(-1 << 31, 1 << 31) for a in atoms}
                        env[cells[0]] = tv
                        got = S.wrap(S.evaluate(wet, env), 16, True)
                        base_v = S.evaluate(d, env)
                        t8 = S.wrap(tv, 8, True)
                        s = [k for k in (1, -1) if S.wrap(base_v + k * t8, 16, True) == got]
                        if t8 == 0:
                            if got != S.wrap(base_v, 16, True):
                                fail(name, f'water: line {i} with table value 0 differs from the dry line')
                            continue
                        if len(s) != 1:
                            fail(name, f'water: line {i} is not the dry line plus or minus (int8){tname}[k]')
                        if sign is None:
                            sign = s[0]
                        elif sign != s[0]:
                            fail(name, f'water: line {i}: sign {s[0]} after {sign}')
    if table is None or n_wet == 0:
        fail(name, 'water: the routine reads the water inputs but no line changed below the surface')
    src, ctype, vals = table_definition(table)
    if len(vals) != 256:
        fail(name, f'water: {table} has {len(vals)} entries; the index is (phase + line) & 255')
    rules['WATER_runs'] = n_runs
    rules['WATER_lines'] = n_wet
    return {'surface': WATER_SURFACE, 'phase': {'word': WATER_PHASE, 'step': step},
            'table_name': table, 'table_source': src,
            'table': [S.wrap(v, 8, True) for v in vals],
            'sign': -sign}


# ----------------------------------------------------------------- derivation

def derive(path):
    R = Runner(path)
    name = R.name
    rules = {'WINDOW': 0, 'TAIL': 0, 'SEED': 0}
    R.vertical_raw()

    lines0, m0, _ = R.window(0)
    src0 = getattr(lines0[0], 'src', None)
    if src0 is None:
        fail(name, 'line 0 of window 0 is not a table cell')
    table_obj, base_off = src0
    tobj = next(o for o in m0.state.objs.values() if o.name == table_obj)
    esize = tobj.type.elem.size
    if esize != 2:
        fail(name, f'table {table_obj} has {esize}-byte entries, expected 2')
    base = base_off // esize

    buffer_lines = None
    for P in PERIODS:
        lp, _, _ = R.window(P)
        if getattr(lp[0], 'src', None) == src0:
            buffer_lines = P
            break
    if buffer_lines is None:
        fail(name, f'no window up to {PERIODS[-1]} shows table row 0 again: cannot read the buffer height')

    model = Model(R, m0)
    if not model.layers:
        fail(name, 'no layer positions found')

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

    # XBRANCH: the table must not depend on how a camera X branch went
    for rep, mm in R.rep_runs[0]:
        for i in range(tobj.type.n):
            if S.un(mm.read(f'g:{table_obj}', 2 * i, 2)) != cell_value(i):
                fail(name, f'table row {i - base} differs between camera X representatives')

    # rows written past the buffer are read only by a window that crosses the
    # buffer end, where the IR wraps: they must equal the rows they wrap to
    past = 0
    if n_written == rows:
        i = rows
        while base + i < tobj.type.n and written(base + i):
            if cell_value(base + i) != cell_value(base + i % rows):
                fail(name, f'table row {i} (past the {buffer_lines}-line buffer) differs from row {i % rows}, '
                           'which the wrap shows instead')
            i += 1
            past += 1

    # stitched lines (rule WINDOW)
    stitched = []
    for y in range(buffer_lines):
        top = max(0, (y - (DISPLAY - ROW)) & ~7)
        lines, _, _ = R.window(top)
        stitched.append(lines[y - top])
    rules['WINDOW'] = len({max(0, (y - (DISPLAY - ROW)) & ~7) for y in range(buffer_lines)})

    band_lines = {}
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

    bgy = vertical(R, rules)
    if 'CLAMP0' in rules:
        corrections.append(rules.pop('CLAMP0'))
        rules['CLAMP0_fired'] = 1
    wat = water(R, table_obj, base, buffer_lines, rules) if R.water else None

    # background Y layers used
    used = set()
    for r in runs:
        e = r['expr']
        if 'layer' in e:
            used.add(e['layer'])
    for b in bands:
        used.update((b['expr']['from'], b['expr']['to']))
    used.discard('camera')
    layers = {k: {'C': model.layers[k]['C'], 'U': model.layers[k]['U']} for k in sorted(used)}
    gates = {model.layers[k]['gate'] for k in used if model.layers[k]['U']}
    if len(gates) > 1:
        fail(name, f'layers use different ramp gates: {gates}')

    rnd, act, era = int(Path(path).name[3]), int(Path(path).name[4]), Path(path).name[5]
    _, _, body = scroll_body(Path(path))
    extended = bool(wat) or bgy['op'] not in ('rate', 'camera') or \
        any(r['expr']['op'] not in irc.EXPR_KEYS for r in runs)
    ir = {
        'ir': IRX_VERSION if extended else IR_VERSION,
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
                  'vertical_run_stopped': rules['vertical_run_stopped']},
    }
    if rules.get('CLAMP0_fired'):
        ir['rules']['CLAMP0'] = 1
    if extended:
        ir['water'] = wat
        ir['rules'].update({
            'PROVENANCE_windows': R.provenance_windows,
            'XBRANCH_windows': R.xbranch_windows,
            'rows_past_buffer': past,
            'WATER_runs': rules.get('WATER_runs', 0),
            'WATER_lines': rules.get('WATER_lines', 0),
            'PIECES': rules.get('PIECES', 0),
            'INTERP_rows': sum(r['entries'] for r in runs if r['expr']['op'] == 'interp'),
        })
        irx.validate(ir)
    else:
        irc.validate(ir)
    return ir


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
    ap.add_argument('files', nargs='*', help='retail files, e.g. R1/SCR11A.C')
    ap.add_argument('--round', type=int, help='every SCR program of this round')
    ap.add_argument('--write', action='store_true', help='write tools/scroll/R4/ir/<name>.json')
    args = ap.parse_args(argv)
    paths = [RETAIL / f for f in args.files]
    if args.round is not None:
        paths += [p for r, a, e, p in programs() if r == args.round]
    if not paths:
        ap.error('no programs given')
    for p in paths:
        ir = derive(p)
        text = json.dumps(ir, indent=1)
        if args.write:
            dest = HERE / 'ir' / (p.stem + '.json')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text + '\n')
            print(f'wrote {dest.relative_to(HERE.parents[1])}')
        else:
            print(text)


if __name__ == '__main__':
    try:
        main()
    except (ExtractError, irc.IRError, irx.IRError, InterpError) as e:
        print(f'extract.py: FAIL {e}', file=sys.stderr)
        sys.exit(1)
