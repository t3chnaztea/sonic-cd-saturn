#!/usr/bin/env python3
"""Map a retail level-program address to a source label.

  scd_addr.py R42A F04E            -> enclosing label + offset, source file:line, instruction
  scd_addr.py R52A --refs dair5    -> every instruction that branches to / reads / writes it

The retail program comes from build/retail/sonic.iso and is disassembled with
the m68k objdump in .deps/build-binutils-m68k. Labels are propagated from the
level's act_tbl (the object table in the .deps/soniccd reconstruction): each
named routine's call / jump-table targets are zipped with the calls in its C
body when the counts agree, until nothing new is named. Unnamed routines are
sub_XXXXXX; code reached by a jmp from a routine is <routine>.tail_XXXXXX.
Results are cached in build/scd-addr/<key>/ (key = tool, soniccd, scddisasm,
retail ISO hashes).
"""
import argparse, hashlib, json, re, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPS = next(p for p in [ROOT, *ROOT.parents] if (p / '.deps/soniccd').is_dir())
CSRC = DEPS / '.deps/soniccd/src'
OBJDUMP = DEPS / '.deps/build-binutils-m68k/binutils/objdump'
ISO = DEPS / 'build/retail/sonic.iso'
BASE = 0x200000
import os; DEBUG = os.environ.get("SCD_ADDR_DEBUG")
KEYWORDS = {'if', 'while', 'for', 'switch', 'return', 'sizeof', 'else', 'do'}


def head(repo):
    h = (repo / '.git/HEAD').read_text().strip()
    if h.startswith('ref: '):
        ref = h[5:]
        f = repo / '.git' / ref
        if f.exists():
            return f.read_text().strip()
        for line in (repo / '.git/packed-refs').read_text().splitlines():
            if line.endswith(' ' + ref):
                return line.split()[0]
    return h


def cache_key():
    h = hashlib.sha256(Path(__file__).read_bytes())
    for repo in ('soniccd', 'scddisasm'):
        h.update(head(DEPS / '.deps' / repo).encode())
    side = ISO.with_name('sonic.iso.sha256.json')
    h.update(side.read_bytes() if side.exists() else str(ISO.stat().st_size).encode())
    return h.hexdigest()[:12]


# ---------------------------------------------------------------- C index
def c_functions(zone):
    """{name: [(file, line, calls)]} for the zone dir and the shared src dir."""
    out = {}
    files = sorted((CSRC / f'R{zone}').glob('*.C')) + sorted(CSRC.glob('*.C'))
    for f in files:
        text = f.read_text(errors='replace')
        for m in re.finditer(r'^(?:static\s+)?[A-Za-z_][\w \t\*]*?\b(\w+)\s*\(([^;{)]*)\)\s*\{', text, re.M):
            name = m.group(1)
            if name in KEYWORDS:
                continue
            depth, i = 0, m.end() - 1
            while i < len(text):
                depth += {'{': 1, '}': -1}.get(text[i], 0)
                if depth == 0:
                    break
                i += 1
            body = re.sub(r'/\*.*?\*/|//[^\n]*', '', text[m.end():i], flags=re.S)
            # a local routine table is called where it is indexed, not where declared
            for t in re.finditer(r'\(\s*\*\s*(\w+)\s*\[\w*\]\s*\)\s*\([^)]*\)\s*=\s*\{([^}]*)\}\s*;', body):
                rest = body[:t.start()] + body[t.end():]
                use = re.search(r'\b%s\s*\[[^\]]*\]\s*\(' % t.group(1), rest)
                if use:
                    names_ = ' '.join('&' + n for n in re.findall(r'&?\s*(\w+)', t.group(2)))
                    body = rest[:use.start()] + names_ + ' ' + rest[use.start():]
            calls = re.findall(r'&\s*(\w+)\b|\b(\w+)\s*\(', body)
            calls = [a or b for a, b in calls if (a or b) not in KEYWORDS]
            out.setdefault(name, []).append((str(f.relative_to(CSRC)), text.count('\n', 0, m.start()) + 1, calls))
    return out


def resolve(funcs, name, ctx, zone):
    defs = funcs.get(name)
    if not defs:
        return None
    for d in defs:
        if d[0] == ctx:
            return d
    zd = [d for d in defs if d[0].startswith(f'R{zone}/')]
    if zd:
        return zd[0]
    pick = [d for d in defs if str(zone) in Path(d[0]).stem] or [d for d in defs if not re.search(r'\d', Path(d[0]).stem)]
    return (pick or defs)[0]


