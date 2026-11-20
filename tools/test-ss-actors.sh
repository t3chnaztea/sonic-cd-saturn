#!/bin/bash
# Compiled R7 originals (EMIE7/EMIE7CG, HARI73, WALL73, GAITOU73 ... +
# RIDECHK.C, COLI7.C pcol, SUICIDE.C, PLAYSUB.C explosion/flower/patchg, SCORE.C points) versus the native
# objects_ss_*.inc actors for every Stardust Speedway placement of those
# routines in every era of Acts 1-3: motion, a chase around the actor, a
# player-contact grid around every live piece, a carried/followed player, and
# frameout. See tools/ss_actors_test.c.
set -euo pipefail
cd "$(dirname "$0")/.."
# The R7 routine files under test (EMIE7CG.C holds EMIE7.C's patterns and scripts;
# MOVIE7 spawns FRIEND7 animals).
SS_FILES='EMIE7 EMIE7CG HARI73 WALL73 GAITOU73 CHGBAN SLIGHT7 CHGWALL7 TEKKYU7 TEKKYU7J HOTARU7 KABASIRA KANABUN DANGO7 BRANKO7 FRIEND7 ET7 MOVIE7'
out=build/ss/actors
mkdir -p "$out/orig" build/ss/host
report_inputs='src/objects_ss.inc src/objects_ss_common.inc src/objects_ss_act3.inc src/objects_ss_chgban.inc src/objects_ss_gimmick.inc src/objects_ss_enemies.inc src/objects_ss_story.inc src/objects_tt_ride.inc src/objects_tt_common.inc src/objects.c src/scd_objects.h src/objects_zone_ops.inc tools/ss_actors_test.c tools/test-ss-actors.sh tools/ss_host_objects.py tools/object_layouts.py build/audit/source/src/RIDECHK.C build/audit/source/src/R7/COLI7.C build/audit/source/src/SUICIDE.C build/audit/source/src/PLAYSUB.C build/audit/source/src/SCORE.C build/audit/source/src/TBL1.C src/objects_tt_enemies.inc'
for f in $SS_FILES; do
    report_inputs="$report_inputs build/audit/source/src/R7/$f.C"
