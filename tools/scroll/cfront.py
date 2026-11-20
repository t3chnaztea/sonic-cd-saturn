"""Small, dependency-free C front end shared by census.py and extract.py.

It does exactly four things with a retail SCR*.C file:
  strip_comments(text)       -> text with /* */ and // comments removed
  functions(text)            -> {name: (params, body)} for every top-level
                                function definition (brace matched)
  shape_key(body)            -> md5-8 of the body with comments stripped,
                                every numeric literal replaced by '#', and
                                whitespace collapsed (identifiers are KEPT)
  programs(root)             -> [(round, act, era, path)] for every
                                R<n>/SCR<n><act><era>.C file under root

Nothing here knows a round number, a program name or a table value.
"""
import hashlib
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RETAIL = REPO / 'build/audit/source/src'

_PROGRAM = re.compile(r'^SCR(\d)([1-3])([A-D])\.C$')


def programs(root=RETAIL):
    """Every retail scroll program file, sorted by (round, act, era)."""
    out = []
    for d in sorted(root.glob('R[0-9]')):
        for f in sorted(d.iterdir()):
            m = _PROGRAM.match(f.name)
            if not m:
                continue
            rnd, act, era = int(m.group(1)), int(m.group(2)), m.group(3)
            if f'R{rnd}' != d.name:
                raise SystemExit(f'{f}: file round {rnd} is not its directory {d.name}')
            out.append((rnd, act, era, f))
    return out


def strip_comments(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            if j < 0:
                raise SystemExit('unterminated /* comment')
            out.append(' ')
            i = j + 2
        elif c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif c in '"\'':
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == '\\' else 1
            out.append(text[i:j + 1])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def match_brace(text, open_index):
    """Index of the brace closing the one at open_index."""
    if text[open_index] != '{':
        raise ValueError('not a brace')
    depth = 0
    for k in range(open_index, len(text)):
        if text[k] == '{':
            depth += 1
        elif text[k] == '}':
            depth -= 1
            if depth == 0:
                return k
    raise SystemExit('unbalanced braces')


_FUNC_HEAD = re.compile(
    r'(?m)^[ \t]*(?:static\s+)?(?:unsigned\s+|signed\s+)?[A-Za-z_]\w*[\s*]+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*\{')


def functions(text):
    """Top-level function definitions of comment-stripped text."""
    found, pos = {}, 0
    while True:
        m = _FUNC_HEAD.search(text, pos)
        if not m:
            return found
        open_i = m.end() - 1
        close_i = match_brace(text, open_i)
        name = m.group(1)
        if name in found:
            raise SystemExit(f'function {name} defined twice')
        found[name] = (m.group(2).strip(), text[open_i + 1:close_i])
        pos = close_i + 1


_NUMBER = re.compile(r'\b(?:0[xX][0-9a-fA-F]+|\d+)[uUlL]*\b')


def normalise(body):
    return ' '.join(_NUMBER.sub('#', body).split())


def shape_key(body):
    return hashlib.md5(normalise(body).encode()).hexdigest()[:8]


def scroll_body(path):
    text = strip_comments(path.read_text(errors='replace'))
    funcs = functions(text)
    if 'scroll' not in funcs:
        raise SystemExit(f'{path}: no scroll() definition')
    params, body = funcs['scroll']
    if params not in ('void', ''):
        raise SystemExit(f'{path}: scroll() takes ({params}), expected (void)')
    return text, funcs, body
