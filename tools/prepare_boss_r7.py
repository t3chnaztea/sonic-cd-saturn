#!/usr/bin/env python3
"""Generate the Stardust Speedway Act 3 boss (R7/BOSS_7.C, the Metal Sonic race).

build/probe-source/boss_7.c (Saturn/host) and build/player-reference/boss_7.c
(original PC casts) hold, unchanged except as listed below and the documented retail corrections:
  - R7/BOSS_7.C: egg7 (actor 44, with the forced scroll egg7_hscr), egg7jet (45),
    egg7beam (46), msnc (47, Metal Sonic), msnc_ele (48), msnc_bara (49),
    hahen73 (55) and hari_spdadd (HARI73.C's mover);
  - R7/COLI7.C: the round's touch response (pcol and the classes the race's
    colino values reach), named boss7_* so it links beside COLI1/3/4/5/6.C;
  - SCR73C/D.C divdevset (empty in both futures) and IO.C random, named boss7_*.
Retail corrections (explicitly shared by the cast-reference fixture): beam_next
clears vertical speed; msnc_low_move preserves the floor helper's A2-clobber
return condition; Random uses the 68k shift/move sequence. These corrections
need retail instruction/trace evidence, not just adapted-vs-reference parity.
Changes: includes; pcole calls the native hurt frontend (as tools/prepare_boss.py);
pre-increments/decrements of PC scratch words become compound assignments (same
value, unused result); function-local read-only tables get static storage;
BOSS_7.C's globals (pPlayerwk, pEggman, pMsnc, GL_d5, QuickReturn) get boss7_,
and scd_boss7_statics resets them as a fresh load of the round's program leaves
them. The reference build replaces pattern table pointers with tokens, as for BOSS_1.C.
"""
import re
from audit_source import UPSTREAM
from prepare_boss import NATIVE, REFERENCE, HEAD, ACCESSORS, functions, adapt, zone_header
from generated_io import write_text

COLI = ['pcol', 'CollitblDataXchk', 'CollitblDataYchk', 'ColliHitChk', 'pcolitem', 'pcolnomal',
        'pcolplay2', 'pcolplay', 'pcolspecial', 'eggman_chk', 'main_attack']
GLOBALS = ['pPlayerwk', 'pEggman', 'pMsnc', 'GL_d5', 'QuickReturn']
RENAMED = COLI + GLOBALS + ['pcole', 'escoretbl', 'colitbl', 'playdamagechk', 'playdamageset', 'random', 'divdevset']
PRELUDE = '''#include <stdint.h>
#include "EQU.H"
#include "BOSS_7.H"
#include "COLI7.H"
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
extern short emycol_d(sprite_status *);
extern int actwkchk2(sprite_status *, sprite_status **);
extern void scd_objects_hurt(int source_x);
int random(void);
/* SCR73C.C/SCR73D.C divdevset: empty in both futures. */
static void divdevset(void) {}
'''
PCOLE = '''short pcole(sprite_status* pActwk, sprite_status* pColliAct) {
  if (((unsigned short*)pActwk)[26] != 0)
    return -1;
  /* playdamageset: the native hurt frontend drops rings, shield or a life. */
  scd_objects_hurt(pColliAct->xposi.w.h);
  return -1;
}
'''
STATICS = '''/* BOSS_7.C globals, as a fresh load of the round's program leaves them. */
void scd_boss7_statics(void) { pPlayerwk = pEggman = pMsnc = 0; GL_d5 = 0; QuickReturn = 0; retail_floor_retry = -1; }
'''


def once(text, old, new, what):
    if text.count(old) != 1:
        raise ValueError(f'{what} changed upstream')
    return text.replace(old, new)


