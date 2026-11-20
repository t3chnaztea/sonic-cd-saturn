#!/usr/bin/env python3
"""Generate the Tidal Tempest Act 3 boss (R4/BOSS_4.C, BOSS_4_2.C) with the code it calls.

build/probe-source/boss_4.c (Saturn/host) and build/player-reference/boss_4.c
(original PC casts) hold, unchanged except as listed below:
  - R4/BOSS_4.C: egg4air (actor 74, the fleeing submarine) and egg4airhead (75);
  - R4/BOSS_4_2.C: egg4 (76), egg4meca (77), egg4tama (78), egg4awa (79);
  - R4/WALL4.C: wall4 (71), the maze gates make_gate spawns and the layout wall;
  - R4/COLI4.C: the round's touch response (pcol and the classes the boss
    colino values reach), named boss4_* so it links beside COLI1.C/COLI3.C;
  - RIDECHK.C (wall4's hitchk), R4/PLAYSUB4.C patchg and IO.C random, named boss4_*.
Changes: includes; ychg_ret tests egg4 actfree[2] bit 3 as retail R43C $CBA8 does; egg4air_01's horizontal moves clamp X to the waypoint and
the -192 wrap compare is signed (retail R43C__.MMD $BB8A-$BCC8); an unset
pNewact (no free actor slot) points at a spare actor; pcole calls the native hurt frontend (as tools/prepare_boss.py);
egg4awa_ini and egg4tama_ini fall off their ends after a tail call, and return
that call's result, which is what the PC binary leaves in the return register;
function-local read-only tables get static storage. BOSS_4*.C read the boss
actors' xspeed/yspeed words both as fields and as the long ((int*)p)[4]; the
field accesses become the PC casts ((short*)p)[8]/[9] so both read the PC bytes
(the same code on the PC). The reference build replaces pattern table pointers
with tokens, as for BOSS_1.C.
"""
import re
from audit_source import UPSTREAM
from generated_io import write_text
from prepare_boss import NATIVE, REFERENCE, HEAD, ACCESSORS, functions, adapt, zone_header

COLI = ['pcol', 'CollitblDataXchk', 'CollitblDataYchk', 'ColliHitChk', 'pcolitem', 'pcolnomal',
        'pcolplay2', 'pcolplay', 'pcolspecial', 'eggman_chk', 'main_attack']
RIDE = ['ride_on_clr', 'ride_on_set', 'hitchk_u', 'ridechk', 'ride_on_chk', 'hitchk', 'hit_v', 'hit_x',
        'push_set', 'push_clr', 'hit_y', 'hit_yu', 'hit_yu1', 'hit_yu0', 'hit_e', 'side_coli', 'hit_set', 'hit_clr']
RENAMED = COLI + RIDE + ['pcole', 'escoretbl', 'colitbl', 'playdamagechk', 'playdamageset', 'patchg', 'random',
                         'frameout_s_', 'wall4_init', 'wall4_sense', 'wall4_wait', 'wall4_down', 'pat_wall4', 'wall4_pat0']
