/* Host route exploration using real game routines and controller input only.
 * This is not an independent correctness oracle. Saturn replay must verify a
 * successful route; original behavior and pictures have separate references. */
#include <assert.h>
#include "camera_v.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "player_replay.h"
#include "scd_objects.h"
#include "world.h"
#include "act.h"
#include "title_card.h"
#include "scd_boss.h"
#include "arrival_camera.h"
extern short scralim_left,scralim_right,scralim_down,scra_vline;
extern unsigned char bossflag;
static uint8_t data[3][4][300000],collision[3][4][9472];
static stage_t stages[3][4];
static unsigned act,era,good_flags,finished,loaded,updates;
static int camera_x,camera_y;
static int pending_destination;
static uint32_t state[40];
static int load_assets(void){
    if(loaded)return 0;
    for(unsigned a=0;a<3;a++)for(unsigned e=0;e<4;e++){
        if(a==2 && e<2)continue;
        char path[100];
        if(a)snprintf(path,sizeof(path),"assets/generated/ppz1%u%c.bin",a+1,'A'+e);
        else snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",e);
        FILE *f=fopen(path,"rb");if(!f)return -1;size_t bytes=fread(data[a][e],1,sizeof(data[a][e]),f);int end=feof(f);fclose(f);
        if(!end || stage_open(&stages[a][e],data[a][e],bytes))return -1;
        if(a)snprintf(path,sizeof(path),"assets/generated/collision1%u%c.bin",a+1,'A'+e);
        else snprintf(path,sizeof(path),"assets/generated/collision%u.bin",e);
        f=fopen(path,"rb");if(!f)return -1;bytes=fread(collision[a][e],1,9472,f);fclose(f);if(bytes!=9472)return -1;
    }
    loaded=1;return 0;
}
static int load_act(void){
    scd_objects_act(act);scd_player_act(act);scd_world_act(act);
    if(scd_player_init(&stages[act][era],collision[act][era],9472,era))return -1;scd_player_objects_lead();
    scd_world_reset(era);scd_title_card_start(act);
    camera_y=scd_camera_v_begin(0,act,era,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
    return 0;
}
static void snapshot(void){
    scd_player_state p=scd_player_get();scd_world_state w=scd_world_get();
    scd_replay_words(p,state);
    state[16]=act;state[17]=era;state[18]=good_flags;state[19]=w.good_future;
    state[20]=w.ticks;state[21]=w.direction;state[22]=w.transitions;
    state[23]=camera_x;state[24]=camera_y;state[25]=scd_act_get().phase;
    state[26]=p.control;state[27]=finished;state[28]=updates;state[29]=p.elapsed;
    state[30]=p.score;state[31]=scd_player_checkpoint().id;
}
int journey_init(void){
    if(load_assets())return -1;
    act=era=good_flags=finished=updates=0;memset(state,0,sizeof(state));
    pending_destination=-1;
    scd_objects_time_stones(0);
    if(load_act())return -1;
    snapshot();return 0;
}
const uint32_t *journey_state(void){return state;}
unsigned journey_objects(scd_object_view *views,unsigned capacity){return scd_objects_views(views,capacity);}
int journey_step(unsigned buttons){
    if(buttons&~31u || finished)return -1;
    state[32]=state[33]=state[34]=state[38]=0;state[35]=0xffffffffu;state[36]=buttons;
    /* Fade/loading/warp-cutscene VBlanks have no simulation; omitted here.
       Real Saturn replay must account for them when delivering these pads. */
    if(pending_destination>=0){
        int result=scd_player_arrive(&stages[act][pending_destination],collision[act][pending_destination],9472,pending_destination);if(!result)scd_player_objects_lead();
        if(result)return -3; /* Retain an unsafe landing as a failed route. */
        era=pending_destination;pending_destination=-1;scd_world_arrived(era);scd_player_music_event();
        scd_player_state arrived=scd_player_get();
        scd_arrival_camera(arrived.x/65536,arrived.y/65536,act,scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&camera_y);
        camera_y=scd_camera_v_begin(0,act,era,arrived.y/65536,arrived.resets);
        state[38]=1;
    }
    if(scd_act_get().phase==SCD_ACT_DONE){
        if(act==2){finished=1;snapshot();return 1;}
        scd_player_progress progress=scd_player_progress_get();
        if(scd_world_get().good_future)good_flags|=1u<<act;
        act++;era=act==2?(good_flags==3?2:3):0;
        if(load_act())return -1;
        scd_player_progress_set(progress);state[34]=1;
    }
    scd_world_state travel=scd_world_get();scd_objects_travel_protection(travel.ticks>0);
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    int title_locked=scd_title_card_locked();scd_player_hold_clock(title_locked);
    if(title_locked)buttons=0;state[37]=buttons;
    scd_player_step(buttons);
    scd_title_card_step();
    scd_player_music_event();
    if(scd_objects_big_ring())return -2; /* No silently skipped special stage. */
    scd_act_music();scd_boss_music();
    scd_player_state p=scd_player_get();
    if(act==2 && !bossflag && p.x/65536>=0xD70){int left=p.x/65536-160;if(left>=scralim_left)scralim_left=left>scralim_right?scralim_right:left;}
    if(scd_objects_generator()){scd_world_generator_destroyed();state[32]=1;}
    int destination=scd_world_step(p);
    int post=scd_objects_timepost();if(post){scd_world_activate(post);state[33]=post;}
    if(destination>=0){
        state[35]=destination;
        /* main.c publishes the departure update before loading the new era.
           Arrival is applied between that update and the next simulation. */
        pending_destination=destination;
    }
    {
        camera_y=scd_camera_v_follow(p.y/65536,p.resets);camera_x=scd_camera_h();
        if(camera_x<0)camera_x=0;if(camera_x>16064)camera_x=16064;
        if(camera_y<0)camera_y=0;if(camera_y>(act?scralim_down:1824))camera_y=act?scralim_down:1824;
        if(camera_x>scralim_right)camera_x=scralim_right;if(camera_x<scralim_left)camera_x=scralim_left;
        scd_act_state a=scd_act_get();if(a.goal && camera_x<a.left)camera_x=a.left;
        if(a.phase){camera_x=a.camera_x;camera_y=a.camera_y;}
        scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
    }
    updates++;snapshot();return scd_player_get().game_over?-4:0;
}
#ifdef JOURNEY_MAIN
int main(void){
    if(journey_init())return 2;
    unsigned pad;
    while(scanf("%u",&pad)==1){
        int result=journey_step(pad);
        printf("%d",result);for(unsigned i=0;i<40;i++)printf(" %u",state[i]);putchar('\n');
        if(result)return result<0?1:0;
    }
    return 0;
}
#endif
