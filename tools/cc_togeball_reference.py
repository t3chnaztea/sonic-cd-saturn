#!/usr/bin/env python3
"""Compile all three original spike-ball sources with console init timing."""
import re
from pathlib import Path
import cc_enemy_reference
from cc_togeball_source import verify
verify()
src=Path('build/audit/source/src');parts=[]
for era in 'ABD':
    text=(src/f'R3/TOGEBL3{era}.C').read_text();text=text[text.index('void togeball('):]
    text=re.sub(r'\w+->patbase = \w+;', '(void)0;',text)
    text=text.replace('->actno != 44','->actno != 83')
    start=text.index('void act_init(');end=text.index('\n}',start)
    text=text[:end]+'\n  act_move(actionwk);\n'+text[end:]
    # Preserve the console's signed 32-bit swap/clear result without C UB.
    text=text.replace('sin << 16','(int)((unsigned)sin << 16)').replace('cos << 16','(int)((unsigned)cos << 16)')
    for name in ['togeball_main','togeball_opt','togeball','act_init2','act_move2','act_init','act_move']:
        text=re.sub(r'\b'+name+r'\b',f'toge{era}_{name}',text)
    parts.append(text)
draw=(src/'ACTION.C').read_text();draw=draw[draw.index('void actionsub('):draw.index('void frameout(')]
draw=draw[:draw.index('  pri = pActwk->sprpri;')]+'  pActwk->actflg |= 128;\n}\n'
draw=draw.replace('void actionsub(', 'void toge_viewport(')
draw=re.sub(r'  if \(lpKeepWork->GamePass != 0\) return;[^\n]*\n','',draw)
parts.append(draw)
life=(src/'ACTSET.C').read_text();life=life[life.index('int frameout_s00('):life.index('int frameout_s0(')]
life=life.replace('int frameout_s00(', 'int toge_frameout_s00(');parts.append(life)
text='\n'.join(parts)
text=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',text)
text=re.sub(r'\*\(int\*\)&(\w+)->actfree\[(\d+)\]',r'((ref_unaligned_int*)(void*)&\1->actfree[\2])->value',text)
header='''#include "EQU.H"
typedef struct __attribute__((packed)) { int value; } ref_unaligned_int;
void actionsub(sprite_status*); int frameout_s(sprite_status*); void frameout(sprite_status*);
int actwkchk2(sprite_status*,sprite_status**); void sinset(unsigned char,short*,short*);
'''
prototypes=';\n'.join(re.findall(r'^(?:static )?(?:void|short|int) \w+\([^\n{]+\)',text,re.M))+';\n'
Path('build/cc1/togeball/original.c').write_text(header+prototypes+text)
