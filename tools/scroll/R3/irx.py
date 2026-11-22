#!/usr/bin/env python3
"""Validate, evaluate and compile scroll IR `scroll-ir/1+R3`.

`scroll-ir/1+R3` is scroll-ir/1 (tools/scroll/ir.md) plus the ops Collision
Chaos needs, specified in tools/scroll/R3/ir-extension.md:

  run/band op  interp   a 16.16 accumulator stepped once per table row
  band op      wave     layer + scale * table[(phase + offset + k) & mask]
  bg_y op      clamp    (u16)camY <= ref ? max(min, base - ((ref - camY) >> shift)) : base
  top key      tables   the data a wave reads, copied from the retail tree

    python3 tools/scroll/R3/irx.py tools/scroll/R3/ir/*.json            validate
    python3 tools/scroll/R3/irx.py tools/scroll/R3/ir/*.json -o F.c     validate and emit C
                                                                       tables for evaluate_r3.c

Everything scroll-ir/1 allows is still allowed with the same meaning; the
Python evaluator below mirrors tools/scroll/evaluate.c for those ops and
tools/scroll/R3/evaluate_r3.c for all of them.  Nothing here names a round,
a program or a table value.
"""
import argparse
import json
import re
import sys
from pathlib import Path

IR_VERSION = 'scroll-ir/1+R3'
ROW = 8
INTERP_KEYS = {'from', 'to', 'n', 'D', 'm', 'diff_bits', 'seed'}
SEED_KEYS = {'from', 'to', 'n', 'D', 'm', 'diff_bits'}
EXPR_KEYS = {
    'zero': set(),
    'layer': {'layer'},
    'cloud': {'layer', 'speed'},
    'ramp': {'from', 'to', 'D', 'diff_bits', 'step_bits'},
    'interp': INTERP_KEYS,
    'wave': {'layer', 'table', 'scale', 'phase_speed', 'offset', 'mask'},
}
TOP_KEYS = {'ir', 'program', 'shape', 'slot', 'buffer_lines', 'layers', 'ramp_gate', 'runs',
            'table_end', 'beyond_table', 'bands', 'bg_y', 'corrections', 'rules', 'tables', 'notes'}
OPTIONAL_TOP = {'rules', 'corrections', 'shape', 'ramp_gate', 'notes', 'tables'}


class IRError(Exception):
    pass


def need(cond, where, msg):
    if not cond:
        raise IRError(f'{where}: {msg}')


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_step(e, layers, where):
    for key in ('from', 'to'):
        need(e[key] in layers or e[key] == 'camera', where, f'unknown layer {e[key]!r}')
    need(e['from'] != 'camera', where, 'an interpolation starts from a layer, not the camera')
    need(is_int(e['n']) and e['n'] != 0, where, 'interp n must be a non-zero integer')
    need(is_int(e['D']) and e['D'] > 0, where, 'interp D must be a positive integer')
    need(is_int(e['m']), where, 'interp m must be an integer')
    need(e['diff_bits'] in (16, 32), where, 'interp diff_bits is 16 or 32')


