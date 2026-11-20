#!/bin/bash
# Compiled R5 originals (DENDEN ... KOWASI5 + RIDECHK.C, COLI5.C pcol,
# SUICIDE.C, PLAYSUB.C patchg) versus the native objects_qq_*.inc actors for
# every Quartz Quadrant placement of those routines in every era of Acts 1-3:
# motion, a chase around the actor, a player-contact grid around every live
# piece, a carried/followed player, and frameout. See tools/qq_actors_test.c.
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/qq/actors
mkdir -p "$out/orig" build/qq/host
report_inputs='src/objects_qq.inc src/objects_qq_common.inc src/objects_qq_enemies.inc src/objects_qq_hazards.inc src/objects_qq_platforms.inc src/objects_qq_story.inc src/objects_tt_ride.inc src/objects_tt_friends.inc src/objects.c src/scd_objects.h tools/qq_actors_test.c tools/test-qq-actors.sh tools/qq_host_objects.py tools/object_layouts.py build/audit/source/src/RIDECHK.C build/audit/source/src/R5/COLI5.C build/audit/source/src/SUICIDE.C build/audit/source/src/PLAYSUB.C'
for f in DENDEN SASORI KEMUSI KUMO IWA5 HARI5F HARIR5 IWA5ROLL KUZURE5 IWA5WAVE BURANKO5 HASIRA5 HASHI5 BELTSW5 SHOOT5 MOVIE5 FRIEND5 ET5 KOWASI5; do
    report_inputs="$report_inputs build/audit/source/src/R5/$f.C"
done
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
python3 tools/qq_host_objects.py build/qq/host
python3 - "$out" <<'PY'
from pathlib import Path
import re,sys,struct
sys.path.insert(0,'tools')
out=Path(sys.argv[1])
SRC=Path('build/audit/source/src')
SIZE={'short':2,'unsigned short':2,'char':1,'unsigned char':1,'int':4,'unsigned int':4}
def host(text):
    # PC scratch casts become offsets into actfree (46 = actfree's PC offset);
    # 32-bit views of unaligned actfree bytes go through a packed struct.
    text=re.sub(r'\(\((short|unsigned short|char|unsigned char|int|unsigned int)\*\)(&?\w+(?:\[\d+\])?)\)\[(\d+)\]',
                lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{SIZE[m[1]]*int(m[3])-46}))',text)
    text=re.sub(r'\*\(int\*\)&(\w+)->actfree\[(\d+)\]',r'(((qq_uint*)(void*)&\1->actfree[\2])->value)',text)
    return text
