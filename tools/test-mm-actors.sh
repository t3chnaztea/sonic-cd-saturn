#!/bin/bash
# Compiled R8 originals (DAI8, NOKOGIRI, KUZURE8, PROPERA8, KABUTO8 ... +
# RIDECHK.C, COLI8.C pcol, SUICIDE.C, PLAYSUB.C explosion/flower/patchg, SCORE.C points) versus the native
# objects_mm_*.inc actors for every Metallic Madness placement of those
# routines in every era of Acts 1-3: motion, a chase around the actor, a
# player-contact grid around every live piece, a carried/followed player, and
# frameout. See tools/mm_actors_test.c. MM_ONLY=<type id> runs one routine.
set -euo pipefail
cd "$(dirname "$0")/.."
# The R8 routine files under test.
MM_FILES='SCARAB BIGBOM8 DAI8 NOKOGIRI KUZURE8 PROPERA8 KABUTO8 HACHI8 OKUSIESO HAGURUMA FRIEND8 ET8 KOMA8 TRAP_R81 TRAP_R82 TRAP_R83 SW8 TOBIRA PIPE8 SHOOT SHUT BEAM PLAYSP8 JETTOGE8 KONBEA83 HOTA8C HOTA8D DANGO8 LEGMECA8'
out=build/mm/actors
mkdir -p "$out/orig" build/mm/host
report_inputs='.deps/soniccd/src/R8/SCARAB.C .deps/soniccd/src/R8/BIGBOM8.C .deps/soniccd/src/R8/TRAP_R81.C .deps/soniccd/src/R8/TRAP_R82.C tools/prepare_boss.py src/objects_mm_remaining.inc tools/prepare_mm_remaining.py .deps/soniccd/src/ITEM.C src/objects_mm.inc src/objects_mm_common.inc src/objects_mm_act1.inc src/objects_mm_act1b.inc src/objects_mm_story.inc src/objects_mm_trap.inc src/objects_mm_act2.inc src/objects_mm_act3.inc src/objects_mm_hota8.inc src/objects_mm_enemies.inc build/audit/source/src/SPRING.C src/objects_tt_ride.inc src/objects.c src/scd_objects.h src/objects_zone_ops.inc tools/mm_actors_test.c tools/test-mm-actors.sh tools/mm_host_objects.py tools/object_layouts.py build/audit/source/src/RIDECHK.C build/audit/source/src/R8/COLI8.C build/audit/source/src/SUICIDE.C build/audit/source/src/PLAYSUB.C build/audit/source/src/TBL1.C build/audit/source/src/SCORE.C src/objects_tt_enemies.inc'
for f in $MM_FILES; do
    report_inputs="$report_inputs build/audit/source/src/R8/$f.C"
done
for f in build/auto-extract/8/objects*.bin; do report_inputs="$report_inputs $f"; done
python3 - "$out" $report_inputs <<'PY'
from pathlib import Path
import json,hashlib,datetime,sys,os,subprocess
p=Path(sys.argv[1])/'report.json'
files={Path(n) for n in sys.argv[2:]}
for directory in ('src','assets/generated','build/probe-source','build/audit/source/src'):
    files.update(f for f in Path(directory).rglob('*') if f.is_file())
