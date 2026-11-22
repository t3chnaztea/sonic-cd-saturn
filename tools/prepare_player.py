#!/usr/bin/env python3
"""Generate the explicitly selected terrain/player core; never modify upstream."""
import json
import re
from audit_source import ROOT, UPSTREAM
from player_fixes import patch as player_fixes
from generated_io import write_text, copy_file

OUT = ROOT / 'build/probe-source'

# Upstream declares these lookup tables inside their functions. At -Os the
# compiler copies each initializer onto the stack on every call; sinset alone
# rebuilds 640 bytes per call, several times per simulation update. Every use
# is a read, so static storage is equivalent and removes the per-call copy.
def hoist_tables(source, declarations, where):
    for declaration in declarations:
        if source.count(declaration) != 1:
            raise ValueError(f'{where}: {declaration} changed upstream')
        source = source.replace(declaration, 'static const ' + declaration)
    return source

def functions(source):
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    result = {}
    for match in re.finditer(r'^(?:unsigned |static )*(?:void|char|short|int)\s+(\w+)\([^;]*?\)\s*\{', source, re.M):
        end, depth = match.end(), 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        result[match[1]] = source[match.start():end]
    return result

selected = '''play00init chk11 levermove lmovecol plwalk_l plwalk_r balllmove
ballwalk_l ballwalk_r jumpmove hedcolchk ballchk ballset jumpchk jumpchk2
keispd keispd2 fallchk direcchg jumpcolchk jumpcolsub jumpcolsub0 loopchk
st7_x frip_spd'''.split()
player = functions((UPSTREAM/'src/PLAYER.C').read_text())
content = '\n'.join(player[name] for name in selected)
# This timer occupies scratch bytes 20/21, not a native word at an actor offset.
raw = '((unsigned short*)&actwk[0])[33]'
content = content.replace(raw+' = 30', 'scd_lock_set(30)')
content = content.replace('--'+raw, 'scd_lock_set(scd_lock_get() - 1)')
content = content.replace(raw, 'scd_lock_get()')
content = content.replace('add_speed <<= 8', 'add_speed *= 256')
content = content.replace('d1 <<= 1', 'd1 *= 2')
# ObjSonic_CheckWallCol (Sonic/Main.asm:1179; R73D $20483A) skips
# ceiling-facing angles via ADDI.B #$40; BMI. PC's angle < -64 misses
# angles $40..$7F and wall-zips Sonic off SS loops (SS3D sequence887).
wall_guard = 'if (actwk[0].direc.b.h < -64 || actwk[0].mspeed.w == 0) return;'
if content.count(wall_guard) != 1:
    raise ValueError('PLAYER.C lmovecol ceiling guard changed upstream')
content = content.replace(wall_guard,
    'if ((signed char)((unsigned char)actwk[0].direc.b.h + 64) < 0 || actwk[0].mspeed.w == 0) return;')
# Retail R6's ObjSonic_StartRoll boosts only a stationary Sonic. The shared
# PC PLAYER.C ballset boosts every positive speed below 512 instead.
roll_minimum = 'if (actwk[0].mspeed.w >= 0 && actwk[0].mspeed.w < 512)'
if content.count(roll_minimum) != 1:
    raise ValueError('PLAYER.C ballset roll minimum changed upstream')
content = content.replace(roll_minimum,
                          'if (stageno.b.h == 4 ? actwk[0].mspeed.w == 0 : '
                          'actwk[0].mspeed.w >= 0 && actwk[0].mspeed.w < 512)')
# Retail ObjSonic_JumpHeight has no non-jump upward-speed clamp. PC PLAYER.C
# adds one at -4032, which truncates WW's -5632 electric-floor bounce.
height_cap = 'if (actwk[0].yspeed.w < -4032) actwk[0].yspeed.w = -4032;'
if content.count(height_cap) != 1:
    raise ValueError('PLAYER.C non-jump height cap changed upstream')
content = content.replace(height_cap,
                          'if (stageno.b.h != 4 && actwk[0].yspeed.w < -4032) actwk[0].yspeed.w = -4032;')
