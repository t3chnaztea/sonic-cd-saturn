#!/bin/bash
# Bottom death bound: src/player.c vs original PLAYER.C limitchk (every zone).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/limit
python3 - <<'PY'
import re
t=open('src/player.c').read()
a=t.index('    /* PLAYER.C limitchk (68k ObjSonic_LevelBound .CheckBottom), every zone. */')
b=t.index('\n    }\n',a)+7
open('build/limit/native_limit.inc','w').write(t[a:b])
c=re.sub(r'/\*.*?\*/','',open('build/audit/source/src/PLAYER.C').read(),flags=re.S)
a=c.index('void limitchk(void) {');a=c.index('{',a)+1
b=c.index('\n}',a)
open('build/limit/original_limit.inc','w').write(c[a:b]+'\n')
PY
clang -std=gnu11 -O1 -fsigned-char -fwrapv -Wno-parentheses -Wno-unused-value -Ibuild/probe-source -Ibuild/limit -DR1 -DR11A \
    tools/limit_test.c build/probe-source/equ.c -o build/limit/test
build/limit/test