r=dict(oracle_corrections={'ET8.C:m_die':'R81B $20E4D0/$20E4F6-$20E520: integer-coordinate copy; no immediate baku_init call.','PLAYSUB.C:patchg':'R83D $2059E6 keeps a 0 frame time','RIDECHK.C':'R8 act_tbl ids 9 (chibi_coli) and 10 (spring) map to the renamed actors','PROPERA8.C':'R81B b_open/b_opend fall through','SW8.C':'release lift 8','SHUT.C:kaiten':'R83D $20AB8C carry test','LEGMECA8.C:c_roll':'R82A $20E32E falls through','HOTA8C/D.C':'R83D init falls into dspin; beam addib #$80','BEAM.C:beam_coli':'R82A $20B644 Y half-size from byte $17 (X radius)'},filter=os.environ.get('MM_ONLY'),compiler=subprocess.check_output(['clang','--version'],text=True),passed=False,status='pending',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
       inputs={str(n):hashlib.sha256(n.read_bytes()).hexdigest() for n in sorted(files)})
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
python3 tools/prepare_mm_remaining.py --check
python3 tools/mm_host_objects.py build/mm/host
python3 - "$out" $MM_FILES <<'PY'
from pathlib import Path
import re,sys,struct
sys.path.insert(0,'tools')
out=Path(sys.argv[1])
SRC=Path('build/audit/source/src')
SIZE={'short':2,'unsigned short':2,'char':1,'unsigned char':1,'int':4,'unsigned int':4}
def host(text):
    # PC scratch casts become offsets into actfree (46 = actfree's PC offset);
    # 32-bit views of unaligned actfree bytes go through a packed struct.
    text=re.sub(r'\*\(int\*\)&(\w+)->actfree\[(\d+)\]',r'(((qq_uint*)(void*)&\1->actfree[\2])->value)',text)
    text=re.sub(r'\(\((short|unsigned short|char|unsigned char|int|unsigned int)\*\)(&?\w+(?:\[\w+\])?)\)\[(\d+)\]',
                lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{SIZE[m[1]]*int(m[3])-46}))',text)
    return text
def terminate(text,name):
    # DAI8's scripts end with 0 and no >=250 terminator (see objects_mm_act1.inc).
    m=re.search(r'static char '+name+r'\[(\d+)\] =\s*\{(.*?)\};',text,re.S)
    return text.replace(m[0],f'static char {name}[{int(m[1])+1}] = {{{m[2].rstrip()}, -1}};')
