"""Exact symbolic integers for interpreting decompiled 32-bit C.

A value is a Python int (concrete), a Prov (a value tagged with the memory
cell it was loaded from, kept only while the value is copied unchanged), or
a node tuple.  Arithmetic is modulo 2**32, as on the target.  Nodes:

  ('var',  name, bits, signed)       an input (camera X, camera delta, ...)
  ('init', name, bits, signed)       memory as it was before the routine ran
  ('lin',  ((atom, coef), ...), c)   sum coef*atom + c, atoms sorted
  ('half', x, 'lo'|'hi')             signed 16-bit half of 32-bit x
  ('comp', lo, hi)                   32-bit value built from two halves
  ('trunc', x, bits, signed)         x reduced to bits, sign- or zero-extended
  ('div', x, d, signed) ('mod', x, d, signed)   C division by a constant
  ('shr', x, n, signed)              right shift by a constant
  ('mul', a, b)                      product of two non-constants
  ('band'|'bor'|'bxor', a, b)  ('bnot', x)
  ('cmp', op, a, b, unsigned)  ('lnot', x)  ('land', a, b)  ('lor', a, b)
  ('sel', cond, a, b)                cond ? a : b, from a symbolic branch
  ('byte', x, index)                 unsigned byte `index` of x
  ('poison', why)                    a value the interpreter could not model

Every simplification here is an identity modulo 2**32 (or modulo 2**16
for 16-bit results); nothing is approximated.
"""

M32 = 0xFFFFFFFF


class Prov:
    __slots__ = ('v', 'src')

    def __init__(self, v, src):
        self.v, self.src = v, src

    def __repr__(self):
        return f'<{self.src}:{fmt(self.v)}>'

    def __eq__(self, o):
        return isinstance(o, Prov) and o.v == self.v and o.src == self.src

    def __hash__(self):
        return hash(('prov', self.v, self.src))


def un(x):
    return x.v if isinstance(x, Prov) else x


def wrap(v, bits, signed):
    m = (1 << bits) - 1
    v &= m
    if signed and v >> (bits - 1):
        v -= 1 << bits
    return v


def is_sym(x):
    return isinstance(un(x), tuple)


def poisoned(x):
    x = un(x)
    return isinstance(x, tuple) and x[0] == 'poison'


def kind(x):
    """(bits, signed) known to bound x, or None for a full 32-bit value."""
    x = un(x)
    if isinstance(x, int):
        return None
    t = x[0]
    if t in ('var', 'init'):
        return x[2], x[3]
    if t == 'half':
        return 16, True
    if t == 'trunc':
        return x[2], x[3]
    if t == 'byte':
        return 8, False
    if t in ('cmp', 'lnot', 'land', 'lor'):
        return 1, False
    if t == 'sel':
        ka, kb = kind(x[2]), kind(x[3])
        if ka and kb and ka == kb:
            return ka
        if isinstance(un(x[2]), int) and kb:
            return kb if fits(un(x[2]), *kb) else None
        if isinstance(un(x[3]), int) and ka:
            return ka if fits(un(x[3]), *ka) else None
    return None


def fits(v, bits, signed):
    return wrap(v, bits, signed) == v


def fits_kind(x, bits, signed):
    """True when x is known to be representable as (bits, signed)."""
    x = un(x)
    if isinstance(x, int):
        return fits(x, bits, signed)
    k = kind(x)
    if not k:
        return False
    kb, ks = k
    if ks == signed:
        return kb <= bits
    if not ks and signed:
        return kb < bits
    return False


# ----------------------------------------------------------------- linear forms

def lin_parts(x):
    x = un(x)
    if isinstance(x, int):
        return {}, x
    if x[0] == 'lin':
        return dict(x[1]), x[2]
    if x[0] == 'comp':
        lo, hi = x[1], x[2]
        a = add(trunc(lo, 16, False), mulc(hi, 65536))
        if isinstance(a, tuple) and a[0] == 'comp':
            return {a: 1}, 0
        return lin_parts(a)
    return {x: 1}, 0


def _key(atom):
    return repr(atom)


