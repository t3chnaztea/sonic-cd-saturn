#!/usr/bin/env python3
"""Validate scroll IR JSON and compile it to C tables: tools/scroll/irc.py
plus the R7 vocabulary extensions.  NOT the shared validator.

    python3 tools/scroll/R7/irc_ext.py tools/scroll/R7/ir/*.json
    python3 tools/scroll/R7/irc_ext.py F.json ... -o tables.c

This file is a copy of tools/scroll/irc.py (which it must not replace: other
zone stages run the shared tools at the same time).  Every departure from the
shared file is marked `EXT` and is one of:

  EXT-OP-INTERP  expression op `interp` (ops.md section 1): the high word of
                 a 16.16 accumulator seeded from a linear form of 16-bit layer
                 words and stepped by a truncated quotient.
  EXT-OP-WAVE    expression op `wave` (ops.md section 2): a layer plus a
                 shifted word from a sine table, phase advanced per frame and
                 per line.  Bands only.
  EXT-BGY-SHIFTS background Y op `shifts` (ops.md section 3): the sum of
                 right shifts of the 16-bit camera Y.
  EXT-C          the C emitter writes the extra tables that evaluate_ext.c
                 reads; documents that use none of the extensions compile to
                 the same scroll_ir initialisers as the shared irc.py.

A document that uses no EXT op validates here exactly as it would in the
shared irc.py.  A document that uses one does NOT conform to ir.md until the
op is merged there; the shared irc.py rejects it with "unknown expression".
"""
import argparse
import json
import re
import sys
from math import gcd
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
sys.path.insert(0, str(SHARED))
from cfront import programs      # noqa: E402

IR_VERSION = 'scroll-ir/1'
ROW = 8
EXPR_KEYS = {
    'zero': set(),
    'layer': {'layer'},
    'cloud': {'layer', 'speed'},
    'ramp': {'from', 'to', 'D', 'diff_bits', 'step_bits'},
    # EXT-OP-INTERP
    'interp': {'lin', 'num', 'D', 'M'},
    # EXT-OP-WAVE
    'wave': {'layer', 'table', 'phase_speed', 'phase_step', 'shift'},
}
EXT_OPS = {'interp', 'wave'}
TOP_KEYS = {'ir', 'program', 'shape', 'slot', 'buffer_lines', 'layers', 'ramp_gate', 'runs',
            'table_end', 'beyond_table', 'bands', 'bg_y', 'corrections', 'rules'}
OPTIONAL_TOP = {'rules', 'corrections', 'shape', 'ramp_gate', 'notes'}
TABLES = {'sinset_sin'}          # EXT-OP-WAVE: sine tables a wave may name (ops.md 2)


class IRError(Exception):
    pass


def need(cond, where, msg):
    if not cond:
        raise IRError(f'{where}: {msg}')


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def expr_layers(e):
    """Every layer name an expression reads (camera included)."""
    out = {e[k] for k in ('layer', 'from', 'to') if k in e}
    if e.get('op') == 'interp':                       # EXT-OP-INTERP
        out.update(e['lin'])
        out.update(e['num'])
    return out


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
    if op == 'interp':                                # EXT-OP-INTERP
        for part in ('lin', 'num'):
            m = e[part]
            need(isinstance(m, dict), where, f'interp {part} must be an object {{layer: coefficient}}')
            for name, k in m.items():
                need(name in layers or name == 'camera', where, f'interp {part}: unknown layer {name!r}')
                need(is_int(k) and k != 0, where, f'interp {part}: coefficient of {name} must be a non-zero integer')
        need(len(e['lin']) <= 4 and len(e['num']) <= 4, where, 'interp names at most 4 layers per part')
        need(is_int(e['D']) and e['D'] > 0, where, 'interp D must be a positive integer')
        need(is_int(e['M']), where, 'interp M must be an integer')
        if e['num']:
            need(e['M'] != 0, where, 'interp with a quotient needs M != 0')
            need(sum(abs(k) for k in e['num'].values()) < 65536, where,
                 'interp num coefficients must sum below 65536 (the quotient numerator is 32-bit)')
            g = 0
            for k in e['num'].values():
                g = gcd(g, k)
            need(g % e['D'] != 0, where, 'interp quotient divides exactly: fold it into lin')
        else:
            need(e['D'] == 1 and e['M'] == 0, where, 'interp without a quotient has D 1 and M 0')
        need(not (e['lin'] and len(e['lin']) == 1 and list(e['lin'].values()) == [65536] and not e['num']),
             where, 'interp that is one layer must be written as op layer')
    if op == 'wave':                                  # EXT-OP-WAVE
        need(allow_ramp, where, 'a wave is only valid in a band (it needs a line counter)')
        need(e['layer'] != 'camera', where, 'a wave rides a layer, not the camera')
        need(e['table'] in TABLES, where, f'wave table must be one of {sorted(TABLES)}')
        need(is_int(e['phase_speed']) and 0 < e['phase_speed'] < 65536, where, 'wave phase_speed is 1..65535')
        need(is_int(e['phase_step']) and 0 <= e['phase_step'] < 256, where, 'wave phase_step is 0..255')
        need(is_int(e['shift']) and 0 <= e['shift'] < 16, where, 'wave shift is 0..15')


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
    need(isinstance(g, dict) and g.get('op') in ('rate', 'camera', 'shifts'), where, f'unknown bg_y {g!r}')
    if g['op'] == 'rate':
        need(set(g) == {'op', 'C'} and is_int(g['C']), where, 'bg_y rate is {op, C}')
    elif g['op'] == 'shifts':                         # EXT-BGY-SHIFTS
        s = g.get('shifts')
        need(set(g) == {'op', 'shifts'} and isinstance(s, list) and s and all(is_int(k) and 0 <= k < 16 for k in s)
             and s == sorted(s), where, 'bg_y shifts is {op, shifts: sorted non-empty list of 0..15}')
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
    return ir


