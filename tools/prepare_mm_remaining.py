#!/usr/bin/env python3
"""Prepare the remaining R8 actor routines without sprite assets.

The source functions stay in original order. Only PC scratch access, actor
allocation/draw services and native symbol names change. The comparison gate
compiles the source separately with native PC casts.
"""
import re
import argparse
from pathlib import Path
from prepare_boss import functions, adapt, ACCESSORS
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'.deps/soniccd/src/R8'

def prepare(file, prefix, selected=None):
    raw=(SOURCE/file).read_text()
    text=re.sub(r'/\*.*?\*/','',raw,flags=re.S)
    fs=functions(text)
    if selected is not None:fs={n:v for n,v in fs.items() if n in selected}
    # Keep animation scripts and dispatch tables; sprite mapping assets are
    # extracted separately. Pattern pointers are not used as behavior state.
    data=text
    for body in functions(text).values():data=data.replace(body,'')
    data=re.sub(r'^#include.*\n','',data,flags=re.M)
    data=re.sub(r'^(?:static )?sprite_pattern\s*\**\s*\w+(?:\[[^]]*\])?\s*=\s*\{.*?\};','',data,flags=re.M|re.S)
    data=re.sub(r'^(?:static )?(?:void|short|int)\s+\w+\([^;]*?\);','',data,flags=re.M)
    if selected is not None:
        data='\n'.join(re.findall(r'^static unsigned char (?:gater8|anar8)pchg[lr]\[.*?;',data,re.M|re.S))
    if file=='SCARAB.C':
        item=(SOURCE.parent/'ITEM.C').read_text()
        data=re.sub(r'extern (?:sprite_pattern|unsigned char)\* item(?:pat|chg)\[\];','',data)
        data+='\n'+item[item.index('static unsigned char itemchg0'):item.index('static sprite_pattern')]
        # SCARAB.C iteminit sets mstno to userflag.b.l, and R81 places b.l 10.
        # Retail reads ITEM.C's scripts through a word-offset table (R81A $2093B4):
        # entry 10 is script 0's first word ($0110), so the item runs the bytes at
        # table+$110: 00 00 F0 ... (pose 0, then a code that leaves it). The PC
        # source indexes past its 10 pointers instead. Keep retail's result.
        tail='unsigned char* itemchg[10] = { itemchg0, itemchg1, itemchg2, itemchg3, itemchg4, itemchg5, itemchg6, itemchg7, itemchg8, itemchg9 };'
        assert data.count(tail)==1,'ITEM.C itemchg table changed'
        data=data.replace(tail,'static unsigned char itemchg10[4] = { 0, 0, 240, 255 };\n'+tail.replace('[10]','[11]').replace('itemchg9 }','itemchg9, itemchg10 }'))
    body='\n'.join(fs.values())
    body=re.sub(r'\w+->patbase\s*=\s*\w+;', '',body)
    if file=='SCARAB.C':
        # 32-bit pointer cells live outside scratch storage on the 64-bit
        # host. Store the flag offset and animation selection in native pool
        # fields; the source comparison retains separate actual pointers.
        body=body.replace('*(unsigned char**)&pActwk->actfree[0] = &flagwork[flgwk];','pool[tp_slot(pActwk)].phase = flgwk;')
        body=body.replace('*(unsigned char**)&pActwk->actfree[0]','&tp_flagwork[pool[tp_slot(pActwk)].phase]')
        body=body.replace('((unsigned char***)pActwk)[15] = pchg_n;','pool[tp_slot(pActwk)].timer=0;').replace('((unsigned char***)pActwk)[15] = pchg_o;','pool[tp_slot(pActwk)].timer=1;')
        body=body.replace('((unsigned char***)pActwk)[15]','(pool[tp_slot(pActwk)].timer?pchg_o:pchg_n)')
    # Replace unaligned explicit long views by the indexed PC view first.
    # Also through a pointer to the actor pointer (BIGBOM8.C make_fire's (*pNewActwk)):
    # a 4-byte store at PC offset 54 is an SH-2 address error.
    body=re.sub(r'\*\(int\*\)&(\w+|\(\*\w+\))->actfree\[(\d+)\]',lambda m:f'((int*){m[1]})[{(46+int(m[2]))//4}]' if (46+int(m[2]))%4==0 else f'MMX_LONG({m[1]},{m[2]})',body)
    # These long fields can begin at byte46, unlike indexed PC int cells.
    longref=r'MMX_LONG\((\w+|\(\*\w+\)),(\d+)\)'
    body=re.sub(longref+r'\s*(\+=|\*=|=)\s*([^;]+);',lambda m:f'tp_lset({m[1]},{m[2]},'+(f'tp_l({m[1]},{m[2]}) {m[3][0]} ({m[4]})' if m[3]!='=' else m[4])+');',body)
    body=re.sub(longref,r'tp_l(\1,\2)',body)
    ref=r'\(\((?:unsigned short|short|int|unsigned char|char)\*\)(?:\w+|&actwk\[\d+\])\)\[\d+\]'
    body=re.sub(r'(--|\+\+)\(\(short\*\)(\w+)\)\[(\d+)\]',lambda m:f'mm_ws({m[2]},{m[3]},mm_w({m[2]},{m[3]}) '+('-' if m[1]=='--' else '+')+' 1)',body)
    body=re.sub('('+ref+r')\s*\*=\s*([^;]+);',lambda m:f'{m[1]} = {m[1]} * ({m[2]});',body)
    body=adapt(body)
    body=re.sub(r'(\(\*\w+\)|\w+)->actno\s*=(?!=)\s*([^;]+);',r'tp_setactno(\1,\2);',body)
    services={'actionsub':'tp_draw','frameout':'mm_remaining_frameout','frameout_s':'mm_remaining_frameout_s','frameout_s0':'mm_remaining_frameout_s0','frameout_s00':'mm_remaining_frameout_s00','actwkchk':'tp_actwkchk','actwkchk2':'tp_actwkchk2','ridechk':'tp_ridechk','ride_on_chk':'tp_ride_on_chk','ride_on_clr':'tp_ride_on_clr','hitchk':'tp_hitchk','patchg':'tt_patchg','enemy_suicide':'mm_remaining_suicide'}
    for a,b in services.items():body=re.sub(r'\b'+a+r'\b',b,body)
    body=re.sub(r'(actno\s*[!=]=\s*)47\b',r'\1SCD_OBJ_R8_SCARAB',body)
    body=re.sub(r'(actno\s*[!=]=\s*)35\b',r'\1SCD_OBJ_R8_BIGBOM',body)
    body=body.replace('tp_setactno(pActwk,25)', 'tp_setactno(pActwk,SCD_OBJ_MONITOR_ITEM)')
    body=re.sub(r'tp_setactno\((\w+),47\)',r'tp_setactno(\1,SCD_OBJ_R8_SCARAB)',body)
    body=body.replace('tp_setactno(new_actwk,55)', 'tp_setactno(new_actwk,SCD_OBJ_R8_ANAR8)')
    # Namespacing all file-local definitions allows SS and MM in one TU.
    names=set(fs)|set(re.findall(r'^(?:static )?(?:unsigned )?char\s*\**\s*(\w+)\[',data,re.M))|set(re.findall(r'\(\*(\w+)\[',data))
    both=data+'\n'+body
    for n in sorted(names,key=len,reverse=True):both=re.sub(r'\b'+n+r'\b',prefix+n,both)
    defs=functions(both)
    prototypes='\n'.join(re.sub(r'^static\s+','',b[:b.index('{')]).strip()+';' for b in defs.values())
    both=re.sub(r'^(?!static)(void|short|int)\s',r'static \1 ',both,flags=re.M)
    prototypes='\n'.join('static '+x for x in prototypes.splitlines())
    return prototypes+'\n'+both

