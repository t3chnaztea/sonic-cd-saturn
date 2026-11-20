#ifndef SCD_SPECIAL_CONTACTS_H
#define SCD_SPECIAL_CONTACTS_H
#include "special.h"
#include "special_sprite.h"
#include "special_effects.h"
typedef struct {
    uint32_t timer;
    uint16_t rings,splash_timer,dust[8];
    uint8_t timer_frames,speedup,inactive,stopped,time_attack,stage_over,ufo_count,time_ufo;
    uint8_t sound[3],lost_rings[7];
    uint8_t splash_id,splash_routine,splash_flags,splash_animation,splash_frame,splash_time;
    /* UFO ring bonus, retrieved flag and time stone/sparkle slot IDs. */
    uint16_t ring_bonus;
    uint8_t got_time_stone,time_stone[3];
    /* specStageFlags: bit 0 temporary (attract demos, stage 8), bit 1 time attack
       (time_attack mirrors it), bit 2 secret (stage 8). Fills the struct's tail padding. */
    uint8_t mode;
} scd_special_world;
void scd_special_sound(scd_special_world *world,unsigned sound);
void scd_special_get_contacts(scd_special_player *player,const scd_special_stage *stage);
void scd_special_bumper(scd_special_player *player,scd_special_sprite *sprite,const scd_special_art *art,scd_special_world *world);
void scd_special_contact(scd_special_player *player,scd_special_sprite *sprite,const scd_special_art *art,scd_special_world *world);
void scd_special_contact_state(scd_special_player *player,scd_special_sprite *sprite,const scd_special_art *art,scd_special_world *world,unsigned held,unsigned tapped);
void scd_special_splash(scd_special_world *world,const scd_special_player *player);
void scd_special_splash_draw(scd_special_world *world,const scd_special_player *player,scd_special_effect *drawn);
void scd_special_timer(scd_special_world *world);
void scd_special_player_step(scd_special_player *player,scd_special_sprite *sprite,const scd_special_art *art,scd_special_world *world,const scd_special_stage *stage,unsigned held,unsigned tapped);
#endif
