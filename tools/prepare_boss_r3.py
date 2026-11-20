#!/usr/bin/env python3
"""Generate the Collision Chaos Act 3 boss (R3/BOSS_3.C) with the code it calls.

build/probe-source/boss_3.c (Saturn/host) and build/player-reference/boss_3.c
(original PC casts) hold, unchanged except as listed below:
  - R3/BOSS_3.C: egg3dai_s, egg3dai_l, egg3haguruma, egg3, egg3cannon, punchbom;
  - R3/GATE.C: gate (actor 63), the shutters that jaba_open spawns;
  - R3/COLI3.C: the round's own touch response (pcol and the classes the boss
    colino values reach), named boss3_* so it links beside COLI1.C;
  - RIDECHK.C: ridechk and its helpers for the gates, named boss3_*.
Changes: includes; GATE.C's static tables are renamed where they collide with
BOSS_3.C's and its unterminated pchg0 script gets an end byte; pcole calls the native hurt frontend (as tools/prepare_boss.py);
CollitblDataXchk's fall-through returns CollitblDataYchk's result, which is
the value the PC binary leaves in the return register there. The reference
build replaces pattern table pointers with tokens, as for BOSS_1.C.
"""
import re
from audit_source import UPSTREAM
from generated_io import write_text
from prepare_boss import NATIVE, REFERENCE, HEAD, ACCESSORS, functions, adapt, zone_header

COLI = ['pcol', 'CollitblDataXchk', 'CollitblDataYchk', 'ColliHitChk', 'pcolitem', 'pcolnomal',
        'pcolplay2', 'pcolplay', 'pcolspecial', 'eggman_chk', 'boss_1', 'boss_4', 'boss_5', 'main_attack']
RIDE = ['ride_on_clr', 'ride_on_set', 'hitchk_u', 'ridechk', 'ride_on_chk', 'hitchk', 'hit_v', 'hit_x',
        'push_set', 'push_clr', 'hit_y', 'hit_yu', 'hit_yu1', 'hit_yu0', 'hit_e', 'side_coli', 'hit_set', 'hit_clr']
