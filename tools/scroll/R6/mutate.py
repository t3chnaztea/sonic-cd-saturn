#!/usr/bin/env python3
"""Mutation test for tools/scroll/R6/extract.py.

    python3 tools/scroll/R6/mutate.py

Copies retail files into tools/scroll/R6/build/mut/src (never touching the
retail tree), changes one constant or statement per case, re-extracts, and
checks that the IR moved exactly as the change says (or that extraction
failed loudly, for the cases that must fail).  Exit 1 on any surprise.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from cfront import RETAIL      # noqa: E402
import extract as X            # noqa: E402

MUT = HERE / 'build' / 'mut' / 'src'


def fresh():
    if MUT.parent.exists():
        shutil.rmtree(MUT.parent)
    (MUT / 'R6').mkdir(parents=True)
    for f in list(RETAIL.glob('*.H')) + [RETAIL / 'ETC.C']:
        shutil.copy(f, MUT / f.name)
    for f in (RETAIL / 'R6').glob('*.H'):
        shutil.copy(f, MUT / 'R6' / f.name)


def extract(name, old=None, new=None, drop=None):
    fresh()
    text = (RETAIL / 'R6' / name).read_text(errors='replace')
    if old is not None:
        if text.count(old) != 1:
            raise SystemExit(f'mutate.py: {name}: {old!r} occurs {text.count(old)} times')
        text = text.replace(old, new)
    (MUT / 'R6' / name).write_text(text)
    if drop:
        (MUT / drop).unlink()
    return X.derive(MUT / 'R6' / name)


def runs(ir):
    return [(r['entries'], r['expr']) for r in ir['runs']]


def lerps(ir):
    return [(r['entries'], r['expr']['w']) for r in ir['runs'] if r['expr']['op'] == 'lerp']


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def m01_count_table():
    a = extract('SCR61A.C')
    b = extract('SCR61A.C', '5, 3, 3, 2, 2, 1, 1, 1, 1, 1', '5, 3, 3, 2, 2, 1, 1, 1, 2, 0')
    # the loop writes downward from row 29, so z81ascrtbl[i] sizes the group
    # that is 10 - i groups from the top: entry 8 (now 2) is the w=3 group,
    # entry 9 (now 0) the w=0 group, which is the layer and merges with it
    ra = [(n, e.get('w', e['op'])) for n, e in runs(a)][-5:]
    rb = [(n, e.get('w', e['op'])) for n, e in runs(b)][-5:]
    return ra == [(2, 12), (2, 3), (2, 'layer'), (20, 'layer'), (46, 'layer')] and \
        rb == [(2, 12), (3, 3), (1, 'layer'), (20, 'layer'), (46, 'layer')], (ra, rb)


@case
def m02_angle_step():
    b = extract('SCR61A.C', 'radwk += 6;', 'radwk += 7;')
    # w = 256 - cos(7k) = 256 - sintable[64 + 7k] for k = 9..1 (groups from the
    # top), the table parsed here from ETC.C's text independently of the extractor
    import re
    etc = (RETAIL / 'ETC.C').read_text(errors='replace')
    body = etc[etc.index('sintable[320]'):]
    table = [int(v) for v in re.findall(r'\d+', body[body.index('{') + 1:body.index('}')])]
    want = [256 - table[64 + 7 * k] for k in range(9, 0, -1)]
    return [w for _, w in lerps(b)] == want, (lerps(b), want)


@case
def m03_shift():
    b = extract('SCR61A.C', 'lHwk = (unsigned int)lHwk >> 8;', 'lHwk = (unsigned int)lHwk >> 7;')
    return {r['expr'].get('shift') for r in b['runs'] if r['expr']['op'] == 'lerp'} == {7}, None


@case
def m04_bg_y_shift():
    b = extract('SCR61A.C', 'lYwk = (unsigned short)scra_v_posit.w.h >> 2;',
                'lYwk = (unsigned short)scra_v_posit.w.h >> 3;')
    return b['bg_y'] == {'op': 'shift', 'shifts': [3]}, b['bg_y']


@case
def m05_layer_rate():
    b = extract('SCR61A.C', 'lXwk = scra_hz << 6;', 'lXwk = scra_hz << 5;')
    return b['layers']['scrz_h_posit']['C'] == 32, b['layers']


@case
def m06_step_divisor():
    b = extract('SCR61B.C', 'lXwk /= 17;', 'lXwk /= 15;')
    return {r['expr']['D'] for r in b['runs'] if r['expr']['op'] == 'step'} == {15}, None


@case
def m07_step_numerator():
    b = extract('SCR61B.C', 'lXwk <<= 7;', 'lXwk <<= 6;')
    return {r['expr']['num'] for r in b['runs'] if r['expr']['op'] == 'step'} == {64}, None


@case
def m08_frac_written_zero():
    b = extract('SCR61B.C', 'radwk.w.l = scrb_h_posit.w.h;', 'radwk.w.l = scrb_h_posit.w.h; radwk.w.h = 0;')
    return b['rules']['UNINIT'] == 0 and not b['corrections'] and \
        {r['expr']['frac'] for r in b['runs'] if r['expr']['op'] == 'step'} == {0}, b['corrections']


@case
def m09_frac_written_constant():
    b = extract('SCR61B.C', 'radwk.w.l = scrb_h_posit.w.h;', 'radwk.w.l = scrb_h_posit.w.h; radwk.w.h = 1234;')
    return b['rules']['UNINIT'] == 0 and \
        {r['expr']['frac'] for r in b['runs'] if r['expr']['op'] == 'step'} == {1234}, None


@case
def m10_product_not_narrowed():
    a = extract('SCR61C.C')
    b = extract('SCR61C.C', 'hwk = -(sXwk + (short)((unsigned short)((256 - coswk) * lXwk) >> 8));',
                'hwk = -(sXwk + (short)(((256 - coswk) * lXwk) >> 8));')
    pa = {r['expr']['prod_bits'] for r in a['runs'] if r['expr']['op'] == 'lerp'}
    pb = {r['expr']['prod_bits'] for r in b['runs'] if r['expr']['op'] == 'lerp'}
    return pa == {16} and pb == {32}, (pa, pb)


@case
def m11_frac_expression_fails():
    try:
        extract('SCR61B.C', 'radwk.w.l = scrb_h_posit.w.h;',
                'radwk.w.l = scrb_h_posit.w.h; radwk.w.h = -scra_h_posit.w.h;')
    except X.ExtractError as e:
        return 'not an unwritten local' in str(e), str(e)[:160]
    return False, 'extracted without failing'


@case
def m12_closure_needs_the_file():
    try:
        extract('SCR61A.C', drop='ETC.C')
    except X.ExtractError as e:
        return 'CLOSURE' in str(e) and 'ETC.C does not exist' in str(e), str(e)[:160]
    return False, 'extracted without ETC.C'


@case
def m13_sine_table_value():
    # change cos(54) in ETC.C's table from 62 to 70: w of the top rows follows
    fresh()
    etc = (MUT / 'ETC.C').read_text(errors='replace')
    # sintable[118] is the 7th value of the 15th row of 8: '97,  92,  86,  80,  74,  68,  62,  56,'
    old = '97,  92,  86,  80,  74,  68,  62,  56,'
    if etc.count(old) != 1:
        return False, f'ETC.C row occurs {etc.count(old)} times'
    (MUT / 'ETC.C').write_text(etc.replace(old, '97,  92,  86,  80,  74,  68,  70,  56,'))
    (MUT / 'R6' / 'SCR61A.C').write_text((RETAIL / 'R6' / 'SCR61A.C').read_text(errors='replace'))
    b = X.derive(MUT / 'R6' / 'SCR61A.C')
    return lerps(b)[0] == (6, 186), lerps(b)[0]


def main():
    bad = 0
    for fn in CASES:
        ok, info = fn()
        print(f"mutate {fn.__name__:28} {'ok' if ok else 'UNEXPECTED'}" + (f'  {info}' if info is not None and not ok else ''))
        bad += not ok
    shutil.rmtree(MUT.parent, ignore_errors=True)
    if bad:
        print(f'mutate.py: FAIL {bad} of {len(CASES)} cases', file=sys.stderr)
        return 1
    print(f'mutate.py: {len(CASES)} of {len(CASES)} cases moved the IR as the change says')
    return 0


if __name__ == '__main__':
    sys.exit(main())
