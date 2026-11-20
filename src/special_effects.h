#ifndef SCD_SPECIAL_EFFECTS_H
#define SCD_SPECIAL_EFFECTS_H
#include <stdint.h>
/* Screen coordinates/velocities retain original 16.16 fractions. */
typedef struct {
    uint32_t x,y,x_velocity,y_velocity;
    uint16_t timer;
    uint8_t id,routine,flags,animation,frame,time,time_copy,art,item_type;
} scd_special_effect;
typedef struct {uint32_t seed,d1;uint8_t ring_direction;} scd_special_effect_context;
uint32_t scd_special_random(scd_special_effect_context *context);
/* Return the state drawn this update before clearing a deleted slot. */
void scd_special_dust(scd_special_effect *effect,scd_special_effect_context *context,unsigned held,scd_special_effect *drawn);
void scd_special_lost_ring(scd_special_effect *effect,scd_special_effect_context *context,uint32_t sonic_x,uint32_t sonic_y,scd_special_effect *drawn,unsigned *sound);
/* Item spawn type aliases the timer word's low byte (original oVar51). */
void scd_special_item(scd_special_effect *effect,scd_special_effect_context *context,scd_special_effect *drawn,unsigned *sound);
void scd_special_explosion(scd_special_effect *effect,scd_special_effect_context *context,scd_special_effect *drawn,unsigned *sound);
int scd_special_explosion_slot(const scd_special_effect pool[8]);
#endif
