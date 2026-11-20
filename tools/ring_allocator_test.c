/* Exact allocation assertions, not a reimplementation of the allocator. */
#include <assert.h>
#include <stdio.h>
#ifndef OBJECTS_SOURCE
#define OBJECTS_SOURCE "../src/objects.c"
#endif
#include OBJECTS_SOURCE
void allocator_fixture_reset(void);
void allocator_fixture_dead_borrowed(unsigned);
unsigned scd_boss_retail_slot_peek(unsigned);
static scd_placement layout[5];
static void reset(void){
    memset(pool,0,sizeof(pool));memset(actwk,0,128*sizeof(*actwk));
    memset(consumed,0,sizeof(consumed));memset(tt_ring_pending,0,sizeof(tt_ring_pending));
    memset(&stats,0,sizeof(stats));allocator_fixture_reset();
    objects_zone=1;objects_act=1;current_era=0;era_bit=1;zone_ops=NULL;
    active_placements=layout;active_placement_count=5;
    for(unsigned j=0;j<5;j++)layout[j]=(scd_placement){.x=100+24*j,.y=300,
        .type=SCD_OBJ_RING,.flags=j?TT_RING_MEMBER:0,.eras=1};
}
static void occupy(unsigned i){
    pool[i]=(slot){.type=SCD_OBJ_RING,.origin=65535};actwk[i+1].actno=SCD_OBJ_RING;
}
static void parent(unsigned i){occupy(i);pool[i].origin=0;tt_ring_pending[i]=1;}
int main(void){
    /* Slot 35 is between parent actor33 and first child actor36. The first
       child's real boss sync releases35; second child must reuse35, third37. */
    reset();parent(32);occupy(33);allocator_fixture_dead_borrowed(35);
    active_placement_count=4;
    assert(scd_boss_borrowed_slot(35));assert(!tt_ring_group(32));
    assert(pool[35].origin==1);
    assert(pool[34].origin==2); /* Rejects the unsafe monotonic cursor. */
    assert(pool[36].origin==3);assert(!scd_boss_borrowed_slot(35));
    assert(scd_boss_retail_slot_peek(36)==34);
    assert(scd_boss_retail_slot_peek(35)==35);
    assert(scd_boss_retail_slot_peek(37)==36);
    /* Fragmented native slots; consumed and wrong-era members allocate none. */
    reset();parent(2);occupy(3);occupy(5);consumed[2]=1;layout[3].eras=2;
    assert(!tt_ring_group(2));assert(pool[4].origin==1);assert(pool[6].origin==4);
    assert(stats.spawned==2);
    /* Located slot is encoded +1, including zero and a completely full pool. */
    reset();assert(tt_free_slot()==1);occupy(0);occupy(2);
    assert(tt_free_slot()==2);assert(tt_spawn_record(0)==0);
    assert(pool[1].origin==0);assert(actwk[2].actno==SCD_OBJ_RING);
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)occupy(i);
    layout[1].flags=0;assert(tt_free_slot()==0);assert(tt_spawn_record(1)==-1);
    /* Rejection must leave the located free slot untouched. */
    reset();layout[0].type=SCD_OBJ_SPRING;layout[0].y=-1;
    assert(tt_spawn_record(0)==0);assert(tt_free_slot()==1);assert(!pool[0].type);
    puts("PASS: real ring allocator: borrowed-slot release, fragmented pool, skipped members, located free slot, full pool and rejected spawn");
    return 0;
}