PATCH={
 'SCARAB':[('((short*)&actwk[((short*)pActwk)[23]])[26]','(*(short*)&actwk[((short*)pActwk)[23]].actfree[6])'),('actno = 47','actno = SCD_OBJ_R8_SCARAB'),('actno != 47','actno != SCD_OBJ_R8_SCARAB'),('*(unsigned char**)&pActwk->actfree[0]','mm_scarab_flag[pActwk-actwk]'),('((unsigned char***)pActwk)[15]','mm_scarab_anim[pActwk-actwk]')],
 # Retail R81B m_die $20E4D0 ($20E4F6-$20E520) creates actor24,
 # sets r_no1, copies integer X/Y, then sound158 and returns. Unlike the
 # PC reconstruction, it does NOT call baku_init. Keep the full original
 # PLAYSUB routines; remove only this proven PC-only call site.
 'ET8':[('d0 = ((stageno.w + 1) << 2)','d0 = ((stageno.b.l + 1) << 2)'),('actionwk->sproffset = a1[d0];','actionwk->sproffset = d0 < 11 ? a1[d0] : 0;'),
        ('a1->xposi = actionwk->xposi;','a1->xposi.w.h = actionwk->xposi.w.h;'),
        ('a1->yposi = actionwk->yposi;','a1->yposi.w.h = actionwk->yposi.w.h;'),
        ('baku_init(a1);','/* Retail R81B: no immediate explosion dispatch. */')],
 'BIGBOM8':[('actno == 35','actno == SCD_OBJ_R8_BIGBOM')],
 'DAI8':[('actwk[ano].actno != 44','actwk[ano].actno != SCD_OBJ_R8_DAI8')],
 'NOKOGIRI':[('actwk[ano].actno != 39','actwk[ano].actno != SCD_OBJ_R8_NOKOGIRI')],
 # Retail R81B b_open ($20CE52) and b_opend ($20CE72) fall through into b_open1
 # and b_opend1; the PC source lost both calls (port commit 51eae52).
 'PROPERA8':[('actwk[ano].actno != 40','actwk[ano].actno != SCD_OBJ_R8_PROPERA'),
             ('actionwk->r_no0 += 2; /* Line 252, Address: 0x1023be0 */','actionwk->r_no0 += 2; b_open1(actionwk);'),
             ('actionwk->r_no0 += 2; /* Line 267, Address: 0x1023c94 */','actionwk->r_no0 += 2; b_opend1(actionwk);')],
 'KABUTO8':[('bodywk->actno != 36','bodywk->actno != SCD_OBJ_R8_KABUTO')],
 'KOMA8':[('sprwk->actno = 10;','sprwk->actno = SCD_OBJ_R8_SPRING8;')],
 # SW8.C:88 lifts Sonic 12 on release; retail subq #8 (R81A $20D8C6, R82A $20F498,
 # R83C $20F260; port commit b2ac0d0).
 'SW8':[('actwk[0].yposi.w.h -= 12;','actwk[0].yposi.w.h -= 8;')],
 'TOBIRA':[('actwk[ano].actno != 41','actwk[ano].actno != SCD_OBJ_R8_TOBIRA')],
 'PIPE8':[('actwk[ano].actno != 32','actwk[ano].actno != SCD_OBJ_R8_PIPE8')],
 # The 32-bit PC keeps the route pointer in ((unsigned short**)o)[16] (actfree 18-21).
 # Retail shooter (R82A-D, e.g. R82D $208482): cmpib #4,r_no0; bcc rts; jmp frameout_s.
 'SHOOT':[('&((unsigned short**)shootwk)[16]','&mm_ptr16[shootwk - actwk]'),
          ('          shootermove3(shootwk); /* Line 466, Address: 0x1024d7c */\n          break;\n      }\n',
           '          shootermove3(shootwk); /* Line 466, Address: 0x1024d7c */\n          break;\n      }\n      if (shootwk->r_no0 < 4) frameout_s(shootwk);\n')],
 # ridechk_k has no return statement though its value is used: return ridechk's.
 'SHUT':[('new_actwk->actno = 61;','new_actwk->actno = SCD_OBJ_R8_SHUT;'),('new_actwk->actno = 62;','new_actwk->actno = SCD_OBJ_R8_KAITEN;'),
         ('  ridechk(loopwk, &actwk[0]);','  return ridechk(loopwk, &actwk[0]);'),
         # Retail kaiten_move0 (R83D $20AB8C: subw; addqw #8; bcs; cmpiw #16) rejects
         # on the add's carry, not the sign (port commit 41ff3c9).
         ('if (cal_xposi < 0 || cal_xposi >= 16)','if ((unsigned short)(loopwk->xposi.w.h - actwk[0].xposi.w.h) + 8u > 0xffffu || (unsigned short)cal_xposi >= 16)')],
 # The 32-bit PC keeps the splash pointer in ((sprite_status**)o)[12] (actfree 2-5).
 # Retail beam_coli (R82A $20B644: move.w $16(a6),d1; ext.w d1) takes the Y half-size
 # from Sonic's X radius byte $17 (sprhs), not sprvsize.
 'BEAM':[('&((sprite_status**)beamwk)[12]','&mm_ptr12[beamwk - actwk]'),('new_actwk->actno = 29;','new_actwk->actno = SCD_OBJ_R8_BEAM;'),
         ('cal_size = (char)actwk[0].sprvsize;','cal_size = (char)actwk[0].sprhs;')],
 # KONBEA.C (Acts 1-2) is the global native konbea; Act 3 links KONBEA83.C.
 'KONBEA83':[('pMainwk->actno != 42','pMainwk->actno != SCD_OBJ_R8_KONBEA83'),('void konbea(','void konbea83(')],
 # JETTOGE8 and PROPERA8 both define global a_init/a_move.
 'JETTOGE8':[('a_init(','jt_a_init('),('a_move(','jt_a_move('),('void jettoge(','void jt_a_init(sprite_status*);void jt_a_move(sprite_status*);\nvoid jettoge(')],
 # Retail R82A c_roll ($20E32E) has no rts and runs into c_roll1 (port commit 85c1efa).
 'LEGMECA8':[('pMasterwk->actno != 38','pMasterwk->actno != SCD_OBJ_R8_LEGMECA'),
             ('pActwk->yposi.w.l = -32768; /* Line 270, Address: 0x1026874 */','pActwk->yposi.w.l = -32768; c_roll1(pActwk);')],
 'HACHI8':[('actwk[ano].actno != 46','actwk[ano].actno != SCD_OBJ_R8_HACHI8')],
 # (stageno.w + 1) << 2 reads past the 11-entry tables (stageno.w carries
 # the round byte): index by the act, and read 0 past the end, as the port.
 'FRIEND8':[('d0 = ((stageno.w + 1) << 2)','d0 = ((stageno.b.l + 1) << 2)'),('actionwk->sproffset = a1[d0];','actionwk->sproffset = d0 < 11 ? a1[d0] : 0;')],
}
prelude='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\n#include <string.h>\n#include "scd_objects.h"\n#include "mm_ids.h"\n#include "mm_orig.h"\n'
for f in sys.argv[2:]:
    t=(SRC/'R8'/f'{f}.C').read_text(errors='replace')
    t=re.sub(r'^#include .*\n','',t,flags=re.M)
    for a,b in PATCH.get(f,[]):
        assert a in t,(f,a);t=t.replace(a,b)
    if f=='ET8':assert 'baku_init(a1)' not in t, 'retail ET8 correction missing'
    if f=='SCARAB':
        item=(SRC/'ITEM.C').read_text();t+='\n'+item[item.index('static unsigned char itemchg0'):item.index('static sprite_pattern')]
    if f=='TRAP_R81':t=t.replace('new_actwk->actno = 55;','new_actwk->actno = SCD_OBJ_R8_ANAR8;')
    if f=='DAI8':t=terminate(terminate(t,'p00'),'p01')
    own=f'#include "{f}.H"\n' if (SRC/'R8'/f'{f}.H').exists() else ''
    if f.startswith('HOTA8'):
        # Good/Bad Future rooms: per-file names; the room's second firefly
        # index goes to xposi.w.h (the 32-bit PC's ((unsigned short*)o)[5]);
        # egg8 (actor 63) is the boss system's scd_boss_create_sub.
        n=f[-1].lower()
        for a,b in (('((unsigned short*)roomwk)[5]','roomwk->xposi.w.h'),('->actno = 57;','->actno = SCD_OBJ_R8_HOTARU8;'),('.actno == 57','.actno == SCD_OBJ_R8_HOTARU8'),
                    ('doorwk->actno = 41;','doorwk->actno = SCD_OBJ_R8_TOBIRA;'),('eggwk->actno = 63;','scd_boss_create_sub(3840, 316, 0, 8);'),
                    ('eggwk->xposi.w.h = 3840;',''),('eggwk->yposi.w.h = 316;',''),
                    # Retail hotaru8_init (R83D $20F404) runs into hotaru8_dspin; hotaru8_move3
                    # steps its beam counter with addib #$80 / bcc (port commit d18447c).
                    ('hotaru->actfree[16] = 60; /* Line 122,','hotaru->actfree[16] = 60; hotaru8_dspin(hotaru); /* Line 122,'),
                    ('(hotaru->actfree[21] += 64) < 64','(hotaru->actfree[21] += 128) < 128')):
            assert a in t,(f,a);t=t.replace(a,b)
        # HOTA8D declares its tables static and defines them later without it
        # (MSVC accepts that; C gives them both linkages): declare them extern.
        for a,b in (('static unsigned char clrchgtbl1[16];','extern unsigned char clrchgtbl1[16];'),('static unsigned char clrchgtbl2[16];','extern unsigned char clrchgtbl2[16];'),
                    ('static PALETTEENTRY clrtblC1[48];','extern PALETTEENTRY clrtblC1[48];'),('static PALETTEENTRY clrtblD[108];','extern PALETTEENTRY clrtblD[108];')):
            t=t.replace(a,b)
        t=re.sub(r'\b(hotaru8pat|hotaru8|clrchgtbl1|clrchgtbl2|clrtblC1|clrtblD)\b',r'\1_'+n,t);own=''
    if f.startswith('TRAP_R8'):
        # Each act links its own TRAP file: rename its globals per act, and
        # its spring/self/plate spawns to the port's ids.
        n=f[-2:]
        t=re.sub(r'^#include .*\n','',(SRC/'R8'/f'{f}.H').read_text(errors='replace'),flags=re.M)+t;own=''
        for a,b in (('new_actwk->actno = 10;','new_actwk->actno = SCD_OBJ_R8_SPRING8;'),('new_actwk->actno = 54;','new_actwk->actno = SCD_OBJ_R8_TOGEDAIR8;'),
                    ('new_actwk->actno = 51;','new_actwk->actno = SCD_OBJ_R8_TOGEITA;'),('.actno != 51','.actno != SCD_OBJ_R8_TOGEITA')):
            t=t.replace(a,b)
        t=re.sub(r'\b(togedair8pat|togedair8|harir8pat|harir8|anar8pat|anar8|futagor8pat|futagor8|gater8|togeitapat|togeita|tokusyupat|tokusyu_block)\b',r'\1_'+n,t)
    for m in re.finditer(r'actno\s*[!=]=\s*(\d+)',t):
        if int(m[1]) not in (0,1,24):raise SystemExit(f'{f}: unmapped actor test {m[0]}')
    (out/'orig'/f'{f}.c').write_text(prelude+'#include "RIDECHK.H"\n#include "SUICIDE.H"\n'+own+host(t))
