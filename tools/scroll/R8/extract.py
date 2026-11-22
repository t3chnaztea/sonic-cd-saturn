#!/usr/bin/env python3
"""Retail scroll() C -> scroll IR: ROUND 8 COPY of tools/scroll/extract.py.

    python3 tools/scroll/R8/extract.py R8/SCR81A.C [...]     print IR JSON
    python3 tools/scroll/R8/extract.py --round 8 --write    write tools/scroll/R8/ir/*.json
    python3 tools/scroll/R8/irc.py tools/scroll/R8/ir/*.json -o F   C tables for R8/evaluate.c

Everything the shared extractor does is done here unchanged (the WINDOW, TAIL
and SEED rules below are its text).  Three extensions are added, each a
mapping onto a new piece of vocabulary plus a numeric re-check against the
routine's own symbolic value; tools/scroll/R8/EXTENSIONS.md is the proposed
ir.md text.  A document that uses none of them is plain `scroll-ir/1`,
byte-for-byte what the shared extractor writes; one that uses any is
`scroll-ir/1+R8` and names them in "extensions".

  INTERP   A table word that is the high half of a 16.16 accumulator seeded
           with a layer and stepped by a 32-bit C quotient,
               hi(65536*base + seed + k * div(sum c_i*layer_i, D))
           becomes the run op `interp` {base, num, D, signed, k, seed}.  Only
           k (the group index times the shift after the division) is used,
           never the two factors, because the value depends on their product
           alone.  The seed (the accumulator's starting fraction) must be one
           of: none (`zero`), u16(-camera X) (`neg_camera`), the sign word of
           the base (`base_sign`), or bytes of an uninitialised local
           (`unset`, evaluated as 0, recorded under `corrections` as rule
           UNSET; its effect is bounded by one pixel and re-checked).
  ORIGIN   A layer's position at camera X 0 is what the stage-start routine
           (`scr_set`, which runs playposiset and scrbinit) leaves in it,
           minus its rate at the stage-start camera X; when that is not 0 it
           is written as the layer's K.  rules.ORIGIN_restart lists, per
           layer, how many camera X values in the stage's own left..right
           limits would restart the layer (checkpoint) at a position the IR
           does not give; informational, and not 0 for most programs of any
           round (scrbinit's integer shifts do not match a 16.16 rate).
  SHIFT    A background Y that is a function of the 16-bit camera Y alone (no
           previous background Y, no player X) and equals sum((u16)Y >> k)
           at every one of the 65536 camera Y values becomes bg_y `shift`.
           Candidate shift lists are tried shortest first; each is accepted
           only on an exhaustive match, and a second list that also matched
           everywhere would be the same function.

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
  INTERP, ORIGIN, SHIFT, UNSET  as above (round 8 extensions).
Everything else is a loud failure naming the program and the reason.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))       # this directory's irc.py (the extended validator) wins

import sym as S                                        # noqa: E402
from cfront import RETAIL, programs, scroll_body, shape_key   # noqa: E402
from interp import InterpError, Machine, Pointer, Program, SymbolicControl   # noqa: E402
from cparse import VOID                                 # noqa: E402
import irc                                             # noqa: E402

IR_VERSION = 'scroll-ir/1'
IR_VERSION_EXT = 'scroll-ir/1+R8'

# Rule UDIV (R8 extension).  sym.div folds div(c*a, d) to (c/d)*a whenever d
# divides every coefficient.  For an unsigned division that is not an
# identity modulo 2**32 once the dividend is negative as a signed value
# ((u32)(64*-1)/8 is 2**29 - 8, not -8).  This copy keeps unsigned divisions
# of symbolic values as they are written, so INTERP sees the routine's own
# division and the evaluator reproduces it bit for bit.  Constant arithmetic
# and signed divisions are unchanged.  (It changes SCR82B, whose
# `(unsigned)(d << 6) / 8 << 10` sym.div folded into 8192*d.)
_SYM_DIV = S.div


def _div_keeping_unsigned(a, d, signed):
    au = S.un(a)
    if not signed and d != 1 and isinstance(au, tuple) and not S.poisoned(au):
        return ('div', au, d, False)
    return _SYM_DIV(a, d, signed)


S.div = _div_keeping_unsigned
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
        self.prog = Program(self.path)
        self.name = f'{self.path.parent.name}/{self.path.name}'
        self.int_union = self.prog.unit.typedefs['int_union']
        self.windows = {}

    def machine(self, extra):
        return Machine(self.prog, HORIZONTAL_INPUTS + extra,
                       {'lphscrollbuff': ('hscrollbuff', self.int_union, 1024)})

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
        m.call_function('scroll')
        bgy = S.un(m.load(m.lvalue(m.parse_expr('scrb_v_posit.w.h')))[0])
        if bgy != top:
            fail(self.name, f'window {top}: routine set background Y to {S.fmt(bgy)}')
        lines = []
        for i in range(DISPLAY):
            lines.append(m.read('buf:hscrollbuff', 4 * i, 2))
        self.windows[top] = (lines, m)
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
        self.prog = runner.prog
        self.unset = []        # INTERP rows whose seed is uninitialised memory (rule UNSET)
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
    together and must be exactly the high word of one accumulator).
    R8 extension: the high half of an interpolating accumulator (INTERP)."""
    vu = S.un(v)
    if isinstance(vu, tuple) and vu[0] == 'half' and vu[2] == 'hi' and model.layer_of(vu) is None:
        e = interp_of(model, vu, what)
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


