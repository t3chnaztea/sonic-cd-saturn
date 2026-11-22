#ifndef SCD_SPECIAL_EFFECTS_RUNTIME_H
#define SCD_SPECIAL_EFFECTS_RUNTIME_H
#include "special_contacts.h"
typedef struct {
    scd_special_effect_context context;
    scd_special_effect dust[8],rings[7],drawn[16];
    unsigned previous_held;
} scd_special_effect_pool;
void scd_special_effects_before(scd_special_effect_pool *pool,scd_special_world *world,const scd_special_player *player);
void scd_special_effects_after(scd_special_effect_pool *pool,scd_special_world *world,const scd_special_player *player,unsigned held);
uint32_t scd_special_effects_hash(const scd_special_effect_pool *pool);
#endif