spr=(SRC/'SPRING.C').read_text(errors='replace')
spr=re.sub(r'^#include .*\n','',spr,flags=re.M)
# build/probe-source/interaction.c links its own copy of SPRING.C's movers:
# give this copy's globals (and SPRING.H's prototypes) a _spr suffix.
spr=(SRC/'SPRING.H').read_text(errors='replace')+spr
names=set(re.findall(r'^(?:void|int|short|char|unsigned char)\s*\**\s*\(?\*?(\w+)\s*[\[(]',spr,flags=re.M))
spr=re.sub(r'\b('+'|'.join(sorted(names,key=len,reverse=True))+r')\b',r'\1_spr',spr)
(out/'orig'/'SPRING.c').write_text(prelude+'#include "RIDECHK.H"\n'+host(spr))
ride=(SRC/'RIDECHK.C').read_text()
ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
ride=ride.replace('#if defined(R41A)','if (0)').replace('#endif','',1)
# KOMA8.C:64 and TRAP_R81-83 spawn their spring as actno 10 (R8 act_tbl 10 is
# SPRING.C), renamed SCD_OBJ_R8_SPRING8 above; RIDECHK's actor-10 rules apply to it.
ride=re.sub(r'(\w+)->actno == 10\b',r'(\1->actno == 10 || \1->actno == SCD_OBJ_R8_SPRING8)',ride)
ride=re.sub(r'(\w+)->actno != 10\b',r'(\1->actno != 10 && \1->actno != SCD_OBJ_R8_SPRING8)',ride)
# R8 act_tbl id 9 is PLAYSP8.C chibi_coli (ACT82A/ACT83.C): hit_yu skips its bottom hit.
ride=re.sub(r'(\w+)->actno == 9\b',r'(\1->actno == 9 || \1->actno == SCD_OBJ_R8_CHIBI_COLI)',ride)
(out/'orig'/'RIDECHK.c').write_text(prelude+'#include "RIDECHK.H"\n'+host(ride))
sui=(SRC/'SUICIDE.C').read_text(errors='replace')
sui=re.sub(r'^#include .*\n','',sui,flags=re.M)
(out/'orig'/'SUICIDE.c').write_text(prelude+'#include "SUICIDE.H"\n'+host(sui))
# COLI8.C pcol and its hit handlers (the fixture provides playdamageset;
# PLAYER.C playdamagechk/playdieset come from build/probe-source). The fixture
# places the routine in actor 1 and children from actor 32: scan 1..127.
coli=(SRC/'R8'/'COLI8.C').read_text(errors='replace')
coli=re.sub(r'^#include .*\n','',coli,flags=re.M).replace('extern short actwkchk(sprite_status** ppActwk);\n','')
coli=coli[:coli.index('void playdamagechk(')]+coli[coli.index('short pcolspecial('):]
for a,b in (('pColliAct = &actwk[32];','pColliAct = &actwk[1];'),('for (i = 0; i < 96; ++i, ++pColliAct)','for (i = 0; i < 127; ++i, ++pColliAct)')):
    assert a in coli,a;coli=coli.replace(a,b)
