#!/usr/bin/env python3
"""Compile POCKET.C and the popup branch of SCORE.C with proven console fixes."""
import re
from pathlib import Path
import cc_enemy_reference
from cc_pocket_source import verify

verify()
src = Path('build/audit/source/src')
pocket = (src/'R3/POCKET.C').read_text()
pocket = pocket[pocket.index('static char pchg0'):]
pocket = re.sub(r'\w+->patbase = \w+;', '(void)0;',pocket)
pocket = pocket.replace('->actno != 47','->actno != 84')
# Console capture tail-calls soundset and returns without a_move00.
pocket = re.sub(r'  a_move00\(actionwk\);[^\n]*\n','',pocket)
for name in ['pocket_move_tbl','pocket0','pocket1','pocket','a_init','a_move0','a_check','to_a_move1','a_move00',
             'a_move1','a_move2','a_move3','a_move4','a_move5','a_move6','a_move7','a_move8','b_init','b_move','b_die']:
    pocket = re.sub(r'\b'+name+r'\b','ref_'+name,pocket)
score = (src/'SCORE.C').read_text()
score = score[score.index('static void tensuu(sprite_status* pAct) {'):score.index('void score(sprite_status* pAct) {')]
score = re.sub(r'\w+->patbase = \w+;', '(void)0;',score)
score = score.replace('pAct->actflg = 4;', 'pAct->actflg |= 4; pAct->sproffset = 1734;')
score = score.replace('frameout(pAct);','{ frameout(pAct); return; }')
score = score.replace('static void tensuu(', 'void ref_points(')
play = (src/'PLAYSUB.C').read_text()
play = play[play.index('void tensuu0('):play.index('void bakuha(')]
play = play.replace('new_actwk->actno = 28','new_actwk->actno = 85')
draw = (src/'ACTION.C').read_text()
draw = draw[draw.index('void actionsub('):draw.index('void frameout(')]
# patset's final draw skips an actor deleted after its queue submission. A
# deleted popup must remain zero for a later allocator in the same update.
draw = draw[:draw.index('  pri = pActwk->sprpri;')]+'  if(pActwk->actno) pActwk->actflg |= 128;\n}\n'
draw = draw.replace('void actionsub(', 'void pocket_viewport(')
draw = re.sub(r'  if \(lpKeepWork->GamePass != 0\) return;[^\n]*\n','',draw)
life = (src/'ACTSET.C').read_text()
life = life[life.index('int frameout_s00('):life.index('int frameout_s0(')]
life = life.replace('int frameout_s00(', 'int pocket_frameout_s00(')
body = '\n'.join([pocket,score,play,draw,life])
body = re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
    lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',body)
header = '''#include "EQU.H"
void actionsub(sprite_status*); int frameout_s(sprite_status*); void frameout(sprite_status*);
int actwkchk(sprite_status**); void soundset(short); void scoreup(int);
void patchg(sprite_status*,unsigned char**);
'''
prototypes = ';\n'.join(re.findall(r'^(?:static )?(?:void|short|int) \w+\([^\n{]+\)',body,re.M))+';\n'
Path('build/cc1/pocket/original.c').write_text(header+prototypes+body)
