#!/usr/bin/env python3
"""Validate extended scroll IR (`scroll-ir/1+r4`, R4/ir-extensions.md) and
compile it to C tables for R4/evaluate_x.c.

    python3 tools/scroll/R4/irx.py R4/ir/*.json               validate only
    python3 tools/scroll/R4/irx.py R4/ir/*.json -o tables.c   validate and emit

The extended format is scroll-ir/1 (tools/scroll/ir.md) plus exactly three
additions, each defined with exact integer semantics in R4/ir-extensions.md:

  run op `interp`   a table row interpolated between two layers
  bg_y op `pieces`  background Y as ordered conditional pieces over camera X/Y
  key `water`       the sine wobble added to screen lines below the water surface

A document that uses none of them must be plain scroll-ir/1 and is checked by
the shared tools/scroll/irc.py instead; this file refuses it, so an extended
document is never produced without a reason.  Nothing here is specific to a
zone, act, era or program.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import irc                      # noqa: E402

IR_VERSION = 'scroll-ir/1+r4'
ROW = 8
EXPR_KEYS = dict(irc.EXPR_KEYS)
EXPR_KEYS['interp'] = {'from', 'to', 'k', 'D', 'm', 'diff_bits'}
TOP_KEYS = irc.TOP_KEYS | {'water'}
OPTIONAL_TOP = irc.OPTIONAL_TOP | {'water'}
COND_VARS = {'camera_x', 'camera_y', 'player_x'}
COND_OPS = {'<', '>', '<=', '>=', '==', '!='}
WATER_KEYS = {'surface', 'phase', 'table_name', 'table_source', 'table', 'sign'}


class IRError(Exception):
    pass


def need(cond, where, msg):
    if not cond:
        raise IRError(f'{where}: {msg}')


is_int = irc.is_int


def validate_expr(e, layers, where, in_band):
    need(isinstance(e, dict) and e.get('op') in EXPR_KEYS, where, f'unknown expression {e!r}')
    op = e['op']
    need(set(e) == EXPR_KEYS[op] | {'op'}, where,
         f'{op} takes exactly {sorted(EXPR_KEYS[op])}, got {sorted(set(e) - {"op"})}')
    if op == 'interp':
        need(not in_band, where, 'interp is a table row, not a band')
        for key in ('from', 'to'):
            need(e[key] in layers or e[key] == 'camera', where, f'unknown layer {e[key]!r}')
        need(e['from'] != 'camera', where, 'interp starts from a layer')
        need(is_int(e['k']) and 0 < e['k'] < 1 << 15, where, 'interp k must be 1..32767')
        need(is_int(e['D']) and e['D'] > 0, where, 'interp D must be positive')
        need(is_int(e['m']) and 0 < e['m'] < 1 << 16, where, 'interp m must be 1..65535')
        need(e['diff_bits'] in (16, 32), where, 'interp diff_bits is 16 or 32')
        return
    try:
        irc.validate_expr(e, layers, where, in_band)
    except irc.IRError as x:
        raise IRError(str(x))


def validate_bgy(g, where):
    need(isinstance(g, dict) and g.get('op') in ('rate', 'camera', 'pieces'), where, f'unknown bg_y {g!r}')
    if g['op'] != 'pieces':
        return
    need(set(g) == {'op', 'pieces'} and isinstance(g['pieces'], list) and g['pieces'], where,
         'bg_y pieces is {op, pieces: [...]}')
    seen = []
    for i, p in enumerate(g['pieces']):
        need(set(p) == {'if', 'mul', 'add', 'shift'}, where, f'piece {i} is {{if, mul, add, shift}}')
        need(all(is_int(p[k]) for k in ('mul', 'add', 'shift')) and 0 <= p['shift'] <= 31, where,
             f'piece {i}: integer mul/add, shift 0..31')
        need(isinstance(p['if'], list) and len(p['if']) <= 4, where, f'piece {i}: at most 4 conditions')
        for c in p['if']:
            need(isinstance(c, dict) and set(c) == {'var', 'op', 'value', 'unsigned'}, where,
                 f'piece {i}: condition is {{var, op, value, unsigned}}')
            need(c['var'] in COND_VARS and c['op'] in COND_OPS and is_int(c['value'])
                 and isinstance(c['unsigned'], bool), where, f'piece {i}: bad condition {c}')
        key = json.dumps(p['if'], sort_keys=True)
        need(key not in seen, where, f'piece {i} repeats the conditions of another piece')
        seen.append(key)


def validate_water(w, where):
    need(isinstance(w, dict) and set(w) == WATER_KEYS, where, f'water is {sorted(WATER_KEYS)}')
    need(isinstance(w['surface'], str) and isinstance(w['table_name'], str)
         and isinstance(w['table_source'], str), where, 'water names are strings')
    ph = w['phase']
    need(isinstance(ph, dict) and set(ph) == {'word', 'step'} and isinstance(ph['word'], str)
         and is_int(ph['step']) and 0 <= ph['step'] < 65536, where, 'water phase is {word, step 0..65535}')
    t = w['table']
    need(isinstance(t, list) and len(t) == 256 and all(is_int(v) and -128 <= v <= 127 for v in t), where,
         'water table is 256 signed bytes')
    need(w['sign'] in (1, -1), where, 'water sign is 1 or -1')


def validate(ir, where=None):
    where = where or ir.get('program', '<ir>')
    need(isinstance(ir, dict), where, 'document is not an object')
    need(ir.get('ir') == IR_VERSION, where, f'"ir" must be {IR_VERSION!r}')
    missing = (TOP_KEYS - OPTIONAL_TOP) - set(ir)
    need(not missing, where, f'missing keys {sorted(missing)}')
    extra = set(ir) - TOP_KEYS - OPTIONAL_TOP
    need(not extra, where, f'unknown keys {sorted(extra)}')
    uses = []
    if ir.get('water') is not None:
        validate_water(ir['water'], where)
        uses.append('water')
    need(ir.get('water', 0) is not None, where, 'water, when present, is an object')
    validate_bgy(ir['bg_y'], where)
    if ir['bg_y']['op'] == 'pieces':
        uses.append('pieces')
    if any(r.get('expr', {}).get('op') == 'interp' for r in ir['runs']):
        uses.append('interp')
    need(uses, where, 'uses no extension: emit plain scroll-ir/1 and validate it with irc.py')
    # everything else is scroll-ir/1: check it with the shared validator on a
    # copy whose extension parts are replaced by neutral stand-ins, then check
    # the extension parts here
    core = json.loads(json.dumps(ir))
    core['ir'] = irc.IR_VERSION
    core.pop('water', None)
    if core['bg_y']['op'] == 'pieces':
        core['bg_y'] = {'op': 'rate', 'C': 0}
    layers = core['layers']
    for i, r in enumerate(core['runs']):
        if r['expr']['op'] == 'interp':
            validate_expr(r['expr'], layers, f'{where} run {i}', False)
            # stand-in for the shared check: a plain run on the interp start layer
            r['expr'] = {'op': 'layer', 'layer': ir['runs'][i]['expr']['from']}
            r['_interp'] = i
    for i in range(1, len(ir['runs'])):
        need(ir['runs'][i]['expr'] != ir['runs'][i - 1]['expr'], where,
             f'runs {i - 1} and {i} have the same expression: merge them')
    # the stand-ins may make neighbours equal; merge them only for the shared check
    merged = []
    for r in core['runs']:
        r.pop('_interp', None)
        if merged and merged[-1]['expr'] == r['expr']:
            merged[-1]['entries'] += r['entries']
        else:
            merged.append(r)
    core['runs'] = merged
    # a layer used only as an interp target has no stand-in; its usage was
    # checked above on the full document
    used_core = set()
    for r in core['runs']:
        used_core.update(r['expr'][k] for k in ('layer', 'from', 'to') if k in r['expr'])
    for b in core['bands']:
        used_core.update(b['expr'][k] for k in ('from', 'to'))
    core['layers'] = {k: v for k, v in layers.items() if k in used_core}
    used = set()
    for r in ir['runs']:
        e = r['expr']
        used.update(e[k] for k in ('layer', 'from', 'to') if k in e)
    for b in ir['bands']:
        used.update(b['expr'][k] for k in ('from', 'to'))
    need(used - {'camera'} == set(layers), where, f'layers {sorted(set(layers) ^ (used - {"camera"}))} '
                                                  'are declared but unused, or used but undeclared')
    try:
        irc.validate(core, where)
    except irc.IRError as x:
        raise IRError(str(x))
    return ir


# ----------------------------------------------------------------- C

OPS = {'zero': 'SCROLL_ZERO', 'layer': 'SCROLL_LAYER', 'cloud': 'SCROLL_CLOUD', 'ramp': 'SCROLL_RAMP',
       'interp': 'SCROLL_INTERP'}
VARS = {'camera_x': 'SCROLLX_CAMERA_X', 'camera_y': 'SCROLLX_CAMERA_Y', 'player_x': 'SCROLLX_PLAYER_X'}
CMPS = {'<': 'SCROLLX_LT', '>': 'SCROLLX_GT', '<=': 'SCROLLX_LE', '>=': 'SCROLLX_GE', '==': 'SCROLLX_EQ',
        '!=': 'SCROLLX_NE'}


def c_ident(program):
    return 'scroll_irx_' + re.sub(r'\W', '_', Path(program).stem.lower())


def emit_c(irs, out_path):
    """irs: extended or plain documents (plain ones are validated by irc.py
    by the caller).  Emits scroll_irx tables for evaluate_x.c."""
    out = ['/* Generated by tools/scroll/R4/irx.py.  Do not edit.',
           '   Format: tools/scroll/R4/ir-extensions.md and R4/evaluate_x.h. */',
           '#include "evaluate_x.h"', '']
    idents = []
    for ir in irs:
        ident = c_ident(ir['program'])
        idents.append((ir['program'], ident))
        order = ['camera'] + sorted(ir['layers'])
        idx = {k: i for i, k in enumerate(order)}

        def expr(e):
            op = OPS[e['op']]
            if e['op'] == 'zero':
                return f'{{{op},0,0,0,0,0,0,0}}'
            if e['op'] == 'layer':
                return f"{{{op},{idx[e['layer']]},0,0,0,0,0,0}}"
            if e['op'] == 'cloud':
                return f"{{{op},{idx[e['layer']]},0,0,0,{e['speed']},0,0}}"
            if e['op'] == 'ramp':
                return f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},{e['step_bits']},{e['D']},0,0}}"
            return (f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},0,{e['D']},"
                    f"{e['k']},{e['m']}}}")

        out.append(f'/* {ir["program"]} */')
        out.append(f'static const scroll_layer {ident}_layers[] = {{{{256,0}}' +
                   ''.join(f",{{{ir['layers'][k]['C']},{ir['layers'][k]['U']}}}" for k in order[1:]) + '};')
        out.append(f'static const scrollx_run {ident}_runs[] = {{' +
                   ','.join(f"{{{r['entries'] * ROW},{expr(r['expr'])}}}" for r in ir['runs']) + '};')
        if ir['bands']:
            out.append(f'static const scrollx_band {ident}_bands[] = {{' +
                       ','.join(f"{{{b['start']},{b['lines']},{expr(b['expr'])}}}" for b in ir['bands']) + '};')
        g = ir['bg_y']
        npieces, pieces_ref = 0, '0'
        if g['op'] == 'pieces':
            items = []
            for p in g['pieces']:
                conds = ','.join(f"{{{VARS[c['var']]},{CMPS[c['op']]},{int(c['unsigned'])},{c['value']}}}"
                                 for c in p['if']) or '{0,0,0,0}'
                items.append(f"{{{len(p['if'])},{{{conds}}},{p['mul']}LL,{p['add']}LL,{p['shift']}}}")
            out.append(f'static const scrollx_piece {ident}_pieces[] = {{' + ','.join(items) + '};')
            npieces, pieces_ref = len(g['pieces']), f'{ident}_pieces'
            bgy = '{SCROLLX_BGY_PIECES,0,0,0,0}'
        elif g['op'] == 'rate':
            bgy = f"{{SCROLL_BGY_RATE,{g['C']},0,0,0}}"
        else:
            f = g.get('fold') or {'player_x_min': 0, 'y_min': 0, 'div': 0}
            bgy = f"{{SCROLL_BGY_CAMERA,0,{f['player_x_min']},{f['y_min']},{f['div']}}}"
        w = ir.get('water')
        if w:
            out.append(f'static const int8_t {ident}_water[256] = {{' + ','.join(map(str, w['table'])) + '};')
            water = f"{{1,{w['phase']['step']},{w['sign']},{ident}_water}}"
        else:
            water = '{0,0,0,0}'
        out.append(f"const scrollx_ir {ident} = {{\"{ir['program']}\",{ir['buffer_lines']},"
                   f"{len(order)},{ident}_layers,{len(ir['runs'])},{ident}_runs,"
                   f"{len(ir['bands'])},{ident + '_bands' if ir['bands'] else '0'},{bgy},"
                   f"{npieces},{pieces_ref},{water}}};")
        out.append('')
    out.append(f'const scrollx_ir *const scroll_irx_all[{len(idents)}] = {{' +
               ','.join('&' + i for _, i in idents) + '};')
    out.append(f'const unsigned scroll_irx_count = {len(idents)};')
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
            raise SystemExit(f'irx.py: FAIL {f}: {e}')
    print(f'irx.py: {len(irs)} documents valid')
    if args.output:
        emit_c(irs, args.output)
        print(f'irx.py: wrote {args.output}')


if __name__ == '__main__':
    main()
