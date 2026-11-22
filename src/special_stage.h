#ifndef SCD_SPECIAL_STAGE_H
#define SCD_SPECIAL_STAGE_H
#include "special_effects_runtime.h"
#include "special_ufo.h"
#define SCD_SPECIAL_DRAWS 48
#define SCD_SPECIAL_STAGE_WORDS (14*14+24*7+14*8+2+8*SCD_SPECIAL_DRAWS)
enum {SCD_SPECIAL_DRAW_SONIC,SCD_SPECIAL_DRAW_SFX,SCD_SPECIAL_DRAW_UFX};
/* One DrawObject call in original sprite-table order. x/y are 128-biased
   sprite words; animation/frame select a pose in the SFX or UFX pack.
   object: 0 Sonic, 1 shadow, 2 splash, 3..5 stone/sparkles, 6..13 dust,
   14 item, 15..21 rings, 22..29 explosions, 30..36 UFOs, 37..43 shadows,
   44 title card text, 45 title card bar. */
typedef struct {int16_t x,y;uint8_t kind,animation,frame,palette,visible,object;} scd_special_draw;
typedef struct {
    scd_special_effect_pool effects;
    scd_special_effect item,explosions[8],time_stone[3],title[2]; /* title: text slot 1, bar slot 2 */
    scd_special_ufo_actor ufos[7]; /* 6 is the time UFO */
    scd_special_shadow shadows[7],sonic_shadow;
    scd_special_ufo_paths paths;
    unsigned stage;
    uint8_t zbuffer[64][7],zcount[64],sonic_collision,draw_count;
    scd_special_draw draws[SCD_SPECIAL_DRAWS];
} scd_special_stage_state;
/* SpawnUFOs for stage 0..7 plus Sonic's shadow; world keeps its timer. */
int scd_special_stage_reset(scd_special_stage_state *state,scd_special_world *world,const void *paths,size_t size,unsigned stage);
/* Sub CPU program start: title card IDs, cleared Sonic at routine 0 and an
   inactive stage. Call after reset. */
void scd_special_stage_start(scd_special_stage_state *state,scd_special_world *world,scd_special_player *player,scd_special_sprite *sprite);
/* One Sub CPU RunObjects/UpdateTimer update. yaw is the pre-object graphics
   yaw; pose/visible return Sonic's drawn frame. */
int scd_special_stage_update(scd_special_stage_state *state,scd_special_world *world,scd_special_player *player,scd_special_sprite *sprite,const scd_special_art *sonic_art,const scd_special_art *ufx_art,const scd_special_art *sfx_art,const scd_special_stage *stage,unsigned held,unsigned tapped,unsigned yaw,scd_special_pose *pose,int *visible);
/* Endian-independent semantic words (actors, collision, draw list). */
unsigned scd_special_stage_words(const scd_special_stage_state *state,uint32_t *words);
uint32_t scd_special_stage_hash(const scd_special_stage_state *state);
#endif
