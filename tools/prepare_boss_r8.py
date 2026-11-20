#!/usr/bin/env python3
"""Generate the Metallic Madness Act 3 boss (R8/BOSS_8.C) with the code it calls.

build/probe-source/boss_8.c (Saturn/host) and build/player-reference/boss_8.c
(original PC casts) hold, unchanged except as listed below:
  - R8/BOSS_8.C: egg8 (actor 63), egg8hane (64), egg8meca (65), egg8hibana (66);
    egg8_dead spawns Amy (emie8, 67, EMIE8.C), which is not part of this port;
  - R8/COLI8.C: the round's touch response (pcol and the classes the boss colino
    values reach), named boss8_* so it links beside the other rounds' COLI;
  - R8/COL8C.C and COL8D.C colchg_boss8/fadein_boss8/fadein1_boss8/fadein2 and
    boss8_col1, one copy per future (COL8C.C in the Good Future, generate_flag set);
  - IO.C random, named boss8_random.
Changes: includes; pcole calls the native hurt frontend (as tools/prepare_boss.py);
egg8hibana_ini falls off its end after egg8hibana_1 and returns its result (the
PC's eax); egg8 initialises pMecawk (read only after make_meca sets it; the PC
leaves a stale register there); statement pre-increments and "*= -1" of PC
scratch words become assignments; function-local read-only tables get static
storage. The Saturn build turns the scratch-word updates BOSS_8.C makes inside
expressions (++x == 240, !(--x), (x += 8) >= 256) into SCD_ADD, the same
little-endian update and its new value. The reference build replaces pattern
table pointers (assignments, comparisons and hane_base_tbl) with tokens, as for BOSS_1.C.
"""
import re
from audit_source import UPSTREAM
from prepare_boss import NATIVE, REFERENCE, HEAD, ACCESSORS, TYPES, SIZES, functions, adapt, closing, zone_header, data_names
from generated_io import write_text

COLI = ['pcol', 'CollitblDataXchk', 'CollitblDataYchk', 'ColliHitChk', 'pcolitem', 'pcolnomal',
        'pcolplay2', 'pcolplay', 'pcolspecial', 'eggman_chk', 'main_attack']
COL = ['colchg_boss8', 'fadein_boss8', 'fadein1_boss8', 'fadein2']
RENAMED = COLI + ['pcole', 'escoretbl', 'colitbl', 'playdamagechk', 'playdamageset', 'random']
PRELUDE = '''#include "EQU.H"
#include "BOSS_8.H"
#include "COLI8.H"
#include "ACTION.H"
#include "ACTSET.H"
#include "DIRCOL.H"
#include "ETC.H"
#include "FCOL.H"
#include "GOAL.H"
#include "LOADER2.H"
#include "PLAYSUB.H"
#include "SCORE.H"
extern void colorset2(int ColorNo);
extern void soundset(short);
extern short playdieset(sprite_status *);
extern int actwkchk2(sprite_status *, sprite_status **);
extern void scd_objects_hurt(int source_x);
extern void scd_boss8_plc(int plc);
int random(void);
'''
# A PC scratch word updated inside an expression: the new value, stored little-endian.
NATIVE_ADD = '''#define SCD_ADD(type, p, offset, delta) \\
    ({ type scd_add_v = (type)(SCD_GET(type, (p), (offset)) + (delta)); SCD_SET(type, (p), (offset), scd_add_v); scd_add_v; })
'''
PCOLE = '''short pcole(sprite_status* pActwk, sprite_status* pColliAct) {
  if (((unsigned short*)pActwk)[26] != 0)
    return -1;
  /* playdamageset: the native hurt frontend drops rings, shield or a life. */
  scd_objects_hurt(pColliAct->xposi.w.h);
  return -1;
}
'''
# COL8C.C (Good Future) and COL8D.C differ in fadein_boss8 (COL8D.C also fades line 3).
FUTURES = '''void colchg_boss8(unsigned char *a3, unsigned char *a4) {
  if (generate_flag) col8c_colchg_boss8(a3, a4); else col8d_colchg_boss8(a3, a4);
}
void fadein_boss8(void) {
  if (generate_flag) col8c_fadein_boss8(); else col8d_fadein_boss8();
}
'''
CAST = r'\(\((?:unsigned short|short|int|unsigned char|char)\*\)[&\w\[\]]+\)\[\d+\]'