# Retail ObjSonic_MoveRollRight decelerates with add.w d4,d0 / bcc.s: the carry
# is set when the speed reaches zero as well as when it crosses it, so a
# rolling Sonic braking to exactly 0 gets +$80 (scddisasm Sonic Main.asm
# ObjSonic_MoveRollRight; same bytes D044 6404 303C 0080 in R11A $204B7E,
# R31C $204AE8, R41A $204C56, R51A $204BDC, R53C $204896, R53D $204972).
# PC PLAYER.C ballwalk_r only does so above zero. The left side (sub.w / bcc)
# keeps 0, as PC does.
roll_right = 'if (cal_speed > 0) cal_speed = 128;'
if content.count(roll_right) != 1:
    raise ValueError('PLAYER.C ballwalk_r zero crossing changed upstream')
content = content.replace(roll_right, 'if (cal_speed >= 0) cal_speed = 128;')
content = player_fixes(content)
content = hoist_tables(content, ['char chk11tbl[5]'], 'PLAYER.C')
if re.search(r'\(\([^)]*\*\)\s*&?actwk', content):
    raise ValueError('unadapted actor cast in selected player core')
prefix = '''#include "EQU.H"
#include "PLAYER.H"
#include "ACTION.H"
#include "DIRCOL.H"
#include "FCOL.H"
#include "ETC.H"
#include "IMPFUNCS.H"
extern unsigned char mapwka[8][64];
extern void soundset(short);
static unsigned char Brake_Req, Brake_Sw;
static unsigned int WaveClear;
static unsigned scd_lock_get(void) {
    return actwk[0].actfree[20] | ((unsigned)actwk[0].actfree[21] << 8);
}
static void scd_lock_set(unsigned value) {
    actwk[0].actfree[20] = value;
    actwk[0].actfree[21] = value >> 8;
}
void scd_player_statics_reset(void) { Brake_Req=Brake_Sw=0; WaveClear=0; }
void scd_player_brake_begin(void) { Brake_Req=0; }
void scd_player_brake_end(void) { if (!Brake_Req) Brake_Sw=0; }
'''
write_text(OUT/'player.c',prefix+content+'\n')
for name, choices in [('DIRCOL', None), ('FCOL', None), ('ETC', ['sinset', 'atan_sonic'])]:
    source = (UPSTREAM/f'src/{name}.C').read_text()
    if name == 'FCOL':
        # Remove by brace-aware matching after comments have been stripped.
        source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
        source = source.replace(functions(source)['scramapad'], '')
        # Retail Player_WalkFloor keeps the chosen sensor's steep angle on a
        # zero-distance tie. PC FCOL.C erases the secondary angle in that case.
        # WW1A first reaches such a tie at X=1000 on chunk 56; CC1C/CC1D at
        # X=9414 (block $058 angle $D0, slope repel). The Sega CD has no such
        # step in any zone: scddisasm Player_WalkFloor (R11A) and R31C $200C2E
        # go straight from the second FindLevelFloor to Player_PickSensor
        # (checked in all 70 R1-R8 level programs), so no zone keeps it.
        corner = 'if (dirstk[2] != -1) {'
        if source.count(corner) != 1:
            raise ValueError('FCOL.C floor corner suppression changed upstream')
        source = source.replace(corner, 'if (0 && dirstk[2] != -1) {')
        # Retail accepts exactly -14 pixels of penetration on all four
        # surfaces (CMP.W #-14; BLT). PC walls/ceiling use strict >; its floor
        # already uses >=.
        # R72D $200C8E/$200DBE/$200E60/$200F02; SS2D sequence1371 first
        # exercises the ceiling equality and must move Sonic down 14 pixels.
        if source.count('if (scd0 > -14)') != 3 or source.count('if (iScd >= -14)') != 1:
            raise ValueError('FCOL.C surface penetration thresholds changed upstream')
        source = source.replace('if (scd0 > -14)', 'if (scd0 >= -14)')
    if choices:
        parsed = functions(source)
        source = f'#include "EQU.H"\n#include "{name}.H"\n' + '\n'.join(parsed[n] for n in choices)
    source = source.replace('pActwk->xspeed.w << 8', '(int)pActwk->xspeed.w * 256')
    source = source.replace('pActwk->yspeed.w << 8', '(int)pActwk->yspeed.w * 256')
    source = source.replace('(iHi << 16)', '((unsigned int)iHi << 16)')
    if name == 'ETC':
        source = hoist_tables(source, ['unsigned short sintable[320]', 'char atantbl[257]'], 'ETC.C')
    write_text(OUT/f'{name.lower()}.c',source)
