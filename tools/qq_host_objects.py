#!/usr/bin/env python3
"""Host copy of src/objects.c with the Quartz Quadrant actors wired in.

usage: qq_host_objects.py OUT_DIR

tools/test-qq-actors.sh compiles this copy. Until the R5 ids and the zone 3
entry land in src/scd_objects.h / src/objects_zone_ops.inc it adds
provisional SCD_OBJ_R5_* ids (OUT_DIR/qq_ids.h, zone-local 136..154) and
qq_zone_ops as zone 3 (OUT_DIR/objects_zone_ops.inc). It always appends a
host-only snapshot of the native object state (SCD_HOST_TEST) so the
fixture can replay one-update contacts from a saved world."""
import sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
text=Path('src/objects.c').read_text()
NAMES='DENDEN SASORI KEMUSI KUMO IWA5 HARI5F HARIR5 IWA5ROLL KUZURE5 IWA5WAVE BURANKO5 HASIRA5 HASHI5 BELTSW5 SHOOT5 MOVIE5 FRIEND5 ET5 KOWASI5'.split()
ids='#ifndef SCD_OBJ_R5_DENDEN\nenum{'+','.join(f'SCD_OBJ_R5_{n}={136+i}' for i,n in enumerate(NAMES))+'};\n#endif\n'
if 'SCD_OBJ_R5_DENDEN' in Path('src/scd_objects.h').read_text():ids='/* SCD_OBJ_R5_* come from scd_objects.h. */\n'
(out/'qq_ids.h').write_text(ids)
ops=Path('src/objects_zone_ops.inc').read_text()
if 'qq_zone_ops' not in ops.split('*/',1)[1]:
    a='static const scd_zone_ops *const zone_ops_table[7]={0};'
    if a not in ops:raise SystemExit('qq_host_objects: zone_ops_table anchor missing')
    ops=ops.replace(a,'#include "objects_qq.inc"\nstatic const scd_zone_ops *const zone_ops_table[7]={[3]=&qq_zone_ops};')
(out/'objects_zone_ops.inc').write_text(ops)
text=text.replace('#include "scd_objects.h"','#include "scd_objects.h"\n#include "qq_ids.h"',1)
# Host-only snapshot of the native object state, so the fixture can replay
# one-update contacts from a saved world.
text+='''
#ifdef SCD_HOST_TEST
typedef struct{slot pool[SCD_OBJECT_CAPACITY];unsigned control_actor;uint8_t consumed[SCD_PLACEMENT_CAPACITY],deferred[SCD_PLACEMENT_CAPACITY];
    int pending_post,pending_generator,good_future,projector_destroyed,travel_protection;scd_object_stats stats;}qq_host_state;
size_t scd_qq_host_size(void){return sizeof(qq_host_state);}
void scd_qq_host_save(void *b){qq_host_state *s=b;memcpy(s->pool,pool,sizeof(pool));s->control_actor=control_actor;
    memcpy(s->consumed,consumed,sizeof(consumed));memcpy(s->deferred,deferred_reload,sizeof(deferred_reload));s->pending_post=pending_post;
    s->pending_generator=pending_generator;s->good_future=good_future;s->projector_destroyed=projector_destroyed;s->travel_protection=travel_protection;s->stats=stats;}
void scd_qq_host_load(const void *b){const qq_host_state *s=b;memcpy(pool,s->pool,sizeof(pool));control_actor=s->control_actor;
    memcpy(consumed,s->consumed,sizeof(consumed));memcpy(deferred_reload,s->deferred,sizeof(deferred_reload));pending_post=s->pending_post;
    pending_generator=s->pending_generator;good_future=s->good_future;projector_destroyed=s->projector_destroyed;travel_protection=s->travel_protection;stats=s->stats;}
int scd_qq_host_good_future(void){return good_future;}
#endif
'''
(out/'objects.c').write_text(text)