def once(text, old, new, what):
    if text.count(old) != 1:
        raise ValueError(f'{what} changed upstream')
    return text.replace(old, new)


def future(read, name, prefix):
    """COL8C/D.C boss8 palette routines and boss8_col1, renamed with prefix."""
    source = read(f'src/R8/{name}')
    col = functions(source)
    table = re.search(r'PALETTEENTRY boss8_col1\[\d+\] = \{.*?\};', source, re.S)[0]
    text = 'static const ' + table + '\n' + '\n'.join(col[n] for n in reversed(COL)) + '\n'
    for n in COL + ['boss8_col1']:
        # The read-only table joins the R8 overlay (.rodata.r8_*).
        text = re.sub(rf'\b{n}\b', ('r8_' if n == 'boss8_col1' else '') + prefix + n, text)
    text = re.sub(r'^(?:static )?void ', 'static void ', text, flags=re.M)
    return text.replace('static void ' + prefix + 'fadein2(PALETTEENTRY* lpPeDest, PALETTEENTRY* lpPeSrc)',
                        'static void ' + prefix + 'fadein2(PALETTEENTRY* lpPeDest, const PALETTEENTRY* lpPeSrc)', 1)


def colorsets(read):
    """COL8C/D.C colorset2 (via colorset00) with every palette array it reads,
    renamed col8c_/col8d_; boss8_colorset2 picks the future by generate_flag."""
    out = ''
    for era in ('C', 'D'):
        src = read(f'src/R8/COL8{era}.C')
        # boss8_col1 already comes with future()'s palette routines.
        arrays = [a for a in re.findall(r'PALETTEENTRY\s+\w+\[\d+\]\s*=\s*\{.*?\};', src, re.S)
                  if not re.match(r'PALETTEENTRY\s+boss8_col1\[', a)]
        table = re.search(r'palette_part colortbl\[12\] = \{.*?\};', src, re.S)[0]
        funcs = functions(src)
        block = '\n'.join(arrays + [table, funcs['colorset00'], funcs['colorset2']])
        names = re.findall(r'PALETTEENTRY\s+(\w+)\[', '\n'.join(arrays)) + ['colortbl', 'colorset00', 'colorset2']
        # Read-only tables go to the R8 overlay (src/saturn.x .rodata.r8_*): const,
        # r8_ prefix; the table's source pointers drop const as the PC never writes them.
        arrays_names = names[:-3]
        for name in names:
            block = re.sub(rf'\b{name}\b', (f'r8_col8{era.lower()}_' if name in arrays_names or name == 'colortbl' else f'col8{era.lower()}_') + name, block)
        for name in arrays_names:
            block = re.sub(rf'(\{{\s*)(r8_col8{era.lower()}_{name})(\s*,)', r'\1(PALETTEENTRY*)\2\3', block)
        block = re.sub(r'^(PALETTEENTRY|palette_part) ', r'static const \1 ', block, flags=re.M)
        block = re.sub(r'^void ', 'static void ', block, flags=re.M)
        out += block + '\n'
    return out + 'void boss8_colorset2(int n) {\n  if (generate_flag) col8c_colorset2(n); else col8d_colorset2(n);\n}\n'


def cast_parts(expr):
    """((type*)actor)[n] -> (stdint type, actor, PC offset)."""
    m = re.match(r'\(\((unsigned short|short|int|unsigned char|char)\*\)(.*)\)\[(\d+)\]$', expr)
    kind = TYPES[m[1]]
    return kind, m[2], int(m[3]) * SIZES[kind]


def native_updates(text):
    """Scratch-word updates inside expressions become SCD_ADD (Saturn build only)."""
    def pre(m):
        kind, actor, offset = cast_parts(m[2])
        return f'SCD_ADD({kind}, {actor}, {offset}, {"1" if m[1] == "++" else "-1"})'
    text, pres = re.subn(rf'(\+\+|--)({CAST})', pre, text)
    def compound(m):
        kind, actor, offset = cast_parts(m[1])
        return f'SCD_ADD({kind}, {actor}, {offset}, {"" if m[2] == "+" else "-"}({m[3]}))'
    text, compounds = re.subn(rf'\(({CAST}) (\+|-)= ([^()]+)\)', compound, text)
    return text, pres, compounds


