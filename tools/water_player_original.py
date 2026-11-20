#!/usr/bin/env python3
"""Write build/water/player_original.c: PLAYER.C play00walk, play00jump, ball00walk,
ball00jump and play00damage renamed ref_*, plus ref_motion (the play00 cddat&6
dispatch). Calls the native step makes elsewhere or never (bye_chk, backto_chk,
limitchk; play00damage's playsp, play00damage_sub, playposiwkset, patchgmain,
actionsub) become no-ops. Everything else is the original text."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_source import ROOT, UPSTREAM
from water_original import functions, strip

player = functions(strip((UPSTREAM/'src/PLAYER.C').read_text()))
out = ['#include "EQU.H"', '#include "ACTION.H"', '#include "PLAYER.H"', '#include "FCOL.H"',
       'static void ref_nop(void) {}', 'static void ref_nop1(sprite_status *p) { (void)p; }']
for name in ['play00walk', 'play00jump', 'ball00walk', 'ball00jump', 'play00damage']:
    body = player[name].replace(f'void {name}(', f'void ref_{name}(', 1)
    for stub in ['bye_chk', 'backto_chk', 'limitchk', 'playsp', 'play00damage_sub', 'playposiwkset', 'patchgmain']:
        body = re.sub(r'\b' + stub + r'\(\)', 'ref_nop()', body)
    body = re.sub(r'\bactionsub\(', 'ref_nop1(', body)
    out.append(body)
out.append('void ref_motion(void) {\n  switch (actwk[0].cddat & 6) {\n    case 0: ref_play00walk(); break;\n'
           '    case 2: ref_play00jump(); break;\n    case 4: ref_ball00walk(); break;\n    case 6: ref_ball00jump(); break;\n  }\n}')
path = ROOT/'build/water/player_original.c'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text('\n'.join(out) + '\n')