# ----------------------------------------------------------------- interp (R8 extension)

def _root_name(name):
    """Variable a memory-cell name belongs to: 'ldwk.l@2' -> 'ldwk'."""
    return re.split(r'[.\[@]', name, maxsplit=1)[0]


def interp_of(model, v, what):
    """v = hi(inner).  Returns an `interp` expression when inner is
        65536*base + seed + k*div(sum c_i*layer_i, D)
    exactly (base, layer_i: layers or the camera; seed: see SEEDS), with the
    mapping re-checked numerically; None when inner has no division term (so
    the caller's own failure names the value); fails loudly when it has one
    but does not fit."""
    inner = S.un(v[1])
    terms, c = S.lin_parts(inner)
    divs = [(a, k) for a, k in terms.items() if isinstance(a, tuple) and a[0] == 'div']
    if not divs:
        return None
    if len(divs) != 1 or c:
        fail(model.name, f'{what}: accumulator word with {len(divs)} divisions and constant {c}: {S.fmt(v)}')
    (dnode, k), = divs
    rest = {a: kk for a, kk in terms.items() if a != dnode}
    bases = [a for a, kk in rest.items() if kk == 65536 and model.layer_of(a) is not None]
    if len(bases) != 1:
        fail(model.name, f'{what}: interpolation has no single 65536*layer seed: {S.fmt(v)}')
    base_atom = bases[0]
    base = model.layer_of(base_atom)
    del rest[base_atom]
    seed, unset_atoms = 'zero', set()
    if rest:
        if len(rest) != 1:
            fail(model.name, f'{what}: interpolation fraction has {len(rest)} terms: {S.fmt(v)}')
        (sa, sk), = rest.items()
        if sk != 1:
            fail(model.name, f'{what}: interpolation fraction term {sk}*{S.fmt(sa)}')
        if sa == S.trunc(S.neg(X), 16, False):
            seed = 'neg_camera'
        elif sa == S.trunc(S.half(base_atom, 'hi'), 16, False):
            seed = 'base_sign'
        else:
            leaves = S.atoms(sa)
            globals_ = set(model.prog.statics) | set(model.prog.unit.externs)
            if leaves and all(kind_ == 'init' and _root_name(n) not in globals_ for kind_, n in leaves) \
                    and S.fits_kind(sa, 16, False):
                seed = 'unset'
                unset_atoms = leaves
            else:
                fail(model.name, f'{what}: interpolation fraction {S.fmt(sa)} is not a known seed')
    _, num_expr, D, signed = dnode
    nt, nc = S.lin_parts(num_expr)
    if nc or not nt:
        fail(model.name, f'{what}: interpolation numerator is not a sum of layers: {S.fmt(num_expr)}')
    num, num_atoms = {}, {}
    for a, cc in nt.items():
        L = model.layer_of(a)
        if L is None:
            fail(model.name, f'{what}: interpolation numerator term {S.fmt(a)} is not a layer')
        num[L] = S.wrap(cc, 32, True)
        num_atoms[L] = a
    if not 0 < D < 1 << 31:
        fail(model.name, f'{what}: interpolation divisor {D}')
    expr = {'op': 'interp', 'base': base, 'num': dict(sorted(num.items())), 'D': D,
            'signed': bool(signed), 'k': k & S.M32, 'seed': seed}
    # re-check the parameterisation numerically against the routine's value
    atoms = {base: base_atom, **num_atoms}
    rng = random.Random(8)
    worst = 0
    for i in range(600):
        vals = {L: rng.randint(-32768, 32767) for L in atoms}
        if i % 3 == 0:          # values in the range a stage actually produces
            vals = {L: rng.randint(0, 16383) for L in atoms}
        if 'camera' in vals:
            xv = vals['camera']
        else:
            xv = rng.randint(-32768, 32767)
        env = _layer_env(model, {atoms[L]: vals[L] for L in atoms if L != 'camera'})
        env[('var', 'X')] = xv
        for a in unset_atoms:
            env[a] = 0
        want = interp_eval(expr, dict(vals, camera=xv), xv)
        got = S.evaluate(v, env)
        if (got - want) & 0xFFFF:
            fail(model.name, f'{what}: interp {expr} gives {want} where the routine gives {got} '
                             f'at {vals}, x={xv}')
        if unset_atoms:
            for a in unset_atoms:
                env[a] = rng.randint(0, 255)
            d = (S.evaluate(v, env) - want) & 0xFFFF
            if d not in (0, 1):
                fail(model.name, f'{what}: an uninitialised seed moves the row by {d}, more than 1 pixel')
            worst = max(worst, d)
    if unset_atoms:
        model.unset.append({'row': what, 'literal_seed': S.fmt(next(iter(rest))), 'max_effect_px': worst})
    return expr


