#ifndef PLAYER_REPLAY_H
#define PLAYER_REPLAY_H
#include "scd_player.h"
#include "scd_objects.h"
#define SCD_REPLAY_COUNT 28
#define SCD_REPLAY_FRAMES 600
void scd_replay_begin(unsigned test);
unsigned scd_replay_era(unsigned test);
void scd_replay_tick(unsigned test,unsigned frame);
unsigned scd_replay_buttons(unsigned test,unsigned frame);
void scd_replay_words(scd_player_state state,uint32_t words[16]);
void scd_replay_visual_words(scd_player_state state,uint32_t words[2]);
/* A caller may reuse the full diagnostic snapshot until objects change. */
void scd_replay_words_snapshot(scd_player_state state,uint32_t words[16],scd_object_stats *snapshot);
#endif