RENAMED = COLI + RIDE + ['pcole', 'escoretbl', 'colitbl', 'playdamagechk', 'playdamageset']
PRELUDE = '''#include "EQU.H"
#include "BOSS_3.H"
#include "COLI3.H"
#include "GATE.H"
#include "RIDECHK.H"
#include "ACTION.H"
#include "ACTSET.H"
#include "DIRCOL.H"
#include "ETC.H"
#include "FCOL.H"
#include "GOAL.H"
#include "IMPFUNCS.H"
#include "LOADER2.H"
#include "PLAYSUB.H"
#include "SCORE.H"
extern void colorset2(int ColorNo);
extern void soundset(short);
extern short playdieset(sprite_status *);
extern void scd_objects_hurt(int source_x);
extern sprite_pattern *bakupat[];
extern char *bakuchg[];
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
    boss = strip(read('src/R3/BOSS_3.C'))
    # BOSS_3.C declares bakupat/bakuchg itself; the prelude already does.
    boss = once(boss, 'extern sprite_pattern* bakupat[];\nextern char* bakuchg[];\n', '', 'BOSS_3.C bakupat')
    gate = strip(read('src/R3/GATE.C'))
    for name in ['pat0' + str(n) for n in range(8)] + ['pchg0', 'pchg']:
        gate = re.sub(rf'\b{name}\b', f'gate_{name}', gate)
    # GATE.C pchg0 has no end byte, so PLAYSUB.C patchg's end search reads past it.
    # A 255 end gives the PC's own result for any end other than 252 (one-update
    # hold per frame); act_open stops at frame 7 before the script reaches it.
    gate = once(gate, 'static char gate_pchg0[10] = { 0, 0, 1, 2, 3, 4, 5, 6, 7, 7 };',
                'static char gate_pchg0[11] = { 0, 0, 1, 2, 3, 4, 5, 6, 7, 7, -1 };', 'GATE.C pchg0')
    coli_source = read('src/R3/COLI3.C')
    tables = coli_source[coli_source.index('unsigned short escoretbl'):coli_source.index('short pcol(')]
    coli = functions(coli_source)
    tail = re.search(r'\n  CollitblDataYchk\(pActwk, pColliAct, iYposi, iColiNo, iD5\); *\n\s*\}$', coli['CollitblDataXchk'])
    if not tail:
        raise ValueError('COLI3.C CollitblDataXchk changed upstream')
    coli['CollitblDataXchk'] = coli['CollitblDataXchk'][:tail.start()] + '\n  return CollitblDataYchk(pActwk, pColliAct, iYposi, iColiNo, iD5);\n}'
    ride = functions(read('src/RIDECHK.C'))
    body = (boss + '\n' + gate + '\n' + tables + 'static unsigned char bCarry;\n'
            + '\n'.join([PCOLE] + [coli[n] for n in COLI] + [ride[n] for n in RIDE]) + '\n')
    # COLI3.C's multi-hit rebound halves with C division; the Sega CD halves with
    # asr.w, which rounds down (retail CC3C seq 1275: xspeed 927 -> -464, not -463).
    body = once(body, 'pActwk->xspeed.w /= 2;', 'pActwk->xspeed.w >>= 1;', 'COLI3.C rebound x')
    body = once(body, 'pActwk->yspeed.w /= 2;', 'pActwk->yspeed.w >>= 1;', 'COLI3.C rebound y')
    # Read-only tables declared inside functions are copied to the stack on each call at -Os.
    for declaration in ('short jabaopen_tbl[4]', 'short jabapos_tbl[4]', 'unsigned char cannon_chg_tbl[8]'):
        body = once(body, declaration, 'static const ' + declaration, f'BOSS_3.C {declaration}')
    # Pre-increments of PC scratch words become compound assignments (same value, unused result).
    body, bumps = re.subn(r'\+\+(\(\((?:unsigned short|short|int)\*\)\w+\)\[\d+\]);', r'\1 += 1;', body)
    if bumps != 4:
        raise ValueError(f'BOSS_3.C scratch pre-increments changed upstream ({bumps})')
    headers = {'BOSS_3.H': read('src/R3/BOSS_3.H'), 'COLI3.H': read('src/R3/COLI3.H'),
               'GATE.H': read('src/R3/GATE.H'), 'RIDECHK.H': read('src/RIDECHK.H')}
    # Both bosses link into one program: BOSS_3.C names that BOSS_1.C also defines get boss3_.
    shared = sorted(set(functions(boss)) & set(functions(read('src/R1/BOSS_1.C'))))
    prelude = ''.join(f'#define {n} boss3_{n}\n' for n in RENAMED + shared) + '#include "BOSS3_ZONE.H"\n' + PRELUDE
    native = adapt(body)
    zone = zone_header('z3', 'boss3', set(RENAMED + shared), native, RIDE, PRELUDE + ACCESSORS + native)
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    patterns = sorted(set(re.findall(r'->patbase = (\w+);', body)))
    tokens = ''.join(f'#define SCD_PATTERN3_{name} {n + 1}u\n' for n, name in enumerate(patterns))
    reference = re.sub(r'->patbase = (\w+);', r'->patbase = SCD_PATTERN3_\1;', body)
    for target in (NATIVE, REFERENCE):
        for name, text in headers.items():
            write_text(target / name,text)
        write_text(target / 'BOSS3_ZONE.H',zone)
    write_text(NATIVE / 'boss_3.c',prelude + ACCESSORS + native)
    write_text(REFERENCE / 'BOSS3_PATTERNS.H',tokens)
    write_text(REFERENCE / 'boss_3.c',prelude + '#include "BOSS3_PATTERNS.H"\n' + reference)
    print(f'Boss 3 sources: BOSS_3.C, GATE.C, {len(COLI) + 1} COLI3.C and {len(RIDE)} RIDECHK.C functions; '
          f'{len(HEAD.findall(body))} PC casts adapted; renamed beside BOSS_1.C: {shared}')


if __name__ == '__main__':
    main()
