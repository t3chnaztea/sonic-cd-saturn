#!/usr/bin/env python3
"""Generate the Wacky Workbench Act 3 boss (R6/BOSS_6.C) with the code it calls.

build/probe-source/boss_6.c (Saturn/host) and build/player-reference/boss_6.c
(original PC casts) hold, unchanged except as listed below:
  - R6/BOSS_6.C: egg6boss (actor 52), egg6meca0 (53), egg6meca1 (54),
    egg6meca2 (55), egg6toge (56), egg6gareki (57), egg6yuka (61), egg6door (62),
    egg6bakuha (63), egg6beam (64);
  - R6/COLI6.C: the round's touch response (pcol and the classes the boss
    colino values reach), named boss6_* so it links beside COLI1/3/4/5.C;
  - RIDECHK.C ride_on_chk and its helpers (egg6meca0, egg6yuka, egg6door), named boss6_*;
  - R6/COL6C.C and COL6D.C fin_boss6/fout_boss6/fset_boss6 and their boss6_col4
    tables, one copy per future (COL6C.C in the Good Future, generate_flag set);
  - IO.C random, named boss6_random.
Changes: includes; pcole calls the native hurt frontend (as tools/prepare_boss.py);
pcolplay2 returns pcolplay's result (the PC's eax);
pre-increments of PC scratch words become compound assignments (same value,
unused result); function-local read-only tables get static storage; BOSS_6.C's
helpers other than the egg6 actor routines get boss6_ (they are global and
generic); scd_boss6_statics resets BOSS_6.C's file statics, which the PC reloads
with the round. The reference build replaces pattern table pointers with tokens,
as for BOSS_1.C.
"""
import re
from audit_source import UPSTREAM
from generated_io import write_text
from prepare_boss import zone_header, NATIVE, REFERENCE, HEAD, ACCESSORS, functions, adapt

COLI = ['pcol', 'CollitblDataXchk', 'CollitblDataYchk', 'ColliHitChk', 'pcolitem', 'pcolnomal',
        'pcolplay2', 'pcolplay', 'pcolspecial', 'eggman_chk', 'boss_1', 'boss_4', 'boss_5', 'main_attack']
RIDE = ['ride_on_clr', 'ride_on_set', 'hitchk_u', 'ridechk', 'ride_on_chk', 'hitchk', 'hit_v', 'hit_x',
        'push_set', 'push_clr', 'hit_y', 'hit_yu', 'hit_yu1', 'hit_yu0', 'hit_e', 'side_coli', 'hit_set', 'hit_clr']
COL = ['fin_boss6', 'fout_boss6', 'fset_boss6']
RENAMED = COLI + RIDE + ['pcole', 'escoretbl', 'colitbl', 'playdamagechk', 'playdamageset', 'random']
PRELUDE = '''#include <stdint.h>
#include "EQU.H"
#include "BOSS_6.H"
#include "COLI6.H"
#include "RIDECHK.H"
#include "ACTION.H"
#include "ACTSET.H"
#include "DIRCOL.H"
#include "ETC.H"
#include "FCOL.H"
#include "GOAL.H"
#include "LOADER2.H"
#include "PLAYSUB.H"
#include "SCORE.H"
extern void colorset(int ColorNo);
extern void colorset2(int ColorNo);
extern void flashout(void);
extern void flashin_boss6(void);
extern void soundset(short);
extern short playdieset(sprite_status *);
extern short emycol_d(sprite_status *);
extern void scd_objects_hurt(int source_x);
void fin_boss6(unsigned char *pChgTime, unsigned char *pChgCnt);
void fout_boss6(unsigned char *pChgTime, unsigned char *pChgCnt);
int random(void);
'''
PCOLE = '''short pcole(sprite_status* pActwk, sprite_status* pColliAct) {
  if (((unsigned short*)pActwk)[26] != 0)
    return -1;
  /* playdamageset: the native hurt frontend drops rings, shield or a life. */
  scd_objects_hurt(pColliAct->xposi.w.h);
  return -1;
}
'''
# COL6C.C (Good Future) and COL6D.C differ in boss6_col4 and in the colours fset_boss6 writes.
FUTURES = '''void fin_boss6(unsigned char *pChgTime, unsigned char *pChgCnt) {
  if (generate_flag) col6c_fin_boss6(pChgTime, pChgCnt); else col6d_fin_boss6(pChgTime, pChgCnt);
}
void fout_boss6(unsigned char *pChgTime, unsigned char *pChgCnt) {
  if (generate_flag) col6c_fout_boss6(pChgTime, pChgCnt); else col6d_fout_boss6(pChgTime, pChgCnt);
}
/* BOSS_6.C file statics, as a fresh load of the round's program leaves them. */
void scd_boss6_statics(void) { stbPatOff = 0; stbStx = 0; stbRad = -2; }
'''


