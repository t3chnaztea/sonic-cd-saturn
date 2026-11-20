#!/usr/bin/env python3
"""Compile original KAMA/BANPA and original viewport checks independently."""
from pathlib import Path
import re
import cc_enemy_reference  # Shared original COLI3/SUICIDE and console AnimateObject.
from cc_kama_source import verify
verify()

src=Path('build/audit/source/src')
text=(src/'R3/KAMA.C').read_text()
text=text[text.index('static unsigned char jmp_flg;'):]
# Drawing comes from captured original-machine mappings. Keep animation scripts.
text=re.sub(r'^sprite_pattern[^\n]+\n','',text,flags=re.M)
text=re.sub(r'\w+->patbase = \w+;', '(void)0;',text)
text=re.sub(r'\bmovement\(', 'kama_movement(',text)
# IDs differ between zones in the original; native CC ids are explicitly mapped.
text=text.replace('->actno = 37','->actno = 81').replace('->actno != 36','->actno != 80')
text=re.sub(r'\(\(char\*\)(\w+)\)\[50\]',r'(*(signed char*)&\1->actfree[4])',text)
# These differences are proven in all original programs by cc_kama_source.py.
assert text.count('if (iD1 < 96)')==1
text=text.replace('if (iD1 < 96)','if ((unsigned short)iD1 < 32 && (unsigned short)iD0 < 96)')
text=text.replace('iD1 > -7','iD1 >= -7')
start=text.index('void kama_move(');end=text.index('void kama_reve(',start)
move=text[start:end];assert move.count('pActwk->mstno.b.h = 3;')==1
text=text[:start]+move.replace('pActwk->mstno.b.h = 3;','pActwk->mstno.w = 3;')+text[end:]
# Signed left shifts in reconstructed C express the 68000's 16.16 conversion.
text=re.sub(r'if \(lD0 & 0x80000000\) lD0 <<= 8, lD0 \|= 0x80000000; else lD0 <<= 8;',
            'lD0 *= 256;',text)
ban=(src/'R3/BANPA.C').read_text()
ban=ban[ban.index('void banpa('):]
ban=re.sub(r'\w+->patbase = \w+;', '(void)0;',ban)
ban=re.sub(r'\bact_init\b','banpa_init',ban);ban=re.sub(r'\bact_move\b','banpa_move',ban)
ban=ban.replace('bumperwk->colino = 231;', 'bumperwk->colino = 231; bumperwk->sproffset = 0x435e;')
start=ban.index('static void banpa_init(');end=ban.index('\n}',start)
ban=ban[:end]+'\n  banpa_move(bumperwk);\n'+ban[end:]
text+=ban
c=(src/'R3/COLI3.C').read_text();special=c[c.index('short pcolspecial('):c.index('short eggman_chk(')]
special=special.replace('short pcolspecial(', 'short original_special_contact(')
text+=special
draw=(src/'ACTION.C').read_text();draw=draw[draw.index('void actionsub('):draw.index('void frameout(')]
draw=draw[:draw.index('  pri = pActwk->sprpri;')]+'  pActwk->actflg |= 128;\n}\n'
draw=draw.replace('void actionsub(', 'void original_viewport(')
draw=re.sub(r'  if \(lpKeepWork->GamePass != 0\) return;[^\n]*\n','',draw)
text+=draw
text=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',text)
text=re.sub(r'\*\(int\*\)&(\w+)->actfree\[(\d+)\]',r'((ref_unaligned_int*)(void*)&\1->actfree[\2])->value',text)
header='''#include "EQU.H"
#include "DIRCOL.H"
typedef struct __attribute__((packed)) { int value; } ref_unaligned_int;
void actionsub(sprite_status*); int frameout_s(sprite_status*); int frameout_s00(sprite_status*,short);
int actwkchk(sprite_status**); void frameout(sprite_status*);
void patchg(sprite_status*,unsigned char**); short enemy_suicide(sprite_status*); void soundset(short);
unsigned char CCset(unsigned short,unsigned short); unsigned char bchg(unsigned char,unsigned char);
void main_attack(sprite_status*,sprite_status*); short eggman_chk(sprite_status*,sprite_status*,char);
'''
prototypes=';\n'.join(re.findall(r'^(?:static )?(?:void|short) \w+\([^\n{]+\)',text,re.M))+';\n'
Path('build/cc1/kama/original.c').write_text(header+prototypes+text)