def ext_ops_used(ir):
    """EXT: the extension ops a document uses (empty: it conforms to ir.md)."""
    out = set()
    for e in [r['expr'] for r in ir['runs']] + [b['expr'] for b in ir['bands']]:
        if e['op'] in EXT_OPS:
            out.add(e['op'])
    if ir['bg_y']['op'] == 'shifts':
        out.add('bg_y shifts')
    return sorted(out)


# ----------------------------------------------------------------- C

OPS = {'zero': 'SCROLL_ZERO', 'layer': 'SCROLL_LAYER', 'cloud': 'SCROLL_CLOUD', 'ramp': 'SCROLL_RAMP',
       'interp': 'SCROLL_INTERP', 'wave': 'SCROLL_WAVE'}          # EXT-C


def c_ident(program):
    return 'scroll_ir_' + re.sub(r'\W', '_', Path(program).stem.lower())


def emit_c(irs, out_path):
    out = ['/* Generated by tools/scroll/R7/irc_ext.py from scroll IR JSON.  Do not edit.',
           '   Format: tools/scroll/ir.md, tools/scroll/R7/ops.md, tools/scroll/R7/evaluate_ext.h. */',
           '#include "evaluate_ext.h"', '']
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
        interps, waves = [], []                        # EXT-C

        def expr(e):
            op = OPS[e['op']]
            if e['op'] == 'zero':
                return f'{{{op},0,0,0,0,0}}'
            if e['op'] == 'layer':
                return f"{{{op},{idx[e['layer']]},0,0,0,0}}"
            if e['op'] == 'cloud':
                return f"{{{op},{idx[e['layer']]},0,0,0,{e['speed']}}}"
            if e['op'] == 'interp':                   # EXT-C: k indexes the interp table
                lin = sorted(e['lin'].items())
                num = sorted(e['num'].items())
                interps.append('{%d,%d,{%s},{%s},{%s},{%s},%d,%d}' % (
                    len(lin), len(num),
                    ','.join(str(idx[n]) for n, _ in lin) or '0',
                    ','.join(str(k) for _, k in lin) or '0',
                    ','.join(str(idx[n]) for n, _ in num) or '0',
                    ','.join(str(k) for _, k in num) or '0',
                    e['D'], e['M']))
                return f'{{{op},0,0,0,0,{len(interps) - 1}}}'
            if e['op'] == 'wave':                     # EXT-C: k indexes the wave table
                waves.append('{%d,%d,%d,%d}' % (idx[e['layer']], e['phase_speed'], e['phase_step'], e['shift']))
                return f'{{{op},0,0,0,0,{len(waves) - 1}}}'
            return f"{{{op},{idx[e['from']]},{idx[e['to']]},{e['diff_bits']},{e['step_bits']},{e['D']}}}"

        out.append(f'/* {ir["program"]} */')
        out.append(f'static const scroll_layer {ident}_layers[] = {{{{256,0}}' +
                   ''.join(f",{{{ir['layers'][k]['C']},{ir['layers'][k]['U']}}}" for k in order[1:]) + '};')
        run_text = ','.join(f"{{{r['entries'] * ROW},{expr(r['expr'])}}}" for r in ir['runs'])
        band_text = ','.join(f"{{{b['start']},{b['lines']},{expr(b['expr'])}}}" for b in ir['bands'])
        out.append(f'static const scroll_run {ident}_runs[] = {{{run_text}}};')
        if ir['bands']:
            out.append(f'static const scroll_band {ident}_bands[] = {{{band_text}}};')
        if interps:
            out.append(f'static const scroll_interp {ident}_interp[] = {{{",".join(interps)}}};')
        if waves:
            out.append(f'static const scroll_wave {ident}_wave[] = {{{",".join(waves)}}};')
        g = ir['bg_y']
        if g['op'] == 'rate':
            bgy = f"{{SCROLL_BGY_RATE,{g['C']},0,0,0,0}}"
        elif g['op'] == 'shifts':                     # EXT-C: bit k set = add (u16)y >> k
            mask = sum(1 << k for k in g['shifts'])
            bgy = f"{{SCROLL_BGY_SHIFTS,0,0,0,0,{mask}}}"
        else:
            f = g.get('fold') or {'player_x_min': 0, 'y_min': 0, 'div': 0}
            bgy = f"{{SCROLL_BGY_CAMERA,0,{f['player_x_min']},{f['y_min']},{f['div']},0}}"
        out.append(f"const scroll_ir {ident} = {{\"{ir['program']}\",{ir['buffer_lines']},"
                   f"{len(order)},{ident}_layers,{len(ir['runs'])},{ident}_runs,"
                   f"{len(ir['bands'])},{ident + '_bands' if ir['bands'] else '0'},{bgy},"
                   f"{len(interps)},{ident + '_interp' if interps else '0'},"
                   f"{len(waves)},{ident + '_wave' if waves else '0'}}};")
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
            ir = validate(json.loads(Path(f).read_text()), f)
        except (IRError, json.JSONDecodeError, KeyError, TypeError) as e:
            raise SystemExit(f'irc_ext.py: FAIL {f}: {e}')
        irs.append(ir)
        ext = ext_ops_used(ir)
        print(f'irc_ext.py: {f}: valid; ' + (f'uses extension ops {ext} (does not conform to ir.md yet)'
                                             if ext else 'conforms to ir.md'))
    print(f'irc_ext.py: {len(irs)} documents valid')
    if args.output:
        emit_c(irs, args.output)
        print(f'irc_ext.py: wrote {args.output}')


if __name__ == '__main__':
    main()