def main():
    read = lambda path: (UPSTREAM / path).read_text(encoding='latin1')
    strip = lambda text: re.sub(r'#include "[^"]*"\n', '', text)
    # The decompiler's per-line address comments go, so the edits below match whole statements.
    boss = re.sub(r' */\* Line \d+, Address: 0x[0-9a-f]+ \*/', '', strip(read('src/R8/BOSS_8.C')))
    boss = once(boss, 'extern void colorset2(int ColorNo);\n', '', 'BOSS_8.C colorset2')
    coli_source = read('src/R8/COLI8.C')
    tables = coli_source[coli_source.index('unsigned short escoretbl'):coli_source.index('short pcol(')]
    coli = functions(coli_source)
    random = functions(read('src/IO.C'))['random']
    cols = ''.join(future(read, name, prefix) for name, prefix in (('COL8C.C', 'col8c_'), ('COL8D.C', 'col8d_')))
    body = (boss + '\n' + tables + 'static unsigned char bCarry;\n'
            + '\n'.join([PCOLE] + [coli[n] for n in COLI] + [random]) + '\n' + cols + FUTURES + colorsets(read))
    body = once(body, 'unsigned char colitbl[64][2] = {', 'const unsigned char colitbl[64][2] = {', 'COLI8.C colitbl')
    # Retail art loads the PC source leaves out: LoadPLC(4) after colorset2(9)
    # (R83C $20B524) and LoadPLC(5) in case 1 of egg8's hit count ($20B36A).
    body = once(body, 'colorset2(9);', 'colorset2(9); scd_boss8_plc(4);', 'BOSS_8.C colorset2(9)')
    # Retail egg8_open1 (R83D $20B95E) runs from its first case into case 1's
    # count (addqw #1 / cmpiw #240 at $20B9B4): the 240-update wait before the
    # drop starts on the update that loads the art (retail MM3D drop at 4997).
    body = once(body, 'colorset2(9); scd_boss8_plc(4);\n      break;',
                'colorset2(9); scd_boss8_plc(4);\n      ((short*)pActwk)[23] += 1;\n      break;', 'BOSS_8.C egg8_open1 fall-through')
    body, plc5 = re.subn(r'(case 1:\s*\n\s*if \(pPlayerwk->xposi\.w\.h >= pActwk->xposi\.w\.h\) \{)',
                         r'case 1: scd_boss8_plc(5);\n          if (pPlayerwk->xposi.w.h >= pActwk->xposi.w.h) {', body)
    if plc5 != 1:
        raise ValueError(f'BOSS_8.C egg8_colichk case 1 changed upstream ({plc5})')
    # egg8hibana_ini falls off its end after egg8hibana_1; the PC returns that call's eax.
    body, tails = re.subn(r'(egg8hibana_pat;\s*)egg8hibana_1\(pActwk\);', r'\1return egg8hibana_1(pActwk);', body)
    body, inits = re.subn(r'sprite_status \*pPlayerwk, \*pMecawk;(\s*short idx;)', r'sprite_status *pPlayerwk, *pMecawk = 0;\1', body)
    if (tails, inits) != (1, 1):
        raise ValueError(f'BOSS_8.C egg8hibana_ini tail / egg8 pMecawk changed upstream ({tails}, {inits})')
    # Statement updates of PC scratch words become assignments (same value, unused result).
    body, bumps = re.subn(rf'^(\s*)(\+\+|--)({CAST});', lambda m: f'{m[1]}{m[3]} {m[2][0]}= 1;', body, flags=re.M)
    body, negs = re.subn(rf'({CAST}) \*= -1;', r'\1 = -\1;', body)
    if (bumps, negs) != (1, 4):
        raise ValueError(f'BOSS_8.C statement scratch updates changed upstream ({bumps}, {negs})')
    # Read-only tables declared inside functions are copied to the stack on each call at -Os.
    body = once(body, '  egg8spd spd_tbl[5]', '  static const egg8spd spd_tbl[5]', 'BOSS_8.C spd_tbl')
    headers = {'BOSS_8.H': read('src/R8/BOSS_8.H'), 'COLI8.H': read('src/R8/COLI8.H')}
    others = set()
    for path in ('src/R1/BOSS_1.C', 'src/R3/BOSS_3.C', 'src/R4/BOSS_4.C', 'src/R4/BOSS_4_2.C', 'src/R5/BOSS_5.C',
                 'src/R6/BOSS_6.C', 'src/R7/BOSS_7.C'):
        others |= set(functions(read(path)))
    shared = sorted(set(functions(boss)) & others)
    # COLI8.C colitbl is read-only and read only in the overlay: r8_ places it there.
    prelude = ''.join(f'#define {n} {"r8_" if n == "colitbl" else ""}boss8_{n}\n' for n in RENAMED + shared) + PRELUDE
    native, pres, compounds = native_updates(body)
    if (pres, compounds) != (2, 5):
        raise ValueError(f'BOSS_8.C expression scratch updates changed upstream ({pres}, {compounds})')
    native = adapt(native)
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    # Pattern tables: assigned, compared, and listed in hane_base_tbl.
    hane = re.search(r'static sprite_pattern\*\* hane_base_tbl\[6\] = \{(.*?)\};', body, re.S)
    patterns = sorted(set(re.findall(r'->patbase (?:=|==|!=) (\w+)[;)]', body)) | set(re.findall(r'\w+', hane[1])))
    tokens = ''.join(f'#define SCD_PATTERN8_{name} {n + 1}u\n' for n, name in enumerate(patterns))
    reference = re.sub(r'->patbase (=|==|!=) (\w+)([;)])', r'->patbase \1 SCD_PATTERN8_\2\3', body)
    reference = reference.replace(hane[0], 'static unsigned int hane_base_tbl[6] = {'
                                  + ','.join(f' SCD_PATTERN8_{n}' for n in re.findall(r'\w+', hane[1])) + ' };')
    # EMIE8.C (Amy, actor 67): the MM3 ending, unchanged except includes. The
    # reference build replaces its pattern table pointers with tokens.
    ending = re.sub(r'#include "[^"]*"\n', '', read('src/R8/EMIE8.C'))
    epatterns = sorted(set(re.findall(r'->patbase = (\w+);', ending)))
    etokens = ''.join(f'#define SCD_PATTERN8E_{name} {n + 1}u\n' for n, name in enumerate(epatterns))
    ereference = re.sub(r'->patbase = (\w+);', r'->patbase = SCD_PATTERN8E_\1;', ending)
    eprelude = '#include "EQU.H"\n#include "EMIE8.H"\n#include "ACTION.H"\n#include "PLAYSUB.H"\n#include "ETC.H"\n#include "IMPFUNCS.H"\n'
    enative = adapt(ending)
    if HEAD.search(enative):
        raise ValueError('unadapted EMIE8.C PC cast')
    zone = zone_header('z8', 'boss8', set(RENAMED + shared), native + '\n' + enative)
    # Initialized file-scope data joins the R8 overlay too (src/saturn.x .data.r8_b8_*,
    # .rodata.r8_*): the overlay reloads with the zone, as the original program does.
    data = sorted({f'boss8_{n}' if n in RENAMED else n for n in data_names(native) + data_names(enative)} - {'colitbl'})
    data = [n for n in data if not n.startswith('r8_')]
    zone = zone.replace('#endif\n', ''.join(f'#define {n} r8_b8_{n}\n' for n in data) + '#endif\n')
    for target, body8 in ((NATIVE, ACCESSORS + enative), (REFERENCE, etokens + ereference)):
        write_text(target / 'EMIE8.H', read('src/R8/EMIE8.H'))
        write_text(target / 'ending_8.c', ('#include "BOSS8_ZONE.H"\n' if target == NATIVE else '') + eprelude + body8)
    for target in (NATIVE, REFERENCE):
        write_text(target / 'BOSS8_ZONE.H', zone)
        for name, text in headers.items():
            write_text(target / name, text)
    write_text(NATIVE / 'boss_8.c', '#include "BOSS8_ZONE.H"\n' + prelude + ACCESSORS + NATIVE_ADD + native)
    write_text(REFERENCE / 'BOSS8_PATTERNS.H', tokens)
    write_text(REFERENCE / 'boss_8.c', prelude + '#include "BOSS8_PATTERNS.H"\n' + reference)
    print(f'Boss 8 sources: BOSS_8.C, {len(COLI) + 1} COLI8.C and 2x{len(COL)} COL8C/D.C functions; '
          f'{len(HEAD.findall(body))} PC casts adapted, {pres + compounds} in expressions; renamed: {shared}')


if __name__ == '__main__':
    main()
