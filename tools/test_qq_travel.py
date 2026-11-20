#!/usr/bin/env python3
"""Search controller input for one natural QQ warp, then observe Saturn arrival.

Quartz Quadrant (round 5, level-select zone 3) on the shared natural-travel
driver (tools/test_tt_travel.py run_travel). The derived host
(tools/qq_route_search.c) changes only search goals and termination, not the
gameplay step: a committed warp to --to ends the run; a warp to another era,
the tally or a death prunes the branch. The derived Saturn harness adds one
read-only slave-owner observation: every resumed post-arrival update must see
the R5 background slave ready. No gameplay RAM writes, debug era keys, or
constructed time-post state are used.

Era letters as level select: A Present, B Past, C Good Future, D Bad Future.
Natural pairs: A->B, A->D, B->A, C->A, D->A. Stored scripts:
tests/routes/qq/travel/qq<act><era><to>.txt.
"""
from test_qq_route import NATIVE, ORIGINAL, records
from test_tt_travel import ROOT, once, run_travel

ZONE = 3


def host_source(want):
    """want: destination era index, or -1 for any era other than the start."""
    text = (ROOT/'tools/qq_route_search.c').read_text()
    text = once(text, 'static void load(void){',
                f'static int travel_destination;\nstatic const int travel_want={want};\nstatic void load(void){{\n    travel_destination=-1;')
    # The QQ host advances timeWarpTimer per VBlank (scd_world_step_vblanks).
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
    new = '''fprintf(stderr,"QQ natural travel: sequence=%u act=%u era=%u destination=%d ticks=%u\\n",
                    sequence,act,era,travel_destination,scd_world_get().ticks);'''
    return once(text, old, new)


def harness_source(symbols):
    ready = [v for k, v in symbols.items() if k == '_bg_slave_ready' or k.startswith('_bg_slave_ready.lto_priv.')]  # LTO may suffix the static
    assert len(ready) == 1, ('bg_slave_ready symbol', ready)
    text = (ROOT/'tools/emulator_test.c').read_text()
    anchor = 'unsigned standing=ram_word(ram,world_mailbox+68);'
    address = 0x100000 + (int(ready[0], 16) & 0xfffff)
    return once(text, anchor, anchor + f'\n                        printf("QQ travel ready: %u %u\\n",sequence,ram_word(ram,{address}u));')


def slave_ready(log, settled):
    ready = dict(records(log, 'QQ travel ready'))
    assert all(ready.get(r[0]) == 1 for r in settled), 'slave unavailable after arrival'


def main():
    # src/music_routes.h: zone 3 era cue c -> slot 18+c; the audio mailbox reports slot+2.
    run_travel(dict(label='QQ', zone=ZONE, routes='tests/routes/qq/travel', prefix='qq', host_source=host_source,
                    native=NATIVE, original=ORIGINAL, seed=51, limit=46000, track=20,
                    harness=harness_source, settled=slave_ready, vblank_timer=True, doc=__doc__))


if __name__ == '__main__':
    main()
