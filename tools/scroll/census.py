#!/usr/bin/env python3
"""Census of the retail scroll() routines: 68 programs, 48 structural shapes.

    python3 tools/scroll/census.py              shapes, programs, features
    python3 tools/scroll/census.py --extract    also run extract.py on every
                                                program (about 2 minutes) and
                                                print its result or its loud
                                                failure
    python3 tools/scroll/census.py --json F     write the census as JSON

A shape is the scroll() body with comments removed, every numeric literal
replaced by '#', and whitespace collapsed; identifiers are kept (cfront.py
shape_key).  Two programs share a shape when they differ only in numbers
(table values, counts, rates, masks).

Features are read from the text of scroll() and of the file-local functions
it calls (transitively), so a zone agent can see what a routine needs before
opening it:
  helpers    file-local functions scroll() reaches (besides the camera
             tracking functions and the scrollX_h/scrollb_* position helpers)
  external   functions it calls that the file does not define
  masks      constants c of the form 2^k-8 applied with `& c` (table index
             masks: buffer height = c + 8)
  vertical   which background-Y helper scroll() calls
  hspd       the routine reads the player's X speed (actwk[0].xspeed)
  rowindex   it writes hscrollwork[...] through an index, not a pointer walk
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cfront import programs, scroll_body, shape_key, functions   # noqa: E402

CAMERA = {'scrchk', 'scroll_h', 'scroll_v'}
POSITION = {'scrollz_h', 'scrollc_h', 'scrollb_h', 'scrollb_hv', 'scrollb_v'}
KEYWORDS = {'if', 'for', 'while', 'do', 'return', 'switch', 'sizeof'}


def reach(funcs, start):
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        if f in seen or f not in funcs or f in CAMERA:
            continue
        seen.add(f)
        for c in re.findall(r'\b([A-Za-z_]\w*)\s*\(', funcs[f][1]):
            if c not in KEYWORDS:
                todo.append(c)
    return seen


def features(path):
    text, funcs, body = scroll_body(path)
    reached = reach(funcs, 'scroll')
    calls = set()
    for f in reached | {'scroll'}:
        calls.update(c for c in re.findall(r'\b([A-Za-z_]\w*)\s*\(', funcs[f][1]) if c not in KEYWORDS)
    code = ' '.join(funcs[f][1] for f in reached)
    masks = sorted({int(m) for m in re.findall(r'&\s*(\d+)', code)
                    if int(m) >= 56 and (int(m) + 8) & (int(m) + 7) == 0})
    return {
        'helpers': sorted(reached - {'scroll'} - CAMERA - POSITION),
        'external': sorted(c for c in calls if c not in funcs and c not in CAMERA
                           and not re.match(r'^(int|short|char|unsigned|long)$', c)),
        'masks': masks,
        'vertical': sorted(c for c in ('scrollb_hv', 'scrollb_v') if re.search(rf'\b{c}\s*\(', body)),
        'hspd': bool(re.search(r'xspeed', code)),
        'rowindex': bool(re.search(r'hscrollwork\s*\[\s*[A-Za-z_]', code) and
                         re.search(r'hscrollwork\s*\[[^\]]*\]\s*=[^=]', code)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--extract', action='store_true', help='run extract.py on every program')
    ap.add_argument('--json', help='write the census to this file')
    args = ap.parse_args()
    if args.extract:
        import extract
    progs = programs()
    shapes = {}
    rows = {}
    for rnd, act, era, path in progs:
        name = f'{path.parent.name}/{path.name}'
        _, _, body = scroll_body(path)
        key = shape_key(body)
        shapes.setdefault(key, []).append(name)
        row = {'program': name, 'shape': key, 'features': features(path)}
        if args.extract:
            t = time.time()
            try:
                ir = extract.derive(path)
                row['extract'] = {'ok': True, 'runs': len(ir['runs']), 'bands': len(ir['bands']),
                                  'buffer_lines': ir['buffer_lines'], 'bg_y': ir['bg_y'],
                                  'corrections': len(ir['corrections'])}
            except Exception as e:                      # reported, never hidden
                row['extract'] = {'ok': False, 'error': f'{type(e).__name__}: {e}'.split('\n')[0][:300]}
            row['extract']['seconds'] = round(time.time() - t, 1)
        rows[name] = row

    print(f'{len(progs)} programs, {len(shapes)} shapes\n')
    ok_shapes = ok_progs = 0
    for n, (key, names) in enumerate(sorted(shapes.items(), key=lambda kv: kv[1][0]), 1):
        f = rows[names[0]]['features']
        print(f'shape {n:2d} {key}  {len(names)} program(s): {" ".join(Path(x).stem for x in names)}')
        print(f'   helpers={",".join(f["helpers"]) or "-"}  external={",".join(f["external"]) or "-"}  '
              f'masks={f["masks"] or "-"}  vertical={",".join(f["vertical"]) or "-"}  '
              f'hspd={int(f["hspd"])}  rowindex={int(f["rowindex"])}')
        if args.extract:
            all_ok = True
            for x in names:
                e = rows[x]['extract']
                if e['ok']:
                    ok_progs += 1
                    print(f'   {Path(x).stem}: OK runs={e["runs"]} bands={e["bands"]} buffer={e["buffer_lines"]} '
                          f'bg_y={e["bg_y"]} corrections={e["corrections"]}')
                else:
                    all_ok = False
                    print(f'   {Path(x).stem}: FAIL {e["error"]}')
            ok_shapes += all_ok
    if args.extract:
        print(f'\nextract.py: {ok_progs}/{len(progs)} programs, {ok_shapes}/{len(shapes)} shapes (every program of the shape)')
    if args.json:
        Path(args.json).write_text(json.dumps({'programs': len(progs), 'shapes': {
            k: v for k, v in sorted(shapes.items(), key=lambda kv: kv[1][0])}, 'rows': rows}, indent=1) + '\n')
        print(f'wrote {args.json}')


if __name__ == '__main__':
    main()
