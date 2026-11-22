#!/usr/bin/env python3
"""Generate the Quartz Quadrant Act 3 boss (R5/BOSS_5.C) with the code it calls.

build/probe-source/boss_5.c (Saturn/host) and build/player-reference/boss_5.c
(original PC casts) hold, unchanged except as listed below:
  - R5/BOSS_5.C: egg5hibana (actor 32), egg5hari (33), egg5belt (34),
    egg5bakuha (35), egg5 (50), egg5meca1 (51), egg5meca2 (52), egg5meca3 (53),
    egg5pipe (54), egg5catch (55), egg5bomb (56), egg5bomb2 (57);
  - R5/COLI5.C: the round's touch response (pcol and the classes the boss
    colino values reach), named boss5_* so it links beside COLI1/3/4.C;
  - RIDECHK.C ride_on_chk and its helpers (egg5meca2, egg5hari), named boss5_*;
  - SCR53C/D.C divdevset, an empty function in both futures.
Changes: includes; pcole calls the native hurt frontend (as tools/prepare_boss.py);
pre-decrements of PC scratch words become compound assignments (same value,
unused result); function-local read-only tables get static storage. BOSS_5.C
keeps a long at actfree[16] (PC offset 62, *(int*)&actfree[16]): the Saturn
build reads it with the little-endian accessors, the reference build through a
packed (unaligned) int, which is the PC access. The reference build replaces
pattern table pointers with tokens, as for BOSS_1.C.
"""
import re
from audit_source import UPSTREAM
from generated_io import write_text
from prepare_boss import zone_header, NATIVE, REFERENCE, HEAD, ACCESSORS, functions, adapt

COLI = ['pcol', 'CollitblDataXchk', 'CollitblDataYchk', 'ColliHitChk', 'pcolitem', 'pcolnomal',
        'pcolplay2', 'pcolplay', 'pcolspecial', 'eggman_chk', 'main_attack']
RIDE = ['ride_on_clr', 'ride_on_set', 'hitchk_u', 'ridechk', 'ride_on_chk', 'hitchk', 'hit_v', 'hit_x',
        'push_set', 'push_clr', 'hit_y', 'hit_yu', 'hit_yu1', 'hit_yu0', 'hit_e', 'side_coli', 'hit_set', 'hit_clr']
