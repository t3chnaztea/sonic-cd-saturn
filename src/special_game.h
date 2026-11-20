#ifndef SCD_SPECIAL_GAME_H
#define SCD_SPECIAL_GAME_H
#include "special_main.h"
#include "special_contacts.h"
/* Special Stage program flow from Main.asm (Start, MainLoop, HandlePause,
   Exit, Results, Results_MainLoop) advanced one V-INT at a time. Each call
   runs the V-INT routine, then the Main CPU program until its next VSync.
   UpdateStage starts a Sub CPU update through the callback, which runs
   AnimateStamps, RunObjects and UpdateTimer and renders the floor image. */
typedef int (*scd_special_game_update)(void *context,unsigned held,unsigned tapped);
enum {
    SCD_SPECIAL_GAME_FADE_IN=1,SCD_SPECIAL_GAME_LOOP,SCD_SPECIAL_GAME_PAUSE,SCD_SPECIAL_GAME_EXIT_FADE,
    SCD_SPECIAL_GAME_RESULTS_FADE_IN,SCD_SPECIAL_GAME_RESULTS,SCD_SPECIAL_GAME_RESULTS_FADE_OUT,SCD_SPECIAL_GAME_DONE
};
enum {SCD_SPECIAL_MUSIC_STAGE=1,SCD_SPECIAL_MUSIC_PAUSE,SCD_SPECIAL_MUSIC_RESUME,SCD_SPECIAL_MUSIC_RESULTS};
typedef struct {
    scd_special_main main;
    const scd_special_main_pack *pack;
    scd_special_world *world;
    scd_special_player *player;
    scd_special_game_update update;
    void *context;
    /* VDP state after the last V-INT: CRAM, H-scroll lines 0..223 (A,B). */
    uint16_t cram[64],hscroll[448],stage_scroll[2];
    uint16_t vint,routine,ctrl,saved_ctrl,saved_routine,step,half,vsram_a;
    uint8_t phase,sub,paused,display,h40,cram_dirty,sub_over,pending_over;
    uint8_t lost,next_stage,stage,time_stones,music,fm_count,fm[6];
    /* Update indexes: stageImage/sprites copies, floor buffers 1/2 and the
       floor image and sprite list on screen; -1 before any copy. */
    int32_t updates,copied,image[2],shown_image,shown_sprites;
    uint32_t exit_timer;
    uint16_t exit_rings;
    /* specStageFlags (world->mode) and Main.asm demoActive. */
    uint8_t flags,demo_active;
} scd_special_game;

int scd_special_game_start(scd_special_game *game,const scd_special_main_pack *pack,scd_special_world *world,scd_special_player *player,
    scd_special_game_update update,void *context,uint32_t score,uint32_t next_life,uint8_t lives,uint8_t time_stones,uint8_t stage);
/* stage 1-8; world->mode selects the IPX.asm entry (0 normal: results screen).
   pad: Mega Drive buttons (Start, A, C, B, Right, Left, Down, Up from bit 7).
   Returns 0 while running, 1 when the program has returned, negative on a
   failed Sub CPU update. */
int scd_special_game_vint(scd_special_game *game,unsigned pad);
uint32_t scd_special_game_hash(const scd_special_game *game);
#endif
