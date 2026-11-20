#!/usr/bin/env python3
"""Validate scroll-ir/1+r5 JSON and compile it to C tables for evaluate_r5.c.

    python3 tools/scroll/R5/irc_r5.py R5/ir/*.json               validate only
    python3 tools/scroll/R5/irc_r5.py R5/ir/*.json -o tables.c   validate and emit

scroll-ir/1+r5 is scroll-ir/1 (tools/scroll/ir.md) with three additions,
proposed for the merge stage (R5/extract.py docstring, R5-EXT):

  document  {ir, program, shape, slot, flag, variants[, notes]}
            flag      null, or {name, mask, writers[, constant][, update,
                      values, set_for_player_x]}
            variants  [{when, <every scroll-ir/1 body key>}]: `when` is the
                      value of (flag & mask) the variant is for, or null
                      when flag is null.  With a constant flag there is one
                      variant, when == constant.
  run op    {op: interp, from, to, mul, div, scale, k}
                d = s16(layer(to)) - s16(layer(from))
                q = u32(mul * d) / div          (unsigned 32-bit division)
                value = layer(from) + floor(scale * k * q / 65536)
            (agrees modulo 65536 with retail's hi(65536*from + k*S),
            S = s32(u32(scale * q)); runs only, k >= 1)
  bg_y op   {op: shift, src, terms, post}
                v = u16(camera_y)           src 16
                v = u16(camera_y) << 16     src 32 (16.16 camera Y, fraction 0)
                value = (sum over [s, m] of m * (v >> s)) >> post

A variant body is checked with every scroll-ir/1 invariant of ir.md
section 8 (keys, runs, table_end, bands, tail, layers declared and used).
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cfront import programs      # noqa: E402

IR_VERSION = 'scroll-ir/1+r5'
ROW = 8
EXPR_KEYS = {
    'zero': set(),
    'layer': {'layer'},
    'cloud': {'layer', 'speed'},
    'ramp': {'from', 'to', 'D', 'diff_bits', 'step_bits'},
    'interp': {'from', 'to', 'mul', 'div', 'scale', 'k'},
}
DOC_KEYS = {'ir', 'program', 'shape', 'slot', 'flag', 'variants'}
DOC_OPTIONAL = {'shape', 'notes'}
BODY_KEYS = {'when', 'buffer_lines', 'layers', 'ramp_gate', 'runs', 'table_end', 'beyond_table',
             'bands', 'bg_y', 'corrections', 'rules'}
BODY_OPTIONAL = {'rules', 'corrections', 'ramp_gate'}


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
    if op == 'interp':
        need(not allow_ramp, where, 'interp is a table row op (runs only)')
        need(e['from'] != 'camera', where, 'interp starts from a layer, not the camera')
        for k in ('mul', 'div', 'scale', 'k'):
            need(is_int(e[k]) and e[k] > 0, where, f'interp {k} must be a positive integer')
        need(e['mul'] < 1 << 16 and e['div'] < 1 << 16 and e['scale'] < 1 << 16 and e['k'] < 256,
             where, 'interp constants out of range (mul, div, scale < 65536, k < 256)')


def validate_bgy(g, where):
    need(isinstance(g, dict) and g.get('op') in ('rate', 'camera', 'shift'), where, f'unknown bg_y {g!r}')
    if g['op'] == 'rate':
        need(set(g) == {'op', 'C'} and is_int(g['C']), where, 'bg_y rate is {op, C}')
    elif g['op'] == 'camera':
        need(set(g) <= {'op', 'fold'}, where, 'bg_y camera is {op[, fold]}')
        if 'fold' in g:
            f = g['fold']
            need(set(f) == {'player_x_min', 'y_min', 'div'} and all(is_int(v) for v in f.values()) and f['div'] > 0,
                 where, 'fold is {player_x_min, y_min, div > 0}')
    else:
        need(set(g) == {'op', 'src', 'terms', 'post'}, where, 'bg_y shift is {op, src, terms, post}')
        need(g['src'] in (16, 32) and g['post'] in (0, 16), where, 'shift src is 16 or 32, post 0 or 16')
        need(isinstance(g['terms'], list) and 1 <= len(g['terms']) <= 4, where, 'shift has 1..4 terms')
        for t in g['terms']:
            need(isinstance(t, list) and len(t) == 2 and is_int(t[0]) and is_int(t[1]) and 0 <= t[0] < 32
                 and 0 < t[1] < 256, where, f'shift term {t!r} must be [shift 0..31, mul 1..255]')


def validate_body(ir, where):
    missing = (BODY_KEYS - BODY_OPTIONAL) - set(ir)
    need(not missing, where, f'missing keys {sorted(missing)}')
    extra = set(ir) - BODY_KEYS
    need(not extra, where, f'unknown keys {sorted(extra)}')
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
    validate_bgy(ir['bg_y'], where)
    used = set()
    for e in [r['expr'] for r in runs] + [b['expr'] for b in ir['bands']]:
        used.update(e[k] for k in ('layer', 'from', 'to') if k in e)
    need(used - {'camera'} == set(layers), where, f'layers {sorted(set(layers) - used)} are declared but unused')


def validate(ir, where=None):
    where = where or ir.get('program', '<ir>')
    need(isinstance(ir, dict), where, 'document is not an object')
    need(ir.get('ir') == IR_VERSION, where, f'"ir" must be {IR_VERSION!r}')
    missing = (DOC_KEYS - DOC_OPTIONAL) - set(ir)
    need(not missing, where, f'missing keys {sorted(missing)}')
    extra = set(ir) - DOC_KEYS - DOC_OPTIONAL
    need(not extra, where, f'unknown keys {sorted(extra)}')
    m = re.fullmatch(r'R(\d)/SCR(\d)([1-3])([A-D])\.C', ir['program'])
    need(m and m.group(1) == m.group(2), where, 'program must be R<n>/SCR<n><act><era>.C')
    need(ir['slot'] == {'round': int(m.group(1)), 'act': int(m.group(3)), 'era': m.group(4)}, where,
         'slot does not match the program name')
    flag, variants = ir['flag'], ir['variants']
    need(isinstance(variants, list) and variants, where, 'variants must be a non-empty list')
    if flag is None:
        need(len(variants) == 1 and variants[0].get('when') is None, where, 'no flag: exactly one variant, when null')
    else:
        need(isinstance(flag, dict) and {'name', 'mask', 'writers'} <= set(flag), where, 'flag is {name, mask, writers, ...}')
        need(is_int(flag['mask']) and 0 < flag['mask'] < 256, where, 'flag mask must be 1..255')
        need(isinstance(flag['writers'], list) and flag['writers'], where, 'flag writers must be listed')
        whens = [v.get('when') for v in variants]
        if 'constant' in flag:
            need(whens == [flag['constant'] & flag['mask']], where, 'a constant flag has one variant for its value')
        else:
            need(sorted(whens) == [0, flag['mask']], where, 'a flag has one variant per value of flag & mask')
            need(isinstance(flag.get('set_for_player_x'), list), where, 'a variable flag lists set_for_player_x')
    for v in variants:
        validate_body(v, f'{where} [when {v.get("when")}]')
    return ir


# ----------------------------------------------------------------- C

OPS = {'zero': 'SCROLL5_ZERO', 'layer': 'SCROLL5_LAYER', 'cloud': 'SCROLL5_CLOUD', 'ramp': 'SCROLL5_RAMP',
       'interp': 'SCROLL5_INTERP'}


def c_ident(program):
    return 'scroll_ir5_' + re.sub(r'\W', '_', Path(program).stem.lower())


def emit_c(irs, out_path):
    out = ['/* Generated by tools/scroll/R5/irc_r5.py from scroll-ir/1+r5 JSON.  Do not edit.',
           '   Format: tools/scroll/R5/irc_r5.py and tools/scroll/R5/evaluate_r5.h. */',
           '#include "evaluate_r5.h"', '']
    by_slot = {}
    for ir in irs:
        ident = c_ident(ir['program'])
        s = ir['slot']
        key = (s['round'], s['act'], s['era'])
        if key in by_slot:
            raise IRError(f'{ir["program"]}: two documents for one slot')
        by_slot[key] = ident
        vnames = []
        for vi, body in enumerate(ir['variants']):
            vid = f'{ident}_v{vi}'
            vnames.append((vid, body['when']))
            order = ['camera'] + sorted(body['layers'])
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
                return (f"{{{op},{idx[e['from']]},{idx[e['to']]},0,0,{e['div']},{e['mul']},"
                        f"{e['scale'] * e['k']}}}")

            out.append(f'/* {ir["program"]} variant when={body["when"]} */')
            out.append(f'static const scroll5_layer {vid}_layers[] = {{{{256,0}}' +
                       ''.join(f",{{{body['layers'][k]['C']},{body['layers'][k]['U']}}}" for k in order[1:]) + '};')
            out.append(f'static const scroll5_run {vid}_runs[] = {{' +
                       ','.join(f"{{{r['entries'] * ROW},{expr(r['expr'])}}}" for r in body['runs']) + '};')
            if body['bands']:
                out.append(f'static const scroll5_band {vid}_bands[] = {{' +
                           ','.join(f"{{{b['start']},{b['lines']},{expr(b['expr'])}}}" for b in body['bands']) + '};')
            g = body['bg_y']
            if g['op'] == 'rate':
                bgy = f"{{SCROLL5_BGY_RATE,{g['C']},0,0,0,0,0,{{{{0,0}},{{0,0}},{{0,0}},{{0,0}}}}}}"
            elif g['op'] == 'camera':
                f = g.get('fold') or {'player_x_min': 0, 'y_min': 0, 'div': 0}
                bgy = (f"{{SCROLL5_BGY_CAMERA,0,{f['player_x_min']},{f['y_min']},{f['div']},0,0,"
                       f"{{{{0,0}},{{0,0}},{{0,0}},{{0,0}}}}}}")
            else:
                terms = g['terms'] + [[0, 0]] * (4 - len(g['terms']))
                bgy = (f"{{SCROLL5_BGY_SHIFT,0,0,0,0,{g['src']},{g['post']},{{" +
                       ','.join(f'{{{s},{m}}}' for s, m in terms) + '}}')
            out.append(f"static const scroll5_body {vid} = {{{body['buffer_lines']},"
                       f"{len(order)},{vid}_layers,{len(body['runs'])},{vid}_runs,"
                       f"{len(body['bands'])},{vid + '_bands' if body['bands'] else '0'},{bgy}}};")
        flag = ir['flag']
        mask = flag['mask'] if flag else 0
        out.append(f'static const scroll5_variant {ident}_variants[] = {{' +
                   ','.join(f"{{{-1 if w is None else w},&{vid}}}" for vid, w in vnames) + '};')
        out.append(f"const scroll_ir5 {ident} = {{\"{ir['program']}\",{mask},{len(vnames)},{ident}_variants}};")
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
    out.append(f'const scroll_ir5 *const scroll_ir5_slots[{len(slots)}] = {{' + ','.join(slots) + '};')
    out.append(f'const char *const scroll_ir5_slot_source[{len(slots)}] = {{' +
               ','.join(json.dumps(s) for s in source) + '};')
    out.append(f'const unsigned scroll_ir5_slot_count = {len(slots)};')
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
            raise SystemExit(f'irc_r5.py: FAIL {f}: {e}')
    print(f'irc_r5.py: {len(irs)} documents valid')
    if args.output:
        emit_c(irs, args.output)
        print(f'irc_r5.py: wrote {args.output}')


if __name__ == '__main__':
    main()