(out/'orig'/'COLI8.c').write_text(prelude+'#include "COLI8.H"\nextern unsigned char CCset(int,int);\nextern unsigned char CSset(unsigned short,unsigned short);\n'+host(coli))
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
# Retail patchg (R83D $2059E6: moveb (a1),pattim) keeps a 0 frame time;
# PLAYSUB.C:39's 0 -> 1 is the PC's (port commit 2d04803).
old='patchgwk->pattim = sprpat_adr[search_end - 1] != 252 && *sprpat_adr <= 0 ? 1 : *sprpat_adr;'
assert body.count(old)==1,'PLAYSUB.C patchg timer changed';body=body.replace(old,'patchgwk->pattim = *sprpat_adr;')
score=(SRC/'SCORE.C').read_text(errors='replace')
# SCORE.C's high-userflag path dispatches these three original functions.
body+='\nstatic void ten_init(sprite_status*);static void ten_move(sprite_status*);\n'
body+='sprite_pattern *tenpat[16];\n'
body+=''.join(function(score,n) for n in ['tensuu','ten_init','ten_move'])
body+='void mm_original_points(sprite_status *o){tensuu(o); }\n'
(out/'orig'/'PATCHG.c').write_text(prelude+'#include "PLAYSUB.H"\n'+patterns+host(body))
# Every placement of the ported routines, per act and era.
import object_layouts as L
T=L.act_tables();PORTS=L.port_types(T);DEFS=L.definitions()
NAMES={'scarab':'SCARAB','bigbom':'BIGBOM','anar8':'ANAR8','gater8':'GATER8','dai8':'DAI8','nokogiri':'NOKOGIRI','kuzure8':'KUZURE8','propera':'PROPERA','kabuto':'KABUTO','hachi8':'HACHI8','okusieso':'OKUSIESO',
       'haguruma':'HAGURUMA','friend':'FRIEND8','et':'ET8','koma8':'KOMA8','togedair8':'TOGEDAIR8','futagor8':'FUTAGOR8','togeita':'TOGEITA',
       'sw':'SW8','tobira':'TOBIRA','pipe8':'PIPE8','shooter':'SHOOTER','shut':'SHUT','kaiten':'KAITEN',
       'beam':'BEAM','chibi_coli':'CHIBI_COLI','jettoge':'JETTOGE','konbea':'KONBEA83','hotaru8':'HOTARU8','dango':'DANGO8','legmeca':'LEGMECA'}
