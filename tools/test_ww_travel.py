#!/usr/bin/env python3
"""Search a controller-only Wacky Workbench warp and verify Saturn arrival.

Era letters: A Present, B Past, C Good Future, D Bad Future. The five
natural pairs per act are A->B, A->D, B->A, C->A and D->A.
"""
from test_qq_route import NATIVE, ORIGINAL
from test_tt_travel import ROOT, once, run_travel

ZONE = 4


def host_source(want):
    text = (ROOT/'tools/qq_route_search.c').read_text()
    text = once(text, 'static void load(void){',
                f'static int travel_destination;\nstatic const int travel_want={want};\nstatic void load(void){{\n    travel_destination=-1;')
    text = once(text, 'if(scd_world_step_vblanks(p,world_vblanks)>=0)dead=2;',
                'int target=scd_world_step_vblanks(p,world_vblanks);if(target>=0){'
                'if(travel_want>=0?target==travel_want:target!=(int)era){travel_destination=target;done=1;}else dead=4;}')
    text = once(text, 'if(result.phase==SCD_ACT_DONE)done=1;', 'if(result.phase){dead=3;done=0;}')
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
    old = '''fprintf(stderr,"Tally complete: sequence=%u act=%u era=%u score=%u boss_hits=%u lowered=%u grind_left=%d escaped=%u\\n",
                    sequence,act,era,p.score,boss_hits,boss_lowered,grind_left,escaped);'''
    new = '''fprintf(stderr,"WW natural travel: sequence=%u act=%u era=%u destination=%d ticks=%u\\n",
                    sequence,act,era,travel_destination,scd_world_get().ticks);'''
    return once(text, old, new)


def main():
    # src/music_routes.h: zone 4 era cue c -> slot 22+c; mailbox reports slot+2.
    run_travel(dict(label='WW', zone=ZONE, routes='tests/routes/ww/travel', prefix='ww', host_source=host_source,
                    native=NATIVE+['src/boss_r6.c', 'src/background_r6.c'], original=ORIGINAL+['boss_6'],
                    seed=51, limit=46000, track=24,
                    vblank_timer=True,
                    defines=['-DROUTE_WW'], doc=__doc__))


if __name__ == '__main__':
    main()
