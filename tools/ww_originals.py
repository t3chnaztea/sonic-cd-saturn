#!/usr/bin/env python3
"""Compilable R6 originals and placements for tools/test-ww-actors.sh.

usage: ww_originals.py OUT_DIR

Writes OUT_DIR/orig/*.c (the retail R6 actor sources with the PC scratch casts
turned into actfree offsets, as tools/test-qq-actors.sh does for R5), COLI6.C
pcol, RIDECHK.C, SUICIDE.C and PLAYSUB.C patchg, and OUT_DIR/placements.h with
every R6 placement of the ported routines per act and era."""
import re,struct,sys
from pathlib import Path
sys.path.insert(0,'tools')
import object_layouts as L
out=Path(sys.argv[1]);(out/'orig').mkdir(parents=True,exist_ok=True)
SRC=Path('build/audit/source/src')
SIZE={'short':2,'unsigned short':2,'char':1,'unsigned char':1,'int':4,'unsigned int':4}
# routine -> (file, native id name). Grows as ports land (src/objects_ww_*.inc).
PORTED={
    'batta':('BATTA','BATTA'),
    'hachi6':('HACHI6','HACHI6'),
    'semi':('SEMI','SEMI'),
    'minomusi':('MINOMUSI','MINOMUSI'),
    'beem6':('BEEM6','BEEM6'),
    'dair6':('DAIR6','DAIR6'),
    'kdai6':('KDAI6','KDAI6'),
    'tobidai6':('TOBIDAI6','TOBIDAI6'),
    'block6':('BLOCK6','BLOCK6'),
    'seesaw6':('SEESAW6','SEESAW6'),
    'piston6':('PISTON6','PISTON6'),
    'sw6':('SW6','SW6'),
    'tobira6':('TOBIRA6','TOBIRA6'),
    'udblk6':('UDBLK6','UDBLK6'),
    'optbr6':('TRAP_R6','OPTBR6'),
    'eggz6':('EGG6','EGGZ6'),
    'megami':('SHOOT6','MEGAMI'),
    'gas':('SHOOT6','GAS'),
    'catapalt':('SHOOT6','CATAPALT'),
    'shooter':('SHOOT6','SHOOT6'),
    'togeball':('TOGEBL6A','TOGEBALL6'),
    'et':('ET6','ET6'),
    'movie':('MOVIE6','MOVIE6'),
    'friend':('FRIEND6','FRIEND6'),
}
def host(text):
    # PC scratch casts become offsets into actfree (46 = actfree's PC offset);
    # 32-bit views of unaligned actfree bytes go through a packed struct.
    text=re.sub(r'\(\((short|unsigned short|char|unsigned char|int|unsigned int)\*\)(&?\w+(?:\[\d+\])?)\)\[(\d+)\]',
                lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{SIZE[m[1]]*int(m[3])-46}))',text)
    text=re.sub(r'\*\(int\*\)&(\w+)->actfree\[(\d+)\]',r'(((ww_uint*)(void*)&\1->actfree[\2])->value)',text)
    return text
