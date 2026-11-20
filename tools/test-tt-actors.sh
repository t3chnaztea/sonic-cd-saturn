#!/bin/bash
# Compiled R4 originals versus native Tidal Tempest actors (objects_tt_*.inc).
# usage: tools/test-tt-actors.sh [name ...]   (default: every fixture)
set -euo pipefail
cd "$(dirname "$0")/.."
ALL="tonbo yago amenbo tagameb harir4 harid4 screw screw_f osumizu funsui4 ukidai bou et4 movie4 friend4 awa wave"
NAMES="${*:-$ALL}"
build_one() {
    local name=$1 kind=$2 fn=$3 test=$4; shift 4
    local out=build/tt/$name
    mkdir -p "$out"
    python3 tools/tt_original.py "$name" "$@"
    python3 - "$name" pending <<'PY'
import json,sys,datetime
from pathlib import Path
p=Path('build/tt')/sys.argv[1]/'report.json'
p.write_text(json.dumps(dict(passed=False,status='pending',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
PY
    if ! clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
        -Wno-parentheses -Wno-unused-value -Wno-incompatible-pointer-types -Wno-int-conversion \
        -Isrc -Iassets/generated -Ibuild/probe-source -Itools \
        -DR1 -DR11A ${TT_EXTRA:-} -DTT_KIND="$kind" -DTT_ORIGINAL="$fn" -DTT_NAME="\"$name\"" \
        -fsanitize=address,undefined -fno-sanitize-recover=all \
        "$test" "$out/original.c" build/tt/ridechk.c \
        src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
        src/sonic_animation.c src/stage.c src/objects.c src/water.c \
        build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
        -o "$out/test" >"$out/build.log" 2>&1; then
        grep -m20 error "$out/build.log" >&2 || tail -n 20 "$out/build.log" >&2
        python3 - "$name" <<'PY'
import json,sys
from pathlib import Path
p=Path('build/tt')/sys.argv[1]/'report.json';r=json.loads(p.read_text());r.update(status='failed',stage='build');p.write_text(json.dumps(r,indent=2)+'\n')
PY
        return 1
    fi
    if ! "$out/test" >"$out/result.txt" 2>"$out/stderr.txt"; then
        tail -n 15 "$out/stderr.txt" >&2
        python3 - "$name" <<'PY'
import json,sys
from pathlib import Path
p=Path('build/tt')/sys.argv[1]/'report.json';r=json.loads(p.read_text());r.update(status='failed',stage='run');p.write_text(json.dumps(r,indent=2)+'\n')
PY
        return 1
    fi
    cat "$out/result.txt"
    python3 - "$name" "$test" "$@" <<'PY'
import json,sys,hashlib
from pathlib import Path
name,test,*files=sys.argv[1:]
out=Path('build/tt')/name
paths=[test,'tools/tt_actor_fixture.h','tools/tt_original.py','tools/test-tt-actors.sh','src/objects.c','src/objects_tt_common.inc',
       'src/objects_tt_enemies.inc','src/objects_tt_hazards.inc','src/objects_tt_friends.inc',str(out/'original.c')]+['build/audit/source/src/'+f for f in files if f.endswith('.C')]
paths=[p for p in paths if Path(p).exists()]
r=json.loads((out/'report.json').read_text())
r.update(passed=True,status='passed',result=(out/'result.txt').read_text().strip(),
         inputs={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
         limits='Compiled original actor, PLAYSUB4 patchg, COLI4 pcol and SUICIDE versus native actor/player state on real Tidal Tempest maps; emulator and hardware routes remain separate.')
(out/'report.json').write_text(json.dumps(r,indent=2)+'\n')
PY
}
mkdir -p build/tt
python3 - <<'PY'
from pathlib import Path
import re
ride=Path('build/audit/source/src/RIDECHK.C').read_text()
ride=re.sub(r'^#include .*\n','',ride,flags=re.M)
ride=ride.replace('lXspeed << 8','lXspeed * 256').replace('pActwk->yspeed.w << 8','pActwk->yspeed.w * 256')
text='#include "EQU.H"\n#include "DIRCOL.H"\n#include "ETC.H"\nvoid soundset(short);\n'+Path('build/audit/source/src/RIDECHK.H').read_text()+ride
text=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',text)
Path('build/tt/ridechk.c').write_text(text)
PY
status=0
for name in $NAMES; do
    case $name in
    # Retail R42A $D268-$D2E2: the init falls through into the move (src tonbo_step).
    tonbo) build_one tonbo SCD_OBJ_TONBO tonbo tools/tt_enemy_test.c R4/TONBO.C \
        --replace '((short*)pActwk)[29] >>= 1; ' '((short*)pActwk)[29] >>= 1; act_lr(pActwk); ' || status=1;;
    yago) build_one yago SCD_OBJ_YAGO yago tools/tt_enemy_test.c R4/YAGO.C || status=1;;
    amenbo) build_one amenbo SCD_OBJ_AMENBO amenbo tools/tt_enemy_test.c R4/AMENBO.C \
        --replace '((short*)subActwk)[44] = (unsigned char)(pActwk - actwk);' '' || status=1;;
    # Retail R41A $DC9C a_check: unsigned range tests (src tagameb_step, f0ca5fe).
    tagameb) build_one tagameb SCD_OBJ_TAGAMEB tagameb tools/tt_enemy_test.c R4/TAGAMEB4.C \
        --replace 'actwk[subact].actno != 45' 'actwk[subact].actno != SCD_OBJ_TAGAMEB' \
        --replace 'wD0 = actwk[0].yposi.w.h - pActwk->yposi.w.h - -56 - 56; ' 'wD0 = actwk[0].yposi.w.h - pActwk->yposi.w.h + 56; ' \
        --replace 'if (wD0 < 0) ' 'if ((unsigned short)wD0 < 56) ' \
        --replace 'wD0 -= 0x28 - 0x78; ' 'wD0 -= 40; ' \
        --replace 'if (wD0 >= 0) ' 'if ((unsigned short)wD0 < 120) ' || status=1;;
    harir4) build_one harir4 SCD_OBJ_HARIR4 harir4 tools/tt_hazard_test.c R4/HARIR4.C || status=1;;
    harid4) build_one harid4 SCD_OBJ_HARID4 harid4 tools/tt_hazard_test.c R4/HARID4.C \
        --replace '.actno != 50' '.actno != SCD_OBJ_HARID4' || status=1;;
    screw) build_one screw SCD_OBJ_SCREW screw tools/tt_hazard_test.c R4/SCREW_A.C || status=1;;
    screw_f) build_one screw_f SCD_OBJ_SCREW_F screw tools/tt_hazard_test.c R4/SCREW_C.C || status=1;;
    osumizu) build_one osumizu SCD_OBJ_OSUMIZU osumizu tools/tt_hazard_test.c R4/OSUMIZU.C || status=1;;
    funsui4) build_one funsui4 SCD_OBJ_FUNSUI4 funsui4 tools/tt_hazard_test.c R4/FUNSUI4.C || status=1;;
    ukidai) build_one ukidai SCD_OBJ_UKIDAI ukidai tools/tt_hazard_test.c R4/UKIDAI.C || status=1;;
    bou) build_one bou SCD_OBJ_BOU bou tools/tt_hazard_test.c --section R4/PLAYSUB4.C 'void bou(sprite_status' '' || status=1;;
    wave) build_one wave SCD_OBJ_WAVE wave tools/tt_wave_test.c --section R4/PLAYSUB4.C 'unsigned char wavechg0[50]' 'void patchg(sprite_status' \
        --section R4/PLAYSUB4.C 'void wave(sprite_status' 'void bou(sprite_status' || status=1;;
    et4) build_one et4 SCD_OBJ_ET4 et tools/tt_friends_test.c R4/ET4.C \
        --replace 'extern int hitchk(sprite_status* pActwk, sprite_status* pPlayerwk);' '' || status=1;;
    movie4) TT_EXTRA="-DTT_KIND2=SCD_OBJ_FRIEND4 -DTT_ORIGINAL2=friend4" build_one movie4 SCD_OBJ_MOVIE4 movie4 tools/tt_friends_test.c R4/MOVIE4.C \
        --replace '.actno != 82' '.actno != SCD_OBJ_MOVIE4' --replace 'tempact->actno != 82' 'tempact->actno != SCD_OBJ_MOVIE4' --replace 'subactwk->actno = 47;' 'subactwk->actno = SCD_OBJ_FRIEND4;' \
        R4/FRIEND4.C --replace 'pActwk->sproffset = tbl0sproffset[temp.w];' 'pActwk->sproffset = temp.w < 11 ? tbl0sproffset[temp.w] : 0;' || status=1;;
    friend4) build_one friend4 SCD_OBJ_FRIEND4 friend4 tools/tt_friends_test.c R4/FRIEND4.C \
        --replace 'tempact->actno != 82' 'tempact->actno != SCD_OBJ_MOVIE4' \
        --replace 'pActwk->sproffset = tbl0sproffset[temp.w];' 'pActwk->sproffset = temp.w < 11 ? tbl0sproffset[temp.w] : 0;' || status=1;;
    awa) build_one awa SCD_OBJ_AWA awa tools/tt_friends_test.c R4/AWA.C --section TBL0.C 'unsigned char awasintbl[256]' '' \
        --replace 'pNewactwk->actno = 32;' 'pNewactwk->actno = SCD_OBJ_AWA;' || status=1;;
    *) echo "unknown fixture $name" >&2; status=1;;
    esac
done
exit $status
