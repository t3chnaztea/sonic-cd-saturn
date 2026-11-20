#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/cc1/mecasnc-original
python3 - <<'PY'
from pathlib import Path
import re
text=Path('build/audit/source/src/R3/MECASNC.C').read_text()
text=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',text)
text=re.sub(r'\(\(char\*\)(\w+)\)\[(\d+)\]',
            lambda m:f'(*((char*)({m[1]})->actfree+{int(m[2])-46}))',text)
Path('build/cc1/mecasnc-original/original.c').write_text(text)
PY
clang -x c -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Ibuild/probe-source -Ibuild/audit/source/src/R3 -Ibuild/audit/source/src \
    -c build/cc1/mecasnc-original/original.c -o build/cc1/mecasnc-original/original.o
clang -x c -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Ibuild/probe-source -Ibuild/audit/source/src/R3 -Ibuild/audit/source/src \
    -c build/audit/source/src/R3/MSNCCG.C -o build/cc1/mecasnc-original/maps.o
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
    -Wno-parentheses -Wno-unused-value -Isrc -Iassets/generated -Ibuild/probe-source \
    -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/cc_mecasnc_original_test.c build/cc1/mecasnc-original/{original,maps}.o \
    src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
    -o build/cc1/mecasnc-original/test >build/cc1/mecasnc-original/build.log 2>&1
build/cc1/mecasnc-original/test | tee build/cc1/mecasnc-original/result.txt