def validate_expr(e, layers, tables, where, in_band):
    need(isinstance(e, dict) and e.get('op') in EXPR_KEYS, where, f'unknown expression {e!r}')
    op = e['op']
    need(set(e) == EXPR_KEYS[op] | {'op'}, where, f'{op} takes exactly {sorted(EXPR_KEYS[op])}, got {sorted(set(e) - {"op"})}')
    for key in ('layer', 'from', 'to'):
        if key in e:
            need(e[key] in layers or e[key] == 'camera', where, f'unknown layer {e[key]!r}')
    if op == 'cloud':
        need(e['layer'] != 'camera', where, 'a cloud rides a layer, not the camera')
        need(is_int(e['speed']) and 0 < e['speed'] < 1 << 31, where, 'cloud speed must be 1..2^31-1')
    if op == 'ramp':
        need(in_band, where, 'a ramp is only valid in a band (it needs a line counter)')
        need(is_int(e['D']) and e['D'] > 0, where, 'ramp D must be a positive integer')
        need(e['diff_bits'] in (16, 32) and e['step_bits'] in (16, 32), where, 'ramp widths are 16 or 32')
    if op == 'interp':
        _check_step(e, layers, where)
        if e['seed'] is not None:
            need(isinstance(e['seed'], dict) and set(e['seed']) == SEED_KEYS, where,
                 f'interp seed is null or exactly {sorted(SEED_KEYS)}')
            _check_step(e['seed'], layers, where + ' seed')
    if op == 'wave':
        need(in_band, where, 'a wave is only valid in a band (it needs a line counter)')
        need(e['layer'] != 'camera', where, 'a wave rides a layer, not the camera')
        need(e['table'] in tables, where, f'unknown table {e["table"]!r}')
        n = len(tables[e['table']]['values'])
        need(is_int(e['mask']) and e['mask'] >= 0 and not (e['mask'] + 1) & e['mask'] and e['mask'] < n,
             where, 'wave mask must be 2^k - 1 inside the table')
        need(is_int(e['offset']) and 0 <= e['offset'] <= e['mask'], where, 'wave offset must be 0..mask')
        need(is_int(e['scale']) and e['scale'] != 0, where, 'wave scale must be a non-zero integer')
        need(is_int(e['phase_speed']) and 0 < e['phase_speed'] < 65536, where, 'wave phase_speed must be 1..65535')


