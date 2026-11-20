/* GOAL.C goal_move2 and ZONE.C clear_init: SS3 starts results at Amy,
 * locks input without Right, and does not wait for Sonic to leave the screen.
 * This tests the shared results adapter, not a whole retail results trace. */
#include "act.h"
#include <assert.h>
#include <stdio.h>
static scd_player_state player;
static unsigned score;
scd_player_state scd_player_get(void){return player;}
void scd_player_points(unsigned n){score+=n;}
void scd_player_finish(void){}
void soundset(short n){(void)n;}
int main(void){
    for(unsigned good=0;good<2;good++){
        scd_act_reset();score=0;player=(scd_player_state){0};
        player.elapsed=1800;player.rings=23;player.x=16000*65536;
        scd_act_camera(15800,300);scd_act_ss_goal(good);
        scd_act_state a=scd_act_get();
        assert(a.phase==SCD_ACT_EXIT && a.timer==16 && a.good_future==good);
        assert(a.total_bonus==12300 && scd_act_stationary_results());
        assert(scd_act_music()==1 && scd_act_music()==0);
        scd_act_ss_goal(!good);assert(scd_act_get().good_future==good);
        for(unsigned i=0;i<15;i++)scd_act_step(player);
        assert(scd_act_get().phase==SCD_ACT_EXIT);
        scd_act_step(player);assert(scd_act_get().phase==SCD_ACT_SLIDE);
        for(unsigned i=0;i<1000 && scd_act_get().phase!=SCD_ACT_DONE;i++)scd_act_step(player);
        assert(scd_act_get().phase==SCD_ACT_DONE && score==12300);
    }
    /* Other zones still wait for Sonic to leave the screen. */
    scd_act_reset();scd_act_camera(15800,300);scd_act_capsule(0);
    for(unsigned i=0;i<100;i++)scd_act_step(player);
    assert(scd_act_get().phase==SCD_ACT_EXIT && !scd_act_stationary_results());
    player.x=16137*65536;scd_act_step(player);assert(scd_act_get().phase==SCD_ACT_SLIDE);
    puts("PASS: SS3 Amy results start without offscreen travel; both futures award bonuses; capsule exit unchanged");
}
