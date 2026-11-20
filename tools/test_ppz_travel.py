#!/usr/bin/env python3
"""Search controller input for one natural PPZ warp, then observe Saturn arrival.

Palmtree Panic (round 1, level-select zone 0) on the shared natural-travel
driver (tools/test_tt_travel.py run_travel). The derived host
(tools/cc_campaign_search.c, plain PPZ mode ``p<act>:<era>``, the host of
tools/test_ppz_route.py) changes only search goals and termination, not the
gameplay step: a committed warp to --to ends the run; a warp to another era,
the tally or a death prunes the branch. The Saturn harness is
tools/emulator_test.c unchanged. No gameplay RAM writes, debug era keys, or
constructed time-post state are used.

Each case starts at one level-select title card, so its stored script is
searched on the current PLC 2 unlock and needs no lead (unlike the multi-card
tests/routes/ppz/natural-*.pads journey recordings).

Era letters as level select: A Present, B Past, C Good Future, D Bad Future.
Natural pairs: A->B, A->D, B->A, C->A, D->A. Stored scripts:
tests/routes/ppz/travel/ppz<act><era><to>.txt.
"""
from test_ppz_route import NATIVE, ORIGINAL
from test_tt_travel import ROOT, once, run_travel

ZONE = 0


def host_source(want):
    """want: destination era index, or -1 for any era other than the start."""
    text = (ROOT/'tools/cc_campaign_search.c').read_text()
    text = once(text, 'static void load(void){',
                f'static int travel_destination;\nstatic const int travel_want={want};\nstatic void load(void){{\n    travel_destination=-1;')
    # ppz_step: the warp commit is the goal (plain mode used to prune it).
    text = once(text, '        if(ppz_mode!=PPZ_JOURNEY || act==2){dead=1;return;}',
                '        if(travel_want>=0?destination==travel_want:destination!=(int)era){travel_destination=destination;done=1;}'
                'else dead=1;\n        return;')
    # The tally prunes the branch.
    text = once(text, '        if(ppz_mode==PPZ_JOURNEY && act<2 && milestone!=4){dead=1;return;}', '        dead=1;return;')
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
    new = '''fprintf(stderr,"PPZ natural travel: sequence=%u act=%u era=%u destination=%d ticks=%u%s",
                    sequence,act,era,travel_destination,scd_world_get().ticks,zone?"\\n":"");'''
    return once(text, old, new)


def main():
    # src/music_routes.h: zone 0 keeps the original slots (cue c -> slot c); the audio mailbox reports slot+2.
    # cc_campaign_search.c replay accepts at most 40000 updates.
    run_travel(dict(label='PPZ', zone=ZONE, routes='tests/routes/ppz/travel', prefix='ppz', host_source=host_source,
                    native=NATIVE, original=ORIGINAL, seed=41, limit=40000, track=2, mode_prefix='p', doc=__doc__))


if __name__ == '__main__':
    main()