# Retail actor numbers the originals test or store become native ids; 68k
# behaviour the PC reconstruction leaves undefined is written out.
PATCH={
    # Act 3 indexes past the 11-entry tables (the PC reads what follows): 0.
    'FRIEND6':[('actionwk->sproffset = a1[d0];','actionwk->sproffset = d0 < 11 ? a1[d0] : 0;'),('a1->actno != 47','a1->actno != SCD_OBJ_R6_MOVIE6')],
    'ET6':[('actionwk->sproffset = a1[d0];','actionwk->sproffset = d0 < 11 ? a1[d0] : 0;')],
    'MOVIE6':[('((char**)moviewk)[12]','(*(char**)&ww_ptr[1][moviewk - actwk])'),('new_actwk->actno = 41;','new_actwk->actno = SCD_OBJ_R6_FRIEND6;'),
              ('parent->actno != 47','parent->actno != SCD_OBJ_R6_MOVIE6')],
    'TOGEBL6A':[('a1->actno != 45','a1->actno != SCD_OBJ_R6_TOGEBALL6')],
    'TOGEBL6B':[('a1->actno != 45','a1->actno != SCD_OBJ_R6_TOGEBALL6')],
    'TOGEBL6D':[('actwk[ano].actno != 45','actwk[ano].actno != SCD_OBJ_R6_TOGEBALL6')],
    'SHOOT6':[('((sprite_status**)new_actwk)[12]','(*(sprite_status**)&ww_ptr[2][new_actwk - actwk])'),
              ('((sprite_status**)gaswk)[12]','(*(sprite_status**)&ww_ptr[2][gaswk - actwk])'),
              ('((sprite_status**)catawk)[12]','(*(sprite_status**)&ww_ptr[2][catawk - actwk])'),
              ('((unsigned short**)shootwk)[16]','(*(unsigned short**)&ww_ptr[3][shootwk - actwk])'),
              ('new_actwk->actno = 4;','new_actwk->actno = SCD_OBJ_R6_CATAPALT;'),
              ('new_actwk->actno = 17;','new_actwk->actno = SCD_OBJ_LOST_RING;'),
              # Tunnel Path/Main.asm despawns idle routines; the PC source omits this call.
              ('  (int)stackpointer; ',
               '  (int)stackpointer;\n  if(shootwk->r_no0<4)frameout_s(shootwk); '),
              # ObjLauncher_Launch sets only oFlags bit 2 on this jump.
              ('    actwk[0].cddat |= 4; \n    actwk[0].cddat |= 2; ',
               '    actwk[0].cddat |= 4; ')],
    'EGG6':[('((char**)eggwk)[12]','(*(char**)&ww_ptr[1][eggwk - actwk])')],
    'PISTON6':[('a1->actno = 32;','a1->actno = SCD_OBJ_R6_PISTON6;'),('a1->actno != 32','a1->actno != SCD_OBJ_R6_PISTON6')],
    'SEESAW6':[('pActwk2->actno != 44','pActwk2->actno != SCD_OBJ_R6_SEESAW6')],
    # The 32-bit list pointer in ((char**)o)[12] moves to ww_ptr[0][actor].
    'BLOCK6':[('parent_wk->actno != 42','parent_wk->actno != SCD_OBJ_R6_BLOCK6'),
              ('((char**)blockwk)[12]','(*(char**)&ww_ptr[0][blockwk - actwk])'),
              ('((char**)new_actwk)[12]','(*(char**)&ww_ptr[0][new_actwk - actwk])')],
    # kdai6_ridechk falls off its end with ridechk's result in d0.
    # ObjSpinPlatform_GetOffset uses asr.w #4 after four adds. C division
    # truncates negative offsets toward zero instead of rounding downward.
    'KDAI6':[('  ridechk(pActwk, &actwk[0]); ','  return ridechk(pActwk, &actwk[0]); '),
             ('  iSin /= 16; ','  iSin >>= 4; ')],
    'BEEM6':[('a1->actno == 33','a1->actno == SCD_OBJ_R6_BEEM6'),('a1->actno = 33;','a1->actno = SCD_OBJ_R6_BEEM6;')],
    # The 68k ObjMinomusi_Init falls through SetWait and WaitPlayer; the PC
    # reconstruction returns after body_init. WaitPlayer also reloads 121.
    'MINOMUSI':[('a1->actno != 51','a1->actno != SCD_OBJ_R6_MINOMUSI'),
                ('  body_tbl[actionwk->r_no0 / 2](actionwk); ',
                 '  if (!actionwk->r_no0) { body_init(actionwk); if (actionwk->actno) { body_wait(actionwk); } }\n  else body_tbl[actionwk->r_no0 / 2](actionwk); '),
                ('  if (--((short*)actionwk)[23] != 0) return; ',
                 '  if (--((short*)actionwk)[23] != 0) return;\n  ((short*)actionwk)[23] = 121; ')],
    # The Sega CD ObjBouncePlatform_Bounced branch goes to Solid after a
    # successful floor-cycle check even when oSprFlags bit 7 is clear.
    # The reconstructed PC TOBIDAI6.C falls into the weak landed bounce.
    'TOBIDAI6':[('if (actionwk->actflg & 128) \n      {\n        soundset(180); \n        goto label1; \n      }\n    }\n\n    actionwk->yspeed.w = -384;',
                  'if (actionwk->actflg & 128) \n      {\n        soundset(180); \n        goto label1; \n      }\n      goto label1;\n    }\n\n    actionwk->yspeed.w = -384;')],
    # ObjBataPyon_Init falls directly into ObjBataPyon_Fall in the Sega CD
    # routine; the reconstructed PC dispatcher returns after batta_init.
    # emylr_jump falls off its end with emycol_r/l's result still in d0.
    'BATTA':[('    emycol_r(pActwk, byD3); ','    return emycol_r(pActwk, byD3); '),
             ('    emycol_l(pActwk, byD3); ','    return emycol_l(pActwk, byD3); '),
             ('  batta_tbl[pActwk->r_no0 / 2](pActwk); ',
              '  if (!pActwk->r_no0) { batta_init(pActwk); batta_down(pActwk); }\n  else batta_tbl[pActwk->r_no0 / 2](pActwk); ')],
}
prelude='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\n#include <string.h>\n#include "scd_objects.h"\n#include "ww_orig.h"\n'
def strip(t):return re.sub(r'^#include .*\n','',t,flags=re.M)
FILES=[v[0] for v in PORTED.values()]
if 'togeball' in PORTED:FILES+=['TOGEBL6B','TOGEBL6D']
for f in dict.fromkeys(FILES):
    t=(SRC/'R6'/f'{f}.C').read_text(errors='replace')
    t=re.sub(r'/\* Line \d+, Address: 0x[0-9a-f]+ \*/','',t)
    t=strip(t)
    for a,b in PATCH.get(f,[]):
        assert a in t,(f,a);t=t.replace(a,b)
    if f=='BLOCK6':
        # Retail Snake Blocks/Main.asm falls through at these labels,
        # unlike the reconstructed PC functions.
        for start,wait in (('main_init','main_move'),('sub_stop0','sub_stop01'),
                           ('sub_back','sub_back1'),('sub_stop1','sub_stop11')):
            pattern=rf'(static void {start}\(sprite_status\* blockwk\) \{{.*?)(\n\}})'
            t,n=re.subn(pattern,rf'\1\n  {wait}(blockwk);\2',t,count=1,flags=re.S)
            assert n==1,(f,start)
    if f=='SHOOT6':t=t.replace('new_actwk->actno = 5;','new_actwk->actno = SCD_OBJ_R6_GAS;')
    for m in re.finditer(r'actno\s*[!=]=\s*(\d+)',t):
        if int(m[1]) not in (0,1,24):raise SystemExit(f'{f}: unmapped actor test {m[0]}')
    left=re.findall(r'\(\((?:unsigned )?(?:short|char|int)\*+\)[^)]*\)\[',host(t))
    if left:raise SystemExit(f'{f}: unconverted scratch casts {left}')
    own=f'#include "{f}.H"\n' if (SRC/'R6'/f'{f}.H').exists() else ''
    if f.startswith('TOGEBL6'):
        # Three builds of one routine: rename each file's globals; the fixture
        # dispatches on the era (TOGEBALL.c below).
        own=''.join(f'#define {g} {g}_{f[-1].lower()}\n' for g in ('togeball','togeball_main','togeball_opt','act_init2','act_move2','pat_chg','pat_togeball'))+'#include "TOGEBL6A.H"\n'
    (out/'orig'/f'{f}.c').write_text(prelude+'#include "RIDECHK.H"\n#include "SUICIDE.H"\n'+own+host(t))