done
for f in build/auto-extract/7/objects*.bin; do
    report_inputs="$report_inputs $f"
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
python3 tools/ss_host_objects.py build/ss/host
python3 - "$out" $SS_FILES <<'PY'
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
PATCH={
 'HARI73':[('pNewactwk->actno = 50;','pNewactwk->actno = SCD_OBJ_R7_HARI73;')],
 # Retail R73C $20F1CC confirmed dakicheck: PC line501 reverses facing.
 # Shared correction is tested against retail routes, not by this cast oracle.
 # R73D $20F02E also clears wait bit2 after the distance stop block.
 'EMIE7':[('    }\n  }\n\n\n  spdwk = -32; /* Line 270',
           '    }\n    pActwk->actfree[20] &= 251; /* Retail wait flag release. */\n  }\n\n\n  spdwk = -32; /* Line 270'),('if (actwk[0].cddat & 1) { /* Line 501, Address: 0x10234a8 */',
           'if (!(actwk[0].cddat & 1)) { /* Retail facing test. */'),('pActwk->actno != 51','pActwk->actno != SCD_OBJ_R7_EMIE7'),('pHeartact->actno = 52;','pHeartact->actno = SCD_OBJ_R7_HEART7;')],
 'GAITOU73':[('pNewact->actno = 54;','pNewact->actno = SCD_OBJ_R7_GAITOU73;')],
 'HOTARU7':[('pMainact->actno != 35','pMainact->actno != SCD_OBJ_R7_HOTARU7'),('pBact1->actno != 35 || pBact2->actno != 35','pBact1->actno != SCD_OBJ_R7_HOTARU7 || pBact2->actno != SCD_OBJ_R7_HOTARU7'),
   ('*(unsigned char**)&pActwk->actfree[0] = &flagwork[idx];','ss_ptr0[pActwk - actwk] = &flagwork[idx];'),
   ('*(short**)&pActwk->actfree[4] = &tbl_hotaru7[idx / 2];','ss_ptr4[pActwk - actwk] = &tbl_hotaru7[idx / 2];'),
   ('pFlagWork = *(unsigned char**)&pActwk->actfree[0];','pFlagWork = (unsigned char*)ss_ptr0[pActwk - actwk];'),
   ('pTbl = *(short**)&pActwk->actfree[4];','pTbl = (short*)ss_ptr4[pActwk - actwk];'),
   ('*(unsigned char***)&pActwk->actfree[8] = pchg_hotaru7_e;','ss_ptr8[pActwk - actwk] = pchg_hotaru7_e;'),
   ('*(unsigned char***)&pActwk->actfree[8] = pchg_hotaru7_b;','ss_ptr8[pActwk - actwk] = pchg_hotaru7_b;'),
   ('patchg(pActwk, *(unsigned char***)&pActwk->actfree[8]);','patchg(pActwk, (unsigned char**)ss_ptr8[pActwk - actwk]);')],
 'KABASIRA':[('pMainact->actno == 34','pMainact->actno == SCD_OBJ_R7_KABASIRA')],
 'KANABUN':[('*(unsigned char***)&pActwk->actfree[12] = pchg_e;','ss_ptr8[pActwk - actwk] = pchg_e;'),('*(unsigned char***)&pActwk->actfree[12] = pchg_b;','ss_ptr8[pActwk - actwk] = pchg_b;'),
   ('patchg(pActwk, *(unsigned char***)&pActwk->actfree[12]);','patchg(pActwk, (unsigned char**)ss_ptr8[pActwk - actwk]);')],
 'BRANKO7':[('pNewact->actno = 32;','pNewact->actno = SCD_OBJ_R7_BRANKO7;')],
 'MOVIE7':[('actwk[subact].actno != 39','actwk[subact].actno != SCD_OBJ_R7_MOVIE7'),('subactwk->actno = 40;','subactwk->actno = SCD_OBJ_R7_FRIEND7;'),
   ('((char**)pActwk)[12]','ss_cur12[pActwk - actwk]')],
 'FRIEND7':[('tempact->actno != 39','tempact->actno != SCD_OBJ_R7_MOVIE7')],
 'ET7':[('((char**)pActwk)[12]','ss_cur12[pActwk - actwk]')],
 # Retail R71A-R72D slight7 masks with 3 and 1 (R71A init $20F616, move
 # $20F66A-$20F68A); PC SLIGHT7.C masks with 6 and 2.
 'SLIGHT7':[('pActwk->actfree[6] = pActwk->userflag.b.l & 6;','pActwk->actfree[6] = pActwk->userflag.b.l & 3;'),
   ('bD0 = gametimer.w & 6;','bD0 = gametimer.w & 3;'),('if (pActwk->actfree[6] == (bD0 & 2)) {','if (pActwk->actfree[6] == (bD0 & 1)) {')],
 'CHGBAN':[('pNewact->actno = 30;','pNewact->actno = SCD_OBJ_R7_SPRING_R;'),('pNewact->actno = 8;','pNewact->actno = SCD_OBJ_R7_GUN7;'),('pNewact->actno = 9;','pNewact->actno = SCD_OBJ_R7_HIBANA7;')],
}
prelude='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\n#include <string.h>\n#include "scd_objects.h"\n#include "ss_ids.h"\n#include "ss_orig.h"\n'
FILES=sys.argv[2:]
for f in FILES:
    t=(SRC/'R7'/f'{f}.C').read_text(errors='replace')
    t=re.sub(r'^#include .*\n','',t,flags=re.M)
    for a,b in PATCH.get(f,[]):
        assert a in t,(f,a);t=t.replace(a,b)
    for m in re.finditer(r'actno\s*[!=]=\s*(\d+)',t):
        if int(m[1]) not in (0,1,24):raise SystemExit(f'{f}: unmapped actor test {m[0]}')
    own=f'#include "{f}.H"\n' if (SRC/'R7'/f'{f}.H').exists() else ''
    (out/'orig'/f'{f}.c').write_text(prelude+'#include "RIDECHK.H"\n#include "SUICIDE.H"\n'+own+host(t))
