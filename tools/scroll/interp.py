"""Symbolic interpreter for one retail scroll() routine.

The routine runs exactly as written: every loop, pointer walk, union view and
helper call is executed.  Only the inputs are symbolic (camera X, its delta,
the player's X speed, and memory as it stood before the call), so the output
is the routine's own arithmetic over those inputs.  Control flow must be
concrete, except an `if` whose two arms rejoin: both arms run and every
location they disagree on becomes ('sel', cond, a, b).  A loop, pointer or
return that depends on a symbolic value raises SymbolicControl.

Nothing here knows a program name, a round, a table or a layer.
"""
import copy

import sym as S
from cparse import (Array, Func, Int, Node, Parser, Ptr, Record, S16, S32, U8, U16, U32,
                    Unit, VOID, Void, lex)


class InterpError(Exception):
    pass


class SymbolicControl(InterpError):
    pass


class UnknownCallee(InterpError):
    pass


# Functions that derive the camera from the player.  The model takes the
# camera as its input, so these are not interpreted.  If a routine used a
# different name, the interpreter would run that function instead and the
# camera would reach the model as a selection over player state, which
# extract.py refuses: this list can make a routine fail, never pass wrongly.
CAMERA_TRACKING = frozenset({'scrchk', 'scroll_h', 'scroll_v'})

MAX_STEPS = 2_000_000


class Pointer:
    __slots__ = ('oid', 'off', 'target')

    def __init__(self, oid, off, target):
        self.oid, self.off, self.target = oid, off, target

    def __eq__(self, o):
        return isinstance(o, Pointer) and (o.oid, o.off) == (self.oid, self.off)

    def __hash__(self):
        return hash((self.oid, self.off))

    def __repr__(self):
        return f'&{self.oid}+{self.off}'

    def plus(self, n):
        size = self.target.size if not isinstance(self.target, Void) else 1
        return Pointer(self.oid, self.off + n * size, self.target)


class LV:
    __slots__ = ('oid', 'off', 'type')

    def __init__(self, oid, off, type_):
        self.oid, self.off, self.type = oid, off, type_


class Obj:
    __slots__ = ('name', 'type', 'ent')

    def __init__(self, name, type_):
        self.name, self.type, self.ent = name, type_, {}


class State:
    def __init__(self):
        self.objs = {}
        self.frames = []          # list of {name: oid}

    def clone(self):
        s = State()
        for oid, o in self.objs.items():
            n = Obj(o.name, o.type)
            n.ent = dict(o.ent)
            s.objs[oid] = n
        s.frames = [dict(f) for f in self.frames]
        return s


# ----------------------------------------------------------------- lowering

