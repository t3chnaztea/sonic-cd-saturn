#!/usr/bin/env python3
"""Every object type the native code can spawn has a draw priority.

src/sprite_order.h scd_ppz_priority returns -1 for a type it does not know;
src/main.c then draws it at 3 (it aborted before: the TT1 first-update hang).
This lists every spawnable type that still returns -1 for any probe view.
Spawnable: a layout type objects.c supported_types admits, any type a port
passes to tp_setactno or scd_objects_spawn by name, and every zone-local id
(136-254, priority from the view's flags)."""
import re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
h=(ROOT/'src/scd_objects.h').read_text()
ids={m[1]:int(m[2]) for m in re.finditer(r'SCD_OBJ_(\w+)=(\d+)',h)}
src=''.join(p.read_text() for p in sorted((ROOT/'src').glob('objects*.inc')))+(ROOT/'src/objects.c').read_text()
spawn=set(re.findall(r'\[SCD_OBJ_(\w+)\]=1',(ROOT/'src/objects.c').read_text()))
spawn|=set(re.findall(r'tp_setactno\([^,;]+,\s*SCD_OBJ_(\w+)\)',src))
spawn|=set(re.findall(r'scd_objects_spawn\(\s*SCD_OBJ_(\w+)',src))
spawn|=set(re.findall(r'\.type=SCD_OBJ_(\w+)',src))
# Invisible actors scd_objects_views never lists (its skip condition names them).
# Tidal Tempest slot holders: PLAWA (src/water.c draws it), SCORE and CARD.
VIEWLESS={'SPIN_TAG','TUNNEL','PLAWA','SCORE','CARD'}
views=(ROOT/'src/objects.c').read_text()
for n in VIEWLESS:assert f's->type==SCD_OBJ_{n} ||' in views or f's->type==SCD_OBJ_{n})' in views,(n,'is listed as a view')
types=sorted({ids[n] for n in spawn-VIEWLESS if n in ids}|set(range(136,255)))
c='''#include <stdio.h>
#include "sprite_order.h"
int main(void){
    static const unsigned subs[]={0,1,2,128,129,254,255},frames[]={0,1,2,8,14};
    unsigned types[]={%s};
    for(unsigned t=0;t<sizeof(types)/sizeof(*types);t++)for(unsigned s=0;s<7;s++)for(unsigned f=0;f<5;f++)for(unsigned fl=0;fl<256;fl+=16){
        scd_object_view o={0,0,(uint8_t)types[t],(uint8_t)subs[s],(uint8_t)fl,(uint8_t)frames[f]};
        if(scd_ppz_priority(o)<0){printf("%%u\\n",types[t]);break;}
    }
    return 0;
}''' % ','.join(map(str,types))
with tempfile.TemporaryDirectory() as d:
    Path(d,'t.c').write_text(c)
    subprocess.run(['clang','-std=gnu11','-Isrc','-o',f'{d}/t',f'{d}/t.c'],cwd=ROOT,check=True)
    out=subprocess.run([f'{d}/t'],capture_output=True,text=True,check=True).stdout.split()
bad=sorted({int(x) for x in out})
names={v:n for n,v in ids.items()}
if bad:
    print('FAIL: spawnable types without a draw priority:',', '.join(f'{t} ({names.get(t,"?")})' for t in bad));sys.exit(1)
print(f'PASS: draw priority for all {len(types)} spawnable types (incl. zone-local 136-254)')