def act_table_file(prog):
    z, a, e = prog[1], prog[2], prog[3]
    names = [f'ACT{z}{a}{e}', f'ACT{z}{a}A', f'ACT{z}{a}', f'Z{z}{a}ACT', f'ACT{z}1A', f'Z{z}1ACT']
    seen = []
    for n in names + [p.stem for p in sorted((CSRC / f'R{z}').glob('*.C'))]:
        f = CSRC / f'R{z}/{n}.C'
        if f.exists() and n not in seen:
            seen.append(n)
            m = re.search(r'act_tbl\[\d+\][^=]*=\s*\{(.*?)\}', f.read_text(errors='replace'), re.S)
            if m:
                yield f'R{z}/{n}.C', re.findall(r'&?\s*(\w+)', m.group(1))


# ---------------------------------------------------------------- retail
def program_bytes(prog, cache):
    f = cache / f'{prog}.bin'
    if not f.exists():
        sys.path.insert(0, str(Path(__file__).parent))
        from extract_mmd import disc_files
        f.write_bytes(disc_files(ISO.read_bytes())[f'{prog}__.MMD'])
    return f.read_bytes()


def disassemble(binf):
    out = subprocess.run([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm68k:68000',
                          f'--adjust-vma={BASE:#x}', str(binf)], capture_output=True, text=True, check=True).stdout
    lines = []
    for ln in out.splitlines():
        m = re.match(r'\s+([0-9a-f]+):\t([0-9a-f ]+?)\s*\t(.*)', ln)
        if m:
            lines.append((int(m.group(1), 16), m.group(3).strip()))
    return lines


