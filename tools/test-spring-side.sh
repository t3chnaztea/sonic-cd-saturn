#!/bin/bash
# Spring side hit: src/objects.c spring_step side block vs original RIDECHK.C
# ride_on_chk (hitchk/hit_v/hit_x/push_set/push_clr), spring actno 10.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/spring-side
python3 - <<'PY'
t=open('src/objects.c').read()
a=t.index('            int width=hw+10,height=hh+pr+2')
b=t.index('\n',t.index('            o->cddat=(o->cddat&~32)|(side?32:0);',a))+1
open('build/spring-side/native_side.inc','w').write(t[a:b])
PY
cp build/audit/source/src/RIDECHK.C build/spring-side/ridechk.c
clang -std=gnu11 -O1 -fsigned-char -fwrapv -Wno-parentheses -Wno-unused-value \
    -Ibuild/probe-source -Isrc -DR1 -DR11A '-DSPRING_SIDE_BLOCK="native_side.inc"' -Ibuild/spring-side \
    tools/spring_side_test.c build/spring-side/ridechk.c build/probe-source/equ.c -o build/spring-side/test
build/spring-side/test