ride=(SRC/'RIDECHK.C').read_text()
ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
ride=ride.replace('#if defined(R41A)','if (0)').replace('#endif','',1)
(out/'orig'/'RIDECHK.c').write_text(prelude+'#include "RIDECHK.H"\n'+host(ride))
sui=(SRC/'SUICIDE.C').read_text(errors='replace')
sui=re.sub(r'^#include .*\n','',sui,flags=re.M)
(out/'orig'/'SUICIDE.c').write_text(prelude+'#include "SUICIDE.H"\n'+host(sui))
# COLI7.C pcol and its hit handlers (the fixture provides playdamageset;
# PLAYER.C playdamagechk/playdieset come from build/probe-source). The fixture
# places the routine in actor 1 and children from actor 32: scan 1..127.
coli=(SRC/'R7'/'COLI7.C').read_text(errors='replace')
coli=re.sub(r'^#include .*\n','',coli,flags=re.M).replace('extern short actwkchk(sprite_status** ppActwk);\n','')
coli=coli[:coli.index('void playdamagechk(')]+coli[coli.index('short pcolspecial('):]
for a,b in (('pColliAct = &actwk[32];','pColliAct = &actwk[1];'),('for (i = 0; i < 96; ++i, ++pColliAct)','for (i = 0; i < 127; ++i, ++pColliAct)')):
    assert a in coli,a;coli=coli.replace(a,b)
(out/'orig'/'COLI7.c').write_text(prelude+'#include "COLI7.H"\nextern unsigned char CCset(int,int);\nextern unsigned char CSset(unsigned short,unsigned short);\n'+host(coli))
ps=(SRC/'PLAYSUB.C').read_text(errors='replace')
def function(text, name):
    m=re.search(r'(?:static )?(?:void|short|unsigned char\*) '+name+r'\([^;{}]*\)\s*\{',text)
    assert m,name
    start=m.start();brace=m.end()-1;depth=1;i=brace+1
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}');i+=1
    return text[start:i]+'\n'
# Compile the original actor lifecycle, including its children, rather than
# replacing dead enemies with inert fixture placeholders.
patterns=ps[ps.index('static unsigned char flowchg0'):ps.index('void patchg(')]
tbl=(SRC/'TBL1.C').read_text(errors='replace')
patterns+=tbl[tbl.index('static unsigned char baku_chg0'):tbl.index('static unsigned char mkchg')]
names=['patchg','tensuu_set','tensuu0','bakuha','baku_init','baku_move','baku_die','flower','flow_init','flow_move0','flow_move1','flow_sub','flow_sub1','flow_move2','flow_move3']
body=''.join(function(ps,n) for n in names)
score=(SRC/'SCORE.C').read_text(errors='replace')
# SCORE.C's high-userflag path dispatches these three original functions.
body+='\nstatic void ten_init(sprite_status*);static void ten_move(sprite_status*);\n'
body+='sprite_pattern *tenpat[16];\n'
body+=''.join(function(score,n) for n in ['tensuu','ten_init','ten_move'])
body+='void ss_original_points(sprite_status *o){tensuu(o); }\n'
(out/'orig'/'PATCHG.c').write_text(prelude+'#include "PLAYSUB.H"\n'+patterns+host(body))
# Every placement of the ported routines, per act and era.
import object_layouts as L
T=L.act_tables();PORTS=L.port_types(T);DEFS=L.definitions()
NAMES={'emie7':'EMIE7','hari73':'HARI73','wall73':'WALL73','gaitou73':'GAITOU73','chgban':'CHGBAN','spring_r':'SPRING_R','gun7':'GUN7','slight7':'SLIGHT7','chgwall7':'CHGWALL7','tekkyu7':'TEKKYU7','tekkyu7j':'TEKKYU7J','hotaru7':'HOTARU7','kabasira':'KABASIRA','kanabun':'KANABUN','dango':'DANGO7','branko7':'BRANKO7','friend':'FRIEND7','et':'ET7','movie':'MOVIE7'}
rows=[]
for act in (1,2,3):
    translated,_=L.translate(7,act,T,PORTS,DEFS)
    for x,y,kind,sub,eras,sec in struct.iter_unpack('>HHBBBB',L.layout_bytes(7,act)):
        if x==65535:break
        flags=(y>>14)|(32 if kind&128 else 0);kind&=127;y&=4095
        for era in L.eras_of(act):
            if not (eras>>5)&L.ERA_BIT[era]:continue
            n=L.routine(T,L.table_for(T,7,act,era),kind)
            if n not in NAMES:continue
            e='ABCD'.index(era)
            # Exercise the production translator too: both userflag bytes and
            # flip bits must survive into the correct R7 zone-local actor.
            port=int(re.search(r'SCD_OBJ_R7_'+NAMES[n]+r'=(\d+)',Path('src/scd_objects.h').read_text())[1])
            assert any(row[:5]==(x,y,port,sub,flags) and row[5]&L.ERA_BIT[era] and len(row)==7 and row[6]==sec for row in translated),(act,era,n,x,y,sub,sec)
            # Direct-spawn fixtures accept flip bits only; saved flag32 was
            # checked above against the production layout, not a placement here.
            rows.append(f'{{{act},{e},{x},{y},SCD_OBJ_R7_{NAMES[n]},{sub},{flags&3},{sec}}}')
