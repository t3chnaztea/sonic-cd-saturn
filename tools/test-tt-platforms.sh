#!/bin/bash
# Compiled R4 originals (UDBLK4 ... TEKKYU1 + RIDECHK.C) versus the native
# objects_tt_platforms.inc actors, for every Tidal Tempest placement of those
# routines in every era of Acts 1 and 2: motion, a player-contact grid around
# every live piece, and carried rides. See tools/tt_platforms_test.c.
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/tt/platforms
mkdir -p "$out/orig"
report_inputs='src/objects_tt_platforms.inc src/objects_tt_ride.inc src/objects.c src/scd_objects.h tools/tt_platforms_test.c tools/test-tt-platforms.sh tools/object_layouts.py build/audit/source/src/RIDECHK.C build/audit/source/src/R4/HARIR4.C build/audit/source/src/R4/COLI4.C'
python3 - "$out" $report_inputs <<'PY'
from pathlib import Path
import json,hashlib,datetime,sys
p=Path(sys.argv[1])/'report.json'
r=dict(passed=False,status='pending',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
       inputs={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in sys.argv[2:]})
p.write_text(json.dumps(r,indent=2)+'\n')
PY
finish_report() {
    local result=$?
    python3 - "$out" "$result" <<'PY'
from pathlib import Path
import json,sys
p=Path(sys.argv[1])/'report.json';r=json.loads(p.read_text())
code=int(sys.argv[2])
if code:r.update(passed=False,status='interrupted' if code in (130,143) else 'failed',exit_code=code)
elif r['status']=='pending':r.update(passed=True,status='passed',result=(Path(sys.argv[1])/'result.txt').read_text().strip())
p.write_text(json.dumps(r,indent=2)+'\n')
PY
}
trap finish_report EXIT
python3 - "$out" <<'PY'
from pathlib import Path
import re,sys,struct
sys.path.insert(0,'tools')
out=Path(sys.argv[1])
SRC=Path('build/audit/source/src')
FILES=['UDBLK4','LRBLK4','RBLK4','ESCAL4','BRUNKO4','RENKETU4','KUZURE4','DAID4','BANEIWA','SW4','SWBLK4',
       'SWGUN4','TOBIRA4','TOBIRAS4','WALLS','WALL42','TEKKYU','TEKKYU4','TEKKYU1','HARIR4']
SIZE={'short':2,'unsigned short':2,'char':1,'unsigned char':1,'int':4,'unsigned int':4}
def host(text):
    # PC scratch casts become offsets into actfree (46 = actfree's PC offset).
    text=re.sub(r'\(\((short|unsigned short|char|unsigned char|int|unsigned int)\*\)(\w+)\)\[(\d+)\]',
                lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{SIZE[m[1]]*int(m[3])-46}))',text)
    return text
PATCH={
 'TOBIRAS4':[# Retail R42A adds the speed here (TT2A row 5339; src tobiras4_act_down).
             ('pActwk->yposi.l -= ((int*)pActwk)[12]; /* Line 149','pActwk->yposi.l += ((int*)pActwk)[12]; /* Line 149'),
             # Retail R42A $20CFBE act_down: subq.w #1 then bmi to frameout (TT2A row 5466).
             ('  if (((short*)pActwk)[23] < 0) /* Line 143','  if (--((short*)pActwk)[23] < 0) /* Line 143'),
             ('  --((short*)pActwk)[23]; /* Line 148','  /* Line 148'),
             ('((unsigned char**)pActwk)[13] = p;','*(int*)((char*)pActwk->actfree+6) = (int)(p - switchflag);'),
             ('p = ((unsigned char**)pActwk)[13];','p = switchflag + *(int*)((char*)pActwk->actfree+6);')],
 'WALL42':[('a1 = ((unsigned char**)pActwk)[12];','a1 = flagwork + *(int*)((char*)pActwk->actfree+2);'),
           ('((unsigned char**)pActwk)[12] = a1;','*(int*)((char*)pActwk->actfree+2) = index;'),
           # Retail R42A__.MMD $EFF4-$F02C (src/objects_tt_platforms.inc wall42): the
           # timers decrement first and advance at 0; the push speed is 0x8000 >> 8.
           ('  if (((short*)pActwk)[23] == -1) /* Line 114','  --((short*)pActwk)[23]; if (((short*)pActwk)[23] == 0) /* Line 114'),
           ('  --((short*)pActwk)[23]; /* Line 119','  /* Line 119'),
           ('d0 <<= 8; /* Line 132','d0 >>= 8; /* Line 132'),
           ('  if (((short*)pActwk)[23] == -1) /* Line 136','  --((short*)pActwk)[23]; if (((short*)pActwk)[23] == 0) /* Line 136'),
           ('  --((short*)pActwk)[23]; /* Line 140','  /* Line 140'),
           # Retail $F04E: cmpi.w #640,d0; bls (unsigned): passed walls frame out.
           ('  if (d0 > 640) /* Line 69','  if ((unsigned short)d0 > 640) /* Line 69')],
 'ESCAL4':[('  hitchk(pActwk, &actwk[0]);','  return hitchk(pActwk, &actwk[0]);'),
           # Retail R42A $20C9C6: cmpi.w #640,d0; bhi (unsigned).
           ('  if ((pActwk->xposi.w.h & 65408) - ((scra_h_posit.w.h - 128) & 65408) <= 640) return; /* Line 82',
            '  if ((unsigned short)((pActwk->xposi.w.h & 65408) - ((scra_h_posit.w.h - 128) & 65408)) <= 640) return; /* Line 82')],
}
prelude='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\n#include <string.h>\n#include "tt_orig.h"\n'
for f in FILES:
    t=(SRC/'R4'/f'{f}.C').read_text(errors='replace')
    t=re.sub(r'^#include .*\n','',t,flags=re.M)
    for a,b in PATCH.get(f,[]):
        assert a in t,(f,a);t=t.replace(a,b)
    own=f'#include "{f}.H"\n' if (SRC/'R4'/f'{f}.H').exists() else ''
    (out/'orig'/f'{f}.c').write_text(prelude+'#include "RIDECHK.H"\n'+own+host(t))