rows=[]
IDS={m[1]:int(m[2]) for m in re.finditer(r'SCD_OBJ_R8_(\w+)=(\d+)',Path('src/scd_objects.h').read_text())}
for act in (1,2,3):
    translated,_=L.translate(8,act,T,PORTS,DEFS)
    for x,y,kind,sub,eras,sec in struct.iter_unpack('>HHBBBB',L.layout_bytes(8,act)):
        if x==65535:break
        kind&=127;flags=y>>14;y&=4095
        for era in L.eras_of(act):
            if not (eras>>5)&L.ERA_BIT[era]:continue
            n=L.routine(T,L.table_for(T,8,act,era),kind)
            if n not in NAMES or (n=='konbea' and act!=3):continue
            e='ABCD'.index(era)
            # Exercise the production translator too: both userflag bytes and
            # flip bits must survive into the correct R8 zone-local actor (flags
            # bit 5 is the translator's saved-flag bit, TT_SAVED).
            port=IDS[NAMES[n]]
            assert any(row[:4]==(x,y,port,sub) and row[4]&3==flags and row[5]&L.ERA_BIT[era] and len(row)==7 and row[6]==sec for row in translated),(act,era,n,x,y,sub,sec)
            rows.append(f'{{{act},{e},{x},{y},SCD_OBJ_R8_{NAMES[n]},{sub},{flags},{sec}}}')