(out/'placements.h').write_text('static const struct{unsigned char act,era;short x,y;unsigned char type,sub,flags,sec;}placements[]={\n'+',\n'.join(rows)+'};\n')
print(len(rows),'placement-era records')
PY
cat > "$out/orig/ss_orig.h" <<'H'
/* Retail helpers the R7 originals call, provided by tools/ss_actors_test.c. */
typedef struct __attribute__((packed)){int value;}qq_uint;
/* The 32-bit PC pointers HOTARU7/KANABUN keep in actfree, moved to per-actor arrays. */
extern void *ss_ptr0[128],*ss_ptr4[128],*ss_ptr8[128];
/* MOVIE7/ET7's char* event cursor ((char**)o)[12]. */
extern char *ss_cur12[128];
extern void divdevset(int);
extern short atan_sonic(short,short);
extern void actionsub(sprite_status*);
extern void frameout(sprite_status*);
extern int frameout_s(sprite_status*);
extern int frameout_s0(sprite_status*);
extern int frameout_s00(sprite_status*,short);
extern int actwkchk(sprite_status**);
extern int actwkchk2(sprite_status*,sprite_status**);
extern void soundset(short);
extern void sub_sync(short);
extern void scoreup(unsigned int);
extern void patchg(sprite_status*,unsigned char**);
extern short playdieset(sprite_status*);
extern short emycol_d(sprite_status*);
extern short emycol_d3(sprite_status*,short,short);
extern short playdamageset(sprite_status*,sprite_status*);
extern void sinset(unsigned char,short*,short*);
extern void goal_move2(sprite_status*);
extern void hari_spdadd(sprite_status*);
extern PALETTEENTRY gamecolor[];
extern sprite_pattern* pat_wall7[];
extern sprite_pattern* springpat2[];extern sprite_pattern* spring90pat2[];extern sprite_pattern* spring45pat2[];extern unsigned char* springchg[];
#define sMemCpy(d,s,n) memcpy(d,s,n)
H
flags="-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-return-type -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-implicit-function-declaration -Isrc -Ibuild/ss/host -Iassets/generated -Ibuild/probe-source -Ibuild/audit/source/src/R7 -Ibuild/audit/source/src -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize=shift -fno-sanitize-recover=all ${SS_CFLAGS:-}"
: >"$out/build.log"
objs=()
for f in "$out"/orig/*.c; do
    o="${f%.c}.o"
    clang $flags -I"$out/orig" -c "$f" -o "$o" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
    objs+=("$o")
done
clang $flags -DSCD_HOST_TEST -I"$out" -I"$out/orig" tools/ss_actors_test.c "${objs[@]}" \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c build/ss/host/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
"$out/test" | tee "$out/result.txt"
