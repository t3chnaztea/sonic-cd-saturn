#!/usr/bin/env python3
"""Retail scroll() C -> scroll IR, extended for Collision Chaos (R3).

    python3 tools/scroll/R3/extract.py R3/SCR31A.C [...]     print IR JSON
    python3 tools/scroll/R3/extract.py --round 3 --write     write tools/scroll/R3/ir/R3<act><era>.json
    python3 tools/scroll/R3/extract.py --no-scan ...         skip rule OVERRIDE's full window scan

This file is tools/scroll/extract.py copied and extended.  The shared file,
ir.md and evaluate.c are untouched.  Everything the foundation extractor does
is unchanged; every addition is marked `R3 EXTENSION En` below and emits the
document version `scroll-ir/1+R3`, whose extra ops are specified in
tools/scroll/R3/ir-extension.md and evaluated by tools/scroll/R3/evaluate_r3.c.

How it works is the foundation's (symbolic interpretation of the real C, one
run per render window, every mapping re-verified numerically).  The
extensions, each counted in the output's `rules`:

  E1 PHASE    A table index that depends on memory the routine advances by a
              constant each call (R3: `waterdirec.w += 64`, index
              `awasintbl[waterdirec.b.h + k]`) makes that memory a phase
              input.  It is found from the interpreter's own refusal (the
              refused pointer offset names it), made concrete, and the lines
              that read the table become a `wave` band.  The index relation
              idx = ((phase + speed) >> 8) + offset + k, masked, is checked at
              twelve phase values, including ones that wrap the table.
  E2 TABLES   A `wave` table defined in another file (awasintbl, TBL0.C) is
              read through the same interpreter from its defining file and
              copied into the document (closure over files).
  E3 INTERP   A table row whose value is hi(65536*L + F + m*trunc(n*d/D)),
              d = T - L (optionally narrowed to 16 bits), is an `interp` run:
              a 16.16 accumulator the routine steps once per ROW (the
              foundation's `ramp` steps once per line in a band).  F is 0, or
              the low half another step left behind (`seed`).  Re-verified at
              400 random layer values per row.
     UNINIT   When F is the low half of an uninitialised local (R3 act-D
              programs seed with `lD3.w.l = scrb` and never set lD3.w.h) the
              IR takes F = 0 and records the literal in `corrections`.
  E4 LINES    A non-table line whose value is a layer or a cloud (layer +
              one accumulator), and is not the first line of a 16.16 ramp,
              is a band of that expression (R3: one line per accumulator of
              the 64 per-line accumulators under row 88).
  E5 CLAMP    Background Y `(u16)camY <= ref ? max(min, base - ((ref -
              camY) >> shift)) : base` is bg_y `clamp`; checked at every
              camera Y 0..65535 for nine player X values.
  E6 REACH    With an absolute background Y, a window top no camera Y
              produces cannot be run.  Rule WINDOW's window for line y is
              then replaced by the nearest reachable top above it that still
              shows y; a line no reachable window shows is unreachable, is
              listed, and keeps the conventions (its table row if written,
              else unwritten).  BUFFER_MASK: when the window at the next
              period is unreachable, the buffer height is read from the
              `& M` the render applies to the background Y (the
              interpreter's refused offset) and checked against every
              reachable window.
  E7 OVERRIDE Every reachable window (not only the WINDOW ones) is compared,
              every line, with the document at four camera X values and two
              frame counts.  Lines some window shows differently are listed
              in `rules.overridden_lines` with the windows that do it.
Everything else is a loud failure naming the program and the reason.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCROLL = HERE.parent
sys.path.insert(0, str(SCROLL))
sys.path.insert(0, str(HERE))

import sym as S                                                 # noqa: E402
from cfront import RETAIL, programs, scroll_body, shape_key     # noqa: E402
from interp import Machine, Pointer, Program, SymbolicControl   # noqa: E402
import irx                                                      # noqa: E402

IR_VERSION = irx.IR_VERSION
DISPLAY = 224            # visible lines of the Mega CD screen
ROW = 8                  # lines per table entry
PERIODS = (64, 128, 256, 512, 1024, 2048)

X = ('var', 'X', 16, True)        # scra_h_posit.w.h: camera X after this frame's move
HZ = ('var', 'HZ', 16, True)      # scra_hz: this frame's camera X delta, 8.8
XS = ('var', 'XS', 16, True)      # actwk[0].xspeed.w: player X speed, 8.8
Y = ('var', 'Y', 16, True)        # scra_v_posit.w.h: camera Y
VZ = ('var', 'VZ', 16, True)      # scra_vz: camera Y delta, 8.8
PX = ('var', 'PX', 16, True)      # actwk[0].xposi.w.h: player X

HORIZONTAL_INPUTS = [('scroll_start.w', 0), ('scra_h_posit.w.h', X), ('scra_h_posit.w.l', 0),
                     ('scra_hz', HZ), ('actwk[0].xspeed.w', XS), ('scra_v_posit.w.l', 0)]

# E1: phase values (before the call) at which every wave index relation is checked
PHASE_PROBES = (0, 0x40, 0xC0, 0x100, 0x12F7, 0x3F80, 0x7FC0, 0x8000, 0xA5A5, 0xFF00, 0xFFC0, 0xFFFF)
# E7: inputs of the full window scan
SCAN_X = (0, 1234, 4097, 12345)
SCAN_FRAMES = (1, 777)


class ExtractError(Exception):
    pass


def fail(prog, msg):
    raise ExtractError(f'{prog}: {msg}')


# ----------------------------------------------------------------- running

class Recorder(Machine):
    """R3 EXTENSION E1/E6: a Machine that remembers the last pointer offset it
    refused because the offset was symbolic.  The refusal names what a table
    index depends on (a phase variable, or the background Y and its mask)."""
    refused = None

    def ptr_add(self, p, i, line):
        iv = S.un(i)
        if isinstance(p, Pointer) and not isinstance(iv, int):
            self.refused = iv
        return super().ptr_add(p, i, line)


class Runner:
    def __init__(self, path):
        self.path = Path(path)
        self.prog = Program(self.path)
        self.name = f'{self.path.parent.name}/{self.path.name}'
        self.int_union = self.prog.unit.typedefs['int_union']
        self.windows = {}
        self.phase = {}           # E1: phase lvalue -> value before the call
        self.phase_bits = {}
        self.camera_for = None
        self.reachable = None     # E6: background Y tops some camera Y produces (None: every top)
        self.vertical_refused = None

    def is_global(self, name):
        base = re.split(r'[.\[@]', name, maxsplit=1)[0]
        return base in self.prog.statics or base in self.prog.unit.externs

    def machine(self, extra, phase=None):
        ph = self.phase if phase is None else phase
        return Recorder(self.prog, HORIZONTAL_INPUTS + list(ph.items()) + extra,
                        {'lphscrollbuff': ('hscrollbuff', self.int_union, 1024)})

    def vertical_raw(self):
        """The routine's background Y as a symbolic value of camera Y (Y),
        its delta (VZ), player X (PX) and the previous background Y."""
        m = self.machine([('scra_v_posit.w.h', Y), ('scra_vz', VZ), ('actwk[0].xposi.w.h', PX)])
        try:
            m.call_function('scroll')
            stopped = None
        except SymbolicControl as e:
            stopped = str(e)
            self.vertical_refused = m.refused
        self.bgy_raw = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
        self.bgy_stopped = stopped
        self.camera_for = None
        if ('init', 'scrb_v_posit.l') not in S.atoms(self.bgy_raw):
            self.camera_for = {}
            env = _Default({('var', 'PX'): 0, ('var', 'VZ'): 0})
            for y in range(65536):
                env[('var', 'Y')] = y
                b = S.evaluate(self.bgy_raw, env) & 0xFFFF
                self.camera_for.setdefault(b, S.wrap(y, 16, True) if y < 32768 else None)
            # E6: the tops a camera Y in 0..32767 produces
            self.reachable = {b for b, c in self.camera_for.items() if c is not None}
        return self.bgy_raw

    def discover_phase(self, m, rules):
        """E1: the run stopped on a symbolic table offset.  If every symbol
        in the offset is a scalar global the routine does not treat as a
        layer or an input, make it a phase input (value 0) and report True."""
        refused = m.refused
        if refused is None:
            return False
        leaves = S.atoms(refused)
        if not leaves or any(k != 'init' or not self.is_global(n) for k, n in leaves):
            return False
        for _, n in leaves:
            if n in self.phase:
                return False
            lv = m.lvalue(m.parse_expr(n))
            bits = getattr(lv.type, 'bits', None)
            if bits != 16:
                fail(self.name, f'phase variable {n} is not a 16-bit integer')
            self.phase[n] = 0
            self.phase_bits[n] = bits
            rules['PHASE'] += 1
        return True

    def window(self, top, phase=None, rules=None):
        """Run with background Y = top.  Returns (lines, machine)."""
        def key():
            return (top, tuple(sorted((self.phase if phase is None else phase).items())))
        if key() in self.windows:
            return self.windows[key()]
        cam = top
        if self.camera_for is not None:
            cam = self.camera_for.get(top & 0xFFFF)
            if cam is None:
                fail(self.name, f'no camera Y in 0..32767 gives background Y {top}')
        while True:
            m = self.machine([('scra_v_posit.w.h', cam), ('scra_vz', 0), ('actwk[0].xposi.w.h', 0),
                              ('scrb_v_posit.w.h', top), ('scrb_v_posit.w.l', 0)], phase)
            try:
                m.call_function('scroll')
                break
            except SymbolicControl:
                if phase is not None or rules is None or not self.discover_phase(m, rules):
                    raise
        bgy = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
        if bgy != top:
            fail(self.name, f'window {top}: routine set background Y to {S.fmt(bgy)}')
        lines = []
        for i in range(DISPLAY):
            lines.append(m.read('buf:hscrollbuff', 4 * i, 2))
        self.windows[key()] = (lines, m)
        return self.windows[key()]

    def phase_after(self, m):
        """E1: {phase variable: value after the call} of a finished run."""
        return {n: S.un(m.load(m.lvalue(m.parse_expr(n)))[0]) for n in self.phase}


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
        self.runner = runner
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

    # R3 EXTENSION E3: an init atom of a local the routine never set
    def is_uninit_local(self, atom):
        a = S.un(atom)
        return isinstance(a, tuple) and a[0] == 'init' and not self.runner.is_global(a[1])


def to_expr(model, v, what, ctx=None):
    """Map background X (symbolic) onto the IR vocabulary: one layer, plus at
    most one accumulator term; or (E3) one row interpolation."""
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
            # R3 EXTENSION E3
            e = interp_of(model, v, what, ctx)
            if e is not None:
                return e
            fail(model.name, f'{what}: {S.fmt(remainder)} is neither a layer nor one accumulator '
                             f'nor a row interpolation (in {S.fmt(v)})')
        clouds.append(acc)
    if not layers and not clouds:
        return {'op': 'zero'}
    if len(layers) == 1 and not clouds:
        return {'op': 'layer', 'layer': layers[0]}
    if len(layers) == 1 and len(clouds) == 1 and layers[0] != 'camera':
        return {'op': 'cloud', 'layer': layers[0], 'speed': clouds[0][2]}
    fail(model.name, f'{what}: combination outside the vocabulary: {S.fmt(v)}')


# ----------------------------------------------------------------- R3 EXTENSION E3: row interpolations

def _difference(model, num, what):
    """num == n * [s16](T - L): returns (n, T atom, L atom, diff_bits)."""
    t, c = S.lin_parts(num)
    if c:
        fail(model.name, f'{what}: interpolation numerator has a constant: {S.fmt(num)}')
    if len(t) == 1:
        (a, n), = t.items()
        a = S.un(a)
        if not (isinstance(a, tuple) and a[0] == 'trunc' and a[2] == 16 and a[3]):
            fail(model.name, f'{what}: interpolation numerator is not n*s16(difference): {S.fmt(num)}')
        dt, dc = S.lin_parts(a[1])
        bits = 16
    elif len(t) == 2:
        vals = sorted(t.values())
        if vals[0] != -vals[1]:
            fail(model.name, f'{what}: interpolation numerator is not n*(to - from): {S.fmt(num)}')
        n = vals[1]
        dt, dc = {a: k // n for a, k in t.items()}, 0
        bits = 32
    else:
        fail(model.name, f'{what}: interpolation numerator is not a difference: {S.fmt(num)}')
    if dc or len(dt) != 2 or sorted(dt.values()) != [-1, 1]:
        fail(model.name, f'{what}: interpolation difference is not (to - from): {S.fmt(num)}')
    to = [a for a, k in dt.items() if k == 1][0]
    frm = [a for a, k in dt.items() if k == -1][0]
    return n, to, frm, bits


def _step_part(model, term, coef, what):
    """coef * div(n*d, D) -> dict(from, to, n, D, m, diff_bits) plus atoms."""
    term = S.un(term)
    if not (isinstance(term, tuple) and term[0] == 'div' and term[3]):
        return None
    n, to, frm, bits = _difference(model, term[1], what)
    to_l, from_l = model.layer_of(to), model.layer_of(frm)
    if to_l is None or from_l is None or from_l == 'camera':
        fail(model.name, f'{what}: interpolation ends are not (layer, layer or camera)')
    return {'from': from_l, 'to': to_l, 'n': n, 'D': term[2], 'm': coef, 'diff_bits': bits}, (to, frm)


def interp_of(model, v, what, ctx):
    """v == hi(65536*L + F + m*div(n*[s16](T - L), D)) -> an interp expression.
    F is 0, u16(m2*div(...)) (a seed another step left behind) or u16 of an
    uninitialised local (rule UNINIT: taken as 0)."""
    v = S.un(v)
    if not (isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi'):
        return None
    terms, c = S.lin_parts(v[1])
    if c:
        return None
    base = [a for a, k in terms.items() if k == 65536 and model.layer_of(a) not in (None, 'camera')]
    if len(base) != 1:
        return None
    L_atom = base[0]
    rest = {a: k for a, k in terms.items() if a != L_atom}
    steps = [(a, k) for a, k in rest.items() if isinstance(S.un(a), tuple) and S.un(a)[0] == 'div']
    if len(steps) != 1:
        return None
    step_atom, m = steps[0]
    sp = _step_part(model, step_atom, m, what)
    if sp is None or sp[1][1] != L_atom:
        return None
    part, atoms = sp
    seeds = [(a, k) for a, k in rest.items() if a != step_atom]
    seed, uninit = None, None
    if seeds:
        if len(seeds) != 1 or seeds[0][1] != 1:
            return None
        s = S.un(seeds[0][0])
        if not (isinstance(s, tuple) and s[0] == 'trunc' and s[2] == 16 and not s[3]):
            return None
        leaves = S.atoms(s)
        if leaves and all(k == 'init' and model.is_uninit_local(('init', n)) for k, n in leaves):
            uninit = S.fmt(s)
        else:
            st, sc = S.lin_parts(s[1])
            if sc or len(st) != 1:
                fail(model.name, f'{what}: interpolation seed is not u16(m*div(...)): {S.fmt(s)}')
            (sa, sm), = st.items()
            sp = _step_part(model, sa, sm, what)
            if sp is None:
                fail(model.name, f'{what}: interpolation seed is not u16(m*div(...)): {S.fmt(s)}')
            seed = sp[0]
    e = dict(op='interp', **part, seed=seed)
    # re-check numerically: 400 random layer pairs (uninitialised locals at 0)
    rng = random.Random(3)
    to_atom = atoms[0]
    for _ in range(400):
        tv, fv = rng.randint(-32768, 32767), rng.randint(-32768, 32767)
        env = _layer_env(model, {to_atom: tv, L_atom: fv})
        got = S.evaluate(v, env) & 0xFFFF
        want = irx.interp_value(e, {e['from']: fv, e['to']: tv,
                                    **({e['seed']['from']: fv, e['seed']['to']: tv} if seed else {})}) & 0xFFFF
        if got != want:
            fail(model.name, f'{what}: interp parameters {e} do not reproduce the row at to={tv} from={fv}')
    if seed and {seed['from'], seed['to']} != {e['from'], e['to']}:
        fail(model.name, f'{what}: the seed interpolates other layers than the row')
    if uninit is not None:
        if ctx is None:
            fail(model.name, f'{what}: uninitialised seed {uninit} outside a derivation')
        ctx['uninit'].append((what, uninit))
    return e


# ----------------------------------------------------------------- R3 EXTENSION E1: wave lines

def _table_term(a):
    """('trunc', init NAME[i] (8 bits), 8, signed) or init NAME[i] -> (NAME, i, signed)."""
    a = S.un(a)
    signed = False
    if isinstance(a, tuple) and a[0] == 'trunc' and a[2] == 8:
        signed = a[3]
        a = S.un(a[1])
    if isinstance(a, tuple) and a[0] == 'init' and a[2] == 8:
        m = re.fullmatch(r'(\w+)\[(\d+)\]', a[1])
        if m:
            return m.group(1), int(m.group(2)), signed
    return None


def wave_term(model, v, what):
    """background X == layer + scale * table[i]  ->  dict, or None."""
    terms, c = S.lin_parts(v)
    tab = [(a, k) for a, k in terms.items() if _table_term(a)]
    if not tab:
        return None
    if len(tab) != 1 or c:
        fail(model.name, f'{what}: more than one table read, or a constant: {S.fmt(v)}')
    a, scale = tab[0]
    name, idx, signed = _table_term(a)
    if not model.runner.is_global(name):
        fail(model.name, f'{what}: table {name} is not a global array')
    rest = {x: k for x, k in terms.items() if x != a}
    if len(rest) != 1 or list(rest.values()) != [1]:
        fail(model.name, f'{what}: a table read without exactly one layer: {S.fmt(v)}')
    L = model.layer_of(list(rest)[0])
    if L is None or L == 'camera':
        fail(model.name, f'{what}: a table read rides {S.fmt(list(rest)[0])}, not a layer')
    return {'layer': L, 'table': name, 'index': idx, 'scale': scale, 'signed': signed}


def table_data(runner, name, signed):
    """E2: the values of global table `name`, from the file that defines it
    (this program, or exactly one file of the retail tree), as the routine
    reads them."""
    pat = re.compile(rf'(?m)^[^;{{}}()]*\b{re.escape(name)}\s*\[\s*\d*\s*\]\s*=')
    if name in runner.prog.statics and runner.prog.statics[name][1] is not None:
        prog, where = runner.prog, runner.name
    else:
        found = []
        for f in sorted(RETAIL.glob('*.C')) + sorted(runner.path.parent.glob('*.C')):
            if pat.search(f.read_text(errors='replace')):
                found.append(f)
        if len(found) != 1:
            fail(runner.name, f'table {name}: {len(found)} defining files ({[p.name for p in found]})')
        prog, where = Program(found[0]), found[0].relative_to(RETAIL).as_posix()
    m = Machine(prog, [], {})
    lv = m.global_lv(name)
    if lv is None or not hasattr(lv.type, 'elem') or lv.type.elem.size != 1:
        fail(runner.name, f'table {name}: not an array of bytes in {where}')
    vals = []
    for i in range(lv.type.n):
        b = S.un(m.read(lv.oid, i, 1))
        if not isinstance(b, int):
            fail(runner.name, f'table {name}[{i}] has no constant initialiser in {where}')
        vals.append(S.wrap(b, 8, signed))
    return {'source': f'{where}:{name} ({"s8" if signed else "u8"} as read)', 'values': vals}


# ----------------------------------------------------------------- ramps (foundation)

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

def vertical(runner, rules):
    v, stopped = runner.bgy_raw, runner.bgy_stopped
    start = ('init', 'scrb_v_posit.l', 32, True)
    terms, c = S.lin_parts(v if not (isinstance(v, tuple) and v[0] == 'half') else S.un(v[1]))
    if isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi' and terms.get(start) == 1 and not c \
            and set(terms) == {start, VZ}:
        out = {'op': 'rate', 'C': terms[VZ]}
    else:
        leaves = S.atoms(v)
        if not leaves <= {('var', 'Y'), ('var', 'PX')} or ('var', 'Y') not in leaves:
            fail(runner.name, f'background Y is outside the vocabulary: {S.fmt(v)}')
        candidates = []
        cam = {'op': 'camera'}
        fold = find_fold(v)
        if fold:
            cam['fold'] = fold
        candidates.append(cam)
        clamp = find_clamp(v)            # R3 EXTENSION E5
        if clamp:
            candidates.append(clamp)
        out = None
        for cand in candidates:
            if all(S.wrap(S.evaluate(v, {('var', 'Y'): yv, ('var', 'PX'): pv}), 16, True) ==
                   S.wrap(bg_y_eval(cand, yv, pv), 16, True)
                   for yv in range(0, 65536) for pv in (0, 1, 0x7FF, 0x800, 0x801, 0x1000, 0x2000, 0x3000, 0x7FFF)
                   if pv in (0, 0x800) or yv % 7 == 0):
                out = cand
                break
        if out is None:
            fail(runner.name, f'background Y is outside the vocabulary (tried {candidates}): {S.fmt(v)}')
        if out['op'] == 'clamp':
            rules['CLAMP'] += 1
    for yv, pv, a, d in ((0, 0, 0, 0), (480, 0x800, 3, 2), (1000, 0x900, 100, -5),
                         (1808, 0x100, 7, 16), (481, 0x2000, 60, 1), (37, 0, 1, -16)):
        cm = runner.machine([('scra_v_posit.w.h', yv), ('scra_vz', d << 8), ('actwk[0].xposi.w.h', pv),
                             ('scrb_v_posit.w.h', a), ('scrb_v_posit.w.l', 0)])
        cm.call_function('scroll')
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
        return None
    return {'player_x_min': found['px'].pop(), 'y_min': found['y'].pop(), 'div': found['div'].pop()}


def find_clamp(v):
    """R3 EXTENSION E5: constants of
         (u16)Y <= ref ? max(min, s16(base - ((ref - (u16)Y) >> shift))) : base
    read from the value's own comparison, shift and clamp nodes; the caller
    checks the rule at every camera Y."""
    v = S.un(v)
    if not (isinstance(v, tuple) and v[0] == 'sel'):
        return None
    cond, inner, outer = S.un(v[1]), S.un(v[2]), S.un(v[3])
    if not (isinstance(cond, tuple) and cond[0] == 'cmp' and cond[1] == '<=' and isinstance(S.un(cond[3]), int)
            and S.atoms(cond[2]) == {('var', 'Y')} and isinstance(outer, int)):
        return None
    ref, base = S.un(cond[3]), outer
    if not (isinstance(inner, tuple) and inner[0] == 'sel' and isinstance(S.un(inner[2]), int)):
        return None
    lo = S.un(inner[2])
    shifts = set()

    def walk(x):
        x = S.un(x)
        if isinstance(x, tuple):
            if x[0] == 'shr':
                shifts.add(x[2])
            for p in S.children(x):
                walk(p)
    walk(inner[3])
    if len(shifts) != 1:
        return None
    return {'op': 'clamp', 'ref': ref, 'base': base, 'shift': shifts.pop(), 'min': lo}


def bg_y_eval(rule, y, player_x):
    return irx.bg_y_value(rule, y, player_x)


# ----------------------------------------------------------------- R3 EXTENSION E6: buffer from the mask

def render_mask(R):
    """The `& M` (M = 2^k - 8) the render applies to the background Y before
    indexing the table, read from the offset the symbolic-Y run refused."""
    ref = R.vertical_refused
    if ref is None:
        fail(R.name, 'no refused table offset to read the buffer mask from')
    bg = R.bgy_raw
    masks = set()

    def walk(x):
        x = S.un(x)
        if isinstance(x, tuple):
            if x[0] == 'band':
                for a, b in ((x[1], x[2]), (x[2], x[1])):
                    a, b = S.un(a), S.un(b)
                    if isinstance(b, int) and b & 7 == 0 and ((b + 8) & (b + 7)) == 0 and S.un(a) == bg:
                        masks.add(b)
            for p in S.children(x):
                walk(p)
    walk(ref)
    if len(masks) != 1:
        fail(R.name, f'buffer mask: found {sorted(masks)} in the refused offset {S.fmt(ref)}')
    return masks.pop()


# ----------------------------------------------------------------- R3 EXTENSION E7: numeric window checks

class StrictEnv(dict):
    """Inputs for evaluating a window word; an uninitialised local is 0 (rule
    UNINIT), any other unknown leaf is a loud failure."""

    def __init__(self, model, *a):
        super().__init__(*a)
        self.model = model

    def __missing__(self, key):
        if key[0] == 'init' and self.model.is_uninit_local(('init', key[1])):
            return 0
        raise ExtractError(f'{self.model.name}: window value depends on {key}, which the scan does not set')

    def __contains__(self, key):
        return True


def word_env(model, tables_raw, x, f):
    env = {('var', 'X'): x, ('var', 'HZ'): 0, ('var', 'XS'): 0}
    for name, L in model.layers.items():
        env[('init', f'{name}.l')] = S.wrap(L['C'] * x * 256, 32, True)
    for oname, base, speed, cells, elem in model.accs:
        prev = ((f - 1) * speed) & S.M32
        for i, cell in enumerate(sorted(cells, key=lambda c: int(c.split('[')[1][:-1]))):
            env[('init', cell)] = prev if elem.size == 4 else (prev >> (16 * i)) & 0xFFFF
    for tname, raw in tables_raw.items():
        for i, b in enumerate(raw):
            env[('init', f'{tname}[{i}]')] = b
    return StrictEnv(model, env)


def phase_for_frame(R, f):
    """E1: phase variables before call number f, given `speed` per call from 0."""
    return {n: ((f - 1) * R.phase_speed[n]) & ((1 << R.phase_bits[n]) - 1) for n in R.phase}


def scan_windows(R, model, ir, tables_raw):
    tops = sorted(t for t in R.reachable if t < ir['buffer_lines']) if R.reachable is not None \
        else list(range(ir['buffer_lines']))
    bad = {}
    cache = {}
    for f in SCAN_FRAMES:
        phase = phase_for_frame(R, f)
        envs = {x: word_env(model, tables_raw, x, f) for x in SCAN_X}
        for t in tops:
            lines, m = R.window(t, phase)
            after = R.phase_after(m)
            for n in R.phase:
                if (after[n] - phase[n]) & ((1 << R.phase_bits[n]) - 1) != R.phase_speed[n]:
                    fail(R.name, f'window {t}: {n} advanced by {after[n] - phase[n]}, '
                                 f'not {R.phase_speed[n]} as in window 0')
            for i, word in enumerate(lines):
                y = t + i
                for x in SCAN_X:
                    k = (x, y, f)
                    if k not in cache:
                        cache[k] = irx.raster_x(ir, x, y, f, 0)
                    got = -S.evaluate(word, envs[x])
                    if (got - cache[k]) & 0xFFFF:
                        bad.setdefault(y, set()).add(t)
                        break
    return bad


# ----------------------------------------------------------------- derivation

def derive(path, scan=True):
    R = Runner(path)
    name = R.name
    rules = {'WINDOW': 0, 'TAIL': 0, 'SEED': 0, 'PHASE': 0, 'REACH': 0, 'UNINIT': 0,
             'BUFFER_MASK': 0, 'CLAMP': 0}
    ctx = {'uninit': []}
    R.vertical_raw()

    lines0, m0 = R.window(0, rules=rules)
    # E1: phase speed, read from window 0
    R.phase_speed = {}
    after0 = R.phase_after(m0)
    for n in R.phase:
        d = (after0[n] - R.phase[n]) & ((1 << R.phase_bits[n]) - 1)
        if not isinstance(d, int) or d == 0:
            fail(name, f'phase variable {n} does not advance by a constant')
        R.phase_speed[n] = d
    if len(R.phase) > 1:
        fail(name, f'more than one phase variable: {sorted(R.phase)}')

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
    unreachable_period = False
    for P in PERIODS:
        if R.reachable is not None and (P & 0xFFFF) not in R.reachable:
            unreachable_period = True
            break
        lp, _ = R.window(P)
        if getattr(lp[0], 'src', None) == src0:
            buffer_lines = P
            break
    if buffer_lines is None:
        if not unreachable_period:
            fail(name, f'no window up to {PERIODS[-1]} shows table row 0 again: cannot read the buffer height')
        # E6 BUFFER_MASK
        M = render_mask(R)
        buffer_lines = M + 8
        rules['BUFFER_MASK'] = 1

    model = Model(R, m0)
    if not model.layers:
        fail(name, 'no layer positions found')

    def cell_value(i):
        return S.un(m0.read(f'g:{table_obj}', 2 * i, 2))

    def written(i):
        return cell_value(i) != ('init', f'{table_obj}[{i}]', 16, True)

    rows = buffer_lines // ROW
    if base + rows > tobj.type.n:
        rows = tobj.type.n - base       # the table cannot pass the end of its array
    n_written = 0
    while n_written < rows and written(base + n_written):
        n_written += 1
    if any(written(base + i) for i in range(n_written, rows)):
        fail(name, 'table has a hole: an unwritten row followed by written rows')
    table_end = n_written * ROW

    # stitched lines (rule WINDOW, E6 REACH)
    reach = sorted(t for t in R.reachable if t < buffer_lines) if R.reachable is not None else None

    def top_for(y):
        ideal = max(0, (y - (DISPLAY - ROW)) & ~7)
        if reach is None or ideal in R.reachable:
            return ideal, False
        cands = [t for t in reach if t <= ideal and t + DISPLAY > y]
        if cands:
            return max(cands), True
        return None, False

    stitched, tops_used, unreachable = [], set(), []
    for y in range(buffer_lines):
        top, substituted = top_for(y)
        if top is None:
            stitched.append(None)
            unreachable.append(y)
            continue
        if substituted:
            rules['REACH'] += 1
        tops_used.add(top)
        lines, _ = R.window(top)
        stitched.append(lines[y - top])
    rules['WINDOW'] = len(tops_used)

    if rules['BUFFER_MASK']:
        # every table copy in every reachable window reads row ((top + i) & M) / 8
        for t in reach:
            lines, _ = R.window(t)
            for i, word in enumerate(lines):
                src = getattr(word, 'src', None)
                if src is not None and src[0] == table_obj:
                    row = src[1] // 2 - base
                    if row != ((t + i) & (buffer_lines - 8)) // ROW:
                        fail(name, f'buffer mask {buffer_lines - 8}: window {t} line {i} shows row {row}')

    # classify non-table lines
    band_lines, wave_lines, expr_lines = {}, {}, {}
    accum = {}
    for y, word in enumerate(stitched):
        if word is None:
            continue
        src = getattr(word, 'src', None)
        if src is not None and src[0] == table_obj:
            row = src[1] // 2 - base
            if row != y // ROW:
                fail(name, f'line {y} shows table row {row}, expected {y // ROW}')
            continue
        v = bg_x(word)
        if S.poisoned(v):
            fail(name, f'line {y}: {v[1]}')
        w = wave_term(model, v, f'line {y}')                 # E1
        if w is not None:
            wave_lines[y] = w
            continue
        if isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi' and model.layer_of(v) is None:
            accum[y] = S.un(v[1])
        else:
            expr_lines[y] = v
    # a plain line directly above an accumulator line starts a 16.16 ramp
    # (foundation); every other plain line is a band of its own value (E4)
    for y, v in list(expr_lines.items()):
        if y + 1 in accum:
            band_lines[y] = S.mulc(v, 65536)
            del expr_lines[y]
    band_lines.update(accum)

    # runs
    runs = []
    for i in range(n_written):
        e = to_expr(model, bg_x(cell_value(base + i)), f'table row {i}', ctx)
        if runs and runs[-1]['expr'] == e:
            runs[-1]['entries'] += 1
        else:
            runs.append({'entries': 1, 'expr': e})

    # bands: 16.16 ramps (foundation)
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

    # E4: plain lines outside the table, merged while the expression repeats
    for y in sorted(expr_lines):
        if tail_region is not None and tail_region[0] <= y < tail_region[1]:
            continue
        e = to_expr(model, expr_lines[y], f'line {y}', ctx)
        if bands and bands[-1].get('_lines') and bands[-1]['start'] + bands[-1]['lines'] == y \
                and bands[-1]['expr'] == e:
            bands[-1]['lines'] += 1
        else:
            bands.append({'start': y, 'lines': 1, 'expr': e, '_lines': True})

    # E1: wave bands, merged while the index steps by one
    tables_raw, tables = {}, {}
    wave_bands = []
    for y in sorted(wave_lines):
        w = wave_lines[y]
        prev = wave_bands[-1] if wave_bands else None
        if prev and prev['start'] + prev['lines'] == y and all(prev['w'][k] == w[k] for k in
                                                                 ('layer', 'table', 'scale', 'signed')) \
                and w['index'] == prev['w']['index'] + prev['lines']:
            prev['lines'] += 1
        else:
            wave_bands.append({'start': y, 'lines': 1, 'w': w})
    if wave_bands and not R.phase:
        fail(name, 'table-read lines without a phase variable')
    for wb in wave_bands:
        w = wb['w']
        if w['table'] not in tables:
            t = table_data(R, w['table'], w['signed'])
            tables[w['table']] = t
            tables_raw[w['table']] = [v & 0xFF for v in t['values']]
        size = len(tables[w['table']]['values'])
        if size & (size - 1):
            fail(name, f'table {w["table"]} has {size} entries, not a power of two')
        (pvar,) = R.phase
        speed, bits = R.phase_speed[pvar], R.phase_bits[pvar]
        mask = size - 1

        def W(P):
            return (((P + speed) & ((1 << bits) - 1)) >> (bits - 8))
        offset = (w['index'] - W(R.phase[pvar])) & mask
        # every line of the band, at every probe phase: idx == (W + offset + k) & mask
        for P in PHASE_PROBES:
            for k in range(wb['lines']):
                y = wb['start'] + k
                top, _ = top_for(y)
                lines, _ = R.window(top, {pvar: P})
                got = wave_term(model, bg_x(lines[y - top]), f'line {y} at phase {P:#x}')
                want = (W(P) + offset + k) & mask
                if got is None or got['index'] != want or got['layer'] != w['layer'] or got['scale'] != w['scale']:
                    fail(name, f'line {y}: at {pvar} = {P:#x} the table index is '
                               f'{None if got is None else got["index"]}, the wave rule says {want}')
        bands.append({'start': wb['start'], 'lines': wb['lines'],
                      'expr': {'op': 'wave', 'layer': w['layer'], 'table': w['table'], 'scale': w['scale'],
                               'phase_speed': speed, 'offset': offset, 'mask': mask}})
    for b in bands:
        b.pop('_lines', None)
    bands.sort(key=lambda b: b['start'])

    covered = set()
    for b in bands:
        covered.update(range(b['start'], b['start'] + b['lines']))
    stray = [y for y in list(band_lines) + list(expr_lines) + list(wave_lines) if y not in covered]
    if stray:
        fail(name, f'non-table lines outside any band: {stray[:8]}')
    for b in bands:
        for y in range(b['start'], b['start'] + b['lines']):
            if y < table_end and b['start'] >= table_end:
                fail(name, 'band overlaps the table')

    # E3 UNINIT
    if ctx['uninit']:
        seen = {}
        for what, lit in ctx['uninit']:
            seen.setdefault(lit, []).append(what)
        for lit, whats in seen.items():
            rules['UNINIT'] += 1
            corrections.append({'rule': 'UNINIT', 'literal_seed': lit, 'taken': 0,
                                'rows': sorted({int(w.split()[-1]) for w in whats})})

    bgy = vertical(R, rules)

    used = set()
    for e in [r['expr'] for r in runs] + [b['expr'] for b in bands]:
        for k in ('layer', 'from', 'to'):
            if k in e:
                used.add(e[k])
        if e.get('seed'):
            used.update((e['seed']['from'], e['seed']['to']))
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
        'tables': tables,
        'corrections': corrections,
        'rules': {'WINDOW_windows': rules['WINDOW'], 'TAIL': rules['TAIL'], 'SEED': rules['SEED'],
                  'PHASE': ({'variable': next(iter(R.phase)), 'speed': R.phase_speed[next(iter(R.phase))]}
                            if R.phase else None),
                  'REACH_substituted_lines': rules['REACH'],
                  'unreachable_lines': ranges(unreachable),
                  'reachable_background_y': ranges(reach) if reach is not None else 'all',
                  'BUFFER_MASK': rules['BUFFER_MASK'],
                  'UNINIT': rules['UNINIT'],
                  'CLAMP': rules['CLAMP'],
                  'overridden_lines': ranges(overridden),
                  'vertical_run_stopped': rules['vertical_run_stopped']},
    }
    irx.validate(ir)
    if scan:
        bad = scan_windows(R, model, ir, tables_raw)
        over = sorted(set(overridden) | set(bad))
        ir['rules']['overridden_lines'] = ranges(over)
        ir['rules']['overrides'] = [
            {'lines': [a, b], 'windows': ranges(sorted(set().union(*(bad.get(y, set()) for y in range(a, b + 1)))))}
            for a, b in ranges(over)]
        ir['rules']['scan'] = {'windows': len([t for t in (R.reachable or range(buffer_lines))
                                               if t < buffer_lines]),
                               'camera_x': list(SCAN_X), 'frames': list(SCAN_FRAMES)}
        irx.validate(ir)
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
    ap.add_argument('files', nargs='*', help='retail files, e.g. R3/SCR31A.C')
    ap.add_argument('--round', type=int, help='every SCR program of this round')
    ap.add_argument('--write', action='store_true', help='write tools/scroll/R3/ir/R<n><act><era>.json')
    ap.add_argument('--no-scan', action='store_true', help='skip rule OVERRIDE (E7)')
    args = ap.parse_args(argv)
    paths = [RETAIL / f for f in args.files]
    if args.round is not None:
        paths += [p for r, a, e, p in programs() if r == args.round]
    if not paths:
        ap.error('no programs given')
    for p in paths:
        ir = derive(p, scan=not args.no_scan)
        text = json.dumps(ir, indent=1)
        if args.write:
            dest = HERE / 'ir' / (p.parent.name + p.stem[4:] + '.json')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text + '\n')
            print(f'wrote {dest.relative_to(HERE.parents[2])}')
        else:
            print(text)


if __name__ == '__main__':
    try:
        main()
    except (ExtractError, irx.IRError) as e:
        print(f'extract.py: FAIL {e}', file=sys.stderr)
        sys.exit(1)
