#!/usr/bin/env python3
"""Compile ET3.C with the explicitly verified Sega CD differences."""
from pathlib import Path
import re
import cc_enemy_reference
from cc_generator_source import verify
verify()
src=Path('build/audit/source/src')
text=(src/'R3/ET3.C').read_text();text=text[text.index('static unsigned short tbl0sproffset'):]
text=text.replace('{ 1087, 1033, 0, 0, 1108, 1024, 0, 0, 0, 0, 0 }','{ 830, 830, 0, 0, 874, 874, 0, 0, 0, 0, 0 }')
text=text.replace('(stageno.w + 1 << 2) + (unsigned short)time_flag','(stageno.b.l << 2) + (unsigned short)time_flag')
text=text.replace('actionwk->colino = 0;', 'actionwk->colino = actionwk->colicnt = 0;')
text=text.replace('a1->xposi = actionwk->xposi;', 'a1->xposi.w.h = actionwk->xposi.w.h;').replace('a1->yposi = actionwk->yposi;', 'a1->yposi.w.h = actionwk->yposi.w.h;')
text=re.sub(r'  baku_init\(a1\);[^\n]*\n','',text)
text=re.sub(r'\w+->patbase = \w+;', '(void)0;',text)
for n in ['et','m_init','m_wait','m_die','m1wait','a_hover']:text=re.sub(r'\b'+n+r'\b','ref_'+n,text)
ride=re.sub(r'^#include .*\n','',(src/'RIDECHK.C').read_text(),flags=re.M)
# The collision scan comes from the independent COLI3.C reference; preserve
# its actual main_attack handler for the generator's special type 58.
col=(src/'R3/COLI3.C').read_text();attack=col[col.index('void main_attack('):];attack=attack[:attack.index('\n}')+2]
p=(src/'PLAYSUB.C').read_text();a=p.index('void bakuha(');b=p.index('void baku_die(');b=p.index('\n}',b)+2
expl=p[a:b];expl=re.sub(r'\w+->patbase = \w+;', '(void)0;',expl)
t=(src/'TBL1.C').read_text();scripts=t[t.index('static unsigned char baku_chg0'):t.index('static sprite_pattern bak00')]
draw=(src/'ACTION.C').read_text();draw=draw[draw.index('void actionsub('):draw.index('void frameout(')]
draw=draw[:draw.index('  pri = pActwk->sprpri;')]+'  if(pActwk->actno) pActwk->actflg |= 128;\n}\n'
draw=draw.replace('void actionsub(', 'void generator_viewport(')
draw=re.sub(r'  if \(lpKeepWork->GamePass != 0\) return;[^\n]*\n','',draw)
life=(src/'ACTSET.C').read_text();life=life[life.index('int frameout_s00('):life.index('int frameout_s0(')]
life=life.replace('int frameout_s00(', 'int generator_frameout(')
body=text+ride+attack+scripts+expl+draw+life
body=re.sub(r'\(\((unsigned short|short)\*\)(\w+|&actwk\[0\])\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',body)
body=re.sub(r'\(\(char\*\)(\w+)\)\[46\]',r'\1->actfree[0]',body)
for v in ['lXspeed','pActwk->yspeed.w','floorwk->xspeed.w']:body=body.replace(v+' << 8',v+' * 256')
header='''#include "EQU.H"
#include "DIRCOL.H"
#include "ETC.H"
void actionsub(sprite_status*); int frameout_s(sprite_status*); void frameout(sprite_status*);
int actwkchk(sprite_status**); void soundset(short); void scoreup(int); void tensuu_set(sprite_status*);
void patchg(sprite_status*,unsigned char**);
'''+(src/'RIDECHK.H').read_text()
prototypes=';\n'.join(re.findall(r'^(?:static )?(?:void|short|int) \w+\([^\n{]+\)',body,re.M))+';\n'
Path('build/cc1/generator/original.c').write_text(header+prototypes+body)