ride=(SRC/'RIDECHK.C').read_text()
ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
ride=ride.replace('#if defined(R41A)','if (stageno.b.l == 0 && time_flag == 1)').replace('#endif','',1)
ride=ride.replace('if (stageno.b.l == 0 && time_flag == 1)\n    if','if (stageno.b.l == 0 && time_flag == 1)\n    if',1)
(out/'orig'/'RIDECHK.c').write_text(prelude+'#include "RIDECHK.H"\n'+host(ride))
# COLI4.C pcol and its hit handlers (the fixture provides playdamageset,
# PLAYER.C playdamagechk/playdieset come from build/probe-source). The fixture
# places the routine in actor 1 and children from actor 32: scan 1..127.
coli=(SRC/'R4'/'COLI4.C').read_text(errors='replace')
coli=re.sub(r'^#include .*\n','',coli,flags=re.M).replace('extern short actwkchk(sprite_status** ppActwk);\n','')
coli=coli[:coli.index('void playdamagechk(')]+coli[coli.index('short pcolspecial('):]
for a,b in (('pColliAct = &actwk[32];','pColliAct = &actwk[1];'),('for (i = 0; i < 96; ++i, ++pColliAct)','for (i = 0; i < 127; ++i, ++pColliAct)')):
    assert a in coli,a;coli=coli.replace(a,b)
(out/'orig'/'COLI4.c').write_text(prelude+'#include "COLI4.H"\nextern void plairset(void);\nextern unsigned char CCset(unsigned short,unsigned short);\nextern unsigned char CSset(unsigned short,unsigned short);\n'+host(coli))
ps=(SRC/'R4'/'PLAYSUB4.C').read_text(errors='replace')
body=ps[ps.index('void patchg('):]
depth=0
for i,c in enumerate(body):
    if c=='{':depth+=1
    elif c=='}':
        depth-=1
        if depth==0:body=body[:i+1];break
(out/'orig'/'PATCHG.c').write_text(prelude+host(body)+'\n')
# Every placement of the ported routines, per act and era.
import object_layouts as L
lay=L.all_layouts()
TYPES={99,102,103,106,107,108,109,110,111,112,113,115,116,117,118,121,123,124,125}
rows=[]
for act in (1,2):
    for e in lay[(4,act)][0]:
        x,y,t,s,f,eras=e[:6];sec=e[6] if len(e)>6 else 0
        if t not in TYPES:continue
        for era,bit in ((0,2),(1,1),(2,4),(3,4)):
            if eras&bit:rows.append(f'{{{act},{era},{x},{y},{t},{s},{f},{sec}}}')
# Routine subtypes no layout places still run on a placed record's spot.
base={}
for r in list(rows):
    a,e,x,y,ty=[int(v) for v in r.strip('{}').split(',')[:5]]
    base.setdefault(ty,(a,x,y))
for ty,subs in ((106,range(12)),(113,range(9))):
    a,x,y=base[ty]
    for s in subs:
        for era in (0,2):rows.append(f'{{{a},{era},{x},{y},{ty},{s},0,0}}')
(out/'placements.h').write_text('static const struct{unsigned char act,era;short x,y;unsigned char type,sub,flags,sec;}placements[]={\n'+',\n'.join(rows)+'};\n')
print(len(rows),'placement-era cases')
PY
cat > "$out/orig/tt_orig.h" <<'H'
/* Retail helpers the R4 originals call, provided by tools/tt_platforms_test.c. */
extern void actionsub(sprite_status*);
extern void frameout(sprite_status*);
extern int frameout_s(sprite_status*);
extern int frameout_s0(sprite_status*);
extern int frameout_s00(sprite_status*,short);
extern int actwkchk(sprite_status**);
extern int actwkchk2(sprite_status*,sprite_status**);
extern void soundset(short);
extern void scoreup(unsigned int);
extern void ringgetsub(void);
extern void patchg(sprite_status*,unsigned char**);
extern void speedset2(sprite_status*);
extern short playdieset(sprite_status*);
extern short scdchk(sprite_status*,short,short,short,short,short,char*);
extern short emycol_d(sprite_status*);
extern short emycol_u(sprite_status*);
extern short playdamageset(sprite_status*,sprite_status*);
#define sMemCpy(d,s,n) memcpy(d,s,n)
H
flags="-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-return-type -Wno-incompatible-pointer-types -Wno-int-conversion -Isrc -Iassets/generated -Ibuild/probe-source -Ibuild/audit/source/src/R4 -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize=shift -fno-sanitize-recover=all"
objs=()
for f in "$out"/orig/*.c; do
    o="${f%.c}.o"
    clang $flags -I"$out/orig" -c "$f" -o "$o" >>"$out/build.log" 2>&1 || { tail -n 30 "$out/build.log"; exit 1; }
    objs+=("$o")
done
clang $flags -DSCD_HOST_TEST -I"$out" tools/tt_platforms_test.c "${objs[@]}" \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
"$out/test" | tee "$out/result.txt"