class Code:
    def __init__(self, name, body):
        self.name, self.ops, self.labels = name, [], {}
        self.fixups = []
        self.lower(body, None, None)
        for i, (op, *rest) in enumerate(self.ops):
            if op == 'goto':
                if rest[0] not in self.labels:
                    raise InterpError(f'{name}: goto to unknown label {rest[0]}')
                self.ops[i] = ('jmp', self.labels[rest[0]], rest[1])
        for i, op in enumerate(self.ops):
            if op[0] in ('jmp', 'br') and not isinstance(op[1], int):
                raise InterpError(f'{name}: unresolved jump')

    def here(self):
        return len(self.ops)

    def emit(self, *op):
        self.ops.append(op)
        return len(self.ops) - 1

    def patch(self, i, index, value):
        op = list(self.ops[i])
        op[index] = value
        self.ops[i] = tuple(op)

    def lower(self, n, brk, cont):
        k = n.kind
        if k == 'block':
            for s in n.a[0]:
                self.lower(s, brk, cont)
        elif k in ('expr',):
            self.emit('expr', n.a[0], n.line)
        elif k == 'decl':
            self.emit('decl', n, n.line)
        elif k == 'empty':
            pass
        elif k == 'if':
            br = self.emit('br', None, n.a[0], None, True, n.line)
            self.lower(n.a[1], brk, cont)
            if n.a[2] is not None:
                j = self.emit('jmp', None, n.line)
                self.patch(br, 1, self.here())
                self.lower(n.a[2], brk, cont)
                self.patch(j, 1, self.here())
            else:
                self.patch(br, 1, self.here())
            self.patch(br, 3, self.here())
        elif k == 'for':
            init, cond, step, body = n.a
            if init is not None:
                if isinstance(init, Node) and init.kind == 'decl':
                    self.emit('decl', init, n.line)
                else:
                    self.emit('expr', init, n.line)
            top = self.here()
            br = self.emit('br', None, cond, None, False, n.line) if cond is not None else None
            breaks, conts = [], []
            self.lower(body, breaks, conts)
            step_at = self.here()
            if step is not None:
                self.emit('expr', step, n.line)
            self.emit('jmp', top, n.line)
            end = self.here()
            if br is not None:
                self.patch(br, 1, end)
                self.patch(br, 3, end)
            for b in breaks:
                self.patch(b, 1, end)
            for c in conts:
                self.patch(c, 1, step_at)
        elif k == 'while':
            cond, body = n.a
            top = self.here()
            br = self.emit('br', None, cond, None, False, n.line)
            breaks, conts = [], []
            self.lower(body, breaks, conts)
            self.emit('jmp', top, n.line)
            end = self.here()
            self.patch(br, 1, end)
            self.patch(br, 3, end)
            for b in breaks:
                self.patch(b, 1, end)
            for c in conts:
                self.patch(c, 1, top)
        elif k == 'do':
            body, cond = n.a
            top = self.here()
            breaks, conts = [], []
            self.lower(body, breaks, conts)
            test = self.here()
            br = self.emit('br', None, cond, None, False, n.line)
            self.emit('jmp', top, n.line)
            end = self.here()
            self.patch(br, 1, end)
            self.patch(br, 3, end)
            for b in breaks:
                self.patch(b, 1, end)
            for c in conts:
                self.patch(c, 1, test)
        elif k == 'return':
            self.emit('ret', n.a[0], n.line)
        elif k == 'break':
            if brk is None:
                raise InterpError(f'{self.name}:{n.line}: break outside a loop')
            brk.append(self.emit('jmp', None, n.line))
        elif k == 'continue':
            if cont is None:
                raise InterpError(f'{self.name}:{n.line}: continue outside a loop')
            cont.append(self.emit('jmp', None, n.line))
        elif k == 'goto':
            self.emit('goto', n.a[0], n.line)
        elif k == 'label':
            if n.a[0] in self.labels:
                raise InterpError(f'{self.name}: label {n.a[0]} defined twice')
            self.labels[n.a[0]] = self.here()
            self.lower(n.a[1], brk, cont)
        else:
            raise InterpError(f'{self.name}:{n.line}: cannot lower {k}')


# ----------------------------------------------------------------- machine

def promote(t):
    if isinstance(t, Int):
        return U32 if (t.bits == 32 and not t.signed) else S32
    return t


def arith_type(a, b):
    a, b = promote(a), promote(b)
    return U32 if (a == U32 or b == U32) else S32


class Program:
    """A retail file ready to interpret."""

    def __init__(self, path):
        self.unit = Unit(path)
        self.name = self.unit.path.name
        self.codes = {}
        self.statics = {}          # file-scope objects: name -> (type, init node)
        for d in self.unit.decls:
            for name, t, init in d.a[1]:
                if isinstance(t, Func):
                    continue
                self.statics[name] = (t, init)

    def code(self, name):
        if name not in self.codes:
            ftype, body, line = self.unit.funcs[name]
            self.codes[name] = Code(name, body)
        return self.codes[name]


