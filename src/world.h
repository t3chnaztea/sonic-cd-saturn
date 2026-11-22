#ifndef SCD_WORLD_H
#define SCD_WORLD_H
#include "scd_player.h"
typedef struct {unsigned era,ticks,transitions,cancelled,good_future;int direction,destination;} scd_world_state;
void scd_world_reset(unsigned era);
void scd_world_activate(int direction);
void scd_world_generator_destroyed(void);
int scd_world_step(scd_player_state player);
int scd_world_step_vblanks(scd_player_state player,unsigned elapsed);
void scd_world_arrived(unsigned era);
void scd_world_abort(void);
/* Act index for act-specific travel rules (0 = Act 1). */
void scd_world_act(unsigned act);
void scd_world_zone(unsigned zone);
scd_world_state scd_world_get(void);
#endif
