"""A small C parser for the decompiled retail sources (build/audit/source).

It covers the subset those files use: typedef'd structs and unions, extern
and static declarations with initialisers, function definitions, the full
C expression grammar, and if / for / while / do / goto / labels / return /
break / continue.  Anything else is a loud CParseError naming the file and
line.  It never guesses: an unknown type name, a switch statement or a
construct it does not model stops the parse.

Types
  Int(bits, signed)            char/short/int/long (long is 32 bits, as on
                               the 32-bit x86 target the decompile is from)
  Ptr(target)                  4 bytes
  Array(elem, n)               n may be None for `[]`
  Record(kind, name, fields)   struct or union; fields = [(name, type, offset)]
  Void, Func(ret, params)
"""
import re
from pathlib import Path


class CParseError(Exception):
    pass


# ----------------------------------------------------------------- types

class Type:
    size = 0
    align = 1


class Int(Type):
    def __init__(self, bits, signed):
        self.bits, self.signed = bits, signed
        self.size = self.align = bits // 8

    def __repr__(self):
        return f"{'s' if self.signed else 'u'}{self.bits}"

    def __eq__(self, o):
        return isinstance(o, Int) and (o.bits, o.signed) == (self.bits, self.signed)

    def __hash__(self):
        return hash((self.bits, self.signed))


class Void(Type):
    size = 1

    def __repr__(self):
        return 'void'


class Ptr(Type):
    size = align = 4

    def __init__(self, target):
        self.target = target

    def __repr__(self):
        return f'{self.target!r}*'


class Array(Type):
    def __init__(self, elem, n):
        self.elem, self.n = elem, n
        self.size = elem.size * (n or 0)
        self.align = elem.align

    def __repr__(self):
        return f'{self.elem!r}[{self.n}]'


class Record(Type):
    def __init__(self, kind, name, fields):
        self.kind, self.name = kind, name
        self.fields = []
        off, size, align = 0, 0, 1
        for fname, ftype in fields:
            align = max(align, ftype.align)
            if kind == 'struct':
                off = (off + ftype.align - 1) // ftype.align * ftype.align
                self.fields.append((fname, ftype, off))
                off += ftype.size
                size = off
            else:
                self.fields.append((fname, ftype, 0))
                size = max(size, ftype.size)
        self.align = align
        self.size = (size + align - 1) // align * align

    def field(self, name):
        for fname, ftype, off in self.fields:
            if fname == name:
                return ftype, off
        raise CParseError(f'{self.kind} {self.name} has no member {name}')

    def __repr__(self):
        return f'{self.kind} {self.name}'


class Func(Type):
    size = 4

    def __init__(self, ret, params):
        self.ret, self.params = ret, params

    def __repr__(self):
        return f'func->{self.ret!r}'


S8, U8, S16, U16, S32, U32 = Int(8, True), Int(8, False), Int(16, True), Int(16, False), Int(32, True), Int(32, False)
VOID = Void()


# ----------------------------------------------------------------- lexer

_TOKEN = re.compile(r'''
    (?P<ws>\s+)
  | (?P<num>0[xX][0-9a-fA-F]+[uUlL]*|\d+[uUlL]*)
  | (?P<id>[A-Za-z_]\w*)
  | (?P<chr>'(?:\\.|[^'\\])')
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<op>\.\.\.|>>=|<<=|->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\^=|\|=|[-+*/%&|^~!<>=?:;,.()\[\]{}])
''', re.X)


class Tok:
    __slots__ = ('kind', 'text', 'line')

    def __init__(self, kind, text, line):
        self.kind, self.text, self.line = kind, text, line

    def __repr__(self):
        return f'{self.text!r}@{self.line}'


def lex(text, fname):
    toks, pos, line = [], 0, 1
    lines = text.split('\n')
    # drop preprocessor lines but keep line numbering
    clean = []
    macros = {}
    for ln in lines:
        s = ln.strip()
        if s.startswith('#'):
            m = re.match(r'#\s*define\s+(\w+)\s+(.+)$', s)
            if m:
                macros[m.group(1)] = m.group(2).strip()
            clean.append('')
        else:
            clean.append(ln)
    text = '\n'.join(clean)
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise CParseError(f'{fname}:{line}: cannot lex {text[pos:pos + 20]!r}')
        kind = m.lastgroup
        t = m.group(kind)
        if kind != 'ws':
            if kind == 'id' and t in macros:
                sub = lex(macros[t], fname)[0][:-1]
                for s in sub:
                    s.line = line
                toks.extend(sub)
            else:
                toks.append(Tok(kind, t, line))
        line += t.count('\n')
        pos = m.end()
    toks.append(Tok('eof', '', line))
    return toks, macros


