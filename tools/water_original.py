#!/usr/bin/env python3
"""Write build/water/original.c: the pinned original water routines, compiled
unchanged except for host adaptations (PC actor word casts become actfree
offsets on the host, the per-act watercolitbl becomes a selectable pointer).

PLAYER.C plwaterchk jumpcolsub; R4/GAME4.C water1chk..watercoli and the
game_init water block; R4/PLAYSUB4.C plairset plawamaster* plawa* patchg
exit2*; the 68k Level Random (tools/level_random.py, not IO.C random); ACTSET.C actwkchk; ACTION.C actionsub frameout;
TBL0.C awasintbl; TBL1.C exit2chg; R4/WTBL4*.C watercolitbl.
"""
import re
import sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from level_random import level_random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_source import ROOT, UPSTREAM

SRC = UPSTREAM/'src'


def strip(text):
    return re.sub(r'/\*.*?\*/', '', text, flags=re.S)


def functions(source):
    result = {}
    for match in re.finditer(r'^(?:unsigned |static )*(?:void|char|short|int)\s+(\w+)\([^;]*?\)\s*\{', source, re.M):
        end, depth = match.end(), 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        result[match[1]] = source[match.start():end]
    return result


def raw_words(text):
    # ((short*)p)[n] -> the PC word at byte 2n; actfree starts at PC byte 46.
    return re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',
                  lambda m: f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))', text)


def main():
    player = functions(strip((SRC/'PLAYER.C').read_text()))
    game4_text = strip((SRC/'R4/GAME4.C').read_text())
    game4 = functions(game4_text)
    playsub = strip((SRC/'R4/PLAYSUB4.C').read_text())
    playsub_f = functions(playsub)
    out = ['#include "EQU.H"', '#include "ACTION.H"', '#include "ETC.H"', '#include "PLAYER.H"',
           '#include "IMPFUNCS.H"',
           'void soundset(short);', 'void bgmset(short);', 'int random(void);',
           'int actwkchk(sprite_status**);', 'void frameout(sprite_status*);', 'void actionsub(sprite_status*);',
           'void patchg(sprite_status*, unsigned char**);', 'void plairset(void);',
           'void plawamaster(sprite_status*); void plawamaster_jump0(sprite_status*);',
           'void plawamaster_jump(sprite_status*); void plawamaster_jump2(sprite_status*);',
           'void plawainit(sprite_status*); void plawamove(sprite_status*); void plawamove2(sprite_status*);',
           'void plawamove3(sprite_status*); void plawamove4(sprite_status*); void plawamove5(sprite_status*);',
           'void plawasub(sprite_status*); void exit2_init(sprite_status*); void exit2_move(sprite_status*);',
           'void exit2_erase(sprite_status*);',
           'void water1chk(void); void water2chk(void); void water3chk(void);',
           'sprite_pattern* awapat[23]; sprite_pattern* exit2pat[3];',
           'short *water_original_table;',
           '#define watercolitbl ((short_union*)water_original_table)']
    # Tables.
    tbl0 = strip((SRC/'TBL0.C').read_text())
    out.append(re.search(r'unsigned char awasintbl\[256\] = \{.*?\};', tbl0, re.S)[0])
    tbl1 = strip((SRC/'TBL1.C').read_text())
    names = re.search(r'unsigned char\* exit2chg\[3\] = \{(.*?)\};', tbl1, re.S)
    for n in sorted(set(re.findall(r'exit2chg\d+', names[1]))):
        out.append(re.search(r'static unsigned char ' + n + r'\[\d+\] = \{.*?\};', tbl1, re.S)[0])
    out.append(names[0])
    out.append(re.search(r'unsigned char plawachg0\[9\].*?;', playsub, re.S)[0])
    out.append(re.search(r'unsigned char\* plawachg\[16\] = \{.*?\};', playsub, re.S)[0])
    for name in ['41A', '41B', '41C', '42A', '42B', '42C', '43']:
        text = strip((SRC/f'R4/WTBL{name}.C').read_text())
        out.append(text.replace('short watercolitbl[', f'short water_original_{name}['))
    # Routines.
    out.append(player['plwaterchk'])
    for n in ['water1chk', 'water2chk', 'water3chk', 'watercntsub', 'watercnt', 'watercoli']:
        out.append(game4[n])
    init = re.search(r'unsigned short waterpositbl\[12\] = \{.*?\};', game4['game_init'], re.S)[0]
    block = game4['game_init']
    zero = block[block.index('waterposi = 0;'):block.index('waterflag2 = 0;') + len('waterflag2 = 0;')]
    coli = block[block.index('watercoliflag = 0;'):block.index('mizuflag = 0;') + len('mizuflag = 0;')]
    water = block[block.index('if (stageno.b.h == 2) {'):block.index('pl_air = 30;') + len('pl_air = 30;')]
    out.append('void water_original_game_init(void) {\n  ' + init + '\n  ' + zero + '\n  ' + coli +
               '\n  waterdirec.w = 0;\n  sysdirec = 0; gametimer.w = 0; ranum = 0; scroll_start.w = 0;\n  ' +
               # Retail sway phase (src/water.c water_reset): angle 4 before the init watercnt.
               water.replace('watercnt();', 'sysdirec = 4; watercnt();') + '\n}')
    for n in ['plairset', 'patchg', 'plawamaster', 'plawamaster_jump0', 'plawamaster_jump', 'plawamaster_jump2',
              'plawa', 'plawainit', 'plawamove', 'plawamove2', 'plawamove3', 'plawamove4', 'plawamove5',
              'plawasub', 'exit2', 'exit2_init', 'exit2_move', 'exit2_erase']:
        out.append(raw_words(playsub_f[n]))
    out.append(level_random())  # 68k Level Random; IO.C random's seed chain differs
    actset = functions(strip((SRC/'ACTSET.C').read_text()))
    out.append(actset['actwkchk'])
    action = functions(strip((SRC/'ACTION.C').read_text()))
    out.append(action['actionsub'].replace('sMemSet', 'memset'))
    out.append('void frameout(sprite_status* pActwk) { memset(pActwk, 0, sizeof(*pActwk)); }')
    text = '#include <string.h>\n' + '\n'.join(out) + '\n'
    path = ROOT/'build/water/original.c'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    # Both fixture builds share the original jumpcolsub (the drown path calls it).
    (path.parent/'jumpcolsub.c').write_text('#include "EQU.H"\n#include "IMPFUNCS.H"\nvoid soundset(short);\n'
        'unsigned int WaveClear;\n' + player['jumpcolsub'] + '\n')


if __name__ == '__main__':
    main()
