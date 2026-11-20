#!/usr/bin/env python3
"""Retail scroll() C -> scroll IR (tools/scroll/ir.md), with the R6 extensions.

This file is tools/scroll/extract.py copied and extended for Wacky Workbench
(R6).  Every change against the shared file is marked `R6-EXT`; the shared
file is not modified.  The extensions are specified, normatively, in
tools/scroll/R6/ir_ext.md.

    python3 tools/scroll/R6/extract.py R6/SCR61A.C [...]    print draft IR JSON
    python3 tools/scroll/R6/extract.py --round 6 --write   write R6/draft/*.json
    python3 tools/scroll/R6/irc_ext.py R6/draft/*.json -o F  C tables for evaluate_ext.c

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
R6-EXT rules (tools/scroll/R6/ir_ext.md), each counted in the output:
  CLOSURE  A function the file calls but does not define, declared by a
           header the file includes, is interpreted from the retail .C file
           that has that header's name (ETC.H -> ETC.C), when that file
           defines it exactly once.  Anything else stays an UnknownCallee.
  UNINIT   A value built from a local variable the routine reads before
           writing it (an 'init' atom whose root is a local, not a global)
           is taken as 0, and the literal read is recorded under
           `corrections`.  Only the `frac` of a `step` row may be one.
R6-EXT vocabulary (outside ir.md, so a document that uses any of it is a
draft, and tools/scroll/ir gets a .gap.md for it instead of a .json):
  lerp     table row  from + ((w*(to - from) [mod 2^16 if prod_bits 16]) >> shift)
  step     table row  hi(65536*from + frac + m*trunc(num*(to - from)/D))
  shift    bg_y       sum over s of ((uint16)camera_y >> s)
Everything else is a loud failure naming the program and the reason.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent               # R6-EXT: tools/scroll/R6
SHARED = HERE.parent                                   # R6-EXT: tools/scroll
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))

import sym as S                                        # noqa: E402
from cfront import RETAIL, programs, scroll_body, shape_key   # noqa: E402
from cfront import _FUNC_HEAD, functions, strip_comments      # noqa: E402  R6-EXT
from cparse import Parser, lex                         # noqa: E402  R6-EXT
from interp import CAMERA_TRACKING, Machine, Program, SymbolicControl   # noqa: E402
import irc                                             # noqa: E402
import irc_ext                                         # noqa: E402  R6-EXT

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

# R6-EXT: rule CLOSURE ------------------------------------------------------

KEYWORDS = {'if', 'for', 'while', 'do', 'return', 'switch', 'sizeof'}


def called_names(body_text):
    import re
    return {c for c in re.findall(r'\b([A-Za-z_]\w*)\s*\(', body_text) if c not in KEYWORDS}


def link_closure(prog, name):
    """Rule CLOSURE.  Returns [(function, defining file)] for every function
    scroll() reaches that the file does not define, which a header the file
    includes declares, and which the .C file named like that header defines
    exactly once.  The definition is parsed with the program's own typedefs
    and interpreted like any file-local helper."""
    import re
    from cparse import Unit
    unit = prog.unit
    own = functions(strip_comments(unit.path.read_text(errors='replace')))
    headers = Unit.headers(unit.path, set())
    linked, todo, seen = [], ['scroll'], set()
    bodies = dict((k, v[1]) for k, v in own.items())
    while todo:
        f = todo.pop()
        if f in seen or f in CAMERA_TRACKING:
            continue
        seen.add(f)
        if f not in bodies:
            continue
        for c in sorted(called_names(bodies[f])):
            if c in unit.funcs or c in CAMERA_TRACKING or c in seen:
                todo.append(c)
                continue
            if c not in unit.header_funcs:
                continue          # the interpreter raises UnknownCallee
            decl = [h for h in headers
                    if re.search(r'\b' + re.escape(c) + r'\s*\(', strip_comments(h.read_text(errors='replace')))]
            if len(decl) != 1:
                fail(name, f'CLOSURE: {c} is declared by {len(decl)} included headers')
            src = decl[0].with_suffix('.C')
            if not src.exists():
                fail(name, f'CLOSURE: {c} is declared in {decl[0].name} but {src.name} does not exist')
            stext = strip_comments(src.read_text(errors='replace'))
            heads = [m for m in _FUNC_HEAD.finditer(stext) if m.group(1) == c]
            if len(heads) != 1:
                fail(name, f'CLOSURE: {src.name} defines {c} {len(heads)} times')
            params, body = functions(stext)[c]
            snippet = heads[0].group(0)[:-1] + '{' + body + '}'
            toks, _ = lex(snippet, str(src))
            p = Parser(toks, str(src), unit.typedefs)
            funcs, decls = p.parse_unit()
            if set(funcs) != {c} or decls:
                fail(name, f'CLOSURE: parsing {c} from {src.name} gave {sorted(funcs)}')
            unit.funcs.update(funcs)
            bodies[c] = body
            linked.append((c, src.relative_to(unit.path.parents[1]).as_posix()))
            todo.append(c)
    return linked


class Runner:
    def __init__(self, path):
        self.path = Path(path)
        self.prog = Program(self.path)
        self.name = f'{self.path.parent.name}/{self.path.name}'
        self.linked = link_closure(self.prog, self.name)          # R6-EXT
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


# ----------------------------------------------------------------- R6-EXT rows

def local_roots(machine):
    """Names of the local objects (and parameters) a run created."""
    return {o.name.split('.')[0] for oid, o in machine.state.objs.items() if oid.startswith('l')}


def global_roots(prog):
    return set(prog.statics) | set(prog.unit.externs)


def atom_root(name):
    import re
    return re.split(r'[.\[@+]', name, maxsplit=1)[0]


def lerp_eval(to, frm, w, shift, prod_bits):
    """Reference semantics of `lerp` (mirrors evaluate_ext.c)."""
    p = w * (to - frm)
    if prod_bits == 16:
        p &= 0xFFFF
    return frm + (p >> shift)          # Python >> floors


def step_eval(to, frm, num, D, m, frac):
    """Reference semantics of `step` (mirrors evaluate_ext.c)."""
    q = S.div(num * (to - frm), D, True)       # C division, toward zero
    return (65536 * frm + frac + m * q) >> 16  # floor


def lerp_expr(model, v, what):
    """`from + (P >> shift)` with P = w*(to - from), or its low 16 bits.
    Returns the expression, or None when v does not have that structure."""
    terms, c = S.lin_parts(v)
    if c:
        return None
    frm, rest = [], []
    for a, k in terms.items():
        if k == 1 and model.layer_of(a) is not None:
            frm.append(a)
        else:
            rest.append((a, k))
    if len(frm) != 1 or len(rest) != 1 or rest[0][1] != 1:
        return None
    node = S.un(rest[0][0])
    if not (isinstance(node, tuple) and node[0] == 'shr'):
        return None
    shift, inner, prod_bits = node[2], S.un(node[1]), 32
    if isinstance(inner, tuple) and inner[0] == 'trunc':
        if inner[2] != 16 or inner[3]:
            return None
        prod_bits, inner = 16, S.un(inner[1])
    if not 0 < shift <= 16:
        fail(model.name, f'{what}: lerp shift {shift} outside 1..16')
    t, c2 = S.lin_parts(inner)
    if c2 or len(t) != 2:
        return None
    (a1, k1), (a2, k2) = t.items()
    if k1 + k2 != 0 or k1 == 0:
        return None
    (to_a, w), from_a = ((a1, k1), a2) if k1 > 0 else ((a2, k2), a1)
    if from_a != frm[0] or model.layer_of(to_a) is None or to_a == from_a:
        return None
    e = {'op': 'lerp', 'from': model.layer_of(from_a), 'to': model.layer_of(to_a), 'w': w,
         'shift': shift, 'prod_bits': prod_bits}
    rng = random.Random(6)
    probes = [(0, 0), (1, 0), (0, 1), (-1, 0), (32767, -32768), (-32768, 32767), (255, 0), (256, 0)]
    probes += [(rng.randint(-32768, 32767), rng.randint(-32768, 32767)) for _ in range(4000)]
    for tv, fv in probes:
        got = S.evaluate(v, _layer_env(model, {to_a: tv, from_a: fv}))
        want = lerp_eval(tv, fv, w, shift, prod_bits)
        if S.wrap(got, 16, True) != S.wrap(want, 16, True):
            fail(model.name, f'{what}: lerp {e} does not reproduce the routine at to={tv} from={fv} '
                             f'({got} vs {want})')
    return e


def step_expr(model, v, what, ctx):
    """hi(65536*from + frac + m*div(num*(to - from), D)).  frac is the low
    half the accumulator starts with; ctx supplies the local/global roots
    for rule UNINIT.  Returns the expression, or None."""
    v = S.un(v)
    if not (isinstance(v, tuple) and v[0] == 'half' and v[2] == 'hi'):
        return None
    terms, c = S.lin_parts(S.un(v[1]))
    frm, divs, rest = [], [], []
    for a, k in terms.items():
        au = S.un(a)
        if k == 65536 and model.layer_of(a) is not None:
            frm.append(a)
        elif isinstance(au, tuple) and au[0] == 'div':
            divs.append((au, k))
        else:
            rest.append((a, k))
    if len(frm) != 1 or len(divs) != 1:
        return None
    (dnode, m), from_a = divs[0], frm[0]
    if not dnode[3]:
        fail(model.name, f'{what}: step divides unsigned: {S.fmt(dnode)}')
    D = dnode[2]
    t, c2 = S.lin_parts(S.un(dnode[1]))
    if c2 or len(t) != 2:
        return None
    (a1, k1), (a2, k2) = t.items()
    if k1 + k2 != 0 or k1 == 0:
        return None
    (to_a, num), other = ((a1, k1), a2) if k1 > 0 else ((a2, k2), a1)
    if other != from_a or model.layer_of(to_a) is None or to_a == from_a:
        return None
    # frac: a constant, or (rule UNINIT) a value read from an unwritten local
    frac_term = S.make_lin(dict(rest), c)
    frac_atoms = S.atoms(frac_term)
    literal = None
    if frac_atoms:
        roots = {atom_root(n) for kd, n in frac_atoms}
        kinds = {kd for kd, n in frac_atoms}
        if kinds != {'init'} or not roots <= ctx['locals'] or roots & ctx['globals']:
            fail(model.name, f'{what}: step fraction {S.fmt(frac_term)} is not an unwritten local '
                             f'(an expression fraction needs an op the extension does not have)')
        literal = S.fmt(frac_term)
        frac = 0
    else:
        frac = S.un(frac_term)
        if not isinstance(frac, int) or not 0 <= frac < 65536:
            fail(model.name, f'{what}: step fraction {S.fmt(frac_term)} is not 0..65535')
    e = {'op': 'step', 'from': model.layer_of(from_a), 'to': model.layer_of(to_a), 'num': num, 'D': D,
         'm': m, 'frac': frac}
    # verify the structure with the fraction free (every value it can take)
    rng = random.Random(61)
    probes = [(0, 0, 'min'), (1, 0, 'min'), (0, 1, 'max'), (-1, 0, 'max'), (32767, -32768, 'max'),
              (-32768, 32767, 'min')]
    probes += [(rng.randint(-32768, 32767), rng.randint(-32768, 32767), 'rand') for _ in range(4000)]
    for tv, fv, mode in probes:
        env = _layer_env(model, {to_a: tv, from_a: fv})
        for kd, n in sorted(frac_atoms):
            env[(kd, n)] = {'min': 0, 'max': 0xFFFFFFFF, 'rand': rng.randint(0, 0xFFFFFFFF)}[mode]
        fr = S.evaluate(frac_term, env) & 0xFFFF if frac_atoms else frac
        got = S.evaluate(v, env)
        want = step_eval(tv, fv, num, D, m, fr)
        if S.wrap(got, 16, True) != S.wrap(want, 16, True):
            fail(model.name, f'{what}: step {e} does not reproduce the routine at to={tv} from={fv} '
                             f'frac={fr} ({got} vs {want})')
    return e, literal


def to_expr_ext(model, v, what, ctx):
    """to_expr, then (R6-EXT) the lerp and step rows."""
    try:
        return to_expr(model, v, what), None
    except ExtractError as err:
        base = err
    e = lerp_expr(model, v, what)
    if e is not None:
        return e, None
    r = step_expr(model, v, what, ctx)
    if r is not None:
        return r
    raise ExtractError(f'{base} (and it is neither an R6-EXT lerp nor step row)')


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
    elif shift_rule(v) is not None:                           # R6-EXT
        out = shift_rule(v)
        for yv in range(0, 65536):
            for pv in ((0, 1, 0x800, 0x7FFF) if yv % 61 == 0 else (0,)):
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
        cm.call_function('scroll')
        got = S.un(cm.load(cm.lvalue(cm.parse_expr('scrb_v_posit.w.h')))[0])
        env = _Default({('var', 'Y'): yv, ('var', 'PX'): pv, ('var', 'VZ'): d << 8,
                        ('init', 'scrb_v_posit.l'): a << 16})
        if got != S.wrap(S.evaluate(v, env), 16, True):
            fail(runner.name, f'background Y from the symbolic run ({S.fmt(v)}) differs from a concrete run')
    rules['vertical_run_stopped'] = stopped
    return out


def shift_rule(v):
    """R6-EXT: background Y = sum of ((uint16)camera Y >> s).  The value may
    be narrowed to 16 bits at the top (scrollb_v takes a short)."""
    x = S.un(v)
    while isinstance(x, tuple) and x[0] == 'trunc' and x[2] == 16:
        x = S.un(x[1])
    terms, c = S.lin_parts(x)
    if c or not terms:
        return None
    shifts = []
    for a, k in terms.items():
        a = S.un(a)
        if k != 1 or not (isinstance(a, tuple) and a[0] == 'shr'):
            return None
        inner = S.un(a[1])
        if not (isinstance(inner, tuple) and inner[0] == 'trunc' and inner[2] == 16 and not inner[3]
                and S.un(inner[1]) == Y):
            return None
        shifts.append(a[2])
    return {'op': 'shift', 'shifts': sorted(shifts)}


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
    if rule['op'] == 'shift':                                  # R6-EXT
        return sum((y & 0xFFFF) >> s for s in rule['shifts'])
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
    ctx = {'locals': set(), 'globals': global_roots(R.prog)}          # R6-EXT

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
    ctx['locals'] = local_roots(m0) - ctx['globals']                  # R6-EXT

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
    uninit_rows = []                                                  # R6-EXT
    for i in range(n_written):
        e, literal = to_expr_ext(model, bg_x(cell_value(base + i)), f'table row {i}', ctx)
        if literal is not None:
            uninit_rows.append((i, literal))
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
        e = r['expr']
        used.update(e[k] for k in ('layer', 'from', 'to') if k in e)  # R6-EXT: lerp/step name two
    for b in bands:
        used.update((b['expr']['from'], b['expr']['to']))
    used.discard('camera')
    layers = {k: {'C': model.layers[k]['C'], 'U': model.layers[k]['U']} for k in sorted(used)}
    gates = {model.layers[k]['gate'] for k in used if model.layers[k]['U']}
    if len(gates) > 1:
        fail(name, f'layers use different ramp gates: {gates}')

    rnd, act, era = int(Path(path).name[3]), int(Path(path).name[4]), Path(path).name[5]
    _, _, body = scroll_body(Path(path))
    # R6-EXT: rule UNINIT is recorded once per literal read, with its rows
    for literal in sorted({lit for _, lit in uninit_rows}):
        rows = [i for i, lit in uninit_rows if lit == literal]
        corrections.append({'rule': 'UNINIT', 'rows': ranges(rows), 'literal_frac': literal, 'taken': 0})
    ext_ops = sorted({r['expr']['op'] for r in runs if r['expr']['op'] in irc_ext.EXT_EXPR}
                     | ({'bg_y.' + bgy['op']} if bgy['op'] in irc_ext.EXT_BGY else set()))
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
                  'CLOSURE': [f'{f} from {src}' for f, src in R.linked],        # R6-EXT
                  'UNINIT': len(uninit_rows)},                                   # R6-EXT
    }
    if ext_ops:                                                                  # R6-EXT
        ir['notes'] = {'extensions': ext_ops, 'spec': 'tools/scroll/R6/ir_ext.md'}
        irc_ext.validate(ir)
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
    ap.add_argument('--write', action='store_true',
                    help='R6-EXT: write tools/scroll/R6/draft/<name>.json (every document, draft or not)')
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
            dest = HERE / 'draft' / (p.stem + '.json')                           # R6-EXT
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text + '\n')
            print(f'wrote {dest.relative_to(HERE.parents[2])}')
        else:
            print(text)


if __name__ == '__main__':
    try:
        main()
    except (ExtractError, irc.IRError, irc_ext.IRError) as e:
        print(f'R6/extract.py: FAIL {e}', file=sys.stderr)
        sys.exit(1)