PRELUDE = '''#include "EQU.H"
#include "BOSS_4.H"
#include "BOSS_4_2.H"
#include "COLI4.H"
#include "WALL4.H"
#include "RIDECHK.H"
#include "ACTION.H"
#include "ACTSET.H"
#include "DIRCOL.H"
#include "ETC.H"
#include "FCOL.H"
#include "GOAL.H"
#include "LOADER2.H"
#include "SCORE.H"
extern void colorset2(int ColorNo);
extern void soundset(short);
extern short playdieset(sprite_status *);
extern void plairset(void);
extern void scd_objects_hurt(int source_x);
void patchg(sprite_status *, unsigned char **);
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


def once(text, old, new, what):
    if text.count(old) != 1:
        raise ValueError(f'{what} changed upstream')
    return text.replace(old, new)


def main():
    read = lambda path: (UPSTREAM / path).read_text(encoding='latin1')
    strip = lambda text: re.sub(r'#include "[^"]*"\n', '', text)
    air = strip(read('src/R4/BOSS_4.C'))
    egg = strip(read('src/R4/BOSS_4_2.C'))
    # Retail e4a_03_most_near (R43D__.MMD $BDF8, $BE7C-$BE8A) tests the player's
    # (lea $FFFFD000,a1) Y and X speed; the PC decompile reads the boss's own.
    air = once(air, '  if ((long int)(int)pActwk->yspeed.w > 2048 || (long int)(int)pActwk->xspeed.w > 2048) { /* Line 815,',
               '  if ((long int)(int)actwk[0].yspeed.w > 2048 || (long int)(int)actwk[0].xspeed.w > 2048) { /* Line 815,', 'e4a_03_most_near player speed')
    # Retail R43C__.MMD egg4air_01 ($BB8A, $BBB2) clamps X to the waypoint on
    # arrival ("move.w d0,8(a0)") before egg4air_01_next; the PC decompile drops
    # that store (retail TT3C level frame 959: X stops at 1596, the PC at 1599).
    air = once(air, '        egg4air_01_next(pActwk, pEscRoot); /* Line 403,',
               '        pActwk->xposi.w.h = pEscRoot->E4A_X; egg4air_01_next(pActwk, pEscRoot); /* Line 403,', 'egg4air_01 right clamp')
    air = once(air, '        egg4air_01_next(pActwk, pEscRoot); /* Line 417,',
               '        pActwk->xposi.w.h = pEscRoot->E4A_X; egg4air_01_next(pActwk, pEscRoot); /* Line 417,', 'egg4air_01 left clamp')
    # $BCBA: "cmpi.w #-192,d0"; the decompile's unsigned 65344 never equals the short.
    air = once(air, 'pEscRoot->E4A_Y != 65344)', 'pEscRoot->E4A_Y != -192)', 'egg4air_01 wrap compare')
    # Retail ychg_ret (R43C__.MMD $CBA4-$CBB0: move.w #$480,d0; btst #3,$2C(a1);
    # bne; neg.w d0) turns the bubbles back while egg4's actfree[2] bit 3 is clear;
    # the PC's "!(x) & 8" is always 0, so its bubbles always add 1152.
    egg = once(egg, '  if (!(pEggwk->actfree[2]) & 8) { /* Line 1518,', '  if (!(pEggwk->actfree[2] & 8)) { /* Line 1518,',
               'ychg_ret direction test')
    # Both fall off their end after a tail call; the PC returns that call's eax.
    egg = once(egg, '  egg4awa_deru(pActwk); /* Line 1213', '  return egg4awa_deru(pActwk); /* Line 1213', 'egg4awa_ini tail')
    egg = once(egg, '  egg4tama_01(pActwk); /* Line 1730', '  return egg4tama_01(pActwk); /* Line 1730', 'egg4tama_ini tail')
    wall = strip(read('src/R4/WALL4.C'))
    # PC xspeed/yspeed words that BOSS_4*.C also address as the long ((int*)p)[4].
    boss = air + '\n' + egg
    # make_awa/make_awa2/make_tama leave pNewact unset when actwkchk finds no
    # free slot and the callers still write through it (the 68000 build's a1
    # then points past the object table). Here it points at a spare actor.
    boss = 'static sprite_status boss4_spare;\n' + boss.replace('sprite_status* pNewact;', 'sprite_status* pNewact = &boss4_spare;')
    boss, fields = re.subn(r'pActwk->([xy])speed\.w', lambda m: f'((short*)pActwk)[{8 if m[1] == "x" else 9}]', boss)
    if fields != 6:  # 8 PC accesses, 2 moved to the player (e4a_03_most_near)
        raise ValueError(f'BOSS_4*.C speed field accesses changed upstream ({fields})')
    coli_source = read('src/R4/COLI4.C')
    tables = coli_source[coli_source.index('unsigned short escoretbl'):coli_source.index('short pcol(')]
    coli = functions(coli_source)
    ride = functions(read('src/RIDECHK.C'))
    patchg = functions(read('src/R4/PLAYSUB4.C'))['patchg']
    random = functions(read('src/IO.C'))['random']
    # Retail Player_ObjCollide (Palmtree Panic/Player Object Collision.asm:81-98)
    # branches to the touch handler, which ends the scan with rts: one contact per
    # update. The PC pcol keeps scanning when ColliHitChk returns 1, so an egg4 hit
    # also popped an overlapping egg4awa bubble (TT3C level frame 7,847).
    coli['pcol'] = once(coli['pcol'], 'if (iRet == -1)', 'if (iRet != 0)', 'pcol one contact')
    body = (boss + '\n' + wall + '\n' + tables + 'static unsigned char bCarry;\n'
            + '\n'.join([PCOLE] + [coli[n] for n in COLI] + [ride[n] for n in RIDE] + [patchg, random]) + '\n')
    # Three scratch updates inside expressions become a statement and a read (same value).
    # Retail pcolnomal (R43C__.MMD $7160-$716C) halves with asr.w after neg.w.
    body = once(body, 'pActwk->xspeed.w /= 2;', 'pActwk->xspeed.w >>= 1;', 'pcolnomal xspeed halve')
    body = once(body, 'pActwk->yspeed.w /= 2;', 'pActwk->yspeed.w >>= 1;', 'pcolnomal yspeed halve')
    # Retail egg4_movec (R43C__.MMD $C618: neg.l $38(a0)) negates the X:Y offset
    # words as one big-endian long, X high; the PC's little-endian int has Y high,
    # so with both words set the borrow lands in the other word (retail TT3C
    # level frame 6119: egg4 at X 2735, the PC order gives 2736).
    body = once(body, '((int*)pActwk)[15] *= -1;',
                '{ unsigned int offs = 0u - (((unsigned int)(unsigned short)((short*)pActwk)[30] << 16) | (unsigned short)((short*)pActwk)[31]);'
                ' ((short*)pActwk)[30] = (short)(offs >> 16); ((short*)pActwk)[31] = (short)offs; }', 'egg4_movec negate')
    body = once(body, 'if ((((int*)pActwk)[16] -= 65536) < 0) {',
                '((int*)pActwk)[16] -= 65536; if (((int*)pActwk)[16] < 0) {', 'egg4awa_ychg step')
    body = once(body, 'if (!(--((short*)pActwk)[23])) {', '((short*)pActwk)[23] -= 1; if (!((short*)pActwk)[23]) {', 'wall4_down count')
    # Read-only tables declared inside functions are copied to the stack on each call at -Os.
    for declaration in ('char awaposi_cnt_tbl[8]', 'short bom_tbl[20]', 'void(*wall4_acttbl[4])(sprite_status*)'):
        body = once(body, declaration, 'static const ' + declaration if '(' not in declaration else
                    'static void(*const wall4_acttbl[4])(sprite_status*)', f'{declaration}')
    headers = {name: read(f'src/R4/{name}') for name in ('BOSS_4.H', 'BOSS_4_2.H', 'COLI4.H', 'WALL4.H')}
    headers['RIDECHK.H'] = read('src/RIDECHK.H')
    # Every boss links into one program: names that BOSS_1.C or BOSS_3.C also define get boss4_.
    mine = set(functions(boss))
    shared = sorted(mine & (set(functions(read('src/R1/BOSS_1.C'))) | set(functions(read('src/R3/BOSS_3.C')))))
    prelude = ''.join(f'#define {n} boss4_{n}\n' for n in RENAMED + shared) + '#include "BOSS4_ZONE.H"\n' + PRELUDE
    native = adapt(body)
    zone = zone_header('z4', 'boss4', set(RENAMED + shared), native, RIDE, PRELUDE + ACCESSORS + native)
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    patterns = sorted(set(re.findall(r'->patbase = (\w+);', body)))
    tokens = ''.join(f'#define SCD_PATTERN4_{name} {n + 1}u\n' for n, name in enumerate(patterns))
    reference = re.sub(r'->patbase = (\w+);', r'->patbase = SCD_PATTERN4_\1;', body)
    for target in (NATIVE, REFERENCE):
        for name, text in headers.items():
            write_text(target / name,text)
        write_text(target / 'BOSS4_ZONE.H',zone)
    write_text(NATIVE / 'boss_4.c',prelude + ACCESSORS + native)
    write_text(REFERENCE / 'BOSS4_PATTERNS.H',tokens)
    write_text(REFERENCE / 'boss_4.c',prelude + '#include "BOSS4_PATTERNS.H"\n' + reference)
    print(f'Boss 4 sources: BOSS_4.C, BOSS_4_2.C, WALL4.C, {len(COLI) + 1} COLI4.C and {len(RIDE)} RIDECHK.C functions; '
          f'{len(HEAD.findall(body))} PC casts adapted; renamed beside BOSS_1.C/BOSS_3.C: {shared}')


if __name__ == '__main__':
    main()