def interp_eval(e, vals, x):
    """Reference semantics of `interp` (mirrors R8/evaluate.c).  vals maps each
    layer the expression names (and 'camera') to its exact pixel position."""
    base = vals[e['base']]
    n = 0
    for L, cc in e['num'].items():
        n = (n + cc * S.wrap(vals[L], 16, True)) & S.M32
    if e['signed']:
        q = S.div(S.wrap(n, 32, True), e['D'], True) & S.M32
    else:
        q = n // e['D']
    seed = {'zero': 0, 'unset': 0, 'neg_camera': (-x) & 0xFFFF,
            'base_sign': 0xFFFF if S.wrap(base, 16, True) < 0 else 0}[e['seed']]
    s = S.wrap(seed + e['k'] * q, 32, True)
    return base + (s >> 16)


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
        out = shift_rule(runner, v) if leaves == {('var', 'Y')} else None
        if out is not None:
            rules['SHIFT'] += 1
        else:
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


def shift_rule(runner, v):
    """Rule SHIFT (R8 extension).  v depends on the 16-bit camera Y alone.
    Returns {'op': 'shift', 'k': [...]} when sum((u16)Y >> k) equals v at
    every one of the 65536 camera Y values, trying one shift, then two;
    None when no such list exists (the caller then tries `camera`)."""
    table = [S.wrap(S.evaluate(v, {('var', 'Y'): y}), 16, True) for y in range(65536)]
    lists = [[k] for k in range(16)] + [[a, b] for a in range(16) for b in range(a, 16)]
    for ks in lists:
        if all(S.wrap(sum(y >> k for k in ks), 16, True) == table[y] for y in range(65536)):
            return {'op': 'shift', 'k': ks}
    return None