def main():
    read = lambda path: (UPSTREAM / path).read_text(encoding='latin1')
    strip = lambda text: re.sub(r'#include "[^"]*"\n', '', text)
    boss = strip(read('src/R7/BOSS_7.C'))
    # BOSS_7.C declares scr_dir_tbl unsigned (SCR73C/D.C define it so); src/boss.c defines the table.
    boss = once(boss, 'extern unsigned short scr_dir_tbl[];', 'extern short scr_dir_tbl[];', 'BOSS_7.C scr_dir_tbl')
    # R73C retail $20C656 beam_next sets X speed512 then clears Y speed
    # ($20C676 clr.w18(a0)); the PC source accidentally clears X twice.
    boss = once(boss, '  pActwk->xspeed.w = 0; /* Line 1694, Address: 0x102b368 */',
                '  pActwk->yspeed.w = 0; /* Retail beam_next clears vertical speed. */',
                'BOSS_7.C beam_next vertical speed')
    # Retail msnc_low_move calls the floor helper before tst.b57(a2).
    # hight_set_retry ($20CA0C in R73C) leaves A2 at its table cursor;
    # the PC reconstruction keeps pEggman instead. Both Futures read zero
    # after entries0..3, nonzero after entries4..13 or the terminating word.
    # Preserve that original early-return behavior without reading code bytes.
    boss = 'static int retail_floor_retry = -1;\n' + boss
    boss = once(boss, '  msnc_hight(pActwk); /* Line 996, Address: 0x1029a9c */',
                '  retail_floor_retry = -1;\n  msnc_hight(pActwk); /* Line 996, Address: 0x1029a9c */',
                'BOSS_7.C msnc_low_move floor phase')
    boss = once(boss, '  if (pEggman->actfree[15]) return; /* Line 997, Address: 0x1029aa8 */',
                '  if (retail_floor_retry < 0 ? pEggman->actfree[15] != 0 : retail_floor_retry) return;',
                'BOSS_7.C retail A2 scratch clobber')
    boss = once(boss, '    if (d2 < 0) return -1; /* Line 2133, Address: 0x102c1b0 */',
                '    if (d2 < 0) { retail_floor_retry = 1; return -1; }',
                'BOSS_7.C floor retry miss cursor')
    boss = once(boss, '  pActwk->xposi.w.h += d3; /* Line 2149, Address: 0x102c268 */',
                '  retail_floor_retry = (a2 - egg_move_tbl) > 12;\n  pActwk->xposi.w.h += d3; /* Line 2149, Address: 0x102c268 */',
                'BOSS_7.C floor retry matched cursor')
    coli_source = read('src/R7/COLI7.C')
    tables = coli_source[coli_source.index('unsigned short escoretbl'):coli_source.index('short pcol(')]
    coli = functions(coli_source)
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
    body = (boss + '\n' + tables + 'static unsigned char bCarry;\n'
            + '\n'.join([PCOLE] + [coli[n] for n in COLI] + [random]) + '\n' + STATICS)
    # Pre-increments/decrements of PC scratch words become compound assignments (same value, unused result).
    body, bumps = re.subn(r'(\+\+|--)(\(\((?:short|char)\*\)\w+\)\[\d+\]);', lambda m: f'{m[2]} {m[1][0]}= 1;', body)
    if bumps != 13:
        raise ValueError(f'BOSS_7.C scratch pre-increments changed upstream ({bumps})')
    # Read-only tables declared inside functions are copied to the stack on each call at -Os.
    for declaration in ('short event_tbl_t[2]', 'short event_tbl_t[4]', 'short event_tbl_t[3]', 'short event_tbl_t[12]',
                        'short spd_tbl[8]', 'short egg_move_tbl[43]'):
        body = once(body, '  ' + declaration, '  static const ' + declaration, f'BOSS_7.C {declaration}')
    # emie7clrset reads emie7_clr through a non-const pointer; it is never written.
    body = once(body, '  PALETTEENTRY emie7_clr[16]', '  static PALETTEENTRY emie7_clr[16]', 'BOSS_7.C emie7_clr')
    # event_timer and hight_set_retry read those tables through non-const pointers.
    if body.count('static void event_timer(sprite_status* pActwk, short* pTimer,') != 2:
        raise ValueError('event_timer prototype/definition changed upstream')
    body = body.replace('static void event_timer(sprite_status* pActwk, short* pTimer,',
                        'static void event_timer(sprite_status* pActwk, const short* pTimer,')
    body = once(body, '  short* a2;', '  const short* a2;', 'hight_set_retry table pointer')
    headers = {'BOSS_7.H': read('src/R7/BOSS_7.H'), 'COLI7.H': read('src/R7/COLI7.H')}
    # Every boss links into one program: names that another boss also defines get boss7_.
    others = set()
    for path in ('src/R1/BOSS_1.C', 'src/R3/BOSS_3.C', 'src/R4/BOSS_4.C', 'src/R4/BOSS_4_2.C', 'src/R5/BOSS_5.C', 'src/R6/BOSS_6.C'):
        others |= set(functions(read(path)))
    shared = sorted(set(functions(boss)) & others)
    prelude = ''.join(f'#define {n} boss7_{n}\n' for n in RENAMED + shared) + PRELUDE
    native = adapt(body)
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    patterns = sorted(set(re.findall(r'->patbase = (\w+);', body)))
    tokens = ''.join(f'#define SCD_PATTERN7_{name} {n + 1}u\n' for n, name in enumerate(patterns))
    reference = re.sub(r'->patbase = (\w+);', r'->patbase = SCD_PATTERN7_\1;', body)
    zone = zone_header('z7', 'boss7', set(RENAMED + shared), native, ['scd_boss7_statics'], PRELUDE + ACCESSORS + native)
    for target in (NATIVE, REFERENCE):
        write_text(target / 'BOSS7_ZONE.H',zone)
        for name, text in headers.items():
            write_text(target / name,text)
    write_text(NATIVE / 'boss_7.c','#include "BOSS7_ZONE.H"\n' + prelude + ACCESSORS + native)
    write_text(REFERENCE / 'BOSS7_PATTERNS.H',tokens)
    write_text(REFERENCE / 'boss_7.c',prelude + '#include "BOSS7_PATTERNS.H"\n' + reference)
    print(f'Boss 7 sources: BOSS_7.C, {len(COLI) + 1} COLI7.C functions; '
          f'{len(HEAD.findall(body))} PC casts adapted; renamed beside the other bosses: {shared}')


if __name__ == '__main__':
    main()