class Machine:
    def __init__(self, program, inputs, buffers):
        """inputs: list of (lvalue C text, value).  buffers: {global pointer
        name: (object name, element type, count)} - storage a global pointer
        refers to (the routine's output buffer)."""
        self.p = program
        self.state = State()
        self.steps = 0
        self.local_serial = 0
        self.log = []
        self.state.frames.append({})
        for name, (oname, etype, count) in buffers.items():
            oid = 'buf:' + oname
            self.state.objs[oid] = Obj(oname, Array(etype, count))
            lv = self.global_lv(name)
            self.store(lv, Pointer(oid, 0, etype), lv.type)
        for text, value in inputs:
            lv = self.lvalue(self.parse_expr(text))
            self.store(lv, value, lv.type)

    # -- setup helpers
    def parse_expr(self, text):
        toks, _ = lex(text, '<input>')
        p = Parser(toks, '<input>', self.p.unit.typedefs)
        e = p.parse_expr()
        if p.peek().kind != 'eof':
            raise InterpError(f'bad input expression {text!r}')
        return e

    def global_lv(self, name):
        oid = 'g:' + name
        if oid not in self.state.objs:
            if name in self.p.statics:
                t, init = self.p.statics[name]
                self.state.objs[oid] = Obj(name, t)
                if init is not None:
                    self.initialise(LV(oid, 0, t), init)
            elif name in self.p.unit.externs:
                self.state.objs[oid] = Obj(name, self.p.unit.externs[name])
            else:
                return None
        o = self.state.objs[oid]
        return LV(oid, 0, o.type)

    # -- memory
    def leaf(self, t, off, path):
        """(leaf offset, size, signed, path) of the scalar containing byte off."""
        if isinstance(t, Int):
            return 0, t.size, t.signed, path
        if isinstance(t, Ptr):
            return 0, 4, False, path
        if isinstance(t, Array):
            i = off // t.elem.size
            lo, sz, sg, pth = self.leaf(t.elem, off - i * t.elem.size, f'{path}[{i}]')
            return lo + i * t.elem.size, sz, sg, pth
        if isinstance(t, Record):
            if t.kind == 'union':
                fname, ftype, _ = t.fields[0]
                return self.leaf(ftype, off, f'{path}.{fname}')
            for fname, ftype, foff in t.fields:
                if foff <= off < foff + ftype.size:
                    lo, sz, sg, pth = self.leaf(ftype, off - foff, f'{path}.{fname}')
                    return lo + foff, sz, sg, pth
            return off, 1, False, f'{path}+{off}'
        return off, 1, False, f'{path}+{off}'

    def covering(self, obj, b):
        for k in range(b, b - 4, -1):
            e = obj.ent.get(k)
            if e is not None and k + e[0] > b:
                return k
        return None

    def ensure(self, obj, off, size):
        b = off
        while b < off + size:
            if self.covering(obj, b) is not None:
                b += 1
                continue
            lo, sz, sg, path = self.leaf(obj.type, b, obj.name)
            if lo <= b and lo + sz > b and all(self.covering(obj, x) is None for x in range(lo, lo + sz)):
                if isinstance(obj.type, Ptr) or self.leaf_is_ptr(obj.type, lo):
                    obj.ent[lo] = (sz, ('poison', f'uninitialised pointer {path}'))
                else:
                    obj.ent[lo] = (sz, ('init', path, sz * 8, sg))
                b = lo + sz
            else:
                obj.ent[b] = (1, ('init', f'{path}@{b - lo}', 8, False))
                b += 1

    def leaf_is_ptr(self, t, off):
        if isinstance(t, Ptr):
            return True
        if isinstance(t, Array):
            return self.leaf_is_ptr(t.elem, off % t.elem.size)
        if isinstance(t, Record):
            if t.kind == 'union':
                return self.leaf_is_ptr(t.fields[0][1], off)
            for fname, ftype, foff in t.fields:
                if foff <= off < foff + ftype.size:
                    return self.leaf_is_ptr(ftype, off - foff)
        return False

    @staticmethod
    def extract(v, esize, rel, size):
        if isinstance(v, Pointer):
            if rel == 0 and size == esize:
                return v
            raise InterpError('partial read of a pointer')
        if size == esize:
            return v
        if esize == 4 and size == 2:
            return S.half(v, 'lo' if rel == 0 else 'hi')
        if size == 1:
            return S.byte(v, rel)
        if esize == 4 and size == 2 and rel == 1:
            raise InterpError('misaligned 16-bit read')
        raise InterpError(f'cannot read {size} bytes at {rel} of a {esize}-byte value')

    def read(self, oid, off, size):
        obj = self.state.objs[oid]
        if off < 0 or (obj.type.size and off + size > obj.type.size):
            # retail reads whatever lies past the array; the value is
            # unknown, and any use of it that matters is refused later
            return ('poison', f'read outside {obj.name}: {off}+{size} of {obj.type.size}')
        self.ensure(obj, off, size)
        e = obj.ent.get(off)
        if e is not None and e[0] == size:
            v = e[1]
            # a load from a global array or variable records where it came
            # from; copies through locals keep that record
            if oid.startswith('g:') and not isinstance(v, Pointer):
                return S.Prov(S.un(v), (obj.name, off))
            return v
        k = self.covering(obj, off)
        ek = obj.ent[k]
        if k + ek[0] >= off + size:
            return self.extract(ek[1], ek[0], off - k, size)
        # spans several entries
        pieces, b = [], off
        while b < off + size:
            k = self.covering(obj, b)
            sz, v = obj.ent[k]
            n = min(k + sz, off + size) - b
            pieces.append((b - off, n, self.extract(v, sz, b - k, n)))
            b += n
        if size == 4 and len(pieces) == 2 and pieces[0][1] == 2:
            return S.comp(pieces[0][2], pieces[1][2])
        total = 0
        for rel, n, v in pieces:
            if isinstance(v, Pointer):
                raise InterpError('pointer inside a combined read')
            total = S.add(total, S.mulc(S.trunc(v, 8 * n, False), 1 << (8 * rel)))
        return total

    def write(self, oid, off, size, value):
        obj = self.state.objs[oid]
        if off < 0 or (obj.type.size and off + size > obj.type.size):
            raise InterpError(f'write outside {obj.name}: {off}+{size} of {obj.type.size}')
        for k in range(off - 3, off + size):
            e = obj.ent.get(k)
            if e is None or k + e[0] <= off or k >= off + size:
                continue
            del obj.ent[k]
            sz, v = e
            for a, b in ((k, off), (off + size, k + sz)):
                x = a
                while x < b:
                    n = 2 if (b - x >= 2 and (x - k) % 2 == 0) else 1
                    obj.ent[x] = (n, self.extract(v, sz, x - k, n))
                    x += n
        obj.ent[off] = (size, value)

    # -- values
    def load(self, lv):
        t = lv.type
        if isinstance(t, Array):
            return Pointer(lv.oid, lv.off, t.elem), Ptr(t.elem)
        if isinstance(t, Record):
            return ('struct', lv), t
        if isinstance(t, Int):
            v = self.read(lv.oid, lv.off, t.size)
            return S.trunc(v, t.bits, t.signed), t
        if isinstance(t, Ptr):
            v = self.read(lv.oid, lv.off, 4)
            v = S.un(v) if not isinstance(v, Pointer) else v
            if S.poisoned(v):
                raise InterpError(f'read of {v[1]}')
            return v, t
        raise InterpError(f'cannot load a {t!r}')

    def store(self, lv, value, vtype):
        t = lv.type
        if isinstance(t, Int):
            if isinstance(value, Pointer):
                raise InterpError('storing a pointer into an integer')
            self.write(lv.oid, lv.off, t.size, S.trunc(value, t.bits, t.signed))
            return
        if isinstance(t, Ptr):
            if isinstance(value, Pointer):
                self.write(lv.oid, lv.off, 4, Pointer(value.oid, value.off, t.target))
                return
            if S.un(value) == 0:
                self.write(lv.oid, lv.off, 4, 0)
                return
            raise InterpError(f'storing a non-pointer into a pointer: {S.fmt(value)}')
        if isinstance(t, Record):
            if not (isinstance(value, tuple) and value[0] == 'struct'):
                raise InterpError('struct assignment from a non-struct')
            src = value[1]
            sobj = self.state.objs[src.oid]
            self.ensure(sobj, src.off, t.size)
            items = []
            b = src.off
            while b < src.off + t.size:
                k = self.covering(sobj, b)
                sz, v = sobj.ent[k]
                n = min(k + sz, src.off + t.size) - b
                items.append((b - src.off, n, self.extract(v, sz, b - k, n)))
                b += n
            for rel, n, v in items:
                self.write(lv.oid, lv.off + rel, n, v)
            return
        raise InterpError(f'cannot store to a {t!r}')

    def convert(self, value, vtype, t):
        if isinstance(t, Int):
            if isinstance(value, Pointer):
                raise InterpError('pointer converted to integer')
            return S.trunc(value, t.bits, t.signed)
        if isinstance(t, Ptr):
            if isinstance(value, Pointer):
                return Pointer(value.oid, value.off, t.target)
            if S.un(value) == 0:
                return 0
            raise InterpError('integer converted to pointer')
        if isinstance(t, Void):
            return None
        return value

    # -- initialisers
    def initialise(self, lv, init):
        t = lv.type
        if init.kind == 'init':
            items = init.a[0]
            if isinstance(t, Array):
                for i, it in enumerate(items):
                    self.initialise(LV(lv.oid, lv.off + i * t.elem.size, t.elem), it)
                return
            if isinstance(t, Record):
                fields = t.fields[:1] if t.kind == 'union' else t.fields
                for (fname, ftype, foff), it in zip(fields, items):
                    self.initialise(LV(lv.oid, lv.off + foff, ftype), it)
                return
            if len(items) == 1:
                return self.initialise(lv, items[0])
            raise InterpError('brace initialiser for a scalar')
        v, vt = self.rvalue(init)
        self.store(lv, self.convert(v, vt, t) if not isinstance(t, Record) else v, vt)

    # -- lookup
    def lookup(self, name, line):
        frame = self.state.frames[-1]
        if name in frame:
            oid = frame[name]
            return LV(oid, 0, self.state.objs[oid].type)
        lv = self.global_lv(name)
        if lv is not None:
            return lv
        if name in self.p.unit.funcs or name in self.p.unit.header_funcs or name in CAMERA_TRACKING:
            return ('func', name)
        raise InterpError(f'{self.p.name}:{line}: unknown identifier {name}')

    # -- expressions
    def lvalue(self, n):
        k = n.kind
        if k == 'id':
            lv = self.lookup(n.a[0], n.line)
            if not isinstance(lv, LV):
                raise InterpError(f'{self.p.name}:{n.line}: {n.a[0]} is not an object')
            return lv
        if k == 'member':
            base = self.lvalue(n.a[0])
            if not isinstance(base.type, Record):
                raise InterpError(f'{self.p.name}:{n.line}: member of a non-record')
            ft, foff = base.type.field(n.a[1])
            return LV(base.oid, base.off + foff, ft)
        if k == 'arrow':
            p, pt = self.rvalue(n.a[0])
            base = self.deref(p, pt, n.line)
            if not isinstance(base.type, Record):
                raise InterpError(f'{self.p.name}:{n.line}: -> on a non-record')
            ft, foff = base.type.field(n.a[1])
            return LV(base.oid, base.off + foff, ft)
        if k == 'index':
            a, at = self.rvalue(n.a[0])
            i, it = self.rvalue(n.a[1])
            if isinstance(i, Pointer):
                a, at, i, it = i, it, a, at
            return self.deref(self.ptr_add(a, i, n.line), at, n.line)
        if k == 'unop' and n.a[0] == '*':
            p, pt = self.rvalue(n.a[1])
            return self.deref(p, pt, n.line)
        if k == 'cast':
            raise InterpError(f'{self.p.name}:{n.line}: cast used as an lvalue')
        raise InterpError(f'{self.p.name}:{n.line}: not an lvalue: {k}')

    def deref(self, p, pt, line):
        if not isinstance(p, Pointer):
            raise SymbolicControl(f'{self.p.name}:{line}: dereference of a non-pointer {S.fmt(p) if not isinstance(p, Pointer) else p}')
        return LV(p.oid, p.off, p.target)

    def ptr_add(self, p, i, line):
        if not isinstance(p, Pointer):
            raise InterpError(f'{self.p.name}:{line}: pointer arithmetic on a non-pointer')
        i = S.un(i)
        if not isinstance(i, int):
            raise SymbolicControl(f'{self.p.name}:{line}: pointer offset depends on {S.fmt(i)}')
        return p.plus(i)

    def rvalue(self, n):
        k = n.kind
        if k == 'num':
            v = n.a[0]
            return (v, S32) if v <= 0x7FFFFFFF else (S.wrap(v, 32, False), U32)
        if k == 'id':
            lv = self.lookup(n.a[0], n.line)
            if isinstance(lv, tuple):
                return lv, VOID
            return self.load(lv)
        if k in ('member', 'arrow', 'index'):
            return self.load(self.lvalue(n))
        if k == 'unop':
            op = n.a[0]
            if op == '*':
                return self.load(self.lvalue(n))
            if op == '&':
                lv = self.lvalue(n.a[1])
                return Pointer(lv.oid, lv.off, lv.type), Ptr(lv.type)
            v, t = self.rvalue(n.a[1])
            if op == '!':
                return S.lnot(v), S32
            t = promote(t)
            if op == '-':
                return self.fix(S.neg(v), t), t
            if op == '+':
                return v, t
            if op == '~':
                return self.fix(S.bnot(v), t), t
        if k in ('preinc', 'postinc'):
            lv = self.lvalue(n.a[1])
            old, t = self.load(lv)
            d = 1 if n.a[0] == '++' else -1
            if isinstance(old, Pointer):
                new = old.plus(d)
            else:
                new = S.add(old, d)
            self.store(lv, new, t)
            if k == 'preinc':
                return self.load(lv)
            return old, t
        if k == 'cast':
            v, t = self.rvalue(n.a[1])
            return self.convert(v, t, n.a[0]), n.a[0]
        if k == 'sizeof':
            e = n.a[0]
            if e.kind == 'id':
                lv = self.lookup(e.a[0], e.line)
                return lv.type.size, U32
            raise InterpError(f'{self.p.name}:{n.line}: sizeof of an expression')
        if k == 'comma':
            self.rvalue(n.a[0])
            return self.rvalue(n.a[1])
        if k == 'assign':
            return self.assign(n)
        if k == 'cond':
            c, _ = self.rvalue(n.a[0])
            c = S.un(c)
            if isinstance(c, int):
                return self.rvalue(n.a[1] if c else n.a[2])
            self.require_pure(n.a[1])
            self.require_pure(n.a[2])
            a, at = self.rvalue(n.a[1])
            b, bt = self.rvalue(n.a[2])
            if isinstance(a, Pointer) or isinstance(b, Pointer):
                raise SymbolicControl(f'{self.p.name}:{n.line}: pointer chosen by a symbolic condition')
            return S.sel(c, a, b), arith_type(at, bt)
        if k == 'binop':
            return self.binop(n)
        if k == 'call':
            return self.call(n)
        raise InterpError(f'{self.p.name}:{n.line}: cannot evaluate {k}')

    def require_pure(self, n):
        if isinstance(n, Node):
            if n.kind in ('assign', 'preinc', 'postinc', 'call'):
                raise SymbolicControl(f'{self.p.name}:{n.line}: side effect under a symbolic condition')
            for a in n.a:
                if isinstance(a, Node):
                    self.require_pure(a)
                elif isinstance(a, list):
                    for x in a:
                        if isinstance(x, Node):
                            self.require_pure(x)

    @staticmethod
    def fix(v, t):
        if isinstance(S.un(v), int):
            return S.wrap(S.un(v), 32, t.signed if isinstance(t, Int) else True)
        return v

    def binop(self, n):
        op = n.a[0]
        if op in ('&&', '||'):
            a, _ = self.rvalue(n.a[1])
            a = S.un(a)
            if isinstance(a, int):
                if (op == '&&' and not a) or (op == '||' and a):
                    return int(op == '||'), S32
                b, _ = self.rvalue(n.a[2])
                return S.truth(b), S32
            self.require_pure(n.a[2])
            b, _ = self.rvalue(n.a[2])
            return (S.land(a, b) if op == '&&' else S.lor(a, b)), S32
        a, at = self.rvalue(n.a[1])
        b, bt = self.rvalue(n.a[2])
        return self.arith(op, a, at, b, bt, n.line)

    def arith(self, op, a, at, b, bt, line):
        if isinstance(a, Pointer) or isinstance(b, Pointer):
            if op == '+':
                return (self.ptr_add(a, b, line), at) if isinstance(a, Pointer) else (self.ptr_add(b, a, line), bt)
            if op == '-' and isinstance(a, Pointer) and not isinstance(b, Pointer):
                return self.ptr_add(a, S.neg(b), line), at
            if op == '-' and isinstance(a, Pointer) and isinstance(b, Pointer):
                if a.oid != b.oid:
                    raise InterpError(f'{self.p.name}:{line}: pointer difference across objects')
                return (a.off - b.off) // a.target.size, S32
            if op in ('==', '!=', '<', '>', '<=', '>='):
                if isinstance(a, Pointer) and isinstance(b, Pointer) and a.oid == b.oid:
                    return S.cmp(op, a.off, b.off, False), S32
                if S.un(b if isinstance(a, Pointer) else a) == 0:
                    return int(op == '!='), S32
            raise InterpError(f'{self.p.name}:{line}: unsupported pointer operation {op}')
        if op in ('<<', '>>'):
            t = promote(at)
            bv = S.un(b)
            if not isinstance(bv, int):
                raise SymbolicControl(f'{self.p.name}:{line}: shift by a symbolic amount')
            if op == '<<':
                return self.fix(S.shl(a, bv), t), t
            return self.fix(S.shr(a, bv, t.signed), t), t
        t = arith_type(at, bt)
        if op == '+':
            return self.fix(S.add(a, b), t), t
        if op == '-':
            return self.fix(S.sub(a, b), t), t
        if op == '*':
            return self.fix(S.mul(a, b), t), t
        if op in ('/', '%'):
            bv = S.un(b)
            if not isinstance(bv, int):
                raise InterpError(f'{self.p.name}:{line}: division by a symbolic value')
            if bv == 0:
                raise InterpError(f'{self.p.name}:{line}: division by zero')
            f = S.div if op == '/' else S.mod
            return self.fix(f(a, bv, t.signed), t), t
        if op == '&':
            return self.fix(S.band(a, b), t), t
        if op == '|':
            return self.fix(S.bor(a, b), t), t
        if op == '^':
            return self.fix(S.bxor(a, b), t), t
        if op in ('==', '!=', '<', '>', '<=', '>='):
            return S.cmp(op, a, b, not t.signed), S32
        raise InterpError(f'{self.p.name}:{line}: unsupported operator {op}')

    def assign(self, n):
        op, lhs, rhs = n.a
        lv = self.lvalue(lhs)
        if op == '=':
            v, vt = self.rvalue(rhs)
            if isinstance(lv.type, Record):
                self.store(lv, v, vt)
                return v, lv.type
            v = self.convert(v, vt, lv.type)
            self.store(lv, v, vt)
            return self.load(lv)
        cur, ct = self.load(lv)
        v, vt = self.rvalue(rhs)
        r, rt = self.arith(op[:-1], cur, ct, v, vt, n.line)
        self.store(lv, self.convert(r, rt, lv.type), rt)
        return self.load(lv)

    # -- calls
    def call(self, n):
        f = n.a[0]
        if f.kind != 'id':
            raise InterpError(f'{self.p.name}:{n.line}: call through an expression')
        name = f.a[0]
        args = [self.rvalue(a) for a in n.a[1]]
        if name in CAMERA_TRACKING:
            self.log.append(('camera', name))
            return None, VOID
        if name not in self.p.unit.funcs:
            raise UnknownCallee(f'{self.p.name}:{n.line}: call to {name}, which this file does not define')
        return self.invoke(name, args, n.line)

    def invoke(self, name, args, line):
        ftype, body, _ = self.p.unit.funcs[name]
        code = self.p.code(name)
        params = ftype.params or []
        if len(params) != len(args):
            raise InterpError(f'{self.p.name}:{line}: {name} takes {len(params)} arguments, got {len(args)}')
        self.local_serial += 1
        frame = {}
        for (pname, ptype), (v, vt) in zip(params, args):
            oid = f'l{self.local_serial}:{name}:{pname}'
            self.state.objs[oid] = Obj(f'{name}.{pname}', ptype)
            frame[pname] = oid
            lv = LV(oid, 0, ptype)
            self.store(lv, self.convert(v, vt, ptype) if not isinstance(ptype, Record) else v, vt)
        self.state.frames.append(frame)
        try:
            kind_, value = self.run(code, 0, None)
        finally:
            self.state.frames.pop()
        if kind_ != 'ret':
            raise InterpError(f'{name} did not return')
        if value is None:
            return None, ftype.ret
        v, vt = value
        return self.convert(v, vt, ftype.ret), ftype.ret

    # -- statements
    def declare(self, node):
        frame = self.state.frames[-1]
        for name, t, init in node.a[1]:
            if isinstance(t, Func):
                continue
            self.local_serial += 1
            oid = f'l{self.local_serial}:{name}'
            self.state.objs[oid] = Obj(name, t)
            frame[name] = oid
            if init is not None:
                self.initialise(LV(oid, 0, t), init)

    def run(self, code, pc, stop):
        ops = code.ops
        while True:
            if stop is not None and pc == stop:
                return 'stop', None
            if pc >= len(ops):
                return 'ret', None
            self.steps += 1
            if self.steps > MAX_STEPS:
                raise InterpError(f'{self.p.name}: step limit in {code.name}')
            op = ops[pc]
            kind_ = op[0]
            if kind_ == 'expr':
                self.rvalue(op[1])
                pc += 1
            elif kind_ == 'decl':
                self.declare(op[1])
                pc += 1
            elif kind_ == 'jmp':
                pc = op[1]
            elif kind_ == 'br':
                _, false_pc, cond, join, is_if, line = op
                c, _ = self.rvalue(cond)
                c = S.un(c)
                if isinstance(c, int):
                    pc = pc + 1 if c else false_pc
                    continue
                if S.poisoned(c):
                    raise InterpError(f'{self.p.name}:{line}: branch on {c[1]}')
                if not is_if:
                    raise SymbolicControl(f'{self.p.name}:{line}: loop condition depends on {S.fmt(c)}')
                self.fork(code, pc + 1, false_pc, join, c, line)
                pc = join
            elif kind_ == 'ret':
                if stop is not None:
                    raise SymbolicControl(f'{self.p.name}:{op[2]}: return under a symbolic condition')
                return 'ret', (self.rvalue(op[1]) if op[1] is not None else None)
            else:
                raise InterpError(f'bad op {kind_}')

    def fork(self, code, then_pc, else_pc, join, cond, line):
        base = self.state
        self.state = base.clone()
        if self.run(code, then_pc, join)[0] != 'stop':
            raise SymbolicControl(f'{self.p.name}:{line}: symbolic branch does not rejoin')
        a = self.state            # nested forks replace the state object
        self.state = base.clone()
        if self.run(code, else_pc, join)[0] != 'stop':
            raise SymbolicControl(f'{self.p.name}:{line}: symbolic branch does not rejoin')
        b = self.state
        self.state = self.merge(cond, a, b, line)

    def merge(self, cond, a, b, line):
        out = State()
        out.frames = a.frames
        if [set(f) for f in a.frames] != [set(f) for f in b.frames]:
            raise SymbolicControl(f'{self.p.name}:{line}: symbolic branch declares variables')
        for oid in set(a.objs) | set(b.objs):
            if oid not in a.objs or oid not in b.objs:
                src = a.objs.get(oid) or b.objs.get(oid)
                n = Obj(src.name, src.type)
                n.ent = dict(src.ent)
                out.objs[oid] = n
                continue
            oa, ob = a.objs[oid], b.objs[oid]
            n = Obj(oa.name, oa.type)
            out.objs[oid] = n
            if oa.ent == ob.ent:
                n.ent = dict(oa.ent)
                continue
            same_shape = oa.ent.keys() == ob.ent.keys() and all(oa.ent[k][0] == ob.ent[k][0] for k in oa.ent)
            if same_shape:
                for k in oa.ent:
                    (sz, va), (_, vb) = oa.ent[k], ob.ent[k]
                    n.ent[k] = (sz, self.merge_value(cond, va, vb, line))
                continue
            # different layouts: merge byte by byte over the union of bytes
            self.state = a
            bytes_ = set()
            for o in (oa, ob):
                for k, (sz, _) in o.ent.items():
                    bytes_.update(range(k, k + sz))
            for x in sorted(bytes_):
                self.state = a
                self.ensure(oa, x, 1)
                va = self.byte_of(oa, x)
                self.state = b
                self.ensure(ob, x, 1)
                vb = self.byte_of(ob, x)
                n.ent[x] = (1, self.merge_value(cond, va, vb, line))
        return out

    def byte_of(self, obj, x):
        k = self.covering(obj, x)
        sz, v = obj.ent[k]
        if isinstance(v, Pointer):
            return ('poison', 'pointer byte')
        return self.extract(v, sz, x - k, 1)

    def merge_value(self, cond, va, vb, line):
        if va == vb:
            return va
        if isinstance(va, Pointer) or isinstance(vb, Pointer):
            return ('poison', f'pointer chosen by a symbolic condition at line {line}')
        return S.sel(cond, S.un(va), S.un(vb))

    # -- entry point
    def call_function(self, name):
        self.log.clear()
        return self.invoke(name, [], 0)
