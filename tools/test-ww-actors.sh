#!/bin/bash
# Compiled R6 originals (the routines tools/ww_originals.py PORTED lists, with
# RIDECHK.C, COLI6.C pcol, SUICIDE.C and PLAYSUB.C patchg) versus the native
# objects_ww_*.inc actors for every Wacky Workbench placement of those routines
# in every era of Acts 1-3: motion, a chase around the actor, a player-contact
# grid around every live piece, a followed player, and frameout. Same method
# as tools/test-qq-actors.sh; see tools/ww_actors_test.c.
set -euo pipefail
cd "$(dirname "$0")/.."
out=build/ww/actors
mkdir -p "$out/orig" build/ww/host
inputs=$(ls src/objects_ww*.inc | tr '\n' ' ')
inputs="$inputs src/objects.c src/objects_tt_enemies.inc src/scd_objects.h src/objects_zone_ops.inc tools/ww_actors_test.c tools/test-ww-actors.sh tools/ww_host_objects.py tools/ww_originals.py tools/ww_retail_piston_ref.py tools/object_layouts.py build/audit/source/src/RIDECHK.C build/audit/source/src/R6/COLI6.C build/audit/source/src/SUICIDE.C build/audit/source/src/PLAYSUB.C"
python3 - "$out" $inputs '.deps/scddisasm/src/Level/Wacky Workbench/Objects/Piston/Main.asm' '.deps/scddisasm/src/Level/Wacky Workbench/Objects/Minomusi/Main.asm' '.deps/scddisasm/src/Level/_Objects/Explosion/Main.asm' '.deps/scddisasm/src/Level/_Objects/HUD and Points/Main.asm' '.deps/scddisasm/src/Level/_Objects/Flower/Main.asm' <<'PY'
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
python3 tools/ww_host_objects.py build/ww/host
python3 tools/ww_originals.py "$out"
python3 tools/ww_retail_piston_ref.py "$out/orig/PISTON6.C"
cat > "$out/orig/ww_orig.h" <<'H'
/* Retail helpers the R6 originals call, provided by tools/ww_actors_test.c. */
typedef struct __attribute__((packed)){int value;}ww_uint;
extern void *ww_ptr[4][128];
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
extern short playdamageset(sprite_status*,sprite_status*);
extern void sinset(unsigned char,short*,short*);
#define sMemCpy(d,s,n) memcpy(d,s,n)
H
cat > "$out/orig/PATS.c" <<'C'
/* Pattern tables other programs define; the fixture only stores them. */
#include "EQU.H"
sprite_pattern *ringpat[9],*bariapat[13];
C
flags="-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-return-type -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-implicit-function-declaration -Isrc -Ibuild/ww/host -Iassets/generated -Ibuild/probe-source -Ibuild/audit/source/src/R6 -Ibuild/audit/source/src -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize=shift -fno-sanitize-recover=all ${WW_CFLAGS:-}"
: >"$out/build.log"
objs=()
for f in "$out"/orig/*.c; do
    o="${f%.c}.o"
    clang $flags -I"$out/orig" -c "$f" -o "$o" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
    objs+=("$o")
done
clang $flags -DSCD_HOST_TEST -I"$out" -I"$out/orig" tools/ww_actors_test.c "${objs[@]}" \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
    src/sonic_animation.c src/stage.c build/ww/host/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o "$out/test" >>"$out/build.log" 2>&1 || { grep -E "error" "$out/build.log" | head -n 30; exit 1; }
"$out/test" | tee "$out/result.txt"
