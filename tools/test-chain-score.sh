#!/bin/bash
# Enemy chain score: src/objects.c vs original R1/COLI1.C emyscorecnt scoring,
# and no per-frame chain reset in src/objects.c (the original clears the chain
# only in jumpcolsub/jumpcolsub0 and at act/era init).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/chain-score
if grep -rq 'enemy_chain' src; then echo 'FAIL: src keeps its own enemy_chain' >&2; exit 1; fi
python3 - <<'PY'
import re
t=open('src/objects.c').read()
a=t.index('                /* COLI1.C: escoretbl')
b=t.index('\n',t.index('scd_player_points(',a))+1
open('build/chain-score/native_kill.inc','w').write(t[a:b])
c=open('build/audit/source/src/R1/COLI1.C').read()
c=re.sub(r'/\*.*?\*/','',c,flags=re.S)
a=c.index('iScoreCntwk = emyscorecnt;')
b=c.index('}',c.index('iScoreData = 1000;',a))+1
open('build/chain-score/original_kill.inc','w').write(c[a:b]+'\n')
PY
clang -std=gnu11 -O1 -fsigned-char -fwrapv -Wno-unused-value -Ibuild/chain-score tools/chain_score_test.c -o build/chain-score/test
build/chain-score/test
