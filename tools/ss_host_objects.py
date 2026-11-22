#!/usr/bin/env python3
"""Host copy of src/objects.c with the Stardust Speedway actors wired in.

usage: ss_host_objects.py OUT_DIR

tools/test-ss-actors.sh compiles this copy with production R7 ids and zone
operations unchanged. Only host state snapshot helpers are appended so the
fixture can replay one-update contacts from a saved world.
"""
import sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
text=Path('src/objects.c').read_text()
(out/'ss_ids.h').write_text('/* R7 ids come from production scd_objects.h. */\n')
(out/'objects_zone_ops.inc').write_text(Path('src/objects_zone_ops.inc').read_text())
# objects.c's own chain counter (enemy_chain) is being removed in favour of
# the global emyscorecnt; snapshot it only while it exists.
chain='enemy_chain' in text
text+='''
#ifdef SCD_HOST_TEST
typedef struct{slot pool[SCD_OBJECT_CAPACITY];unsigned control_actor,chain;uint8_t consumed[SCD_PLACEMENT_CAPACITY],deferred[SCD_PLACEMENT_CAPACITY];
    int pending_post,pending_generator,good_future,projector_destroyed,travel_protection;scd_object_stats stats;uint8_t flagwork[sizeof(tp_flagwork)];}ss_host_state;
size_t scd_ss_host_size(void){return sizeof(ss_host_state);}
void scd_ss_host_save(void *b){ss_host_state *s=b;memcpy(s->pool,pool,sizeof(pool));s->control_actor=control_actor;SS_CHAIN_SAVE
    memcpy(s->consumed,consumed,sizeof(consumed));memcpy(s->deferred,deferred_reload,sizeof(deferred_reload));s->pending_post=pending_post;
    s->pending_generator=pending_generator;s->good_future=good_future;s->projector_destroyed=projector_destroyed;s->travel_protection=travel_protection;s->stats=stats;memcpy(s->flagwork,tp_flagwork,sizeof(tp_flagwork));}
void scd_ss_host_load(const void *b){const ss_host_state *s=b;memcpy(pool,s->pool,sizeof(pool));control_actor=s->control_actor;SS_CHAIN_LOAD
    memcpy(consumed,s->consumed,sizeof(consumed));memcpy(deferred_reload,s->deferred,sizeof(deferred_reload));pending_post=s->pending_post;
    pending_generator=s->pending_generator;good_future=s->good_future;projector_destroyed=s->projector_destroyed;travel_protection=s->travel_protection;stats=s->stats;memcpy(tp_flagwork,s->flagwork,sizeof(tp_flagwork));}
int scd_ss_host_good_future(void){return good_future;}
void scd_ss_host_projector(int v){projector_destroyed=v;}
unsigned scd_ss_host_chain(void){return SS_CHAIN_GET;}
#endif
'''
text=text.replace('SS_CHAIN_SAVE','s->chain=enemy_chain;' if chain else '').replace('SS_CHAIN_LOAD','enemy_chain=s->chain;' if chain else '').replace('SS_CHAIN_GET','enemy_chain' if chain else '(unsigned)emyscorecnt')
(out/'objects.c').write_text(text)