# Retail corrections on top of the source-derived text (each cites its retail
# evidence in the emitted comment). Every anchor must occur exactly once.
SCARAB_CDSTS="""  /* SCARAB.C:252-254 with ACTSET.C:337 cdsts, the record's flagwork index:
     native placements index it by origin (tp_cdsts). A raw 0 made every
     controller share flagwork[time_flag], so one dead scarab framed out the
     next controller (retail MM1A slot 88 keeps its scarab past row 3127). */
  /* ACTSET.C actnoset sets cdsts only for a record with the saved bit
     (a & 128); an unsaved controller keeps cdsts 0 and shares
     flagwork[time_flag] (retail MM1A 3556: such a controller frames out
     with its scarab once its item is taken). */
  {unsigned n=tp_origin(pActwk);
   flgwk = (unsigned char)(n<SCD_PLACEMENT_CAPACITY && (active_placements[n].flags&TT_SAVED) ? tp_cdsts(pActwk) : 0);}"""
SCARAB_CMOVE="""  /* SCARAB.C:427 keeps only "flagwk.w == 0;". Retail R81A c_move
     $20DE04-$20DE46: with neither flag bit set and exactly one child left,
     it clears that child ($20371E, the enemy's shadow first loses bit 0) and
     drops it, so the frameout_s0 below runs (retail MM1A 3557: the item is
     taken at 3556 and the controller, enemy and shadow go next update). */
  if (flagwk.w == 0) {
    short e = SCD_GET(int16_t, pActwk, 50), it = SCD_GET(int16_t, pActwk, 52);
    if ((e != 0) != (it != 0)) {
      if (e) {
        if ((idx = SCD_GET(int16_t, &actwk[e], 54)) > 0) actwk[idx].actfree[2] &= 254;
        mm_remaining_frameout(&actwk[e]);
        SCD_SET(int16_t, pActwk, 50,  0);
      } else {
        mm_remaining_frameout(&actwk[it]);
        SCD_SET(int16_t, pActwk, 52,  0);
      }
    }
  }"""
