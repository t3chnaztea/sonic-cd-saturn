#!/usr/bin/env python3
"""Host copy of src/objects.c with the Wacky Workbench actors wired in.

usage: ww_host_objects.py OUT_DIR

tools/test-ww-actors.sh compiles this copy. Until objects_zone_ops.inc lists
ww_zone_ops as zone 4 it adds that entry to the copy. It always appends a
host-only snapshot of the native object state (SCD_HOST_TEST) so the fixture
can replay one-update contacts from a saved world."""
import sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
text=Path('src/objects.c').read_text()
ops=Path('src/objects_zone_ops.inc').read_text()
if 'ww_zone_ops' not in ops.split('*/',1)[1]:
    import re
    m=re.search(r'static const scd_zone_ops \*const zone_ops_table\[7\]=\{([^}]*)\};',ops)
    if not m:raise SystemExit('ww_host_objects: zone_ops_table anchor missing')
    entries=m[1].strip()
    entries='[4]=&ww_zone_ops' if entries in ('','0') else entries+',[4]=&ww_zone_ops'
    ops=ops.replace(m[0],'#include "objects_ww.inc"\nstatic const scd_zone_ops *const zone_ops_table[7]={'+entries+'};')
(out/'objects_zone_ops.inc').write_text(ops)
text+='''
#ifdef SCD_HOST_TEST
typedef struct{slot pool[SCD_OBJECT_CAPACITY];unsigned control_actor,enemy_chain;uint8_t consumed[SCD_PLACEMENT_CAPACITY],deferred[SCD_PLACEMENT_CAPACITY];
    int pending_post,pending_generator,good_future,projector_destroyed,travel_protection;scd_object_stats stats;
    uint16_t colorwk[2][64];uint64_t colorset[2];unsigned char st6;short gt;int16_t block_list[128];unsigned char sw[32];int16_t link[128];int ranum;}ww_host_state;
size_t scd_ww_host_size(void){return sizeof(ww_host_state);}
void scd_ww_host_save(void *b){ww_host_state *s=b;memcpy(s->pool,pool,sizeof(pool));s->control_actor=control_actor;s->enemy_chain=(unsigned short)emyscorecnt;
    memcpy(s->consumed,consumed,sizeof(consumed));memcpy(s->deferred,deferred_reload,sizeof(deferred_reload));s->pending_post=pending_post;
    s->pending_generator=pending_generator;s->good_future=good_future;s->projector_destroyed=projector_destroyed;s->travel_protection=travel_protection;s->stats=stats;
    memcpy(s->colorwk,ww_colorwk,sizeof(ww_colorwk));memcpy(s->colorset,ww_colorset,sizeof(ww_colorset));s->st6=st6clrchg;s->gt=gametimer.w;memcpy(s->block_list,ww_block_list,sizeof(ww_block_list));memcpy(s->sw,switchflag,32);memcpy(s->link,ww_link,sizeof(ww_link));s->ranum=ranum;}
void scd_ww_host_load(const void *b){const ww_host_state *s=b;memcpy(pool,s->pool,sizeof(pool));control_actor=s->control_actor;emyscorecnt=s->enemy_chain;
    memcpy(consumed,s->consumed,sizeof(consumed));memcpy(deferred_reload,s->deferred,sizeof(deferred_reload));pending_post=s->pending_post;
    pending_generator=s->pending_generator;good_future=s->good_future;projector_destroyed=s->projector_destroyed;travel_protection=s->travel_protection;stats=s->stats;
    memcpy(ww_colorwk,s->colorwk,sizeof(ww_colorwk));memcpy(ww_colorset,s->colorset,sizeof(ww_colorset));st6clrchg=s->st6;gametimer.w=s->gt;memcpy(ww_block_list,s->block_list,sizeof(ww_block_list));memcpy(switchflag,s->sw,32);memcpy(ww_link,s->link,sizeof(ww_link));ranum=s->ranum;}
int scd_ww_host_good_future(void){return good_future;}
#endif
'''
(out/'objects.c').write_text(text)