# ----------------------------------------------------------------- AST

class Node:
    __slots__ = ('kind', 'a', 'line')

    def __init__(self, kind, *a, line=0):
        self.kind, self.a, self.line = kind, a, line

    def __repr__(self):
        return f'({self.kind} ' + ' '.join(map(repr, self.a)) + ')'


BASE_WORDS = {'void', 'char', 'short', 'int', 'long', 'unsigned', 'signed'}
QUALIFIERS = {'const', 'volatile', 'register', 'static', 'extern', 'inline', '__inline'}

ASSIGN_OPS = {'=', '+=', '-=', '*=', '/=', '%=', '&=', '^=', '|=', '<<=', '>>='}
BINARY_PREC = [
    ('||',), ('&&',), ('|',), ('^',), ('&',), ('==', '!='), ('<', '>', '<=', '>='),
    ('<<', '>>'), ('+', '-'), ('*', '/', '%'),
]


class Parser:
    def __init__(self, toks, fname, typedefs):
        self.t, self.i, self.fname = toks, 0, fname
        self.typedefs = typedefs      # name -> Type

    # -- token helpers
    def peek(self, k=0):
        return self.t[self.i + k]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def accept(self, text):
        if self.peek().text == text and self.peek().kind in ('op', 'id'):
            return self.next()
        return None

    def expect(self, text):
        tok = self.next()
        if tok.text != text:
            self.fail(f'expected {text!r}, found {tok.text!r}', tok)
        return tok

    def fail(self, msg, tok=None):
        tok = tok or self.peek()
        raise CParseError(f'{self.fname}:{tok.line}: {msg}')

    # -- types
    def starts_type(self, k=0):
        tok = self.peek(k)
        return tok.kind == 'id' and (tok.text in BASE_WORDS or tok.text in QUALIFIERS or
                                     tok.text in self.typedefs or tok.text in ('struct', 'union'))

    def parse_specifiers(self):
        storage, words, named = set(), [], None
        while True:
            tok = self.peek()
            if tok.kind != 'id':
                break
            if tok.text in QUALIFIERS:
                storage.add(self.next().text)
            elif tok.text in BASE_WORDS:
                words.append(self.next().text)
            elif tok.text in ('struct', 'union') and not words and named is None:
                named = self.parse_record()
            elif tok.text in self.typedefs and not words and named is None:
                named = self.typedefs[self.next().text]
            else:
                break
        if named is not None:
            if words:
                self.fail('typedef name combined with base type words')
            return storage, named
        if not words:
            self.fail('expected a type')
        return storage, base_type(words, self)

    def parse_record(self):
        kind = self.next().text
        tag = self.next().text if self.peek().kind == 'id' else None
        if not self.accept('{'):
            key = f'{kind} {tag}'
            if key in self.typedefs:
                return self.typedefs[key]
            self.fail(f'unknown {key}')
        fields = []
        while not self.accept('}'):
            _, base = self.parse_specifiers()
            while True:
                name, t = self.parse_declarator(base)
                fields.append((name, t))
                if not self.accept(','):
                    break
            self.expect(';')
        rec = Record(kind, tag, fields)
        if tag:
            self.typedefs[f'{kind} {tag}'] = rec
        return rec

    def parse_declarator(self, base, abstract=False):
        """Returns (name, type).  Handles pointers, arrays, function
        pointers `(*name)(params)` and function declarators `name(params)`."""
        ptrs = 0
        while self.accept('*'):
            ptrs += 1
            while self.peek().text in ('const', 'volatile'):
                self.next()
        t = base
        for _ in range(ptrs):
            t = Ptr(t)
        if self.peek().text == '(' and self.peek(1).text == '*':
            self.next()
            self.next()
            name = self.next().text if self.peek().kind == 'id' else None
            self.expect(')')
            self.expect('(')
            self.skip_params()
            return name, Ptr(Func(t, None))
        name = None
        if self.peek().kind == 'id' and not self.starts_type():
            name = self.next().text
        elif not abstract:
            self.fail('expected a declarator name')
        dims = []
        while self.accept('['):
            if self.accept(']'):
                dims.append(None)
            else:
                e = self.parse_cond()
                dims.append(const_eval(e, self))
                self.expect(']')
        if self.peek().text == '(' and name is not None and not dims:
            self.next()
            params = self.parse_params()
            return name, Func(t, params)
        for n in reversed(dims):
            t = Array(t, n)
        return name, t

    def skip_params(self):
        depth = 1
        while depth:
            tok = self.next()
            if tok.text == '(':
                depth += 1
            elif tok.text == ')':
                depth -= 1
            elif tok.kind == 'eof':
                self.fail('unterminated parameter list')

    def parse_params(self):
        params = []
        if self.accept(')'):
            return params
        if self.peek().text == 'void' and self.peek(1).text == ')':
            self.next()
            self.next()
            return params
        while True:
            if self.accept('...'):
                params.append(('...', None))
            else:
                _, base = self.parse_specifiers()
                name, t = self.parse_declarator(base, abstract=True)
                if isinstance(t, Array):
                    t = Ptr(t.elem)
                params.append((name, t))
            if self.accept(')'):
                return params
            self.expect(',')

    def parse_type_name(self):
        _, base = self.parse_specifiers()
        _, t = self.parse_declarator(base, abstract=True)
        return t

    # -- expressions
    def parse_expr(self):
        e = self.parse_assign()
        while self.peek().text == ',':
            tok = self.next()
            e = Node('comma', e, self.parse_assign(), line=tok.line)
        return e

    def parse_assign(self):
        lhs = self.parse_cond()
        tok = self.peek()
        if tok.kind == 'op' and tok.text in ASSIGN_OPS:
            self.next()
            return Node('assign', tok.text, lhs, self.parse_assign(), line=tok.line)
        return lhs

    def parse_cond(self):
        c = self.parse_binary(0)
        if self.peek().text == '?':
            tok = self.next()
            a = self.parse_expr()
            self.expect(':')
            b = self.parse_cond()
            return Node('cond', c, a, b, line=tok.line)
        return c

    def parse_binary(self, level):
        if level == len(BINARY_PREC):
            return self.parse_cast()
        e = self.parse_binary(level + 1)
        while self.peek().kind == 'op' and self.peek().text in BINARY_PREC[level]:
            tok = self.next()
            e = Node('binop', tok.text, e, self.parse_binary(level + 1), line=tok.line)
        return e

    def parse_cast(self):
        if self.peek().text == '(' and self.starts_type(1):
            tok = self.next()
            t = self.parse_type_name()
            self.expect(')')
            if self.peek().text == '{':
                self.fail('compound literals are not supported')
            return Node('cast', t, self.parse_cast(), line=tok.line)
        return self.parse_unary()

    def parse_unary(self):
        tok = self.peek()
        if tok.kind == 'op' and tok.text in ('++', '--'):
            self.next()
            return Node('preinc', tok.text, self.parse_unary(), line=tok.line)
        if tok.kind == 'op' and tok.text in ('-', '+', '!', '~', '*', '&'):
            self.next()
            return Node('unop', tok.text, self.parse_cast(), line=tok.line)
        if tok.text == 'sizeof':
            self.next()
            if self.peek().text == '(' and self.starts_type(1):
                self.next()
                t = self.parse_type_name()
                self.expect(')')
                return Node('num', t.size, line=tok.line)
            e = self.parse_unary()
            return Node('sizeof', e, line=tok.line)
        return self.parse_postfix()

    def parse_postfix(self):
        e = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.text == '[':
                self.next()
                i = self.parse_expr()
                self.expect(']')
                e = Node('index', e, i, line=tok.line)
            elif tok.text == '(':
                self.next()
                args = []
                if not self.accept(')'):
                    while True:
                        args.append(self.parse_assign())
                        if self.accept(')'):
                            break
                        self.expect(',')
                e = Node('call', e, args, line=tok.line)
            elif tok.text == '.':
                self.next()
                e = Node('member', e, self.next().text, line=tok.line)
            elif tok.text == '->':
                self.next()
                e = Node('arrow', e, self.next().text, line=tok.line)
            elif tok.text in ('++', '--'):
                self.next()
                e = Node('postinc', tok.text, e, line=tok.line)
            else:
                return e

    def parse_primary(self):
        tok = self.next()
        if tok.kind == 'num':
            return Node('num', int(tok.text.rstrip('uUlL'), 0), line=tok.line)
        if tok.kind == 'chr':
            body = tok.text[1:-1]
            val = ord(body) if len(body) == 1 else {'\\0': 0, '\\n': 10, '\\t': 9}.get(body)
            if val is None:
                self.fail(f'unsupported char literal {tok.text}', tok)
            return Node('num', val, line=tok.line)
        if tok.kind == 'str':
            return Node('str', tok.text, line=tok.line)
        if tok.kind == 'id':
            return Node('id', tok.text, line=tok.line)
        if tok.text == '(':
            e = self.parse_expr()
            self.expect(')')
            return e
        self.fail(f'unexpected {tok.text!r}', tok)

    def parse_initializer(self):
        if self.peek().text == '{':
            tok = self.next()
            items = []
            while not self.accept('}'):
                items.append(self.parse_initializer())
                if not self.accept(','):
                    self.expect('}')
                    break
            return Node('init', items, line=tok.line)
        return self.parse_assign()

    # -- statements
    def parse_block_items(self):
        items = []
        while not self.accept('}'):
            items.append(self.parse_statement())
        return items

    def parse_declaration(self):
        tok = self.peek()
        storage, base = self.parse_specifiers()
        decls = []
        if self.accept(';'):
            return Node('decl', storage, decls, line=tok.line)
        while True:
            name, t = self.parse_declarator(base)
            init = None
            if self.accept('='):
                init = self.parse_initializer()
            if isinstance(t, Array) and t.n is None and init is not None and init.kind == 'init':
                t = Array(t.elem, len(init.a[0]))
            decls.append((name, t, init))
            if not self.accept(','):
                break
        self.expect(';')
        return Node('decl', storage, decls, line=tok.line)

    def parse_statement(self):
        tok = self.peek()
        if tok.text == '{' and tok.kind == 'op':
            self.next()
            return Node('block', self.parse_block_items(), line=tok.line)
        if tok.kind == 'id':
            if tok.text == 'if':
                self.next()
                self.expect('(')
                c = self.parse_expr()
                self.expect(')')
                a = self.parse_statement()
                b = self.parse_statement() if self.accept('else') else None
                return Node('if', c, a, b, line=tok.line)
            if tok.text == 'for':
                self.next()
                self.expect('(')
                if self.starts_type():
                    init = self.parse_declaration()
                else:
                    init = None if self.peek().text == ';' else self.parse_expr()
                    self.expect(';')
                cond = None if self.peek().text == ';' else self.parse_expr()
                self.expect(';')
                step = None if self.peek().text == ')' else self.parse_expr()
                self.expect(')')
                return Node('for', init, cond, step, self.parse_statement(), line=tok.line)
            if tok.text == 'while':
                self.next()
                self.expect('(')
                c = self.parse_expr()
                self.expect(')')
                return Node('while', c, self.parse_statement(), line=tok.line)
            if tok.text == 'do':
                self.next()
                body = self.parse_statement()
                self.expect('while')
                self.expect('(')
                c = self.parse_expr()
                self.expect(')')
                self.expect(';')
                return Node('do', body, c, line=tok.line)
            if tok.text == 'return':
                self.next()
                e = None if self.peek().text == ';' else self.parse_expr()
                self.expect(';')
                return Node('return', e, line=tok.line)
            if tok.text in ('break', 'continue'):
                self.next()
                self.expect(';')
                return Node(tok.text, line=tok.line)
            if tok.text == 'goto':
                self.next()
                label = self.next().text
                self.expect(';')
                return Node('goto', label, line=tok.line)
            if tok.text in ('switch', 'case', 'default'):
                self.fail(f'{tok.text} is not supported by this parser')
            if self.peek(1).text == ':' and tok.text not in self.typedefs:
                self.next()
                self.next()
                if self.peek().text == '}':
                    return Node('label', tok.text, Node('empty', line=tok.line), line=tok.line)
                return Node('label', tok.text, self.parse_statement(), line=tok.line)
            if self.starts_type():
                return self.parse_declaration()
        if tok.text == ';':
            self.next()
            return Node('empty', line=tok.line)
        e = self.parse_expr()
        self.expect(';')
        return Node('expr', e, line=tok.line)

    # -- translation unit
    def parse_unit(self):
        """Returns (functions, declarations) where functions maps name to
        (Func type, [param names], body block) and declarations is a list of
        file-scope decl nodes (typedefs are recorded in self.typedefs)."""
        funcs, decls = {}, []
        while self.peek().kind != 'eof':
            if self.accept(';'):
                continue
            if self.peek().text == 'typedef':
                self.next()
                _, base = self.parse_specifiers()
                while True:
                    name, t = self.parse_declarator(base)
                    self.typedefs[name] = t
                    if not self.accept(','):
                        break
                self.skip_attributes()
                self.expect(';')
                continue
            tok = self.peek()
            storage, base = self.parse_specifiers()
            if self.accept(';'):
                continue
            name, t = self.parse_declarator(base)
            if isinstance(t, Func) and self.peek().text == '{':
                self.next()
                body = Node('block', self.parse_block_items(), line=tok.line)
                if name in funcs:
                    self.fail(f'function {name} defined twice', tok)
                funcs[name] = (t, body, tok.line)
                continue
            items = []
            while True:
                init = None
                if self.accept('='):
                    init = self.parse_initializer()
                if isinstance(t, Array) and t.n is None and init is not None and init.kind == 'init':
                    t = Array(t.elem, len(init.a[0]))
                items.append((name, t, init))
                if not self.accept(','):
                    break
                name, t = self.parse_declarator(base)
            self.skip_attributes()
            self.expect(';')
            decls.append(Node('decl', storage, items, line=tok.line))
        return funcs, decls

    def skip_attributes(self):
        while self.peek().text == '__attribute__':
            self.next()
            self.expect('(')
            self.skip_params()


