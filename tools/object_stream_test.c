/* Differential test of the actual native stream against its pre-V055 loop.
   Include the implementation to compare private slots and ownership, not just
   a lossy render view. Boss actor creation is weak/no-op in this focused test;
   the full Saturn journey separately checks the linked boss implementation. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "../src/objects.c"

static void reference_stream(int x) {
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && pool[i].origin!=65535 && !(pool[i].type==SCD_OBJ_PROJECTOR && pool[i].state>=2) && !(pool[i].type==SCD_OBJ_TUNNEL && pool[i].state) && magnitude(((pool[i].type==SCD_OBJ_SWING || pool[i].type==SCD_OBJ_MOVING_SPRING || (pool[i].type==SCD_OBJ_ANIMAL && !(pool[i].subtype&127)))?pool[i].home_x:actwk[i+1].xposi.w.h)-x)>640)remove_slot(i);
    if(!load_placements)return;
    for(unsigned j=0;j<active_placement_count;j++) {
        const scd_placement *e=&active_placements[j];
        if(e->type==SCD_OBJ_BOSS){if(!consumed[j] && (e->eras&era_bit) && magnitude(e->x-x)<=480){consumed[j]=1;scd_boss_create(e->x,e->y);}continue;}
        if(magnitude(e->x-x)>640)deferred_reload[j]=0;
        if(deferred_reload[j])continue;
        if((e->type==SCD_OBJ_PROJECTOR && projector_destroyed) || (e->type==SCD_OBJ_ANIMAL && !(e->subtype&128) && current_era>=2 && !good_future))continue;
        if(((current_era==2 || (good_future && (current_era!=0 || e->subtype))) && enemy(e->type)) || (consumed[j] && e->type!=SCD_OBJ_TIMEPOST && e->type!=SCD_OBJ_SONIC_HOLE) || !(e->eras&era_bit) || magnitude(e->x-x)>480)continue;
        unsigned i;for(i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && pool[i].origin==j)break;
        if(i<SCD_OBJECT_CAPACITY)continue;
        int index=scd_objects_spawn(e->type,e->x,e->y,e->subtype,e->flags);
        if(index<0)break;pool[index].origin=j;actwk[index+1].userflag.b.l=e->secondary;
        if(consumed[j] && e->type==SCD_OBJ_SONIC_HOLE)pool[index].state=1;
        if(consumed[j] && e->type==SCD_OBJ_TIMEPOST){pool[index].state=2;pool[index].frame=e->subtype<8?11:(e->subtype==9?3:1);}
    }
}
typedef struct {
    slot slots[SCD_OBJECT_CAPACITY];
    sprite_status actors[128];
    uint8_t used[SCD_PLACEMENT_CAPACITY],deferred[SCD_PLACEMENT_CAPACITY];
    scd_object_stats counts;
    unsigned control;
    uint8_t amy;
} snapshot;
static void save(snapshot *s){
    memset(s,0,sizeof(*s));memcpy(s->slots,pool,sizeof(pool));memcpy(s->actors,actwk,sizeof(s->actors));
    memcpy(s->used,consumed,sizeof(consumed));memcpy(s->deferred,deferred_reload,sizeof(deferred_reload));
    s->counts=stats;s->control=control_actor;s->amy=amy_palette_active;
}
static void restore(const snapshot *s){
    memcpy(pool,s->slots,sizeof(pool));memcpy(actwk,s->actors,sizeof(s->actors));
    memcpy(consumed,s->used,sizeof(consumed));memcpy(deferred_reload,s->deferred,sizeof(deferred_reload));
    stats=s->counts;control_actor=s->control;amy_palette_active=s->amy;
}
static uint32_t random_state=0x9db84121;
static unsigned next(void){random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;return random_state;}
static void compare(int x){
    static snapshot before,expected,actual;
    save(&before);reference_stream(x);save(&expected);restore(&before);stream(x);save(&actual);
    if(memcmp(&actual,&expected,sizeof(actual))){
        fprintf(stderr,"Stream differs act=%u era=%u x=%d\n",objects_act,current_era,x);
        for(unsigned j=0;j<active_placement_count;j++)if(actual.deferred[j]!=expected.deferred[j])
            fprintf(stderr,"deferred j=%u type=%u placement_x=%d actual=%u expected=%u\n",j,active_placements[j].type,active_placements[j].x,actual.deferred[j],expected.deferred[j]);
        abort();
    }
}
int main(void){
    unsigned cases=0;
    /* Every zone (PPZ to MM) streams through the retail Object Spawner (tt_stream,
       covered by the zone gates). No zone uses the player-distance stream this
       reference describes; run it with an unassigned zone index (7, no zone ops)
       over the Palmtree Panic packs. This is a legacy-stream optimization
       regression, not a retail placement acceptance test. */
    for(unsigned act=0;act<3;act++)for(unsigned era=0;era<4;era++){
        if(act==2 && era<2)continue;
        scd_objects_zone(0);scd_objects_act(act);scd_objects_zone(7);assert(active_placement_count && active_placement_count<=SCD_PLACEMENT_CAPACITY);
        for(unsigned mode=0;mode<8;mode++){
            memset(actwk,0,sizeof(sprite_status)*128);scd_objects_reset(era,mode!=7);
            assert(!tt_streamed()); /* Keep the reference and candidate on the same algorithm. */
            good_future=mode==6 || era==2;projector_destroyed=mode==6;
            actwk[0].r_no0=2;actwk[0].sprvsize=19;
            for(unsigned tick=0;tick<1024;tick++){
                int x=mode==0?(int)tick*16:mode==1?16383-(int)tick*16:(int)(next()%16384);
                actwk[0].xposi.w.h=x;
                if(mode>=2){
                    /* Fragmented/full pools, repeated layout records, deferred
                       reloads and persistent consumed flags. All edits occur
                       before the two identical candidate inputs are saved. */
                    if(tick%13==0)for(unsigned n=0;n<(mode==3?SCD_OBJECT_CAPACITY:8);n++)
                        scd_objects_spawn(SCD_OBJ_RING,x,300,0,0);
                    for(unsigned n=0;n<3;n++){
                        unsigned i=next()%SCD_OBJECT_CAPACITY;if(pool[i].type)remove_slot(i);
                        unsigned j=next()%active_placement_count;consumed[j]=next()&1;deferred_reload[j]=next()&1;
                    }
                    if(mode==4)for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && (i%3)==0)pool[i].origin=next()%active_placement_count;
                    if(mode==5 && tick%17==0){
                        int parent=scd_objects_spawn(SCD_OBJ_MOVING_SPRING,x,300,0,0);
                        int child=scd_objects_spawn(SCD_OBJ_SPRING,x,290,0,0);
                        if(parent>=0 && child>=0){pool[parent].origin=0;pool[child].parent=parent+1;pool[child].origin=1;}
                    }
                }
                compare(x);cases++;
            }
        }
    }
    printf("%u exact object-stream comparisons across 10 packs: slot/actor bytes, flags, counters, fragmentation, full pools, children and reversals\n",cases);
    return 0;
}
