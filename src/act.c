/* PPZ finish/signpost/results from Level End/Main.asm and Results/Main.asm.
 * Bonus values and player score are actual display points, not units of ten. */
#include "act.h"
extern void soundset(short);
static scd_act_state state;
static int view_x,view_y,music_pending,special_warp,ss_results;
void scd_act_reset(void){state=(scd_act_state){0};view_x=view_y=music_pending=special_warp=ss_results=0;}
int scd_act_view_x(void){return view_x;}
int scd_act_view_y(void){return view_y;}
void scd_act_special(int active){special_warp=active;}
void scd_act_camera(int x,int y){view_x=x;view_y=y;}
scd_act_state scd_act_get(void){return state;}
int scd_act_music(void){int event=music_pending;music_pending=0;return event;}
unsigned scd_act_time_bonus(unsigned elapsed){
    static const uint16_t bonus[]={50000,50000,10000,5000,4000,4000,3000,3000,2000,2000,2000,2000,1000,1000,1000,1000,500,500,500,500,0};
    unsigned index=elapsed/900;return bonus[index<20?index:20];
}
static int in_range(scd_player_state p,int y){int dy=p.y/65536-y;return p.routine<4 && dy>=-128 && dy<128;}
int scd_act_goal(int x,int y){
    scd_player_state p=scd_player_get();if(state.goal || !in_range(p,y) || p.x/65536<x)return 0;
    state.goal=1;state.left=view_x;return 1;
}
int scd_act_sign(int x,int y,int good_future){
    scd_player_state p=scd_player_get();if(state.phase || !in_range(p,y) || p.x/65536<=x)return 0;
    state.goal=1;state.phase=SCD_ACT_SPIN;state.timer=120;state.good_future=!!good_future;state.sign=1;
    state.left=state.camera_x=view_x;state.camera_y=view_y;
    scd_player_finish();soundset(157);return 1;
}
void scd_act_capsule(int good_future){
    if(state.phase)return;
    state.goal=1;state.phase=SCD_ACT_DELAY;state.timer=60;state.good_future=!!good_future;
    state.left=state.camera_x=view_x;state.camera_y=view_y;
}
void scd_act_ss_goal(int good_future){
    if(state.phase)return;
    scd_player_state p=scd_player_get();
    ss_results=1;state.good_future=!!good_future;state.goal=1;state.phase=SCD_ACT_EXIT;state.timer=16;music_pending=1;
    state.left=state.camera_x=view_x;state.camera_y=view_y;
    state.time_bonus=scd_act_time_bonus(p.elapsed);state.ring_bonus=p.rings*100u;
    state.total_bonus=state.time_bonus+state.ring_bonus;
}
int scd_act_stationary_results(void){return ss_results;}
unsigned scd_act_sign_frame(void){
    static const uint8_t sequence[]={0,1,2,4,3,3,1,2,4};
    if(!state.phase)return 0;
    return state.phase==SCD_ACT_SPIN?sequence[((120-state.timer)/2)%9]:3;
}
void scd_act_step(scd_player_state p){
    if(p.routine>=6)return;
    switch(state.phase){
    case SCD_ACT_SPIN:
        if(!--state.timer){state.phase=SCD_ACT_DELAY;state.timer=60;}break;
    case SCD_ACT_DELAY:
        if(!--state.timer){
            state.phase=SCD_ACT_EXIT;state.timer=16;music_pending=1;
            state.time_bonus=scd_act_time_bonus(p.elapsed);state.ring_bonus=p.rings*100u;
            state.total_bonus=state.time_bonus+state.ring_bonus;
        }break;
    case SCD_ACT_EXIT:
        if(state.timer)state.timer--;
        if(!state.timer && (ss_results || p.x/65536>state.camera_x+336)){state.phase=SCD_ACT_SLIDE;state.timer=480;state.slide=0;}
        break;
    case SCD_ACT_SLIDE:
        if(state.timer)state.timer--;
        if(state.slide<36)state.slide++;else state.phase=SCD_ACT_TALLY;
        break;
    case SCD_ACT_TALLY:
        if(state.time_bonus || state.ring_bonus){
            unsigned points=0;
            if(state.time_bonus){state.time_bonus-=100;points+=100;}
            if(state.ring_bonus){state.ring_bonus-=100;points+=100;}
            if(!state.time_bonus && !state.ring_bonus){soundset(154);if(state.timer<45)state.timer=45;}
            else {if(state.timer)state.timer--;if(!(state.timer&1))soundset(189);}
            scd_player_points(points);
        }else if(state.timer){state.timer--;if(special_warp && state.timer==30)soundset(200);}else state.phase=SCD_ACT_DONE;
        break;
    default:break;
    }
}
