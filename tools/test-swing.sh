#!/bin/bash
# Compare the native Act 2 swing with the PC reconstruction's BRANKO1.C (R12A).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/probe-source
# The PC source indexes actor words as if pointers were 32 bits. Address them
# through actfree (byte 46 of the 68000/PC actor) so the host layout is exact.
python3 - <<'EOF'
import re
from pathlib import Path
source=Path('.deps/soniccd/src/BRANKO1.C').read_text()
source=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',source)
source=source.replace('((char*)pActwk)[64]','((char)pActwk->actfree[18])').replace('((char*)pActwk)[23]','((char)pActwk->sprvsize)').replace('((char*)pPlayerwk)[23]','((char)pPlayerwk->sprvsize)')
assert '*)pActwk)[' not in source and '*)pNewact)[' not in source and '*)pPlayerwk)[' not in source
Path('build/probe-source/branko1.c').write_text(source)
EOF
clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value -Wno-implicit-function-declaration \
    -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR12A \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    tools/swing_test.c build/probe-source/branko1.c src/act.c src/player.c src/sonic_animation.c src/stage.c src/objects.c \
    build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/swing_test
build/swing_test