def base_type(words, parser):
    signed = 'unsigned' not in words
    core = [w for w in words if w not in ('unsigned', 'signed')]
    if core == ['void']:
        return VOID
    if core == ['char']:
        return Int(8, signed)
    if core in (['short'], ['short', 'int']):
        return Int(16, signed)
    if core in ([], ['int'], ['long'], ['long', 'int']):
        return Int(32, signed)
    parser.fail(f'unsupported base type {" ".join(words)}')


def const_eval(e, parser):
    if e.kind == 'num':
        return e.a[0]
    if e.kind == 'binop':
        a, b = const_eval(e.a[1], parser), const_eval(e.a[2], parser)
        return {'+': a + b, '-': a - b, '*': a * b, '/': a // b if b else 0}[e.a[0]]
    parser.fail(f'array dimension is not a constant: {e!r}')


# ----------------------------------------------------------------- files

class Unit:
    """A parsed retail .C file with the headers it includes."""

    def __init__(self, path):
        self.path = Path(path)
        self.typedefs = {}
        self.externs = {}        # name -> Type (from included headers)
        self.header_funcs = set()
        for h in self.headers(self.path, set()):
            self.parse_header(h)
        text = self.path.read_text(errors='replace')
        toks, _ = lex(strip_comments(text), str(self.path))
        p = Parser(toks, str(self.path), self.typedefs)
        self.funcs, self.decls = p.parse_unit()

    @staticmethod
    def headers(path, seen):
        out = []
        for m in re.finditer(r'(?m)^\s*#\s*include\s+"([^"]+)"', path.read_text(errors='replace')):
            h = (path.parent / m.group(1)).resolve()
            if h in seen or not h.exists():
                if not h.exists():
                    raise CParseError(f'{path}: included header {m.group(1)} not found')
                continue
            seen.add(h)
            out.extend(Unit.headers(h, seen))
            out.append(h)
        return out

    def parse_header(self, h):
        toks, _ = lex(strip_comments(h.read_text(errors='replace')), str(h))
        p = Parser(toks, str(h), self.typedefs)
        funcs, decls = p.parse_unit()
        if funcs:
            raise CParseError(f'{h}: header defines functions {sorted(funcs)}')
        for d in decls:
            for name, t, init in d.a[1]:
                if isinstance(t, Func):
                    self.header_funcs.add(name)
                else:
                    self.externs[name] = t


def strip_comments(text):
    from cfront import strip_comments as sc
    return sc(text)
