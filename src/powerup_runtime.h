#ifndef SCD_POWERUP_RUNTIME_H
#define SCD_POWERUP_RUNTIME_H
#include "powerup_visual.h"
#include "scd_player.h"
typedef struct {
    scd_powerup_visual actors[9];
    scd_powerup_context context;
    uint32_t resets,updates;
    uint16_t submitted;
} scd_powerup_runtime;
void scd_powerup_runtime_reset(scd_powerup_runtime *s,uint32_t resets);
/* Called once per simulation update, never for a paused/redrawn picture.
   sample is before ordinary objects; post flags include late monitor grants. */
void scd_powerup_runtime_step(scd_powerup_runtime *s,scd_player_effect_sample sample,
    unsigned post_shield,unsigned post_invincible,unsigned travel);
/* Original DrawObject bounds/wrap; outputs screen-center coordinates. */
int scd_powerup_screen(const scd_powerup_visual *s,int cx,int cy,int *x,int *y);
#endif
