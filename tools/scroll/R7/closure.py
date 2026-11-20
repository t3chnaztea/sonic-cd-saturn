"""EXT-FILES: interpret a callee defined in another retail file.

The shared interpreter (tools/scroll/interp.py) raises UnknownCallee when a
routine calls a function its own file does not define.  SCR71B.C and SCR72B.C
call sinset(), defined in build/audit/source/src/ETC.C.  ClosureMachine
resolves such a callee to the ONE retail .C file in the tree that defines it
and interprets it there, exactly as written; zero or two defining files is a
loud failure.  The census (ir.md section 9) lists this as the blocker of the
R6 group ("sinset() is defined in another file").

Nothing here names a program, a round or a table.
"""
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from cfront import RETAIL, functions, strip_comments       # noqa: E402
from cparse import Ptr, S16, U8                            # noqa: E402
from interp import (CAMERA_TRACKING, InterpError, Machine, Obj, Pointer,   # noqa: E402
                    Program)
import sym as S                                            # noqa: E402


class ClosureError(InterpError):
    pass


@lru_cache(maxsize=None)
def definers():
    """{function name: [files defining it]} over every .C file in the tree."""
    out = {}
    for f in sorted(RETAIL.rglob('*.C')):
        text = strip_comments(f.read_text(errors='replace'))
        try:
            names = functions(text)
        except SystemExit:
            continue
        for name in names:
            out.setdefault(name, []).append(f)
    return out


@lru_cache(maxsize=None)
def program_defining(name):
    files = definers().get(name, [])
    if len(files) != 1:
        raise ClosureError(f'call to {name}: {len(files)} retail files define it '
                           f'({", ".join(str(f.relative_to(RETAIL)) for f in files) or "none"}); need exactly one')
    return Program(files[0])


class ClosureMachine(Machine):
    """Machine that interprets callees from their unique defining file."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.closure_calls = set()

    def call(self, n):
        f = n.a[0]
        if f.kind != 'id' or f.a[0] in CAMERA_TRACKING or f.a[0] in self.p.unit.funcs:
            return super().call(n)
        name = f.a[0]
        other = program_defining(name)
        args = [self.rvalue(a) for a in n.a[1]]
        self.closure_calls.add((name, other.unit.path.relative_to(RETAIL).as_posix()))
        saved = self.p
        self.p = other
        try:
            return self.invoke(name, args, n.line)
        finally:
            self.p = saved


@lru_cache(maxsize=None)
def sinset_sin():
    """The 256 sine words sinset(p, &sin, &cos) stores through `sin`, as
    unsigned 16-bit values, by interpreting sinset for p = 0..255."""
    prog = program_defining('sinset')
    out = []
    for p in range(256):
        m = Machine(prog, [], {})
        for nm in ('sin', 'cos'):
            m.state.objs['x:' + nm] = Obj(nm, S16)
        m.invoke('sinset', [(p, U8), (Pointer('x:sin', 0, S16), Ptr(S16)),
                            (Pointer('x:cos', 0, S16), Ptr(S16))], 0)
        v = S.un(m.read('x:sin', 0, 2))
        if not isinstance(v, int):
            raise ClosureError(f'sinset({p}) stored a non-constant sine: {S.fmt(v)}')
        out.append(v & 0xFFFF)
    return tuple(out)


# ----------------------------------------------------------------- EXT-WAVE

# Symbolic table reads.  An index expression into an array whose every
# element is a known constant (a table such as sinset's local sintable)
# yields an opaque atom ('var', 'TAB<n>', bits, signed); TABLE_ATOMS[name]
# keeps (where, values, index expression).  table_env() evaluates such an
# atom by evaluating its index and reading the table, and fails loudly on an
# index outside the table.
TABLE_ATOMS = {}


class TableIndexError(InterpError):
    pass


def table_value(name, env):
    where, values, idx = TABLE_ATOMS[name]
    i = S.evaluate(idx, env)
    if not 0 <= i < len(values):
        raise TableIndexError(f'{where}: index {i} outside 0..{len(values) - 1}')
    return values[i]


class TableEnv(dict):
    """Environment that evaluates table atoms from their index; every other
    missing leaf is `default` (None: a missing leaf is an error)."""

    def __init__(self, base, default=None):
        super().__init__(base)
        self.default = default

    def __missing__(self, key):
        if key[0] == 'var' and key[1] in TABLE_ATOMS:
            return table_value(key[1], self)
        if self.default is None:
            raise KeyError(key)
        return self.default

    def __contains__(self, key):
        return self.default is not None or dict.__contains__(self, key) or \
            (key[0] == 'var' and key[1] in TABLE_ATOMS)


class SinsetMachine(ClosureMachine):
    """ClosureMachine whose symbolic-index reads of constant tables give
    table atoms instead of stopping (SymbolicControl)."""

    def rvalue(self, n):
        if n.kind != 'index':
            return super().rvalue(n)
        a, at = super().rvalue(n.a[0])
        i, it = super().rvalue(n.a[1])
        if isinstance(i, Pointer):
            a, at, i, it = i, it, a, at
        if isinstance(a, Pointer) and not isinstance(S.un(i), int):
            got = self.table_atom(a, i, n.line)
            if got is not None:
                return got
        return self.load(self.deref(self.ptr_add(a, i, n.line), at, n.line))

    def table_atom(self, a, i, line):
        from cparse import Array, Int
        obj = self.state.objs[a.oid]
        t = obj.type
        if not isinstance(t, Array) or not isinstance(t.elem, Int) or not t.n:
            return None
        es = t.elem.size
        if a.off % es:
            return None
        vals = []
        for j in range(t.n):
            e = obj.ent.get(j * es)
            if e is None or e[0] != es or not isinstance(S.un(e[1]), int):
                return None           # not a table of known constants
            vals.append(S.wrap(S.un(e[1]), t.elem.bits, t.elem.signed))
        name = f'TAB{len(TABLE_ATOMS)}'
        where = f'{self.p.name}:{line}: {obj.name}'
        TABLE_ATOMS[name] = (where, tuple(vals), S.un(S.add(a.off // es, i)))
        return ('var', name, t.elem.bits, t.elem.signed), t.elem

    @staticmethod
    def index_of(atom):
        atom = S.un(atom)
        if isinstance(atom, tuple) and atom[0] == 'var' and atom[1] in TABLE_ATOMS:
            return TABLE_ATOMS[atom[1]][2]
        return None

    @staticmethod
    def table_of(atom):
        return TABLE_ATOMS[S.un(atom)[1]]

    @staticmethod
    def phase_words(idx):
        return {nm for k, nm in S.atoms(idx)}
