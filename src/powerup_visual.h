#ifndef SCD_POWERUP_VISUAL_H
#define SCD_POWERUP_VISUAL_H
#include <stdint.h>
/* Original Powerup actor state, independent of gameplay ownership/timers.
   Reserved source slots: shield 6, invincibility 8..11, time stars 12..15. */
typedef struct {
    int16_t x,y;
    uint16_t tile;
    uint8_t active,routine,animation,previous,cursor,timer,mapping;
    uint8_t sprite_flags,flags,phase,priority,width;
} scd_powerup_visual;
typedef struct {
    int16_t x,y;
    uint8_t flags,shield,invincible,travel,zone,layer,powerup,record_index;
    int16_t history[64][2];
} scd_powerup_context;
/* One original object update. Returns 1 at DrawObject, 0 for no submission,
   -1 for invalid state. The caller controls spawning and simulation cadence;
   drawing an already-submitted view must not advance its state. */
int scd_powerup_visual_step(scd_powerup_visual *s,scd_powerup_context *context);
#endif