BIGBOM_PACT1="""  /* BIGBOM8.C leaves pAct1 unset when actwkchk finds no free slot, and
     m_move6 still writes the fire speeds through it: a stale or garbage
     pointer (retail writes wherever it points). Start at NULL and skip the
     writes until a fire exists; later failures keep the previous fire, as
     retail's register does. */
  sprite_status* pAct1 = NULL;"""
def retail_fixes(out):
    for old,new in (('  flgwk = pActwk->cdsts;',SCARAB_CDSTS),('  flagwk.w == 0;',SCARAB_CMOVE),('  sprite_status* pAct1;',BIGBOM_PACT1)):
        assert out.count(old)==1,('retail fix anchor',old);out=out.replace(old,new)
    # BIGBOM8.C m_move6: no speed writes through pAct1 until a fire exists.
    body=out[out.index(BIGBOM_PACT1):]
    body=body[:body.index('\n}\n')]
    out=out.replace(body,re.sub(r'^(\s*)(tp_lset\(pAct1,)',r'\1if (pAct1) \2',body,flags=re.M))
    return out

def main():
    out='/* Generated by tools/prepare_mm_remaining.py from original R8 source. */\n'+ACCESSORS.replace('scd_pc_', 'mm_remaining_pc_')
    out+='''
/* ACTION.C frameout clears only the actor. The generic pool release also clears
   Sonic's ride/control state; these R8 services preserve the original contract. */
static void mm_remaining_frameout(sprite_status *o){sprite_status p=actwk[0];tp_frameout(o);actwk[0]=p;}
static int mm_remaining_frameout_s(sprite_status *o){sprite_status p=actwk[0];int r=tp_frameout_s(o);actwk[0]=p;return r;}
static int mm_remaining_frameout_s0(sprite_status *o){sprite_status p=actwk[0];int r=tp_frameout_s0(o);actwk[0]=p;return r;}
static int mm_remaining_frameout_s00(sprite_status *o,short x){sprite_status p=actwk[0];int r=tp_frameout_s00(o,x);actwk[0]=p;return r;}
static int mm_remaining_suicide(sprite_status *o){sprite_status p=actwk[0];int r=mm_enemy_suicide(o);actwk[0]=p;return r;}
'''
    out+=prepare('SCARAB.C','mm_sc_')
    out+=prepare('BIGBOM8.C','mm_bb_')
    out+=prepare('TRAP_R81.C','mm_an_',{'anar8','anar8_ridechk','anar8_rideclr','anar8_init','anar8_move1','anar8_move2'})
    out+='\nstatic void mm_gater8(sprite_status *o){mm_remaining_frameout(o);} /* TRAP_R82.C gater8. */\n#undef SCD_GET\n#undef SCD_SET\n'
    out=re.sub(r'\n\s*\n\s*\n','\n\n',out)
    out='\n'.join(line.rstrip() for line in out.splitlines())+'\n'
    out=retail_fixes(out)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    path=ROOT/'src/objects_mm_remaining.inc'
    if args.check:
        assert path.read_text()==out,'remaining MM actors are stale'
        print('PASS: four MM actor routines match the source-derived include')
    else:path.write_text(out)
if __name__=='__main__':main()
