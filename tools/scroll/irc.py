#!/usr/bin/env python3
"""Validate scroll IR JSON (tools/scroll/ir.md) and compile it to C tables.

    python3 tools/scroll/irc.py ir/R1/*.json               validate only
    python3 tools/scroll/irc.py ir/R1/*.json -o tables.c   validate and emit

The emitted file defines one `scroll_ir` per document plus

    const scroll_ir *const scroll_ir_slots[84];      by background id
    const char *const scroll_ir_slot_source[84];     program, or why absent
    const unsigned scroll_ir_slot_count;

where background id = zone*12 + (act-1)*4 + era (A..D = 0..3) and zone is
the rank of the round directory (R1, R3, R4, ... sort to 0, 1, 2, ...), which
is how src/main.c:bg_id() numbers them.  A validation failure names the file
and the rule it breaks and nothing is written.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cfront import programs      # noqa: E402

IR_VERSION = 'scroll-ir/1'
ROW = 8
EXPR_KEYS = {
    'zero': set(),
    'layer': {'layer'},
    'cloud': {'layer', 'speed'},
    'ramp': {'from', 'to', 'D', 'diff_bits', 'step_bits'},
}
TOP_KEYS = {'ir', 'program', 'shape', 'slot', 'buffer_lines', 'layers', 'ramp_gate', 'runs',
            'table_end', 'beyond_table', 'bands', 'bg_y', 'corrections', 'rules'}
OPTIONAL_TOP = {'rules', 'corrections', 'shape', 'ramp_gate', 'notes'}


class IRError(Exception):
    pass


def need(cond, where, msg):
    if not cond:
        raise IRError(f'{where}: {msg}')


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_expr(e, layers, where, allow_ramp):
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
        need(allow_ramp, where, 'a ramp is only valid in a band (it needs a line counter)')
        need(is_int(e['D']) and e['D'] > 0, where, 'ramp D must be a positive integer')
        need(e['diff_bits'] in (16, 32) and e['step_bits'] in (16, 32), where, 'ramp widths are 16 or 32')


def validate(ir, where=None):
    where = where or ir.get('program', '<ir>')
    need(isinstance(ir, dict), where, 'document is not an object')
    need(ir.get('ir') == IR_VERSION, where, f'"ir" must be {IR_VERSION!r}')
    missing = (TOP_KEYS - OPTIONAL_TOP) - set(ir)
    need(not missing, where, f'missing keys {sorted(missing)}')
    extra = set(ir) - TOP_KEYS - OPTIONAL_TOP
    need(not extra, where, f'unknown keys {sorted(extra)}')
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
        need(set(L) == {'C', 'U'} and is_int(L['C']) and is_int(L['U']), where, f'layer {name} must be {{C, U}}')
    if any(L['U'] for L in layers.values()):
        need(isinstance(ir.get('ramp_gate'), str), where, 'a layer with U != 0 needs ramp_gate')
    runs = ir['runs']
    need(isinstance(runs, list), where, 'runs must be a list')
    for i, r in enumerate(runs):
        need(set(r) == {'entries', 'expr'} and is_int(r['entries']) and r['entries'] > 0, where,
             f'run {i} must be {{entries > 0, expr}}')
        validate_expr(r['expr'], layers, f'{where} run {i}', False)
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
        validate_expr(b['expr'], layers, f'{where} band {i}', True)
        if b.get('tail'):
            need(b['start'] == end and b['start'] + b['lines'] == B, where, 'a tail band runs from table_end to the buffer end')
    g = ir['bg_y']
    need(isinstance(g, dict) and g.get('op') in ('rate', 'camera'), where, f'unknown bg_y {g!r}')
    if g['op'] == 'rate':
        need(set(g) == {'op', 'C'} and is_int(g['C']), where, 'bg_y rate is {op, C}')
    else:
        need(set(g) <= {'op', 'fold'}, where, 'bg_y camera is {op[, fold]}')
        if 'fold' in g:
            f = g['fold']
            need(set(f) == {'player_x_min', 'y_min', 'div'} and all(is_int(v) for v in f.values()) and f['div'] > 0,
                 where, 'fold is {player_x_min, y_min, div > 0}')
    used = set()
    for e in [r['expr'] for r in runs] + [b['expr'] for b in ir['bands']]:
        used.update(e[k] for k in ('layer', 'from', 'to') if k in e)
    need(used - {'camera'} == set(layers), where, f'layers {sorted(set(layers) - used)} are declared but unused')
    return ir


# ----------------------------------------------------------------- C

OPS = {'zero': 'SCROLL_ZERO', 'layer': 'SCROLL_LAYER', 'cloud': 'SCROLL_CLOUD', 'ramp': 'SCROLL_RAMP'}


def c_ident(program):
    return 'scroll_ir_' + re.sub(r'\W', '_', Path(program).stem.lower())


def emit_c(irs, out_path):
    out = ['/* Generated by tools/scroll/irc.py from scroll IR JSON.  Do not edit.',
           '   Format: tools/scroll/ir.md and tools/scroll/evaluate.h. */',
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

        def expr(e):
            op = OPS[e['op']]
            if e['op'] == 'zero':
                return f'{{{op},0,0,0,0,0}}'
            if e['op'] == 'layer':
                return f"{{{op},{idx[e['layer']]},0,0,0,0}}"
            if e['op'] == 'cloud':
                return f"{{{op},{idx[e['layer']]},0,0,0,{e['speed']}}}"
            return f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},{e['step_bits']},{e['D']}}}"

        out.append(f'/* {ir["program"]} */')
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
        else:
            f = g.get('fold') or {'player_x_min': 0, 'y_min': 0, 'div': 0}
            bgy = f"{{SCROLL_BGY_CAMERA,0,{f['player_x_min']},{f['y_min']},{f['div']}}}"
        out.append(f"const scroll_ir {ident} = {{\"{ir['program']}\",{ir['buffer_lines']},"
                   f"{len(order)},{ident}_layers,{len(ir['runs'])},{ident}_runs,"
                   f"{len(ir['bands'])},{ident + '_bands' if ir['bands'] else '0'},{bgy}}};")
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
            raise SystemExit(f'irc.py: FAIL {f}: {e}')
    print(f'irc.py: {len(irs)} documents valid')
    if args.output:
        emit_c(irs, args.output)
        print(f'irc.py: wrote {args.output}')


if __name__ == '__main__':
    main()
