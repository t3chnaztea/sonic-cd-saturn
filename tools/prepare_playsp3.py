#!/usr/bin/env python3
"""Generate Collision Chaos's terrain bumper blocks (R3/PLAYSP3.C) and the break
animation the breakable ones spawn (R3/BOBINB.C, actor 41).

build/probe-source/playsp3.c (Saturn/host, little-endian scratch accessors as
tools/prepare_boss.py) and build/player-reference/playsp3.c (original PC casts).
Only includes change, playsp becomes scd_playsp3 (src/player.c calls it in
Collision Chaos, as PLAYER.C calls the round's playsp), and sub_sync(146) (the
LOADER2.C WaveRequest(85) bumper PCM) goes through src/boss.c sub_sync.
"""
import re
from audit_source import UPSTREAM
from prepare_boss import NATIVE, REFERENCE, HEAD, ACCESSORS, adapt
from generated_io import write_text

PRELUDE = '''#define playsp scd_playsp3
#include "EQU.H"
#include "ACTION.H"
#include "ACTSET.H"
#include "ETC.H"
#include "PLAYSUB.H"
#include "SCORE.H"
void playsp(void);
void boyo(void);
char bycol_sub0(short cal_x, short cal_y);
void bob(short i, short cal_x, short cal_y, short block_back);
void bob_s(short i, short cal_x, short cal_y, short block_back);
void bob_j(void);
void bob0(short i, short cal_x, short cal_y, short block_back);
void bob1(short i, short cal_x, short cal_y, short block_back);
void bob_s0(short i, short cal_x, short cal_y, short block_back);
void bob2(short i, short cal_x, short cal_y, short block_back);
void bob3(short i, short cal_x, short cal_y, short block_back);
void bob4(short i, short cal_x, short cal_y, short block_back);
void bob5(short i, short cal_x, short cal_y, short block_back);
void bob6(short i, short cal_x, short cal_y, short block_back);
void bobinbreak(sprite_status* bobinwk);
extern short scramapad(sprite_status *actor, short x, short y);
extern void block_wrt(unsigned short BlockNo, unsigned short xOffs, unsigned short yOffs);
extern void sub_sync(short ReqNo);
extern void soundset(short ReqNo);
extern void tensuu0(sprite_status *tensuuwk, unsigned char uf_data);
extern void frameout(sprite_status *p);
extern void scoreup(unsigned int points);
'''


def main():
    read = lambda path: re.sub(r'#include "[^"]*"\n', '', (UPSTREAM / path).read_text(encoding='latin1'))
    body = read('src/R3/PLAYSP3.C') + '\n' + read('src/R3/BOBINB.C') + '\n'
    # Sega CD bob_s/bob_s0 (R32B $2068AE/$206924) aim from the 16x16 block
    # centre: andi.w #-16 then addq.w #8 on both axes. The PC build masks to
    # 8 pixels (& 65528), which turns CC2C/CC2D's straight bounces diagonal.
    for axis in ('x', 'y'):
        pc = f'(unsigned short)cal_{axis} & 65528'
        if body.count(pc) != 2:
            raise ValueError(f'PLAYSP3.C bob_s/bob_s0 {axis} mask changed')
        body = body.replace(pc, f'((unsigned short)cal_{axis} & 65520) + 8')
    # Sega CD bob2 (fcol entry 12) picks the opposite axis from the PC build:
    # x & 15 < 8 bounces vertically (bob0) unflipped and horizontally (bob1)
    # when the block is X-flipped, and the reverse for x & 15 >= 8. Identical
    # in all ten R3 programs (R31C $206A9A, R32B $20695C). CC1C seq 3566.
    start, end = body.index('void bob2('), body.index('void bob3(')
    bob2 = body[start:end]
    if bob2.count('bob0(i, cal_x, cal_y, block_back)') != 2 or bob2.count('bob1(i, cal_x, cal_y, block_back)') != 2:
        raise ValueError('PLAYSP3.C bob2 changed')
    bob2 = bob2.replace('bob0(i,', 'bobX(i,').replace('bob1(i,', 'bob0(i,').replace('bobX(i,', 'bob1(i,')
    body = body[:start] + bob2 + body[end:]
    native = adapt(body)
    # Sega CD R3 bob writes its four blocks through a routine that loads
    # move.l #$800000,d7 (R32B $203280). d7 is RunObjects' dbf counter, so
    # every actor after the player skips the update in which a breakable
    # bumper breaks (probe: CC2B rows 689 and 698). The PC build has no such
    # side effect; src/objects.c scd_objects_abort_run models it.
    if native.count('sub_sync(146);') != 1:
        raise ValueError('PLAYSP3.C bob bumper-break request changed')
    native = native.replace('sub_sync(146);', 'sub_sync(146); scd_objects_abort_run();')
    native = '__attribute__((weak)) void scd_objects_abort_run(void) {}\n' + native
    if HEAD.search(native):
        raise ValueError('unadapted PC cast')
    patterns = sorted(set(re.findall(r'->patbase = (\w+);', body)))
    if patterns != ['pat_bobinbreak']:
        raise ValueError(f'BOBINB.C patterns changed: {patterns}')
    reference = body.replace('->patbase = pat_bobinbreak;', '->patbase = 1u;')
    tail = '\n/* ACT3xx.C act_tbl[40]: src/boss.c runs actor 41 in the PC actor slots. */\n' \
           'void (*scd_zone_actor(unsigned id))(sprite_status *) { return id == 41 ? bobinbreak : 0; }\n'
    write_text(NATIVE / 'playsp3.c',PRELUDE + ACCESSORS + native + tail)
    write_text(REFERENCE / 'playsp3.c',PRELUDE + reference + tail)
    print(f'PLAYSP3.C and BOBINB.C: {len(HEAD.findall(body))} PC casts adapted')


if __name__ == '__main__':
    main()