ride=strip((SRC/'RIDECHK.C').read_text())
ride=ride.replace('#if defined(R41A)','if (0)').replace('#endif','',1)
(out/'orig'/'RIDECHK.c').write_text(prelude+'#include "RIDECHK.H"\n'+host(ride))
(out/'orig'/'SUICIDE.c').write_text(prelude+'#include "SUICIDE.H"\n'+host(strip((SRC/'SUICIDE.C').read_text(errors='replace'))))
# COLI6.C pcol and its hit handlers; the fixture provides playdamageset and
# playdieset (PLAYER6 damage belongs to the player port). Scan 1..127.
coli=strip((SRC/'R6'/'COLI6.C').read_text(errors='replace'))
coli=re.sub(r'/\* Line \d+, Address: 0x[0-9a-f]+ \*/','',coli)
def cut(text,start,end):
    a=text.index(start);b=text.index(end,a);return text[:a]+text[b:]
coli=cut(coli,'void playdamagechk(','short pcolspecial(')
for a,b in (('pColliAct = &actwk[32];','pColliAct = &actwk[1];'),('for (i = 0; i < 96; ++i, ++pColliAct)','for (i = 0; i < 127; ++i, ++pColliAct)')):
    assert a in coli,a;coli=coli.replace(a,b)
(out/'orig'/'COLI6.c').write_text(prelude+'#include "COLI6.H"\nextern unsigned char CCset(int,int);\nextern unsigned char CSset(unsigned short,unsigned short);\n'+host(coli))
# BOSS_4.C random() (the shared ranum generator the R6 actors call).
b4=Path('build/probe-source/boss_4.c').read_text()
rb=b4[b4.index('int random(void) {'):];rb=rb[:rb.index('\n}')+2]
(out/'orig'/'RANDOM.c').write_text(prelude+rb)
if 'togeball' in PORTED:
    (out/'orig'/'TOGEBALL.c').write_text(prelude+'void togeball_a(sprite_status*);void togeball_b(sprite_status*);void togeball_d(sprite_status*);\n'
        '/* The Present, Past and Future programs link TOGEBL6A, B and D. */\nunsigned char ww_era;\n'
        'void togeball(sprite_status *o){if(ww_era==0)togeball_a(o);else if(ww_era==1)togeball_b(o);else togeball_d(o);}\n')