def validate(ir, where=None):
    where = where or ir.get('program', '<ir>')
    need(isinstance(ir, dict), where, 'document is not an object')
    need(ir.get('ir') == IR_VERSION, where, f'"ir" must be {IR_VERSION!r}')
    missing = (TOP_KEYS - OPTIONAL_TOP) - set(ir)
    need(not missing, where, f'missing keys {sorted(missing)}')
    extra = set(ir) - TOP_KEYS
    need(not extra, where, f'unknown keys {sorted(extra)}')
    m = re.fullmatch(r'R(\d)/SCR(\d)([1-3])([A-D])\.C', ir['program'])
    need(m and m.group(1) == m.group(2), where, 'program must be R<n>/SCR<n><act><era>.C')
    need(ir['slot'] == {'round': int(m.group(1)), 'act': int(m.group(3)), 'era': m.group(4)}, where,
         'slot does not match the program name')
    B = ir['buffer_lines']
    need(is_int(B) and 8 <= B <= 2048 and not B & (B - 1), where, 'buffer_lines must be a power of two in 8..2048')
    layers = ir['layers']
    need(isinstance(layers, dict) and 'camera' not in layers, where, 'layers must be an object without "camera"')
    for name, L in layers.items():
        need(set(L) == {'C', 'U'} and is_int(L['C']) and is_int(L['U']), where, f'layer {name} must be {{C, U}}')
    if any(L['U'] for L in layers.values()):
        need(isinstance(ir.get('ramp_gate'), str), where, 'a layer with U != 0 needs ramp_gate')
    tables = ir.get('tables', {})
    need(isinstance(tables, dict), where, 'tables must be an object')
    for tname, t in tables.items():
        need(isinstance(t, dict) and set(t) == {'source', 'values'} and isinstance(t['source'], str), where,
             f'table {tname} must be {{source, values}}')
        need(isinstance(t['values'], list) and t['values'] and
             all(is_int(v) and -32768 <= v <= 32767 for v in t['values']), where,
             f'table {tname} values must be 16-bit integers')
    runs = ir['runs']
    need(isinstance(runs, list), where, 'runs must be a list')
    for i, r in enumerate(runs):
        need(set(r) == {'entries', 'expr'} and is_int(r['entries']) and r['entries'] > 0, where,
             f'run {i} must be {{entries > 0, expr}}')
        validate_expr(r['expr'], layers, tables, f'{where} run {i}', False)
        if i:
            need(r['expr'] != runs[i - 1]['expr'], where, f'runs {i - 1} and {i} have the same expression: merge them')
    end = sum(r['entries'] for r in runs) * ROW
    need(end == ir['table_end'], where, f'table_end {ir["table_end"]} != 8 * sum(entries) = {end}')
    need(end <= B, where, 'the table is longer than the buffer')
    need(ir['beyond_table'] == 'unwritten', where, 'beyond_table must be "unwritten"')
    last = 0
    for i, b in enumerate(ir['bands']):
        need(set(b) - {'tail'} == {'start', 'lines', 'expr'}, where, f'band {i} must be {{start, lines, expr[, tail]}}')
        need(is_int(b['start']) and is_int(b['lines']) and b['lines'] > 0, where, f'band {i} start/lines')
        need(b['start'] >= last and b['start'] + b['lines'] <= B, where,
             f'band {i} is out of order, overlaps another or leaves the buffer')
        last = b['start'] + b['lines']
        validate_expr(b['expr'], layers, tables, f'{where} band {i}', True)
        if b.get('tail'):
            need(b['start'] == end and b['start'] + b['lines'] == B, where, 'a tail band runs from table_end to the buffer end')
    g = ir['bg_y']
    need(isinstance(g, dict) and g.get('op') in ('rate', 'camera', 'clamp'), where, f'unknown bg_y {g!r}')
    if g['op'] == 'rate':
        need(set(g) == {'op', 'C'} and is_int(g['C']), where, 'bg_y rate is {op, C}')
    elif g['op'] == 'camera':
        need(set(g) <= {'op', 'fold'}, where, 'bg_y camera is {op[, fold]}')
        if 'fold' in g:
            f = g['fold']
            need(set(f) == {'player_x_min', 'y_min', 'div'} and all(is_int(v) for v in f.values()) and f['div'] > 0,
                 where, 'fold is {player_x_min, y_min, div > 0}')
    else:
        need(set(g) == {'op', 'ref', 'base', 'shift', 'min'} and all(is_int(g[k]) for k in ('ref', 'base', 'shift', 'min')),
             where, 'bg_y clamp is {op, ref, base, shift, min}')
        need(0 <= g['ref'] <= 65535 and 0 <= g['shift'] < 16 and -32768 <= g['base'] <= 32767
             and -32768 <= g['min'] <= 32767, where, 'bg_y clamp constants out of range')
    used, used_tables = set(), set()
    for e in [r['expr'] for r in runs] + [b['expr'] for b in ir['bands']]:
        used.update(e[k] for k in ('layer', 'from', 'to') if k in e)
        if e.get('seed'):
            used.update((e['seed']['from'], e['seed']['to']))
        if e['op'] == 'wave':
            used_tables.add(e['table'])
    need(used - {'camera'} == set(layers), where, f'layers {sorted(set(layers) ^ (used - {"camera"}))} declared/used mismatch')
    need(used_tables == set(tables), where, f'tables {sorted(set(tables) ^ used_tables)} declared/used mismatch')
    return ir


# ----------------------------------------------------------------- reference semantics (Python)

