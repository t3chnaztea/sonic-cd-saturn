#ifndef SCD_ACT_H
#define SCD_ACT_H
#include "scd_player.h"
enum { SCD_ACT_PLAY, SCD_ACT_SPIN, SCD_ACT_DELAY, SCD_ACT_EXIT,
       SCD_ACT_SLIDE, SCD_ACT_TALLY, SCD_ACT_DONE };
typedef struct {
    uint32_t time_bonus,ring_bonus,total_bonus;
    uint16_t timer,slide;
    int16_t left,camera_x,camera_y;
    uint8_t phase,goal,good_future;
    uint8_t sign; /* the act-end sign: Level End sets only leftBound, the camera follows */
} scd_act_state;
void scd_act_reset(void);
int scd_act_stationary_results(void);
void scd_act_ss_goal(int good_future);
void scd_act_camera(int x,int y);
int scd_act_goal(int x,int y);
int scd_act_sign(int x,int y,int good_future);
void scd_act_step(scd_player_state player);
scd_act_state scd_act_get(void);
unsigned scd_act_sign_frame(void);
/* Flower capsule: StartResults 60 updates after the seeds spawn. */
void scd_act_capsule(int good_future);
/* The view X of the last update (ObjBigRing moves Sonic to it + 336). */
int scd_act_view_x(void);
int scd_act_view_y(void);
/* specialStage: the tally plays the special stage warp sound 30 updates before it ends. */
void scd_act_special(int active);
unsigned scd_act_time_bonus(unsigned elapsed);
int scd_act_music(void);
#endif