write_text(OUT/'equ.c',(UPSTREAM/'src/EQU.C').read_text())
report = {'player_functions': selected, 'terrain_sources': ['DIRCOL.C','FCOL.C'],
          'math_functions': ['sinset','atan_sonic'],
          'hoisted_tables': ['chk11tbl','sintable','atantbl'],
          'adaptations': ['endian-aware numeric unions', 'scratch timer byte access',
                         'defined signed velocity multiplication',
                         'read-only local lookup tables given static storage',
                         'bounded Sega CD big-endian chunk lookup replaces scramapad'],
          'excluded': ['full play00 dispatcher', 'time travel', 'object collisions and spawning',
                       'animation dispatcher', 'water', 'death/lives', 'original FM sequencing and soundtrack']}
write_text(ROOT/'build/player-source.json',json.dumps(report,indent=2)+'\n')

action = functions((OUT/'action.c').read_text())
write_text(OUT/'movement.c','#include "EQU.H"\n#include "ACTION.H"\n'+ '\n'.join(action[n] for n in ['speedset','speedset2'])+'\n')
# A desktop reference retains the selected upstream function bodies, including
# native little-endian scratch-word casts. Only its unused sprite pointer slot
# is represented as a 32-bit token to reproduce the PC actor's 68-byte layout.
import shutil
reference=ROOT/'build/player-reference'
reference.mkdir(parents=True,exist_ok=True)
for header in OUT.glob('*.H'):
    copy_file(header,reference/header.name)
types=(reference/'TYPES.H').read_text().replace('sprite_pattern** patbase;', 'unsigned int patbase;')
write_text(reference/'TYPES.H',types)
write_text(reference/'player.c',prefix+'\n#include <stddef.h>\n_Static_assert(sizeof(sprite_status)==68 && offsetof(sprite_status,actfree)==46,"PC actor layout");\n'+player_fixes('\n'.join(player[n] for n in selected))+'\n')
for filename in ['dircol.c','fcol.c','etc.c','equ.c','movement.c']:
    copy_file(OUT/filename,reference/filename)

# Selected original spring impulses and hurt/death transitions. Object broad
# phase/contact classification and sprite animation belong to the new frontend.
spring_names=['sjumpmove','sdushmove','sjump2move','sjump3move']
damage_names=['playdamagechk','playdieset']
spring=functions((UPSTREAM/'src/SPRING.C').read_text())
damage=functions((UPSTREAM/'src/R1/COLI1.C').read_text())
interaction='\n'.join([spring[n] for n in spring_names]+[damage[n] for n in damage_names]+[player['play00damage_sub']])
interaction=interaction.replace('  sjump3move2(actionwk);','  /* Spring animation is advanced by the Saturn object scheduler. */')
headers='''#include "EQU.H"
#include "PLAYER.H"
#include "SPRING.H"
#include "ETC.H"
#include "scd_actor.h"
extern void soundset(short);
extern short playdieset(sprite_status *);
'''
# Transform scratch-word assignments before reads, rejecting any leftover casts.
pattern=r'\(\((unsigned short|short)\*\)(&actwk\[0\]|pActwk|actionwk|a1)\)\[(\d+)\]'
adapted=re.sub(pattern+r' = ([^;]+);',lambda m:f'scd_word_set({m[2]}, {m[3]}, {m[4]});',interaction)
adapted=re.sub(pattern,lambda m:('((short)' if m[1]=='short' else '(')+f'scd_word_get({m[2]}, {m[3]}))',adapted)
if re.search(pattern,adapted):raise ValueError('unadapted interaction scratch access')
write_text(OUT/'interaction.c',headers+adapted+'\n')
write_text(reference/'interaction.c',headers+interaction+'\n')
report['spring_functions']=spring_names
report['damage_functions']=damage_names+['play00damage_sub']
report['adaptations']+=['explicit scratch words for spring strength, hurt timer and death origin',
                         'spring contact callbacks and animation supplied by object frontend']
report['excluded'].remove('object collisions and spawning')
report['excluded'].remove('death/lives')
report['excluded']+=['original game-over, checkpoints and life/score progression']
report['excluded']+=['remaining original object behaviors; bounded native scheduler integrates supported types']
write_text(ROOT/'build/player-source.json',json.dumps(report,indent=2)+'\n')
