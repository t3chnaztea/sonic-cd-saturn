#!/usr/bin/env python3
"""Controller-only Metallic Madness natural travel and Saturn arrival.

Metallic Madness (round 8, level-select zone 6) on the shared natural-travel
driver (tools/test_tt_travel.py run_travel). The derived host is the ROUTE_MM
build of tools/qq_route_search.c; only the search goal and committed-warp
termination change, not the gameplay step. No gameplay RAM writes, debug era
keys or constructed time-post state are used.

Era letters: A Present, B Past, C Good Future, D Bad Future. Five pairs per
act: A->B, A->D, B->A, C->A, D->A. Stored scripts:
tests/routes/mm/travel/mm<act><era><to>.txt.
"""
from test_qq_route import NATIVE, ORIGINAL
from test_qq_travel import host_source as qq_host_source
from test_tt_travel import once, run_travel

ZONE = 6


def host_source(want):
    return once(qq_host_source(want), 'QQ natural travel:', 'MM natural travel:')


def main():
    # src/music_routes.h: zone 6 era cue c -> slot 30+c; the audio mailbox reports slot+2.
    run_travel(dict(label='MM', zone=ZONE, routes='tests/routes/mm/travel', prefix='mm', host_source=host_source,
                    native=NATIVE+['src/boss_r8.c'], original=ORIGINAL+['boss_8', 'ending_8'],
                    seed=51, limit=46000, track=32, vblank_timer=True,
                    defines=['-DROUTE_MM'], doc=__doc__))


if __name__ == '__main__':
    main()
