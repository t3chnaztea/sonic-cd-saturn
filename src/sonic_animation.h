#ifndef SCD_SONIC_ANIMATION_H
#define SCD_SONIC_ANIMATION_H
#include <stdint.h>
/* Animation state, distinct from physics/update count. Sprite flags retain
   their high bits; low bits are the original horizontal/vertical flips. */
typedef struct {
    uint8_t animation,previous,cursor,timer,mapping,sprite_flags;
} scd_sonic_animation;
/* Normal-sized Sonic, as used throughout Palmtree Panic. Returns -1 on an
   invalid animation/cursor without modifying state. The player adapter updates
   the original actor fields before object processing. */
int scd_sonic_animate(scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control);
/* Miniature Sonic (miniSonic set: R8 shrink beam). Returns 1 when the mini
   run curled Sonic on a steep angle: the caller sets the rolling flag and the
   10/5 radii, as .MiniSonicRun does. */
int scd_sonic_animate_mini(scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control);
/* Mapping at the next timer expiry with unchanged inputs, or -1 (render-side prefetch only). */
int scd_sonic_animation_next(const scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control,int mini);
#endif