ps=(SRC/'PLAYSUB.C').read_text(errors='replace')
body=ps[ps.index('void patchg('):];depth=0
for i,c in enumerate(body):
    if c=='{':depth+=1
    elif c=='}':
        depth-=1
        if depth==0:body=body[:i+1];break
(out/'orig'/'PATCHG.c').write_text(prelude+host(body)+'\n')
T=L.act_tables();rows=[]
for act in (1,2,3):
    for x,y,kind,sub,eras,sec in struct.iter_unpack('>HHBBBB',L.layout_bytes(6,act)):
        if x==65535:break
        kind&=127;flags=y>>14;y&=4095
        for era in L.eras_of(act):
            if not (eras>>5)&L.ERA_BIT[era]:continue
            n=L.routine(T,L.table_for(T,6,act,era),kind)
            if n not in PORTED:continue
            rows.append(f'{{{act},{"ABCD".index(era)},{x},{y},SCD_OBJ_R6_{PORTED[n][1]},{sub},{flags},{sec}}}')
(out/'placements.h').write_text('static const struct{unsigned char act,era;short x,y;unsigned char type,sub,flags,sec;}placements[]={\n'+',\n'.join(rows)+'};\n')
(out/'ported.h').write_text(''.join(f'X({n},SCD_OBJ_R6_{v[1]})\n' for n,v in PORTED.items()))
print(len(rows),'placement-era records')
