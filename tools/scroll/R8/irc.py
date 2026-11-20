#!/usr/bin/env python3
"""Validate scroll IR JSON and compile it to C tables: ROUND 8 COPY.

This is tools/scroll/irc.py with three vocabulary extensions that the
Metallic Madness programs need.  The shared file is untouched; the merge stage
folds these back in (tools/scroll/R8/EXTENSIONS.md is the proposed ir.md text).

    python3 tools/scroll/R8/irc.py tools/scroll/R8/ir/*.json               validate
    python3 tools/scroll/R8/irc.py tools/scroll/R8/ir/*.json -o tables.c   and emit

A document either
  - is plain `scroll-ir/1` (no key or op below may appear), or
  - is `scroll-ir/1+R8` and lists, in "extensions", exactly the extensions it
    uses, drawn from:
      interp      table-run op: a row interpolated between layers by a 16.16
                  accumulator whose step is a 32-bit C division
      layer_K     a layer offset K: layer(L) = floor((C*x + U*ramp)/256) + K
      bg_shift    background Y op: sum of ((uint16)camera_y >> k)
The emitted C targets tools/scroll/R8/evaluate.h (the extended evaluator).
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
sys.path.insert(0, str(SHARED))
from cfront import programs      # noqa: E402

IR_VERSION = 'scroll-ir/1'
IR_VERSION_EXT = 'scroll-ir/1+R8'
EXTENSIONS = ('interp', 'layer_K', 'bg_shift')
SEEDS = ('zero', 'neg_camera', 'base_sign', 'unset')
ROW = 8
EXPR_KEYS = {
    'zero': set(),
    'layer': {'layer'},
    'cloud': {'layer', 'speed'},
    'ramp': {'from', 'to', 'D', 'diff_bits', 'step_bits'},
    'interp': {'base', 'num', 'D', 'signed', 'k', 'seed'},
}
TOP_KEYS = {'ir', 'program', 'shape', 'slot', 'buffer_lines', 'layers', 'ramp_gate', 'runs',
            'table_end', 'beyond_table', 'bands', 'bg_y', 'corrections', 'rules'}
OPTIONAL_TOP = {'rules', 'corrections', 'shape', 'ramp_gate', 'notes', 'extensions'}
MAX_NUM_TERMS = 4
MAX_SHIFTS = 4


class IRError(Exception):
    pass


def need(cond, where, msg):
    if not cond:
        raise IRError(f'{where}: {msg}')


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_expr(e, layers, where, allow_ramp, used_ext):
    need(isinstance(e, dict) and e.get('op') in EXPR_KEYS, where, f'unknown expression {e!r}')
    op = e['op']
    need(set(e) == EXPR_KEYS[op] | {'op'}, where, f'{op} takes exactly {sorted(EXPR_KEYS[op])}, got {sorted(set(e) - {"op"})}')
    for key in ('layer', 'from', 'to', 'base'):
        if key in e:
            need(e[key] in layers or e[key] == 'camera', where, f'unknown layer {e[key]!r}')
    if op == 'cloud':
        need(e['layer'] != 'camera', where, 'a cloud rides a layer, not the camera')
        need(is_int(e['speed']) and 0 < e['speed'] < 1 << 31, where, 'cloud speed must be 1..2^31-1')
    if op == 'ramp':
        need(allow_ramp, where, 'a ramp is only valid in a band (it needs a line counter)')
        need(is_int(e['D']) and e['D'] > 0, where, 'ramp D must be a positive integer')
        need(e['diff_bits'] in (16, 32) and e['step_bits'] in (16, 32), where, 'ramp widths are 16 or 32')
    if op == 'interp':
        used_ext.add('interp')
        need(not allow_ramp, where, 'interp is a table-run expression (one value per row), not a band')
        num = e['num']
        need(isinstance(num, dict) and 1 <= len(num) <= MAX_NUM_TERMS, where,
             f'interp num must map 1..{MAX_NUM_TERMS} layers to coefficients')
        for name, c in num.items():
            need(name in layers or name == 'camera', where, f'unknown layer {name!r} in interp num')
            need(is_int(c) and c != 0 and -(1 << 31) <= c < 1 << 31, where, 'interp num coefficients are non-zero int32')
        need(is_int(e['D']) and 0 < e['D'] < 1 << 31, where, 'interp D must be 1..2^31-1')
        need(isinstance(e['signed'], bool), where, 'interp signed is true or false')
        need(is_int(e['k']) and 0 < e['k'] < 1 << 32, where, 'interp k must be 1..2^32-1')
        need(e['seed'] in SEEDS, where, f'interp seed must be one of {SEEDS}')


def expr_layers(e):
    out = {e[k] for k in ('layer', 'from', 'to', 'base') if k in e}
    out.update(e.get('num', {}))
    return out


def validate(ir, where=None):
    where = where or ir.get('program', '<ir>')
    need(isinstance(ir, dict), where, 'document is not an object')
    need(ir.get('ir') in (IR_VERSION, IR_VERSION_EXT), where,
         f'"ir" must be {IR_VERSION!r} or {IR_VERSION_EXT!r}')
    missing = (TOP_KEYS - OPTIONAL_TOP) - set(ir)
    need(not missing, where, f'missing keys {sorted(missing)}')
    extra = set(ir) - TOP_KEYS - OPTIONAL_TOP
    need(not extra, where, f'unknown keys {sorted(extra)}')
    used_ext = set()
    m = re.fullmatch(r'R(\d)/SCR(\d)([1-3])([A-D])\.C', ir['program'])
    need(m and m.group(1) == m.group(2), where, 'program must be R<n>/SCR<n><act><era>.C')
    slot = ir['slot']
    need(slot == {'round': int(m.group(1)), 'act': int(m.group(3)), 'era': m.group(4)}, where,
         'slot does not match the program name')
    B = ir['buffer_lines']
    need(is_int(B) and 8 <= B <= 2048 and not B & (B - 1), where, 'buffer_lines must be a power of two in 8..2048')
    layers = ir['layers']
    need(isinstance(layers, dict) and 'camera' not in layers, where, 'layers must be an object without "camera"')
    for name, L in layers.items():
        need(set(L) in ({'C', 'U'}, {'C', 'U', 'K'}) and all(is_int(v) for v in L.values()), where,
             f'layer {name} must be {{C, U[, K]}}')
        if 'K' in L:
            need(L['K'] != 0, where, f'layer {name}: K is written only when it is not 0')
            used_ext.add('layer_K')
    if any(L['U'] for L in layers.values()):
        need(isinstance(ir.get('ramp_gate'), str), where, 'a layer with U != 0 needs ramp_gate')
    runs = ir['runs']
    need(isinstance(runs, list), where, 'runs must be a list')
    for i, r in enumerate(runs):
        need(set(r) == {'entries', 'expr'} and is_int(r['entries']) and r['entries'] > 0, where,
             f'run {i} must be {{entries > 0, expr}}')
        validate_expr(r['expr'], layers, f'{where} run {i}', False, used_ext)
        if i:
            need(r['expr'] != runs[i - 1]['expr'], where, f'runs {i - 1} and {i} have the same expression: merge them')
    end = sum(r['entries'] for r in runs) * ROW
    need(end == ir['table_end'], where, f'table_end {ir["table_end"]} != 8 * sum(entries) = {end}')
    need(end <= B, where, 'the table is longer than the buffer')
    need(ir['beyond_table'] == 'unwritten', where, 'beyond_table must be "unwritten"')
    last = 0
    for i, b in enumerate(sorted(ir['bands'], key=lambda b: b['start'])):
        need(set(b) - {'tail'} == {'start', 'lines', 'expr'}, where, f'band {i} must be {{start, lines, expr[, tail]}}')
        need(is_int(b['start']) and is_int(b['lines']) and b['lines'] > 0, where, f'band {i} start/lines')
        need(b['start'] >= last and b['start'] + b['lines'] <= B, where, f'band {i} overlaps another or leaves the buffer')
        last = b['start'] + b['lines']
        validate_expr(b['expr'], layers, f'{where} band {i}', True, used_ext)
        if b.get('tail'):
            need(b['start'] == end and b['start'] + b['lines'] == B, where, 'a tail band runs from table_end to the buffer end')
    g = ir['bg_y']
    need(isinstance(g, dict) and g.get('op') in ('rate', 'camera', 'shift'), where, f'unknown bg_y {g!r}')
    if g['op'] == 'rate':
        need(set(g) == {'op', 'C'} and is_int(g['C']), where, 'bg_y rate is {op, C}')
    elif g['op'] == 'shift':
        used_ext.add('bg_shift')
        need(set(g) == {'op', 'k'} and isinstance(g['k'], list) and 1 <= len(g['k']) <= MAX_SHIFTS
             and all(is_int(k) and 0 <= k <= 15 for k in g['k']), where,
             f'bg_y shift is {{op, k: 1..{MAX_SHIFTS} shifts in 0..15}}')
    else:
        need(set(g) <= {'op', 'fold'}, where, 'bg_y camera is {op[, fold]}')
        if 'fold' in g:
            f = g['fold']
            need(set(f) == {'player_x_min', 'y_min', 'div'} and all(is_int(v) for v in f.values()) and f['div'] > 0,
                 where, 'fold is {player_x_min, y_min, div > 0}')
    used = set()
    for e in [r['expr'] for r in runs] + [b['expr'] for b in ir['bands']]:
        used.update(expr_layers(e))
    need(used - {'camera'} == set(layers), where, f'layers {sorted(set(layers) - used)} are declared but unused')
    if ir['ir'] == IR_VERSION:
        need(not used_ext and 'extensions' not in ir, where,
             f'a plain {IR_VERSION} document uses no extension (found {sorted(used_ext)})')
    else:
        ext = ir.get('extensions')
        need(isinstance(ext, list) and all(x in EXTENSIONS for x in ext), where,
             f'"extensions" must list names from {EXTENSIONS}')
        need(set(ext) == used_ext and len(ext) == len(set(ext)), where,
             f'"extensions" {ext} must list exactly the extensions used: {sorted(used_ext)}')
    return ir


# ----------------------------------------------------------------- C

OPS = {'zero': 'SCROLL_ZERO', 'layer': 'SCROLL_LAYER', 'cloud': 'SCROLL_CLOUD', 'ramp': 'SCROLL_RAMP',
       'interp': 'SCROLL_INTERP'}
SEED_C = {'zero': 'SCROLL_SEED_ZERO', 'neg_camera': 'SCROLL_SEED_NEG_CAMERA',
          'base_sign': 'SCROLL_SEED_BASE_SIGN', 'unset': 'SCROLL_SEED_UNSET'}


def c_ident(program):
    return 'scroll_ir_' + re.sub(r'\W', '_', Path(program).stem.lower())


def emit_c(irs, out_path):
    out = ['/* Generated by tools/scroll/R8/irc.py from scroll IR JSON.  Do not edit.',
           '   Format: tools/scroll/R8/EXTENSIONS.md and tools/scroll/R8/evaluate.h. */',
           '#include "evaluate.h"', '']
    by_slot = {}
    for ir in irs:
        ident = c_ident(ir['program'])
        s = ir['slot']
        key = (s['round'], s['act'], s['era'])
        if key in by_slot:
            raise IRError(f'{ir["program"]}: two documents for one slot')
        by_slot[key] = ident
        order = ['camera'] + sorted(ir['layers'])
        idx = {k: i for i, k in enumerate(order)}
        interps = []

        def expr(e):
            op = OPS[e['op']]
            if e['op'] == 'zero':
                return f'{{{op},0,0,0,0,0}}'
            if e['op'] == 'layer':
                return f"{{{op},{idx[e['layer']]},0,0,0,0}}"
            if e['op'] == 'cloud':
                return f"{{{op},{idx[e['layer']]},0,0,0,{e['speed']}}}"
            if e['op'] == 'interp':
                terms = sorted(e['num'].items(), key=lambda kv: idx[kv[0]])
                lay = ','.join(str(idx[n]) for n, _ in terms) or '0'
                coef = ','.join(str(c) for _, c in terms) or '0'
                interps.append(f"{{{idx[e['base']]},{len(terms)},{{{lay}}},{{{coef}}},{e['D']},"
                               f"{1 if e['signed'] else 0},{e['k']}u,{SEED_C[e['seed']]}}}")
                return f'{{{op},{len(interps) - 1},0,0,0,0}}'
            return f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},{e['step_bits']},{e['D']}}}"

        runs_c = ','.join(f"{{{r['entries'] * ROW},{expr(r['expr'])}}}" for r in ir['runs'])
        bands_c = ','.join(f"{{{b['start']},{b['lines']},{expr(b['expr'])}}}" for b in ir['bands'])
        out.append(f'/* {ir["program"]} */')
        out.append(f'static const scroll_layer {ident}_layers[] = {{{{256,0,0}}' +
                   ''.join(f",{{{ir['layers'][k]['C']},{ir['layers'][k]['U']},{ir['layers'][k].get('K', 0)}}}"
                           for k in order[1:]) + '};')
        out.append(f'static const scroll_run {ident}_runs[] = {{{runs_c}}};')
        if ir['bands']:
            out.append(f'static const scroll_band {ident}_bands[] = {{{bands_c}}};')
        if interps:
            out.append(f'static const scroll_interp {ident}_interps[] = {{' + ','.join(interps) + '};')
        g = ir['bg_y']
        if g['op'] == 'rate':
            bgy = f"{{SCROLL_BGY_RATE,{g['C']},0,0,0,0,{{0}}}}"
        elif g['op'] == 'shift':
            bgy = f"{{SCROLL_BGY_SHIFT,0,0,0,0,{len(g['k'])},{{{','.join(str(k) for k in g['k'])}}}}}"
        else:
            f = g.get('fold') or {'player_x_min': 0, 'y_min': 0, 'div': 0}
            bgy = f"{{SCROLL_BGY_CAMERA,0,{f['player_x_min']},{f['y_min']},{f['div']},0,{{0}}}}"
        out.append(f"const scroll_ir {ident} = {{\"{ir['program']}\",{ir['buffer_lines']},"
                   f"{len(order)},{ident}_layers,{len(ir['runs'])},{ident}_runs,"
                   f"{len(ir['bands'])},{ident + '_bands' if ir['bands'] else '0'},"
                   f"{len(interps)},{ident + '_interps' if interps else '0'},{bgy}}};")
        out.append('')
    rounds = sorted({r for r, a, e, p in programs()})
    have = {(r, a, e) for r, a, e, p in programs()}
    slots, source = [], []
    for r in rounds:
        for act in (1, 2, 3):
            for era in 'ABCD':
                key = (r, act, era)
                if key in by_slot:
                    slots.append('&' + by_slot[key])
                    source.append(f'R{r}/SCR{r}{act}{era}.C')
                else:
                    slots.append('0')
                    source.append('no IR yet' if key in have else 'no program file')
    out.append(f'const scroll_ir *const scroll_ir_slots[{len(slots)}] = {{' + ','.join(slots) + '};')
    out.append(f'const char *const scroll_ir_slot_source[{len(slots)}] = {{' +
               ','.join(json.dumps(s) for s in source) + '};')
    out.append(f'const unsigned scroll_ir_slot_count = {len(slots)};')
    Path(out_path).write_text('\n'.join(out) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+')
    ap.add_argument('-o', '--output')
    args = ap.parse_args(argv)
    irs = []
    for f in args.files:
        try:
            irs.append(validate(json.loads(Path(f).read_text()), f))
        except (IRError, json.JSONDecodeError, KeyError, TypeError) as e:
            raise SystemExit(f'irc.py (R8): FAIL {f}: {e}')
    print(f'irc.py (R8): {len(irs)} documents valid')
    if args.output:
        emit_c(irs, args.output)
        print(f'irc.py (R8): wrote {args.output}')


if __name__ == '__main__':
    main()