ID={'DENDEN':32,'SASORI':33,'KEMUSI':34,'IWA5ROLL':39,'IWA5WAVE':41,'BURANKO5':42,'MOVIE5':44,'FRIEND5':45,'HASHI5':47}
# Actor numbers the originals test or store become the native ids; the
# 32-bit PC pointers kept in scratch move to per-actor arrays (qq_orig.h).
PATCH={
 'DENDEN':[('pMainwk->actno != 32','pMainwk->actno != SCD_OBJ_R5_DENDEN')],
 'SASORI':[('pMainwk->actno != 33','pMainwk->actno != SCD_OBJ_R5_SASORI')],
 'KEMUSI':[('pActwk1->actno != 34 || pActwk2->actno != 34 || pActwk3->actno != 34','pActwk1->actno != SCD_OBJ_R5_KEMUSI || pActwk2->actno != SCD_OBJ_R5_KEMUSI || pActwk3->actno != SCD_OBJ_R5_KEMUSI'),
           ('((short*)((char*)pActwk + i))[23]','(*(short*)((char*)pActwk->actfree + i))')],
 'KUMO':[('((unsigned char***)pActwk)[12] = pchg_e;','qq_ptr12[pActwk - actwk] = (void*)pchg_e;'),
         ('((unsigned char***)pActwk)[12] = pchg_b;','qq_ptr12[pActwk - actwk] = (void*)pchg_b;'),
         ('patchg(pActwk, ((unsigned char***)pActwk)[12]);','patchg(pActwk, (unsigned char**)qq_ptr12[pActwk - actwk]);'),
         # Retail R52B kumo_check: subi/bcc unsigned range tests (src kumo_act, 8d1cbe6).
         ('if (pActwk1->yposi.w.h - pActwk0->yposi.w.h + 80 < 160) { /* Line 283','if ((unsigned short)(pActwk1->yposi.w.h - pActwk0->yposi.w.h + 80) < 160) { /* Line 283'),
         ('if (wD0 + 80 < 160) { /* Line 286','if ((unsigned short)(wD0 + 80) < 160) { /* Line 286')],
 'IWA5ROLL':[('.actno != 39','.actno != SCD_OBJ_R5_IWA5ROLL')],
 'IWA5WAVE':[('pMainwk->actno == 41','pMainwk->actno == SCD_OBJ_R5_IWA5WAVE'),
             # Retail R52C $20E47A: swap d1 leaves the x step's high word in the
             # sine fraction (src iwa5wave_act, 114700d).
             ('ld1.w.l = 0; /* Line 160','ld1.w.l = (unsigned short)((unsigned int)d1 >> 16); /* Line 160')],
 'BURANKO5':[('actwk[pActwk->actfree[0]].actno == 42','actwk[pActwk->actfree[0]].actno == SCD_OBJ_R5_BURANKO5')]*1,
 'HARI5F':[('*(int*)((char*)&pActwk->actfree[0])','(((qq_uint*)(void*)&pActwk->actfree[0])->value)')],
 'MOVIE5':[('pMainwk->actno != 44','pMainwk->actno != SCD_OBJ_R5_MOVIE5'),('pNewact->actno = 45;','pNewact->actno = SCD_OBJ_R5_FRIEND5;'),
           ('((char**)pActwk)[12]','qq_cur12[pActwk - actwk]')],
 'FRIEND5':[('pMoviewk->actno != 44','pMoviewk->actno != SCD_OBJ_R5_MOVIE5')],
 'ET5':[('((char**)pActwk)[12]','qq_cur12[pActwk - actwk]')],
 'HASHI5':[('pNewactwk->actno = 47;','pNewactwk->actno = SCD_OBJ_R5_HASHI5;'),('.actno != 47','.actno != SCD_OBJ_R5_HASHI5')],
 'SHOOT5':[('((short**)pActwk)[16]','qq_ptr16[pActwk - actwk]')],
}
prelude='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\n#include <string.h>\n#include "scd_objects.h"\n#include "qq_ids.h"\n#include "qq_orig.h"\n'
FILES=['DENDEN','SASORI','KEMUSI','KUMO','IWA5','HARI5F','HARIR5','IWA5ROLL','KUZURE5','IWA5WAVE','BURANKO5','HASIRA5','HASHI5','BELTSW5','SHOOT5','MOVIE5','FRIEND5','ET5','KOWASI5']
for f in FILES:
    t=(SRC/'R5'/f'{f}.C').read_text(errors='replace')
    t=re.sub(r'^#include .*\n','',t,flags=re.M)
    for a,b in PATCH.get(f,[]):
        assert a in t,(f,a);t=t.replace(a,b)
    # Unpatched numeric actor tests would compare against R5 ids.
    for m in re.finditer(r'actno\s*[!=]=\s*(\d+)',t):
        if int(m[1]) not in (0,1,24):raise SystemExit(f'{f}: unmapped actor test {m[0]}')
    left=re.findall(r'\(\((?:unsigned )?(?:short|char|int)\*+\)[^)]*\)\[',host(t))
    if left:raise SystemExit(f'{f}: unconverted scratch casts {left}')
    own=f'#include "{f}.H"\n' if (SRC/'R5'/f'{f}.H').exists() else ''
    (out/'orig'/f'{f}.c').write_text(prelude+'#include "RIDECHK.H"\n#include "SUICIDE.H"\n'+own+host(t))
ride=(SRC/'RIDECHK.C').read_text()
ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
ride=ride.replace('#if defined(R41A)','if (0)').replace('#endif','',1)
(out/'orig'/'RIDECHK.c').write_text(prelude+'#include "RIDECHK.H"\n'+host(ride))
sui=(SRC/'SUICIDE.C').read_text(errors='replace')
sui=re.sub(r'^#include .*\n','',sui,flags=re.M)
(out/'orig'/'SUICIDE.c').write_text(prelude+'#include "SUICIDE.H"\n'+host(sui))
# COLI5.C pcol and its hit handlers (the fixture provides playdamageset;
# PLAYER.C playdamagechk/playdieset come from build/probe-source). The fixture
# places the routine in actor 1 and children from actor 32: scan 1..127.
coli=(SRC/'R5'/'COLI5.C').read_text(errors='replace')
coli=re.sub(r'^#include .*\n','',coli,flags=re.M).replace('extern short actwkchk(sprite_status** ppActwk);\n','')
coli=coli[:coli.index('void playdamagechk(')]+coli[coli.index('short pcolspecial('):]
for a,b in (('pColliAct = &actwk[32];','pColliAct = &actwk[1];'),('for (i = 0; i < 96; ++i, ++pColliAct)','for (i = 0; i < 127; ++i, ++pColliAct)')):
    assert a in coli,a;coli=coli.replace(a,b)