def once(text, old, new, what):
    if text.count(old) != 1:
        raise ValueError(f'{what} changed upstream')
    return text.replace(old, new)


def future(read, name, prefix):
    """COL6C/D.C fin/fout/fset_boss6 and boss6_col4, renamed with prefix."""
    source = read(f'src/R6/{name}')
    col = functions(source)
    table = re.search(r'PALETTEENTRY boss6_col4\[\d+\] = \{.*?\};', source, re.S)[0]
    text = 'static const ' + table + '\n' + '\n'.join(col[n] for n in COL) + '\n'
    for n in COL + ['boss6_col4']:
        text = re.sub(rf'\b{n}\b', prefix + n, text)
    return re.sub(r'^void ', 'static void ', text, flags=re.M)


def main():
    read = lambda path: (UPSTREAM / path).read_text(encoding='latin1')
    strip = lambda text: re.sub(r'#include "[^"]*"\n', '', text)
    boss = strip(read('src/R6/BOSS_6.C'))
    # Retail R63C slot 32 at frames 5897-6409 alternates X 2752/2754 while
    # actfree[18] advances once per update. The Sega CD hover step alternates
    # +/-2 each update; the PC source's +/-1 every four updates differs.
    boss = once(boss, 'static char stbRad = 1;',
                'static char stbRad = -2;', 'BOSS_6.C retail hover step')
    boss = once(boss,
                '    if ((bRad % 4) == 0) /* Line 615, Address: 0x1028694 */\n      stbRad = -stbRad; /* Line 616, Address: 0x10286bc */',
                '    stbRad = -stbRad; /* Sega CD retail toggles each update. */',
                'BOSS_6.C retail hover phase')
    # Retail R63D egg6gareki has oYRadius 8 (slot 43, frame 2136). Its
    # decompiled PC source says 4 and delays the first floor collision.
    boss = once(boss, '  pActwk->sprvsize = 4; /* Line 1712, Address: 0x102a1a8 */',
                '  pActwk->sprvsize = 8; /* retail oYRadius */', 'BOSS_6.C egg6gareki radius')
    coli_source = read('src/R6/COLI6.C')
    tables = coli_source[coli_source.index('unsigned short escoretbl'):coli_source.index('short pcol(')]
    coli = functions(coli_source)
    # pcolplay2 falls off its end after pcolplay; the PC returns that call's eax.
    coli['pcolplay2'] = once(coli['pcolplay2'], '  pcolplay(pActwk, pColliAct);', '  return pcolplay(pActwk, pColliAct);', 'COLI6.C pcolplay2')
    # Player_TouchEnemy in WW's disassembly negates velocity, then uses asr.w.
    # C division rounds a negative odd bounce toward zero (C seq 4820: -101
    # versus retail -102), while the 68k shift rounds it down.
    for axis in ('x', 'y'):
        coli['pcolnomal'] = once(coli['pcolnomal'], f'    pActwk->{axis}speed.w /= 2;',
                                 f'    pActwk->{axis}speed.w >>= 1;', f'COLI6.C pcolnomal {axis}speed halving')
    ride = functions(read('src/RIDECHK.C'))
    random = functions(read('src/IO.C'))['random']
    # Level/Functions (General).asm Random uses plain 32-bit asl.l and
    # move.w d1,d0. Decompiled IO.C preserves a negative sign bit and adds
    # the first low word, both of which change the debris sequence.
    if random.count('  lD0.w.l += lD1.w.l;') != 2 or random.count('lD1.l |= 0x80000000;') != 2:
        raise ValueError('IO.C Random changed upstream')
    random = '''int random(void) {
  uint32_t d1 = ranum ? (uint32_t)ranum : 0x2A6D365Au, d0 = d1;
  d1 = (d1 << 2) + d0;
  d1 = (d1 << 3) + d0;
  d0 = (d0 & 0xFFFF0000u) | (d1 & 0xFFFFu);
  d1 = (d1 << 16) | (d1 >> 16);
  d0 = (d0 & 0xFFFF0000u) | ((d0 + d1) & 0xFFFFu);
  d1 = (d1 & 0xFFFF0000u) | (d0 & 0xFFFFu);
  ranum = (int)((d1 << 16) | (d1 >> 16));
  return (int)d0;
}'''
    cols = []
    for name, prefix in (('COL6C.C', 'col6c_'), ('COL6D.C', 'col6d_')):
        text = future(read, name, prefix)
        # fset_boss6 is called before its definition in each copy.
        cols.append(f'static void {prefix}fset_boss6(char d0, unsigned char* pChgCnt);\n' + text)
    body = (boss + '\n' + tables + 'static unsigned char bCarry;\n'
            + '\n'.join([PCOLE] + [coli[n] for n in COLI] + [ride[n] for n in RIDE] + [random]) + '\n'
            + ''.join(cols) + FUTURES)
    # Pre-increments of PC scratch words become compound assignments (same value, unused result).
    body, bumps = re.subn(r'\+\+(\(\((?:short|char)\*\)\w+\)\[\d+\]);', r'\1 += 1;', body)
    if bumps != 10:
        raise ValueError(f'BOSS_6.C scratch pre-increments changed upstream ({bumps})')
    # Read-only tables declared inside functions are copied to the stack on each call at -Os.
    for declaration in ('unsigned short down_pos[3]', 'short up_pos[3]', 'char egg6meca1_pchg[5]', 'short para[16]',
                        'short beam_ytbl[3]', 'short xposi_tbl[2]'):
        body = once(body, '  ' + declaration, '  static const ' + declaration, f'BOSS_6.C {declaration}')
    headers = {'BOSS_6.H': read('src/R6/BOSS_6.H'), 'COLI6.H': read('src/R6/COLI6.H'), 'RIDECHK.H': read('src/RIDECHK.H')}
    # BOSS_6.C's helpers are global with generic names: all but the egg6 routines get boss6_.
    helpers = sorted(n for n in functions(boss) if not n.startswith('egg6'))
    prelude = ''.join(f'#define {n} boss6_{n}\n' for n in RENAMED + helpers) + '#include "BOSS6_ZONE.H"\n' + PRELUDE
    native = adapt(body)
    zone = zone_header('z6', 'boss6', set(RENAMED + helpers), native, RIDE + ['scd_boss6_statics'], PRELUDE + ACCESSORS + native)
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    # egg6beam_01 cycles patbase through e6beam_tbl: its entries are pattern tokens too.
    patterns = sorted(set(re.findall(r'->patbase = (\w+);', body)) | {'egg6beam2_pat', 'egg6beam3_pat'})
    tokens = ''.join(f'#define SCD_PATTERN6_{name} {n + 1}u\n' for n, name in enumerate(patterns))
    reference = re.sub(r'->patbase = (\w+);', r'->patbase = SCD_PATTERN6_\1;', body)
    reference = once(reference, 'static sprite_pattern** e6beam_tbl[3] = { egg6beam_pat, egg6beam2_pat, egg6beam3_pat };',
                     'static unsigned int e6beam_tbl[3] = { SCD_PATTERN6_egg6beam_pat, SCD_PATTERN6_egg6beam2_pat, SCD_PATTERN6_egg6beam3_pat };',
                     'BOSS_6.C e6beam_tbl')
    for target in (NATIVE, REFERENCE):
        for name, text in headers.items():
            write_text(target / name,text)
        write_text(target / 'BOSS6_ZONE.H',zone)
    write_text(NATIVE / 'boss_6.c',prelude + ACCESSORS + native)
    write_text(REFERENCE / 'BOSS6_PATTERNS.H',tokens)
    write_text(REFERENCE / 'boss_6.c',prelude + '#include "BOSS6_PATTERNS.H"\n' + reference)
    print(f'Boss 6 sources: BOSS_6.C, {len(COLI) + 1} COLI6.C, {len(RIDE)} RIDECHK.C and 2x{len(COL)} COL6C/D.C functions; '
          f'{len(HEAD.findall(body))} PC casts adapted; {len(helpers)} helpers renamed boss6_')


if __name__ == '__main__':
    main()
