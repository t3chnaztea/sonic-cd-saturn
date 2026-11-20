#include <assert.h>
#include <stdio.h>
#include "objects.c"
#include "boss_zone.h"
extern void (*fixture_routine(unsigned))(sprite_status*);
const scd_boss_zone_ops r7_boss_zone_ops={.routine=fixture_routine};
const scd_boss_zone_ops r6_boss_zone_ops={.routine=fixture_routine};
void fixture_reset(void);void fixture_maps(unsigned);void fixture_boss_setup(unsigned);
void fixture_integration_setup(unsigned);
void fixture_before(unsigned,int);size_t fixture_dump(void*);unsigned fixture_event_count(void);
void fixture_pool_create(unsigned actor){assert(actor>0&&actor<=SCD_OBJECT_CAPACITY);pool[actor-1]=(slot){.type=SCD_OBJ_RING,.origin=65535};actwk[actor].actno=SCD_OBJ_RING;}
void fixture_pool_replace(unsigned actor,unsigned reuse){
    remove_slot(actor-1);if(reuse){fixture_pool_create(actor);actwk[actor].actfree[7]=42;}
}
static unsigned lookups;
static unsigned counted_slot(unsigned actor){lookups++;return scd_boss_retail_slot(actor);}
static const uint8_t *counted_map(unsigned actor,unsigned *key){lookups++;return scd_boss_retail_slot_map(actor,key);}
static void setup(void){
    memset(pool,0,sizeof(pool));memset(actwk,0,128*sizeof(*actwk));memset(&stats,0,sizeof(stats));
    memset(consumed,0,sizeof(consumed));memset(tt_ring_pending,0,sizeof(tt_ring_pending));
    fixture_reset();objects_zone=5;objects_act=2;level_vint=41;zone_ops=NULL;
}
static unsigned select_old(unsigned retail_after,unsigned *selected_key){
    unsigned key=~0u,i=SCD_OBJECT_CAPACITY;
    for(unsigned j=0;j<SCD_OBJECT_CAPACITY;j++)if(pool[j].type){
        unsigned k=counted_slot(j+1);
        if(k>retail_after&&k<key){key=k;i=j;}
    }*selected_key=key;return i;
}
static unsigned select_new(unsigned retail_after,unsigned *selected_key){unsigned i;
#define scd_boss_retail_slot counted_slot
#define scd_boss_retail_slot_map counted_map
#ifdef NEG_NO_RESYNC
#include "selector-negative.inc"
#else
#include "selector.inc"
#endif
    *selected_key=key;
#undef scd_boss_retail_slot
#undef scd_boss_retail_slot_map
    return i;
}
static unsigned char first[1048576],second[1048576];
static size_t dump(void *out){unsigned char *p=out;memcpy(p,pool,sizeof(pool));p+=sizeof(pool);memcpy(p,actwk,128*sizeof(*actwk));p+=128*sizeof(*actwk);p+=fixture_dump(p);return p-(unsigned char*)out;}
int main(void){unsigned selectors=0,bosses=0,callbacks=0;
    for(unsigned mode=0;mode<7;mode++)for(unsigned cursor=0;cursor<5;cursor++){
        unsigned a=0,b=0,ka=0,kb=0;size_t na=0,nb=0;
        for(unsigned optimized=0;optimized<2;optimized++){
            setup();if(mode!=6){fixture_pool_create(1);fixture_pool_create(2);fixture_pool_create(3);fixture_pool_create(35);}
            if(mode!=6)fixture_maps(mode);
            unsigned after=(unsigned[]){0,32,33,65,127}[cursor];
            lookups=0;unsigned got=optimized?select_new(after,&kb):select_old(after,&ka);
            if(mode==6)assert(!lookups);
            if(optimized){b=got;nb=dump(second);}else{a=got;na=dump(first);}
        }
        assert(a==b&&ka==kb&&na==nb&&!memcmp(first,second,na));selectors++;
    }
    for(unsigned mode=0;mode<10;mode++){
        size_t na=0,nb=0;
        for(unsigned optimized=0;optimized<2;optimized++){
            setup();fixture_boss_setup(mode);
            static const unsigned cutoffs[]={32,33,34,36,65,97,128,~0u};
            for(unsigned c=0;c<sizeof(cutoffs)/sizeof(*cutoffs);c++){
                fixture_before(cutoffs[c],optimized);
                if(optimized)nb+=dump(second+nb);else na+=dump(first+na);
                assert(na<sizeof(first)&&nb<sizeof(second));
            }
            if(optimized)callbacks+=fixture_event_count();
        }
        if(na!=nb||memcmp(first,second,na)){fprintf(stderr,"boss scenario %u differs\n",mode);assert(0);}
        bosses++;
    }
    for(unsigned reuse=0;reuse<2;reuse++){
        size_t na=0,nb=0;
        for(unsigned optimized=0;optimized<2;optimized++){
            setup();fixture_integration_setup(reuse);unsigned after=0;
            for(unsigned pass=0;pass<4;pass++){
                unsigned key,i=optimized?select_new(after,&key):select_old(after,&key);
                if(i==SCD_OBJECT_CAPACITY)break;
                fixture_before(key,optimized);after=key;
                /* Same preselected slot/cursor and post-callback liveness
                   test as production objects.c. No reselect after callback. */
                if(pool[i].type)actwk[i+1].actfree[3]++;
                if(optimized)nb+=dump(second+nb);else na+=dump(first+na);
            }
            fixture_before(~0u,optimized);
            if(optimized)nb+=dump(second+nb);else na+=dump(first+na);
            assert(!reuse?!pool[0].type:actwk[1].actfree[7]==42&&actwk[1].actfree[3]==1);
        }
        assert(na==nb&&!memcmp(first,second,na));
    }
    assert(callbacks>50);
    printf("PASS: actual SS3 scheduler: %u selector states/cursors; %u boss mutation/cutoff/reset scenarios; %u callbacks; 2 integrated selected-pool deletion/reuse cases; per-cutoff actor/pool/maps/events match old loops\n",selectors,bosses,callbacks);
    return 0;
}