(out/'orig'/'COLI5.c').write_text(prelude+'#include "COLI5.H"\nextern unsigned char CCset(int,int);\nextern unsigned char CSset(unsigned short,unsigned short);\n'+host(coli))
ps=(SRC/'PLAYSUB.C').read_text(errors='replace')
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
T=L.act_tables()
NAMES={'denden':'DENDEN','sasori':'SASORI','kemusi':'KEMUSI','kumo':'KUMO','iwa5':'IWA5','hari5f':'HARI5F','harir5':'HARIR5',
       'iwa5roll':'IWA5ROLL','kuzure5':'KUZURE5','iwa5wave':'IWA5WAVE','buranko5':'BURANKO5','hasira5':'HASIRA5','hashi5':'HASHI5',
       'beltsw5':'BELTSW5','shooter':'SHOOT5','movie':'MOVIE5','friend':'FRIEND5','et':'ET5','kowasi':'KOWASI5'}
rows=[];seen=set()
for act in (1,2,3):
    for x,y,kind,sub,eras,sec in struct.iter_unpack('>HHBBBB',L.layout_bytes(5,act)):
        if x==65535:break
        kind&=127;flags=y>>14;y&=4095
        for era in L.eras_of(act):
            if not (eras>>5)&L.ERA_BIT[era]:continue
            n=L.routine(T,L.table_for(T,5,act,era),kind)
            if n not in NAMES:continue
            e='ABCD'.index(era)
            rows.append(f'{{{act},{e},{x},{y},SCD_OBJ_R5_{NAMES[n]},{sub},{flags},{sec}}}')
# KOWASI5 has no placement in any act; run it on a placed ledge's spot,
# both subtypes' patterns and the flipped one.
for s in (0,1,2):
    for e in (0,1,2):rows.append(f'{{1,{e},2432,752,SCD_OBJ_R5_KOWASI5,{s},0,0}}')
(out/'placements.h').write_text('static const struct{unsigned char act,era;short x,y;unsigned char type,sub,flags,sec;}placements[]={\n'+',\n'.join(rows)+'};\n')
print(len(rows),'placement-era records')
PY
cat > "$out/orig/qq_orig.h" <<'H'
/* Retail helpers the R5 originals call, provided by tools/qq_actors_test.c. */
typedef struct __attribute__((packed)){int value;}qq_uint;
extern void *qq_ptr12[128];extern short *qq_ptr16[128];extern char *qq_cur12[128];
extern void actionsub(sprite_status*);
extern void frameout(sprite_status*);
extern int frameout_s(sprite_status*);
extern int frameout_s0(sprite_status*);
extern int frameout_s00(sprite_status*,short);
extern int actwkchk(sprite_status**);
extern int actwkchk2(sprite_status*,sprite_status**);
extern void soundset(short);
extern void scoreup(unsigned int);
extern void patchg(sprite_status*,unsigned char**);
extern short playdieset(sprite_status*);
extern short emycol_d(sprite_status*);
extern short emycol_d3(sprite_status*,short,short);
extern short playdamageset(sprite_status*,sprite_status*);
extern void sinset(unsigned char,short*,short*);
#define sMemCpy(d,s,n) memcpy(d,s,n)
H
flags="-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-return-type -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-implicit-function-declaration -Isrc -Ibuild/qq/host -Iassets/generated -Ibuild/probe-source -Ibuild/audit/source/src/R5 -Ibuild/audit/source/src -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize=shift -fno-sanitize-recover=all ${QQ_CFLAGS:-}"
: >"$out/build.log"
objs=()
for f in "$out"/orig/*.c; do
    o="${f%.c}.o"
    clang $flags -I"$out/orig" -c "$f" -o "$o" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
    objs+=("$o")
done
clang $flags -DSCD_HOST_TEST -I"$out" -I"$out/orig" tools/qq_actors_test.c "${objs[@]}" \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c build/qq/host/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
"$out/test" | tee "$out/result.txt"
