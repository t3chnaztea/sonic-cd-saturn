#!/bin/bash
# Host tests for the zone objects ported from the retail source (src/objects_*.inc):
# R4 wall1 and R7 wall7/wall73, R5 dair5, R8 konbea, R8 piston. Each test checks
# the object against the retail routine and walks the route it was ported for.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/zone-objects
FLAGS=(-std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value
       -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all)
COMMON=(src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/sonic_animation.c src/stage.c src/objects.c
        build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c)
# The konbea test runs the retail KONBEA.C beside the port as a parity oracle.
# That file addresses actor words as 32-bit PC offsets; route them through actfree,
# as tools/test-swing.sh does for BRANKO1.C.
python3 - "$PWD" > build/zone-objects/konbea_pc.c <<'PY'
import re,sys
src=sys.argv[1]+'/build/audit/source/src'
k=open(src+'/R8/KONBEA.C').read()
k=k.replace('#include "../','#include "').replace('#include "KONBEA.H"\n','void konbea(sprite_status* pActwk);\n')
k=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',k)
assert '*)pActwk)[' not in k and '*)pNewact)[' not in k and '*)pMainwk)[' not in k
p=open(src+'/PLAYSUB.C').read();b=p[p.index('void patchg(sprite_status* patchgwk'):]
sys.stdout.write(k+'\n'+b[:b.index('\n}')+2]+'\n')
PY
status=0
for o in walls dair5 konbea piston; do
    extra=(); [ $o = konbea ] && extra=(build/zone-objects/konbea_pc.c)
    clang "${FLAGS[@]}" tools/object_${o}_test.c ${extra[@]+"${extra[@]}"} "${COMMON[@]}" -o build/zone-objects/$o 2>build/zone-objects/$o.build.log
    if build/zone-objects/$o "$PWD" > build/zone-objects/$o.log 2>&1; then echo "$o: PASS"; else echo "$o: FAIL ($(tail -1 build/zone-objects/$o.log))"; status=1; fi
done
exit $status