def analyse(prog, cache):
    data = program_bytes(prog, cache)
    lines = disassemble(cache / f'{prog}.bin')
    idx = {a: i for i, (a, _) in enumerate(lines)}
    zone = int(prog[1])
    funcs = c_functions(zone)
    word = lambda a: struct.unpack_from('>H', data, a - BASE)[0]
    # jump tables: movew %pc@(T,%dN:w),%dN ; jsr|jmp %pc@(T,...)
    tables = {}
    for i in range(len(lines) - 1):
        m = re.match(r'movew %pc@\((0x[0-9a-f]+),%d\d:w\)', lines[i][1])
        if m and re.match(r'j(sr|mp) %pc@\(' + m.group(1), lines[i + 1][1]):
            t = int(m.group(1), 16)
            ents, lo = [], 1 << 30
            while t + 2 * len(ents) < t + lo and len(ents) < 128:
                off = word(t + 2 * len(ents))
                if off & 0x8000 or off == 0:
                    break
                ents.append(t + off); lo = min(lo, off)
            tables[lines[i + 1][0]] = (t, ents)
    skip = {a for t, e in tables.values() for a in range(t, t + 2 * len(e))}
    target = lambda s: (lambda m: int(m.group(1), 16) if m and BASE <= int(m.group(1), 16) < BASE + len(data) else None)(re.search(r'\s(0x20[0-9a-f]{4})$', s))
    starts = set()
    for a, s in lines:
        if s.split()[0] in ('jsr', 'bsrs', 'bsrw', 'bsr') and target(s):
            starts.add(target(s))
    for t, e in tables.values():
        starts.update(e)
    # a braw that crosses another routine's entry reaches a separate routine
    # (if (x) f0(); else f1(); compiles to an inlined f0 and a long bra to f1)
    import bisect
    srt = sorted(starts)
    for a, s in lines:
        t = target(s)
        if s.startswith('braw') and t in idx:
            k = bisect.bisect_right(srt, min(a, t))
            if k < len(srt) and srt[k] < max(a, t) and srt[k] != t:
                starts.add(t)
    names, files = {}, {}
    inrange = lambda v: BASE + 0x100 <= v < BASE + len(data)
    longs = [inrange(struct.unpack_from('>I', data, o)[0]) for o in range(0, len(data) - 3, 2)]
    runs, o = {}, 0
    while o < len(longs):          # maximal runs of code pointers, stride 4
        if longs[o]:
            e = o
            while e < len(longs) and longs[e]:
                e += 2
            if (e - o) // 2 >= 8:
                runs.setdefault((e - o) // 2, []).append(o * 2)
                o = e
            else:
                o += 1
        else:
            o += 1
    for cf, entries in act_table_file(prog):
        if len(runs.get(len(entries), [])) != 1:
            continue
        off = runs[len(entries)][0]
        vals = struct.unpack_from(f'>{len(entries)}I', data, off)
        for nm, v in zip(entries, vals):
            starts.add(v)
            if v not in names or names[v] == 'noact':
                names[v], files[v] = nm, resolve(funcs, nm, cf, zone)
        break

    def events(a, tail=False, seen=None):
        seen = set() if seen is None else seen
        out, tails = [], []
        i = idx.get(a)
        while i is not None and i < len(lines):
            ad, s = lines[i]
            i += 1
            if ad != a and ad in starts:
                break
            if ad in skip:
                continue
            op = s.split()[0]
            if ad in tables:
                out += tables[ad][1]
            t = target(s)
            if t is not None and op in ('jsr', 'bsrs', 'bsrw', 'bsr'):
                out.append(t)
            elif t is not None and op == 'braw' and t in starts and t != a:
                out.append(-t)
            elif t is not None and op == 'jmp':
                if t in starts:
                    out.append(t)
                elif t not in seen:
                    seen.add(t); tails.append(t)
                    o2, t2 = events(t, True, seen)
                    out += o2; tails += t2
            if tail and op in ('rts', 'jmp'):
                break
        return out, tails
    tails, roots, guess = {}, sorted(names), set()
    rcache, ccache = {}, {}

    def rcalls(x):
        if x not in rcache:
            ev, tl = events(x)
            for t in tl:
                tails.setdefault(t, x)
            bra = {-t for t in ev if t < 0}
            ev = [abs(t) for t in ev]
            ev = [t for k, t in enumerate(ev) if t != x and t not in ev[:k]]
            rcache[x] = (ev, bra)
        return rcache[x][0]

    def ccalls(d):
        key = (d[0], d[1])
        if key not in ccache:
            out = []
            for c in d[2]:
                r = resolve(funcs, c, d[0], zone)
                if r and (c, r) not in out and r[:2] != key:
                    out.append((c, r))
            ccache[key] = out
        return ccache[key]

    owner = {files[a][:2]: a for a in names if files.get(a)}
    wowner = {}

    def name(t, c, d, weak=False):
        if t in names and not (t in guess and not weak):
            return False
        own = wowner if weak else owner
        if owner.get(d[:2], t) != t or own.get(d[:2], t) != t:
            return False
        own[d[:2]] = t
        names[t], files[t] = c, d
        (guess.add if weak else guess.discard)(t)
        return True

    def anchors(cv, rv):
        n = 0
        for (c, d), t in zip(cv, rv):
            if t in names and t not in guess:
                if not files.get(t) or files[t][:2] != d[:2]:
                    return -1
                n += 1
            elif owner.get(d[:2], t) != t:
                return -1
        return n

    def propagate():
        changed = False
        for x in list(names):
            if not files.get(x):
                continue
            cc, rr = ccalls(files[x]), rcalls(x)
            if DEBUG:
                print(names[x], [c for c, _ in cc], [hex(t) for t in rr], file=sys.stderr)
            cvs = [(cc, 0)]
            inl = [k for k, (c, d) in enumerate(cc) if d[0] == files[x][0] and ccalls(d)]
            for k in inl:
                cvs.append((cc[:k] + ccalls(cc[k][1]) + cc[k + 1:], 1))
            if len(inl) > 1:
                flat = []
                for k, e in enumerate(cc):
                    flat += ccalls(e[1]) if k in inl else [e]
                cvs.append((flat, 1))
            bra = rcache[x][1]
            rvs = [(rr, 0)] + ([([t for t in rr if t not in bra] + [t for t in rr if t in bra], 1)] if bra else [])
            best = None
            for cv, cp in cvs:
                for rv, rp in rvs:
                    if len(cv) == len(rv) and cv:
                        n = anchors(cv, rv)
                        if n >= (1 if cp or rp else 0) and (best is None or n > best[0]):
                            best = (n, cv, rv)
            if best:
                for (c, d), t in zip(best[1], best[2]):
                    changed |= name(t, c, d, weak=x in guess)
        return changed

    byfile = {}
    for nm, defs in funcs.items():
        for d in defs:
            byfile.setdefault(d[0], []).append((d[1], nm, d))
    for v in byfile.values():
        v.sort()
    sstarts = sorted(starts)

    def align():
        """Retail routines follow the C file's definition order: align them."""
        changed = False
        for k, r in enumerate(roots):
            if not files.get(r):
                continue
            f, line = files[r][0], files[r][1]
            nxt = next((x for x in roots[k + 1:] if x > r), BASE + len(data))
            S = [x for x in sstarts if r < x < nxt]
            G = [(nm, d) for ln, nm, d in byfile.get(f, []) if ln > line]
            if not S or not G or len(S) > 400:
                continue
            callers = {}
            for x in [r] + S:
                for t in rcalls(x):
                    callers.setdefault(t, set()).add(x)

            def score(g, x):
                nm, d = g
                if x in names and x not in guess:
                    return 50 if names[x] == nm else -100
                ext = {c for c, _ in ccalls(d)}
                sc = 1 + 3 * len({names[t] for t in rcalls(x) if t in names and t not in guess} & ext)
                for y in callers.get(x, ()):
                    if files.get(y) and y not in guess and nm in {c for c, _ in ccalls(files[y])}:
                        sc += 4
                        break
                return sc
            n, m = len(G), len(S)
            M = [[score(G[i], S[j]) for j in range(m)] for i in range(n)]
            D = [[0] * (m + 1) for _ in range(n + 1)]
            for i in range(1, n + 1):
                for j in range(1, m + 1):
                    D[i][j] = max(D[i - 1][j], D[i][j - 1], D[i - 1][j - 1] + M[i - 1][j - 1])
            i, j = n, m
            while i and j:
                sc = M[i - 1][j - 1]
                if sc > 0 and D[i][j] == D[i - 1][j - 1] + sc:
                    nm, d = G[i - 1]
                    changed |= name(S[j - 1], nm, d, weak=True)
                    i, j = i - 1, j - 1
                elif D[i][j] == D[i - 1][j]:
                    i -= 1
                else:
                    j -= 1
        return changed

    for _ in range(12):
        if not propagate() and not align():
            break
    labels = {}
    for a in starts:
        if a in names:
            d = files.get(a)
            labels[a] = [('~' if a in guess else '') + names[a], f'{d[0]}:{d[1]}' if d else '']
        else:
            labels[a] = [f'sub_{a:06x}', '']
    for t, owner in tails.items():
        if t not in labels:
            labels[t] = [f'{labels[owner][0]}.tail_{t:06x}', labels[owner][1]]
    return {'lines': lines, 'labels': {str(k): v for k, v in labels.items()}, 'skip': sorted(skip),
            'tables': [[a, t, e] for a, (t, e) in tables.items()]}


def load(prog):
    cache = DEPS / 'build/scd-addr' / cache_key()
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f'{prog}.json'
    if not f.exists():
        f.write_text(json.dumps(analyse(prog, cache)))
    d = json.loads(f.read_text())
    d['labels'] = {int(k): v for k, v in d['labels'].items()}
    return d


def enclosing(d, a):
    best = max((k for k in d['labels'] if k <= a), default=None)
    if best is None or a >= BASE + 0x40000:
        return '?', ''
    n, src = d['labels'][best]
    return f'{n}+${a - best:X}' if a != best else n, src


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('prog', help='level program, e.g. R42A')
    ap.add_argument('addr', nargs='?', help='retail address ($F04E, 20F04E, 0x20f04e)')
    ap.add_argument('--refs', help='label (name or FILE.C:name) or address to list references to')
    ap.add_argument('-n', type=int, default=2, help='context instructions after the address')
    args = ap.parse_args()
    prog = args.prog.upper()[:4]
    d = load(prog)
    num = lambda s: (lambda v: v | BASE if v < BASE else v)(int(s.lstrip('$').replace('0x', ''), 16))
    if args.addr:
        a = num(args.addr)
        i = max(j for j, (ad, _) in enumerate(d['lines']) if ad <= a)
        lab, src = enclosing(d, a)
        print(f'{prog} ${a:X}  {lab}  {src}')
        for ad, s in d['lines'][i:i + 1 + args.n]:
            print(f'  {ad:06x}: {s}')
    if args.refs:
        byname = {v[0].lstrip('~'): k for k, v in d['labels'].items()}
        byname |= {Path(v[1].split(':')[0]).name + ':' + v[0].lstrip('~'): k for k, v in d['labels'].items() if v[1]}
        t = byname.get(args.refs.lstrip('~')) or num(args.refs)
        lab, src = enclosing(d, t)
        print(f'{prog} refs to ${t:X} ({lab} {src})')
        pat = re.compile(r'(?<![0-9a-fx])0x%x\b' % t)
        skip = set(d['skip'])
        hits = [(ad, s) for ad, s in d['lines'] if ad not in skip and pat.search(s)]
        hits += [(ad, f'jump table ${tb:X} entry {e.index(t)}') for ad, tb, e in d['tables'] if t in e]
        hits.sort()
        for ad, s in hits[:40]:
            print(f'  {ad:06x} {enclosing(d, ad)[0]:<34} {s}')
        if len(hits) > 40:
            print(f'  ... {len(hits) - 40} more')


if __name__ == '__main__':
    main()