def make_lin(terms, c):
    out = {}
    for a, k in terms.items():
        k = wrap(k, 32, True)
        if k:
            # 65536*trunc16(x) == 65536*x modulo 2**32
            if k % 65536 == 0:
                while isinstance(a, tuple) and a[0] == 'trunc' and a[2] >= 16:
                    a = un(a[1])
            if isinstance(a, tuple) and a[0] == 'lin':
                sub, sc = dict(a[1]), a[2]
                for sa, sk in sub.items():
                    out[sa] = out.get(sa, 0) + sk * k
                c += sc * k
                continue
            out[a] = out.get(a, 0) + k
    out = {a: wrap(k, 32, True) for a, k in out.items() if wrap(k, 32, True)}
    c = wrap(c, 32, True)
    out, c = _rejoin(out, c)
    if not out:
        return c
    if len(out) == 1 and c == 0:
        (a, k), = out.items()
        if k == 1:
            return a
    return ('lin', tuple(sorted(out.items(), key=lambda p: _key(p[0]))), c)


def _rejoin(out, c):
    """65536*m*hi(X) + m*u16(L), where L and X agree in their low 16 bits,
    is m*X.  This is how a 16.16 accumulator kept with swapped halves
    (swap, add, swap) folds back into one linear value."""
    changed = True
    while changed:
        changed = False
        for a, k in list(out.items()):
            if not (isinstance(a, tuple) and a[0] == 'half' and a[2] == 'hi' and k % 65536 == 0):
                continue
            m = wrap(k // 65536, 16, True)
            x = a[1]
            low = trunc(x, 16, False)
            if out.get(low) == m or (isinstance(low, int) and low == 0):
                del out[a]
                if not isinstance(low, int):
                    del out[low]
                tx, cx = lin_parts(x)
                for xa, xk in tx.items():
                    out[xa] = wrap(out.get(xa, 0) + xk * m, 32, True)
                    if not out[xa]:
                        del out[xa]
                c = wrap(c + cx * m, 32, True)
                changed = True
                break
    return out, c


def add(a, b):
    a, b = un(a), un(b)
    if isinstance(a, int) and isinstance(b, int):
        return wrap(a + b, 32, True)
    if poisoned(a):
        return a
    if poisoned(b):
        return b
    ta, ca = lin_parts(a)
    tb, cb = lin_parts(b)
    for k, v in tb.items():
        ta[k] = ta.get(k, 0) + v
    return make_lin(ta, ca + cb)


def mulc(a, k):
    a = un(a)
    if isinstance(a, int):
        return wrap(a * k, 32, True)
    if poisoned(a):
        return a
    t, c = lin_parts(a)
    return make_lin({x: v * k for x, v in t.items()}, c * k)


def neg(a):
    return mulc(a, -1)


def sub(a, b):
    return add(a, neg(b))


def mul(a, b):
    a, b = un(a), un(b)
    if isinstance(b, int):
        return mulc(a, b)
    if isinstance(a, int):
        return mulc(b, a)
    if poisoned(a):
        return a
    if poisoned(b):
        return b
    return ('mul',) + tuple(sorted((a, b), key=_key))


# ----------------------------------------------------------------- 16-bit halves

def trunc(x, bits, signed):
    """x reduced to `bits` and extended back to 32 bits.  A Prov input keeps
    its provenance when at least 16 bits survive (a re-typed copy)."""
    if isinstance(x, Prov):
        r = _trunc(x.v, bits, signed)
        return Prov(r, x.src) if bits >= 16 else r
    return _trunc(x, bits, signed)


def _trunc(x, bits, signed):
    p = None
    if isinstance(x, int):
        return wrap(x, bits, signed)
    if bits >= 32:
        return x if p is None else p
    if poisoned(x):
        return x
    if fits_kind(x, bits, signed):
        return x if p is None else p
    t = x[0]
    if t == 'trunc':
        if x[2] <= bits and fits_kind(x, bits, signed):
            return x
        if x[2] >= bits:
            return trunc(x[1], bits, signed)
    if t == 'lin':
        terms = {}
        for a, k in x[1]:
            k = wrap(k, bits, True)
            # only the low `bits` of each term matter here
            while isinstance(a, tuple) and a[0] == 'trunc' and a[2] >= bits:
                a = un(a[1])
            if k:
                terms[a] = terms.get(a, 0) + k
        c = wrap(x[2], bits, True)
        if not terms:
            return wrap(c, bits, signed)
        red = make_lin(terms, c)
        if red != x:
            return trunc(red, bits, signed)
    if t == 'comp' and bits == 16:
        return trunc(x[1], 16, signed)
    if t == 'half' and bits == 16:
        return ('trunc', x, 16, False) if not signed else x
    out = ('trunc', x, bits, signed)
    return out if p is None else Prov(out, p.src)


def half(x, which):
    xv = un(x)
    if which == 'lo' and isinstance(x, Prov):
        # the low half of a loaded word is still that word's content
        return Prov(half(xv, 'lo'), x.src)
    if isinstance(xv, int):
        return wrap(xv >> 16 if which == 'hi' else xv, 16, True)
    if poisoned(xv):
        return xv
    t = xv[0]
    if t == 'comp':
        part = xv[1] if which == 'lo' else xv[2]
        return trunc(part, 16, True)
    if t in ('trunc', 'var', 'init', 'half', 'byte') or kind(xv):
        k = kind(xv)
        if k and k[0] <= 16:
            if which == 'lo':
                return trunc(xv, 16, True)
            if k[1] and k[0] <= 16:
                # sign extension of a signed 16-bit value
                return ('half', xv, 'hi')
            return 0
    if t == 'lin':
        hiT, loT = {}, {}
        for a, k in xv[1]:
            if k % 65536 == 0:
                hiT[a] = k // 65536
            else:
                loT[a] = k
        c = xv[2]
        qc, rc = c // 65536, c % 65536
        lo = make_lin(loT, rc)
        lo_bounded = (isinstance(lo, int) and 0 <= lo < 65536) or \
            (isinstance(lo, tuple) and fits_kind(lo, 16, False))
        if lo_bounded:
            if which == 'lo':
                return trunc(lo, 16, True)
            return trunc(make_lin(hiT, qc), 16, True)
    return ('half', xv, which)


def comp(lo, hi):
    """32-bit value whose low half is lo and high half hi (halves may be
    wider values; only their low 16 bits count)."""
    lo_u, hi_u = un(lo), un(hi)
    if isinstance(lo_u, int) and isinstance(hi_u, int):
        return wrap((lo_u & 0xFFFF) | ((hi_u & 0xFFFF) << 16), 32, True)
    if poisoned(lo_u):
        return lo_u
    if poisoned(hi_u):
        return hi_u
    ls, hs = strip_trunc16(lo_u), strip_trunc16(hi_u)
    if isinstance(ls, tuple) and isinstance(hs, tuple) and ls[0] == 'half' and hs[0] == 'half' \
            and ls[2] == 'lo' and hs[2] == 'hi' and ls[1] == hs[1]:
        return ls[1]
    if isinstance(hs, tuple) and hs[0] == 'half' and hs[2] == 'hi' and \
            trunc(lo_u, 16, False) == trunc(hs[1], 16, False):
        return hs[1]
    if isinstance(lo_u, int) and lo_u & 0xFFFF == 0:
        return mulc(hi_u, 65536)
    if isinstance(hi_u, int) and hi_u & 0xFFFF == 0:
        return trunc(lo, 16, False)
    return ('comp', lo, hi)


def strip_trunc16(x):
    x = un(x)
    while isinstance(x, tuple) and x[0] == 'trunc' and x[2] == 16:
        x = un(x[1])
    return x


def as_comp(x):
    """(lo, hi) halves of a 32-bit value."""
    xv = un(x)
    if isinstance(xv, tuple) and xv[0] == 'comp':
        return xv[1], xv[2]
    return half(xv, 'lo'), half(xv, 'hi')


# ----------------------------------------------------------------- bit operations

def band(a, b):
    a, b = un(a), un(b)
    if isinstance(a, int) and isinstance(b, int):
        return wrap(a & b, 32, True)
    if isinstance(a, int):
        a, b = b, a
    if poisoned(a):
        return a
    if isinstance(b, int):
        m = b & M32
        if m == 0:
            return 0
        if m == M32:
            return a
        if m == 0xFFFF:
            return trunc(a, 16, False)
        if m == 0xFF:
            return trunc(a, 8, False)
        if m == 0xFFFF0000:
            return comp(0, as_comp(a)[1])
        k = kind(a)
        if k and not k[1] and m == (1 << k[0]) - 1:
            return a
    return ('band',) + tuple(sorted((a, b), key=_key))


def bor(a, b):
    a, b = un(a), un(b)
    if isinstance(a, int) and isinstance(b, int):
        return wrap(a | b, 32, True)
    if a == 0:
        return b
    if b == 0:
        return a
    if poisoned(a):
        return a
    if poisoned(b):
        return b
    la, ha = as_comp(a)
    lb, hb = as_comp(b)
    if un(ha) == 0 and un(lb) == 0 and _halfword_clean(a, 'hi') and _halfword_clean(b, 'lo'):
        return comp(la, hb)
    if un(hb) == 0 and un(la) == 0 and _halfword_clean(b, 'hi') and _halfword_clean(a, 'lo'):
        return comp(lb, ha)
    return ('bor',) + tuple(sorted((a, b), key=_key))


def _halfword_clean(x, zero_half):
    """True when the named half of x is exactly zero as a bit pattern."""
    xv = un(x)
    if isinstance(xv, int):
        return (xv >> 16 if zero_half == 'hi' else xv) & 0xFFFF == 0
    if xv[0] == 'comp':
        return un(xv[2] if zero_half == 'hi' else xv[1]) == 0
    if zero_half == 'hi':
        k = kind(xv)
        return bool(k) and not k[1] and k[0] <= 16
    t, c = lin_parts(xv)
    return c % 65536 == 0 and all(k % 65536 == 0 for k in t.values())


def bxor(a, b):
    a, b = un(a), un(b)
    if isinstance(a, int) and isinstance(b, int):
        return wrap(a ^ b, 32, True)
    if poisoned(a):
        return a
    if poisoned(b):
        return b
    if a == 0:
        return b
    if b == 0:
        return a
    return ('bxor',) + tuple(sorted((a, b), key=_key))


def bnot(a):
    a = un(a)
    if isinstance(a, int):
        return wrap(~a, 32, True)
    return sub(-1, a)


def shl(a, n):
    return mulc(a, 1 << n)


def shr(a, n, signed):
    a = un(a)
    if isinstance(a, int):
        return wrap(a if signed else a & M32, 32, signed) >> n if signed else (a & M32) >> n
    if poisoned(a):
        return a
    if n == 0:
        return a
    if n == 16 and isinstance(a, tuple) and a[0] == 'comp':
        return trunc(a[2], 16, signed)
    t, c = lin_parts(a)
    d = 1 << n
    if c % d == 0 and all(k % d == 0 for k in t.values()):
        return trunc(make_lin({x: k // d for x, k in t.items()}, c // d), 32 - n, signed)
    k = kind(a)
    if k and signed and k[1]:
        pass
    if n == 16:
        return trunc(half(a, 'hi'), 16, signed)
    return ('shr', a, n, signed)


def div(a, d, signed):
    a = un(a)
    if isinstance(a, int):
        if signed:
            q = abs(a) // abs(d)
            return wrap(q if (a >= 0) == (d > 0) else -q, 32, True)
        return wrap((a & M32) // (d & M32), 32, False)
    if poisoned(a):
        return a
    if d == 1:
        return a
    t, c = lin_parts(a)
    if c % d == 0 and all(k % d == 0 for k in t.values()):
        return make_lin({x: k // d for x, k in t.items()}, c // d)
    return ('div', a, d, signed)


def mod(a, d, signed):
    a = un(a)
    if isinstance(a, int):
        if signed:
            return wrap(a - d * div(a, d, True), 32, True)
        return wrap((a & M32) % (d & M32), 32, False)
    return ('mod', a, d, signed)


def byte(x, index):
    xv = un(x)
    if isinstance(xv, int):
        return (xv >> (8 * index)) & 0xFF
    if poisoned(xv):
        return xv
    if index == 0:
        return trunc(xv, 8, False)
    return ('byte', xv, index)


# ----------------------------------------------------------------- logic

def cmp(op, a, b, unsigned):
    a, b = un(a), un(b)
    if isinstance(a, int) and isinstance(b, int):
        if unsigned:
            a, b = a & M32, b & M32
        return int({'<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b,
                    '==': a == b, '!=': a != b}[op])
    if poisoned(a):
        return a
    if poisoned(b):
        return b
    if a == b:
        return int(op in ('<=', '>=', '=='))
    if op in ('==', '!='):
        d = sub(a, b)
        if isinstance(d, int):
            return int((d == 0) == (op == '=='))
    return ('cmp', op, a, b, unsigned)


def lnot(a):
    a = un(a)
    if isinstance(a, int):
        return int(a == 0)
    if poisoned(a):
        return a
    if a[0] == 'lnot':
        return truth(a[1])
    return ('lnot', a)


def truth(a):
    a = un(a)
    if isinstance(a, int):
        return int(a != 0)
    if a[0] in ('cmp', 'lnot', 'land', 'lor'):
        return a
    return ('cmp', '!=', a, 0, False)


def land(a, b):
    a, b = un(a), un(b)
    if isinstance(a, int):
        return truth(b) if a else 0
    if isinstance(b, int):
        return truth(a) if b else 0
    return ('land', truth(a), truth(b))


def lor(a, b):
    a, b = un(a), un(b)
    if isinstance(a, int):
        return 1 if a else truth(b)
    if isinstance(b, int):
        return 1 if b else truth(a)
    return ('lor', truth(a), truth(b))


def sel(c, a, b):
    c = un(c)
    if isinstance(c, int):
        return a if c else b
    if a == b:
        return a
    if poisoned(c):
        return c
    return ('sel', c, a, b)


# ----------------------------------------------------------------- evaluation

def evaluate(x, env):
    """Concrete value of x; env maps ('var'|'init', name) -> int."""
    x = un(x)
    if isinstance(x, int):
        return x
    t = x[0]
    if t in ('var', 'init'):
        key = (t, x[1])
        if key not in env:
            raise KeyError(f'no value for {t} {x[1]}')
        return wrap(env[key], x[2], x[3])
    if t == 'lin':
        return wrap(sum(k * evaluate(a, env) for a, k in x[1]) + x[2], 32, True)
    if t == 'half':
        return half(evaluate(x[1], env), x[2])
    if t == 'comp':
        return comp(evaluate(x[1], env), evaluate(x[2], env))
    if t == 'trunc':
        return wrap(evaluate(x[1], env), x[2], x[3])
    if t == 'div':
        return div(evaluate(x[1], env), x[2], x[3])
    if t == 'mod':
        return mod(evaluate(x[1], env), x[2], x[3])
    if t == 'shr':
        return shr(evaluate(x[1], env), x[2], x[3])
    if t == 'mul':
        return wrap(evaluate(x[1], env) * evaluate(x[2], env), 32, True)
    if t == 'band':
        return band(evaluate(x[1], env), evaluate(x[2], env))
    if t == 'bor':
        return bor(evaluate(x[1], env), evaluate(x[2], env))
    if t == 'bxor':
        return bxor(evaluate(x[1], env), evaluate(x[2], env))
    if t == 'cmp':
        return cmp(x[1], evaluate(x[2], env), evaluate(x[3], env), x[4])
    if t == 'lnot':
        return lnot(evaluate(x[1], env))
    if t == 'land':
        return land(evaluate(x[1], env), evaluate(x[2], env))
    if t == 'lor':
        return lor(evaluate(x[1], env), evaluate(x[2], env))
    if t == 'sel':
        return evaluate(x[2], env) if evaluate(x[1], env) else evaluate(x[3], env)
    if t == 'byte':
        return byte(evaluate(x[1], env), x[2])
    raise ValueError(f'cannot evaluate {t}')


def children(x):
    """Sub-values of a node."""
    x = un(x)
    if not isinstance(x, tuple):
        return []
    if x[0] == 'lin':
        return [a for a, _ in x[1]]
    if x[0] in ('var', 'init', 'poison'):
        return []
    return [p for p in x[1:] if isinstance(p, (tuple, Prov))]


def atoms(x, out=None):
    """Set of ('var'|'init', name) leaves in x."""
    out = set() if out is None else out
    x = un(x)
    if isinstance(x, tuple):
        if x[0] in ('var', 'init'):
            out.add((x[0], x[1]))
        elif x[0] == 'lin':
            for a, _ in x[1]:
                atoms(a, out)
        else:
            for part in x[1:]:
                if isinstance(part, (tuple, Prov)):
                    atoms(part, out)
    return out


def fmt(x):
    x = un(x)
    if isinstance(x, int):
        return str(x)
    t = x[0]
    if t in ('var', 'init'):
        return x[1]
    if t == 'lin':
        parts = []
        for a, k in x[1]:
            s = fmt(a)
            parts.append(s if k == 1 else f'-{s}' if k == -1 else f'{k}*{s}')
        if x[2]:
            parts.append(str(x[2]))
        return '(' + ' + '.join(parts) + ')'
    if t == 'half':
        return f'{x[2]}({fmt(x[1])})'
    if t == 'trunc':
        return f"{'s' if x[3] else 'u'}{x[2]}({fmt(x[1])})"
    if t == 'comp':
        return f'comp({fmt(x[1])}, {fmt(x[2])})'
    if t in ('div', 'mod'):
        return f"{t}({fmt(x[1])}, {x[2]})"
    if t == 'shr':
        return f"({fmt(x[1])} >>{'s' if x[3] else 'u'} {x[2]})"
    if t == 'cmp':
        return f"({fmt(x[2])} {x[1]}{'u' if x[4] else ''} {fmt(x[3])})"
    if t == 'sel':
        return f'({fmt(x[1])} ? {fmt(x[2])} : {fmt(x[3])})'
    return f"{t}(" + ', '.join(fmt(p) if isinstance(p, (tuple, int, Prov)) else str(p) for p in x[1:]) + ')'