def bg_y_eval(rule, y, player_x):
    """Reference semantics of the bg_y vocabulary (mirrors evaluate.c)."""
    if rule['op'] == 'rate':
        return (rule['C'] * y) >> 8
    if rule['op'] == 'shift':
        return sum((y & 0xFFFF) >> k for k in rule['k'])
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
    rules = {'WINDOW': 0, 'TAIL': 0, 'SEED': 0, 'SHIFT': 0}
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

    buffer_lines = None
    for P in PERIODS:
        lp, _ = R.window(P)
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

    # stitched lines (rule WINDOW)
    stitched = []
    for y in range(buffer_lines):
        top = max(0, (y - (DISPLAY - ROW)) & ~7)
        lines, _ = R.window(top)
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
    unset_rows = []
    for i in range(n_written):
        before = len(model.unset)
        e = to_expr(model, bg_x(cell_value(base + i)), f'table row {i}')
        if len(model.unset) > before:
            unset_rows.append((i, model.unset[-1]))
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

    # background Y layers used
    used = set()
    for r in runs:
        used.update(irc.expr_layers(r['expr']))
    for b in bands:
        used.update(irc.expr_layers(b['expr']))
    used.discard('camera')
    K, restart, x0 = origin(R, model, sorted(used))
    layers = {}
    for k in sorted(used):
        layers[k] = {'C': model.layers[k]['C'], 'U': model.layers[k]['U']}
        if K[k]:
            layers[k]['K'] = K[k]
    gates = {model.layers[k]['gate'] for k in used if model.layers[k]['U']}
    if len(gates) > 1:
        fail(name, f'layers use different ramp gates: {gates}')

    extensions = []
    n_interp = sum(r['entries'] for r in runs if r['expr']['op'] == 'interp')
    if n_interp:
        extensions.append('interp')
    if any('K' in L for L in layers.values()):
        extensions.append('layer_K')
    if bgy['op'] == 'shift':
        extensions.append('bg_shift')
    groups = []
    for i, info in unset_rows:
        if groups and groups[-1]['literal_seed'] == info['literal_seed'] and groups[-1]['rows'][-1][1] == i - 1:
            groups[-1]['rows'][-1][1] = i
            groups[-1]['max_effect_px'] = max(groups[-1]['max_effect_px'], info['max_effect_px'])
        else:
            groups.append({'rule': 'UNSET', 'rows': [[i, i]], 'literal_seed': info['literal_seed'],
                           'taken': 0, 'max_effect_px': info['max_effect_px']})
    corrections.extend(groups)

    rnd, act, era = int(Path(path).name[3]), int(Path(path).name[4]), Path(path).name[5]
    _, _, body = scroll_body(Path(path))
    ir = {
        'ir': IR_VERSION_EXT if extensions else IR_VERSION,
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
    if extensions:
        ir['extensions'] = extensions
        ir['rules'].update({'INTERP_rows': n_interp, 'SHIFT': rules['SHIFT'],
                            'UNSET_rows': len(unset_rows),
                            'ORIGIN_start_camera_x': x0, 'ORIGIN_K': {k: v for k, v in K.items() if v},
                            'ORIGIN_restart': restart})
    print(f'extract.py (R8): {name}: ORIGIN start camera X {x0}, K {K}, restart mismatches {restart}',
          file=sys.stderr)
    irc.validate(ir)
    return ir


# ----------------------------------------------------------------- origin (R8 extension)

STAGE_START = 'scr_set'          # sets the camera limits, runs playposiset -> scrbinit


def _read(m, text):
    return S.un(m.load(m.lvalue(m.parse_expr(text)))[0])


class _StageMachine(Machine):
    """The interpreter, for the stage-start routine only.  That routine calls
    two host functions this file does not define; they are given their
    meaning here and nowhere else:
      sMemSet   memset: GAME.C:32 declares it void(*)(void*, unsigned char,
                int), filled from the host's function table.  R1's scrbinit
                clears hscrollwork with it.
      playload  restores the player state saved at a checkpoint.  The
                restart diagnostic supplies that state (the player's X) as an
                input, so the call itself does nothing.
    Any other undefined callee still fails."""

    HOST = ('sMemSet', 'playload')

    def call(self, n):
        f = n.a[0]
        if f.kind == 'id' and f.a[0] in self.HOST and f.a[0] not in self.p.unit.funcs:
            args = [self.rvalue(a) for a in n.a[1]]
            if f.a[0] == 'sMemSet':
                (ptr, _), (val, _), (cnt, _) = args
                val, cnt = S.un(val), S.un(cnt)
                if not isinstance(ptr, Pointer) or not isinstance(val, int) or not isinstance(cnt, int):
                    raise InterpError(f'{self.p.name}:{n.line}: sMemSet with a symbolic argument')
                for i in range(cnt):
                    self.write(ptr.oid, ptr.off + i, 1, val & 0xFF)
            return None, VOID
        return super().call(n)


def _stage_machine(runner, extra, restart=False):
    """A stage entered normally (plflag 0) or from a checkpoint (plflag 1),
    never a demo (demoflag 0, read directly or, in 2 of the 68 programs,
    through the game-state pointer lpKeepWork, which is given storage here)."""
    buffers = {'lphscrollbuff': ('hscrollbuff', runner.int_union, 1024)}
    inputs = [('plflag', 1 if restart else 0), ('demoflag.w', 0)]
    unit = runner.prog.unit
    if 'lpKeepWork' in unit.externs:
        buffers['lpKeepWork'] = ('keepwork', unit.typedefs['game_info'], 1)
        inputs.append(('lpKeepWork->demoflag.w', 0))
    return _StageMachine(runner.prog, inputs + extra, buffers)


def origin(runner, model, used):
    """Rule ORIGIN.  Returns ({layer: K}, {layer: restart mismatches}, start camera X)."""
    name = runner.name
    try:
        m = _stage_machine(runner, [])
        m.call_function(STAGE_START)
    except Exception as e:           # noqa: BLE001 - reported loudly with the cause
        fail(name, f'ORIGIN: cannot run {STAGE_START}(): {type(e).__name__}: {e}')
    x0 = _read(m, 'scra_h_posit.w.h')
    if not isinstance(x0, int):
        fail(name, f'ORIGIN: the stage-start camera X is not a constant: {S.fmt(x0)}')
    K = {}
    for L in used:
        v = _read(m, f'{L}.w.h')
        if not isinstance(v, int):
            fail(name, f'ORIGIN: {STAGE_START}() leaves {L} at {S.fmt(v)}, not a constant')
        C = model.layers[L]['C']
        K[L] = S.wrap(v - (C * x0 >> 8), 16, True)
    # restart diagnostic: the same routine with the start position symbolic
    restart = {}
    try:
        P0 = ('var', 'P0', 16, True)      # the player X a checkpoint restores
        m2 = _stage_machine(runner, [('actwk[0].xposi.w.h', P0), ('actwk[0].yposi.w.h', 0)], restart=True)
        m2.call_function(STAGE_START)
        xs = _read(m2, 'scra_h_posit.w.h')
        left, right = _read(m2, 'scralim_left'), _read(m2, 'scralim_right')
        if not (isinstance(left, int) and isinstance(right, int)):
            raise ValueError('camera limits are not constants')
        vals = {L: _read(m2, f'{L}.w.h') for L in used}
        seen = set()
        restart = {L: 0 for L in used}
        for pv in range(32768):
            env = {('var', 'P0'): pv}
            xv = S.evaluate(xs, env)
            if xv in seen or not left <= xv <= right:
                continue
            seen.add(xv)
            for L in used:
                C = model.layers[L]['C']
                lv = S.wrap(S.evaluate(vals[L], env), 16, True)
                if lv != S.wrap((C * xv >> 8) + K[L], 16, True) or (C * xv) % 256:
                    restart[L] += 1
        restart = {L: f'{n} of {len(seen)} restart camera X values' for L, n in restart.items()}
    except Exception as e:           # noqa: BLE001 - informational only, and says so
        restart = {'unavailable': f'{type(e).__name__}: {e}'}
    return K, restart, x0


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
    ap.add_argument('--write', action='store_true', help='write tools/scroll/ir/R<n>/<name>.json')
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
            print(f'wrote {dest.relative_to(HERE.parents[2])}')
        else:
            print(text)


if __name__ == '__main__':
    try:
        main()
    except (ExtractError, irc.IRError) as e:
        print(f'extract.py: FAIL {e}', file=sys.stderr)
        sys.exit(1)
