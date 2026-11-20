#!/usr/bin/env python3
"""Search controller input for one natural CC warp, then observe Saturn arrival.

Collision Chaos (round 3, level-select zone 1) port of tools/test_tt_travel.py,
sharing its driver (run_travel). The derived host (tools/cc_campaign_search.c,
plain mode ``ACT:ERA``) changes only search goals and termination, not the
gameplay step: a committed warp (scd_world_step >= 0, Main.asm
ObjSonic_TimeWarp timer 230) to --to ends the run; a warp to another era, the
tally, or a death prunes the branch. The Saturn harness is tools/emulator_test.c
unchanged (snapshotted into the output). No gameplay RAM writes, debug era
keys, or constructed time-post state are used.

Era letters as level select: A Present, B Past, C Good Future, D Bad Future.
Level select starts the Present with no Good Future, so the natural pairs are
A->B (past post), A->D (future post), B->A (future post), C->A / D->A (past post).
Stored scripts: tests/routes/cc/travel/cc<act><era><to>.txt.
"""
from test_cc2_route import NATIVE, ORIGINAL
from test_tt_travel import ROOT, once, run_travel

ZONE = 1


def host_source(want):
    """want: destination era index, or -1 for any era other than the start."""
    text = (ROOT/'tools/cc_campaign_search.c').read_text()
    text = once(text, 'static void load(void){',
                f'static int travel_destination;\nstatic const int travel_want={want};\nstatic void load(void){{\n    travel_destination=-1;')
    text = once(text, '''    if(result.phase==SCD_ACT_DONE){
        if(plain>=0 || (act==0?milestone==4:milestone==2))done=1;else dead=1;
    }''', '    if(result.phase){dead=1;done=0;}')
    text = once(text, 'if(destination>=0 && plain>=0)dead=1;',
                'if(destination>=0 && plain>=0){if(!dead && (travel_want>=0?destination==travel_want:destination!=(int)era))'
                '{travel_destination=destination;done=1;}else{dead=1;done=0;}return;}')
    begin = text.index('static uint32_t cell_key(void){')
    end = text.index('static void archive(void){', begin)
    text = text[:begin] + '''static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();scd_world_state w=scd_world_get();
    unsigned x=(unsigned)(p.x/65536<0?0:p.x/65536>16383?16383:p.x/65536)/32;
    unsigned y=(unsigned)(p.y/65536<0?0:p.y/65536>2047?2047:p.y/65536)/32;
    return x|(y<<9)|((unsigned)(w.direction+1)<<15)|((w.ticks/8)<<17);
}
static double cell_value(void){
    scd_world_state w=scd_world_get();
    return w.ticks*10000.0+(w.direction?1000000.0:0.0)+scd_player_get().x/65536;
}
''' + text[end:]
    old = '''fprintf(stderr,"Tally complete: sequence=%u era=%u good_future=%u generator=%u warps=%u score=%u%s",
                    sequence,era,scd_world_get().good_future,generator,warps,p.score,zone?"\\n":"");'''
    new = '''fprintf(stderr,"CC natural travel: sequence=%u act=%u era=%u destination=%d ticks=%u%s",
                    sequence,act,era,travel_destination,scd_world_get().ticks,zone?"\\n":"");'''
    return once(text, old, new)


def main():
    # src/music_routes.h: zone 1 era cue c -> slot 10+c; the audio mailbox reports slot+2.
    # cc_campaign_search.c replay accepts at most 40000 updates.
    run_travel(dict(label='CC', zone=ZONE, routes='tests/routes/cc/travel', prefix='cc', host_source=host_source,
                    native=NATIVE, original=ORIGINAL, seed=41, limit=40000, track=12, doc=__doc__))


if __name__ == '__main__':
    main()
