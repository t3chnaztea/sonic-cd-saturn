/* PPZ replay companion for src/boss.c's retail actor slot allocator. The
   standalone player trace does not link the boss runtime, but lost-ring floor
   checks use the same slot number and V-INT counter as the Saturn build. */
#include "EQU.H"
#include "scd_objects.h"
#include <stdint.h>
#include <string.h>

static uint8_t slot_of[SCD_OBJECT_CAPACITY+1],used[128];
static unsigned ring_tick,gen; /* gen counts slot-map changes, as boss.c vslot_gen */
static void sync_slots(void){
    for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++)if(!actwk[i].actno && slot_of[i]){
        used[slot_of[i]]=0;slot_of[i]=0;gen++;
    }
    for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++)if(actwk[i].actno && !slot_of[i]){
        for(unsigned s=32;s<128;s++)if(!used[s]){slot_of[i]=(uint8_t)s;used[s]=1;gen++;break;}
    }
}
void scd_boss_reset(void){memset(slot_of,0,sizeof(slot_of));memset(used,0,sizeof(used));ring_tick=~0u;}
void scd_boss_step(void){sync_slots();}
unsigned scd_boss_retail_slot(unsigned actor){
    if(!actor || actor>SCD_OBJECT_CAPACITY)return actor+31u;
    unsigned tick=scd_objects_vint();
    if(ring_tick!=tick || !slot_of[actor]){sync_slots();ring_tick=tick;}
    return slot_of[actor]?slot_of[actor]:actor+31u;
}
/* objects.c's MM order cache (boss.c counterparts): slot-map generation, a
   lookup that would not synchronize, and the live actor -> slot view. */
unsigned scd_boss_slot_generation(void){return gen;}
int scd_boss_retail_slot_pure(unsigned actor){return actor && actor<=SCD_OBJECT_CAPACITY && ring_tick==scd_objects_vint() && slot_of[actor];}
const uint8_t *scd_boss_retail_slot_view(void){return slot_of;}
const uint8_t *scd_boss_retail_slot_map(unsigned actor,unsigned *first_key){*first_key=scd_boss_retail_slot(actor);return slot_of;}
