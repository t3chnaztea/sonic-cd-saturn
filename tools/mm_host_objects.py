#!/usr/bin/env python3
"""Host copy of src/objects.c with the Metallic Madness actors wired in.

usage: mm_host_objects.py OUT_DIR

tools/test-mm-actors.sh compiles this copy with production R8 ids and zone
operations unchanged. Only host state snapshot helpers are appended so the
fixture can replay one-update contacts from a saved world.
"""
import sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
text=Path('src/objects.c').read_text()
(out/'mm_ids.h').write_text('/* R8 ids come from production scd_objects.h. */\n')
(out/'objects_zone_ops.inc').write_text(Path('src/objects_zone_ops.inc').read_text())
text=text.replace('#include "scd_objects.h"','#include "scd_objects.h"\n#include "mm_ids.h"',1)
# objects.c's own chain counter (enemy_chain) is being removed in favour of
# the global emyscorecnt; snapshot it only while it exists.
chain='enemy_chain' in text
text+='''
#ifdef SCD_HOST_TEST
typedef struct{slot pool[SCD_OBJECT_CAPACITY];unsigned control_actor,chain;uint8_t consumed[SCD_PLACEMENT_CAPACITY],deferred[SCD_PLACEMENT_CAPACITY];
    int pending_post,pending_generator,good_future,projector_destroyed,travel_protection;scd_object_stats stats;uint8_t flagwork[sizeof(tp_flagwork)];uint8_t mmpal[64][4];}mm_host_state;
size_t scd_mm_host_size(void){return sizeof(mm_host_state);}
void scd_mm_host_save(void *b){mm_host_state *s=b;memcpy(s->pool,pool,sizeof(pool));s->control_actor=control_actor;MM_CHAIN_SAVE
    memcpy(s->consumed,consumed,sizeof(consumed));memcpy(s->deferred,deferred_reload,sizeof(deferred_reload));s->pending_post=pending_post;
    s->pending_generator=pending_generator;s->good_future=good_future;s->projector_destroyed=projector_destroyed;s->travel_protection=travel_protection;s->stats=stats;memcpy(s->flagwork,tp_flagwork,sizeof(tp_flagwork));memcpy(s->mmpal,mm_room_palette,sizeof(s->mmpal));}
void scd_mm_host_load(const void *b){const mm_host_state *s=b;memcpy(pool,s->pool,sizeof(pool));control_actor=s->control_actor;MM_CHAIN_LOAD
    memcpy(consumed,s->consumed,sizeof(consumed));memcpy(deferred_reload,s->deferred,sizeof(deferred_reload));pending_post=s->pending_post;
    pending_generator=s->pending_generator;good_future=s->good_future;projector_destroyed=s->projector_destroyed;travel_protection=s->travel_protection;stats=s->stats;memcpy(tp_flagwork,s->flagwork,sizeof(tp_flagwork));memcpy(mm_room_palette,s->mmpal,sizeof(s->mmpal));}
const uint8_t *scd_mm_host_flagwork(void){return tp_flagwork;}
int scd_mm_host_good_future(void){return good_future;}
void scd_mm_host_projector(int v){projector_destroyed=v;}
unsigned scd_mm_host_chain(void){return MM_CHAIN_GET;}
#endif
'''
text=text.replace('MM_CHAIN_SAVE','s->chain=enemy_chain;' if chain else '').replace('MM_CHAIN_LOAD','enemy_chain=s->chain;' if chain else '').replace('MM_CHAIN_GET','enemy_chain' if chain else '(unsigned)emyscorecnt')
(out/'objects.c').write_text(text)