def wrap16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def cdiv(a, b):
    """C division: toward zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def layer_value(ir, name, x, ramp):
    if name == 'camera':
        return x
    L = ir['layers'][name]
    return (L['C'] * x + L['U'] * ramp) // 256          # floor


def _step(e, vals):
    d = vals[e['to']] - vals[e['from']]
    if e['diff_bits'] == 16:
        d = wrap16(d)
    return cdiv(e['n'] * d, e['D'])


def interp_value(e, vals):
    """interp: from + floor((F + m*q) / 65536); vals maps layer names
    (and 'camera') to pixel positions."""
    q = _step(e, vals)
    F = 0
    if e['seed'] is not None:
        s = e['seed']
        F = (s['m'] * _step(s, vals)) & 0xFFFF
    return vals[e['from']] + (F + e['m'] * q) // 65536


def expr_value(ir, e, x, f, ramp, k):
    op = e['op']
    if op == 'zero':
        return 0
    if op == 'layer':
        return layer_value(ir, e['layer'], x, ramp)
    if op == 'cloud':
        return layer_value(ir, e['layer'], x, ramp) + (((f * e['speed']) & 0xFFFFFFFF) >> 16)
    if op == 'ramp':
        frm, to = layer_value(ir, e['from'], x, ramp), layer_value(ir, e['to'], x, ramp)
        d = to - frm
        if e['diff_bits'] == 16:
            d = wrap16(d)
        q = cdiv(256 * d, e['D'])
        if e['step_bits'] == 16:
            q = wrap16(q)
        return frm + (k * q) // 256
    if op == 'interp':
        names = {e['from'], e['to']} | ({e['seed']['from'], e['seed']['to']} if e['seed'] else set())
        return interp_value(e, {n: layer_value(ir, n, x, ramp) for n in names})
    if op == 'wave':
        acc = (f * e['phase_speed']) & 0xFFFF
        idx = ((acc >> 8) + e['offset'] + k) & e['mask']
        return layer_value(ir, e['layer'], x, ramp) + e['scale'] * ir['tables'][e['table']]['values'][idx]
    raise IRError(f'unknown op {op}')


def raster_x(ir, x, y, f, ramp):
    line = y & (ir['buffer_lines'] - 1)
    for b in ir['bands']:
        if b['start'] <= line < b['start'] + b['lines']:
            return expr_value(ir, b['expr'], x, f, ramp, line - b['start'])
    end = 0
    for r in ir['runs']:
        end += r['entries'] * ROW
        if line < end:
            return expr_value(ir, r['expr'], x, f, ramp, 0)
    return 0


def bg_y_value(rule, y, player_x):
    op = rule['op']
    if op == 'rate':
        return (rule['C'] * y) >> 8
    if op == 'camera':
        fo = rule.get('fold')
        if fo and (player_x & 0xFFFF) >= fo['player_x_min'] and (y & 0xFFFF) >= fo['y_min']:
            return cdiv(y - fo['y_min'], fo['div']) + fo['y_min']
        return y
    if op == 'clamp':
        yu = y & 0xFFFF
        if yu <= rule['ref']:
            v = wrap16(rule['base'] - ((rule['ref'] - yu) >> rule['shift']))
            return rule['min'] if v < rule['min'] else v
        return rule['base']
    raise IRError(f'unknown bg_y op {op}')


# ----------------------------------------------------------------- C

OPS = {'zero': 'SCROLL_ZERO', 'layer': 'SCROLL_LAYER', 'cloud': 'SCROLL_CLOUD', 'ramp': 'SCROLL_RAMP',
       'interp': 'SCROLL_INTERP', 'wave': 'SCROLL_WAVE'}


def c_ident(program):
    return 'scroll_ir_' + re.sub(r'\W', '_', Path(program).stem.lower())


def emit_c(irs, out_path):
    """Tables for evaluate_r3.h.  Field order extends evaluate.h's, so tables
    irc.py emits for scroll-ir/1 documents also compile against it."""
    out = ['/* Generated by tools/scroll/R3/irx.py from scroll IR JSON (scroll-ir/1+R3).  Do not edit.',
           '   Format: tools/scroll/R3/ir-extension.md and tools/scroll/R3/evaluate_r3.h. */',
           '#include "evaluate_r3.h"', '']
    idents = []
    for ir in irs:
        ident = c_ident(ir['program'])
        idents.append((ir['program'], ident))
        order = ['camera'] + sorted(ir['layers'])
        idx = {k: i for i, k in enumerate(order)}
        tnames = sorted(ir.get('tables', {}))
        tidx = {k: i for i, k in enumerate(tnames)}

        def part(p):
            return f"{{{idx[p['from']]},{idx[p['to']]},{p['diff_bits']},{p['n']},{p['D']},{p['m']}}}"

        def expr(e):
            op = OPS[e['op']]
            if e['op'] == 'zero':
                return f'{{{op},0,0,0,0,0}}'
            if e['op'] == 'layer':
                return f"{{{op},{idx[e['layer']]},0,0,0,0}}"
            if e['op'] == 'cloud':
                return f"{{{op},{idx[e['layer']]},0,0,0,{e['speed']}}}"
            if e['op'] == 'ramp':
                return f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},{e['step_bits']},{e['D']}}}"
            if e['op'] == 'interp':
                seed = e['seed']
                return (f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},0,{e['D']},"
                        f"{e['n']},{e['m']},{1 if seed else 0},{part(seed) if seed else '{0,0,0,0,1,0}'}}}")
            # wave
            return (f"{{{op},{idx[e['layer']]},0,0,0,0,0,0,0,{{0,0,0,0,1,0}},"
                    f"{tidx[e['table']]},{e['scale']},{e['phase_speed']},{e['offset']},{e['mask']}}}")

        out.append(f'/* {ir["program"]} */')
        for t in tnames:
            vals = ir['tables'][t]['values']
            out.append(f'static const int16_t {ident}_t_{t}[{len(vals)}] = {{' + ','.join(map(str, vals)) + '};')
        if tnames:
            out.append(f'static const scroll_table {ident}_tables[] = {{' +
                       ','.join(f'{{{len(ir["tables"][t]["values"])},{ident}_t_{t}}}' for t in tnames) + '};')
        out.append(f'static const scroll_layer {ident}_layers[] = {{{{256,0}}' +
                   ''.join(f",{{{ir['layers'][k]['C']},{ir['layers'][k]['U']}}}" for k in order[1:]) + '};')
        out.append(f'static const scroll_run {ident}_runs[] = {{' +
                   ','.join(f"{{{r['entries'] * ROW},{expr(r['expr'])}}}" for r in ir['runs']) + '};')
        if ir['bands']:
            out.append(f'static const scroll_band {ident}_bands[] = {{' +
                       ','.join(f"{{{b['start']},{b['lines']},{expr(b['expr'])}}}" for b in ir['bands']) + '};')
        g = ir['bg_y']
        if g['op'] == 'rate':
            bgy = f"{{SCROLL_BGY_RATE,{g['C']},0,0,0}}"
        elif g['op'] == 'camera':
            f = g.get('fold') or {'player_x_min': 0, 'y_min': 0, 'div': 0}
            bgy = f"{{SCROLL_BGY_CAMERA,0,{f['player_x_min']},{f['y_min']},{f['div']}}}"
        else:
            bgy = f"{{SCROLL_BGY_CLAMP,0,0,0,0,{g['ref']},{g['base']},{g['shift']},{g['min']}}}"
        out.append(f"const scroll_ir {ident} = {{\"{ir['program']}\",{ir['buffer_lines']},"
                   f"{len(order)},{ident}_layers,{len(ir['runs'])},{ident}_runs,"
                   f"{len(ir['bands'])},{ident + '_bands' if ir['bands'] else '0'},{bgy},"
                   f"{len(tnames)},{ident + '_tables' if tnames else '0'}}};")
        out.append('')
    out.append(f'const scroll_ir *const scroll_ir_list[{len(idents)}] = {{' +
               ','.join('&' + i for _, i in idents) + '};')
    out.append(f'const char *const scroll_ir_list_names[{len(idents)}] = {{' +
               ','.join(json.dumps(p) for p, _ in idents) + '};')
    out.append(f'const unsigned scroll_ir_list_count = {len(idents)};')
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
    print(f'irx.py: {len(irs)} documents valid ({IR_VERSION})')
    if args.output:
        emit_c(irs, args.output)
        print(f'irx.py: wrote {args.output}')


if __name__ == '__main__':
    main()