# Unplaced original dispatch entries: synthetic function fixtures, not routes.
for e in range(4):
    rows.append(f'{{1,{e},1024,640,SCD_OBJ_R8_ANAR8,0,0,0}}')
    rows.append(f'{{2,{e},1024,640,SCD_OBJ_R8_GATER8,0,0,0}}')
(out/'placements.h').write_text('static const struct{unsigned char act,era;short x,y;unsigned char type,sub,flags,sec;}placements[]={\n'+',\n'.join(rows)+'};\n')
print(len(rows),'placement-era records')
PY
cat > "$out/orig/mm_orig.h" <<'H'
/* Retail helpers the R8 originals call, provided by tools/mm_actors_test.c. */
typedef struct __attribute__((packed)){int value;}qq_uint;
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
extern short playdamageset(sprite_status*,sprite_status*);
extern void sinset(unsigned char,short*,short*);
extern void divdevset(int);
extern void baku_init(sprite_status*);
extern void pa_set();
extern unsigned char *mm_scarab_flag[128];
extern unsigned char **mm_scarab_anim[128];
extern unsigned short *mm_ptr16[128];
extern sprite_status *mm_ptr12[128];
extern void scd_boss_create_sub(int,int,unsigned,unsigned);
extern short hitchk_u(sprite_status*,sprite_status*);
extern short emycol_l(sprite_status*,unsigned char);
extern short emycol_r(sprite_status*,unsigned char);
extern void speedset2(sprite_status*);
extern void speedset(sprite_status*);
extern PALETTEENTRY gamecolor[];
#define sMemCpy(d,s,n) memcpy(d,s,n)
H
flags="-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-return-type -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-implicit-function-declaration -Isrc -Ibuild/mm/host -Iassets/generated -Ibuild/probe-source -Ibuild/audit/source/src/R8 -Ibuild/audit/source/src -DR8 -DR81 -DR81A -fsanitize=address,undefined -fno-sanitize=shift -fno-sanitize-recover=all ${MM_CFLAGS:-}"
: >"$out/build.log"
objs=()
for f in "$out"/orig/*.c; do
    o="${f%.c}.o"
    clang $flags -I"$out/orig" -c "$f" -o "$o" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
    objs+=("$o")
done
clang $flags -DSCD_HOST_TEST -I"$out" -I"$out/orig" tools/mm_actors_test.c "${objs[@]}" \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c build/mm/host/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
python3 - "$out" "$flags" <<'PYHASH'
from pathlib import Path
import hashlib,json,sys
out=Path(sys.argv[1]);p=out/'report.json';r=json.loads(p.read_text())
r['flags']=sys.argv[2]
r['compiled_inputs']={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for directory in (out/'orig',Path('build/mm/host')) for f in directory.iterdir() if f.suffix in ('.c','.h','.inc')}
r['binary_sha256']=hashlib.sha256((out/'test').read_bytes()).hexdigest()
p.write_text(json.dumps(r,indent=2)+'\n')
PYHASH
"$out/test" | tee "$out/result.txt"