RENAMED = COLI + RIDE + ['pcole', 'escoretbl', 'colitbl', 'playdamagechk', 'playdamageset', 'divdevset']
PRELUDE = '''#include "EQU.H"
#include "BOSS_5.H"
#include "COLI5.H"
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
extern void colorset2(int ColorNo);
extern void soundset(short);
extern short playdieset(sprite_status *);
extern void scd_objects_hurt(int source_x);
extern sprite_pattern *bakupat[];
extern short scr_dir_tbl[6];
/* SCR53C.C/SCR53D.C divdevset: empty in both futures. */
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
LONG62 = r'\*\(int\*\)&pActwk->actfree\[16\]'
# PC offset 62 is not 4-byte aligned: a packed int is the PC's unaligned access.
REFERENCE_LONG62 = '''struct __attribute__((packed)) scd_long62 {int v;};
#define SCD_LONG62(p) (((struct scd_long62 *)&(p)->actfree[16])->v)
'''


def once(text, old, new, what):
    if text.count(old) != 1:
        raise ValueError(f'{what} changed upstream')
    return text.replace(old, new)


def long62_native(text):
    text, stores = re.subn(LONG62 + r' (=|\+=|-=) ([^;]+);', lambda m: (
        f'SCD_SET(int32_t, pActwk, 62, {m[2]});' if m[1] == '=' else
        f'SCD_SET(int32_t, pActwk, 62, SCD_GET(int32_t, pActwk, 62) {m[1][0]} ({m[2]}));'), text)
    text, loads = re.subn(LONG62, 'SCD_GET(int32_t, pActwk, 62)', text)
    if (stores, loads) != (5, 3):
        raise ValueError(f'BOSS_5.C actfree[16] long accesses changed upstream ({stores}, {loads})')
    return text


def main():
    read = lambda path: (UPSTREAM / path).read_text(encoding='latin1')
    strip = lambda text: re.sub(r'#include "[^"]*"\n', '', text)
    boss = strip(read('src/R5/BOSS_5.C'))
    # BOSS_5.C declares colorset2 itself; the prelude already does.
    boss = once(boss, 'extern void colorset2(int ColorNo);\n', '', 'BOSS_5.C colorset2')
    coli_source = read('src/R5/COLI5.C')
    tables = coli_source[coli_source.index('unsigned short escoretbl'):coli_source.index('short pcol(')]
    coli = functions(coli_source)
    ride = functions(read('src/RIDECHK.C'))
    body = (boss + '\n' + tables + 'static unsigned char bCarry;\n'
            + '\n'.join([PCOLE] + [coli[n] for n in COLI] + [ride[n] for n in RIDE]) + '\n')
    # Pre-decrements of PC scratch words become compound assignments (same value, unused result).
    body, drops = re.subn(r'--(\(\((?:short)\*\)&?[\w\[\]]+\)\[\d+\]);', r'\1 -= 1;', body)
    if drops != 2:
        raise ValueError(f'BOSS_5.C scratch pre-decrements changed upstream ({drops})')
    # COLI5.C pcolnomal halves the bounce with C division (toward zero); retail
    # R53C negates then asr.w $10/$12(a0) (rounds down): -341 halves to -171.
    for axis in ('x', 'y'):
        body = once(body, f'    pActwk->{axis}speed.w /= 2; ', f'    pActwk->{axis}speed.w >>= 1; ', f'COLI5.C pcolnomal {axis}speed halving')
    # BOSS_5.C egg5belt_1 carries Sonic 4 px left per update past x 3464; retail
    # R53C $20BEDC and R53D $20BFB6 use subq.w #3,8(a1).
    body = once(body, '    actwk[0].xposi.w.h -= 4; ', '    actwk[0].xposi.w.h -= 3; ', 'BOSS_5.C egg5belt_1 belt carry')
    # BOSS_5.C egg5bomb_3 calls egg5bomb_4 on landing but leaves r_no0, so the
    # bomb keeps falling 8 updates; retail R53C $20BB42 and R53D $20BC1E run
    # addq.b #2,$24(a0) after the landing sound, and the bomb rests at y 696.
    body = once(body, '        soundset(180); /* Line 1555, Address: 0x102607c */\n',
                '        soundset(180); /* Line 1555, Address: 0x102607c */\n        pActwk->r_no0 += 2;\n',
                'BOSS_5.C egg5bomb_3 landing')
    # BOSS_5.C egg5meca2 shakes on every other pair of updates (actfree[1] & 2)
    # and moves when the toggle bit was set; retail R53C $20B54A and R53D
    # $20B626 test the belt speed on every update and eori.b #1,$34(a0) first,
    # moving when the toggled bit is set (beq skips when it cleared).
    body = once(body, '      if (pActwk->actfree[1] & 2) /* Line 914, Address: 0x1024750 */\n',
                '      if (1) /* retail: every update */\n', 'BOSS_5.C egg5meca2 shake gate')
    body = once(body, '            if (!(pActwk->actfree[10] & 1)) /* Line 922, Address: 0x10247f8 */\n',
                '            if (pActwk->actfree[10] & 1) /* retail: kept when the toggle clears */\n',
                'BOSS_5.C egg5meca2 fast shake')
    body = once(body, '          if (pActwk->actfree[10] & 1) /* Line 934, Address: 0x1024868 */\n',
                '          if (!(pActwk->actfree[10] & 1)) /* retail: moves when the toggle sets */\n',
                'BOSS_5.C egg5meca2 slow shake')
    # BOSS_5.C make_bomb2 links each fragment to the bomb and copies its pixel
    # words; retail R53C $20C3A2 and R53D copy the bomb's own link ($2E) and the
    # whole x and y longs (move.l 8/12(a0)), so fragments keep the bomb's subpixels.
    body = once(body, '      ((short*)ppActwk)[25] = (unsigned short)(unsigned char)(pActwk - actwk); /* Line 2507, Address: 0x1028330 */\n',
                '      ((short*)ppActwk)[25] = ((short*)pActwk)[25]; /* retail: the bomb\'s link */\n', 'BOSS_5.C make_bomb2 link')
    body = once(body, '      ppActwk->xposi.w.h = pActwk->xposi.w.h; /* Line 2509, Address: 0x102837c */\n'
                '      ppActwk->yposi.w.h = pActwk->yposi.w.h; /* Line 2510, Address: 0x102838c */\n',
                '      ppActwk->xposi.l = pActwk->xposi.l; /* retail: move.l */\n'
                '      ppActwk->yposi.l = pActwk->yposi.l;\n', 'BOSS_5.C make_bomb2 position')
    # Read-only tables declared inside functions are copied to the stack on each call at -Os.
    for declaration in ('short meca2_ytbl[4]', 'PALETTEENTRY belt_col_tblD[9]', 'PALETTEENTRY belt_col_tblC[9]',
                        'short hibana_tbl[16]', 'short hibana_ytbl[6]', 'short bom_tbl[8]'):
        body = once(body, '  ' + declaration, '  static const ' + declaration, f'BOSS_5.C {declaration}')
    headers = {'BOSS_5.H': read('src/R5/BOSS_5.H'), 'COLI5.H': read('src/R5/COLI5.H'), 'RIDECHK.H': read('src/RIDECHK.H')}
    # Every boss links into one program: names that another boss also defines get boss5_.
    others = set()
    for path in ('src/R1/BOSS_1.C', 'src/R3/BOSS_3.C', 'src/R4/BOSS_4.C', 'src/R4/BOSS_4_2.C'):
        others |= set(functions(read(path)))
    shared = sorted(set(functions(boss)) & others)
    prelude = ''.join(f'#define {n} boss5_{n}\n' for n in RENAMED + shared) + '#include "BOSS5_ZONE.H"\n' + PRELUDE
    native = long62_native(adapt(body))
    zone = zone_header('z5', 'boss5', set(RENAMED + shared), native, RIDE)
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    patterns = sorted(set(re.findall(r'->patbase = (\w+);', body)))
    tokens = ''.join(f'#define SCD_PATTERN5_{name} {n + 1}u\n' for n, name in enumerate(patterns))
    reference = re.sub(r'->patbase = (\w+);', r'->patbase = SCD_PATTERN5_\1;', body)
    reference = re.sub(LONG62, 'SCD_LONG62(pActwk)', reference)
    for target in (NATIVE, REFERENCE):
        for name, text in headers.items():
            write_text(target / name,text)
        write_text(target / 'BOSS5_ZONE.H',zone)
    write_text(NATIVE / 'boss_5.c',prelude + ACCESSORS + native)
    write_text(REFERENCE / 'BOSS5_PATTERNS.H',tokens)
    write_text(REFERENCE / 'boss_5.c',prelude + REFERENCE_LONG62 + '#include "BOSS5_PATTERNS.H"\n' + reference)
    print(f'Boss 5 sources: BOSS_5.C, {len(COLI) + 1} COLI5.C and {len(RIDE)} RIDECHK.C functions; '
          f'{len(HEAD.findall(body))} PC casts adapted; renamed beside BOSS_1/3/4.C: {shared}')


if __name__ == '__main__':
    main()
