/* Replay the actual Saturn controller inputs from an untouched era spawn.
 * Compare every player/object word, then independently require the act tally. */
#include "player_replay.h"
#include "camera_v.h"
#include "scd_objects.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "scd_boss.h"
/* PC scroll limits, camera line and boss flag (EQU.C). */
extern short scralim_left,scralim_right,scralim_down,scra_vline;
extern unsigned char bossflag;
static uint8_t data[300000],collision[9472];
/* Optional: act2 replays Act 2 Present (SCD_ACT_ERA selects 1=Past, 2=Good, 3=Bad);
   SCD_ACT_TRACE selects its trace. act3 replays Act 3 in the
   bad future (ppz13D.bin, build/act3-qa, boss sources linked). */
int main(int argc,char **argv){
    unsigned act=argc>1 && !strcmp(argv[1],"act2")?1:argc>1 && !strcmp(argv[1],"act3")?2:0,era=act==2?3:0;
    const char *era_text=getenv("SCD_ACT_ERA");
    if(era_text){char *end;unsigned long value=strtoul(era_text,&end,10);if(!*era_text || *end || value>3 || act!=1)return 2;era=(unsigned)value;}
    char stage_path[80],collision_path[80];
    snprintf(stage_path,sizeof(stage_path),"assets/generated/ppz12%c.bin",'A'+era);
    snprintf(collision_path,sizeof(collision_path),"assets/generated/collision12%c.bin",'A'+era);
    scd_player_act(act);scd_objects_act(act);scd_world_act(act);
    FILE *file=fopen(act==2?"assets/generated/ppz13D.bin":act?stage_path:"assets/generated/ppz0.bin","rb");if(!file)return 2;
    size_t size=fread(data,1,sizeof(data),file);fclose(file);
    file=fopen(act==2?"assets/generated/collision13D.bin":act?collision_path:"assets/generated/collision0.bin","rb");if(!file)return 2;
    if(fread(collision,1,sizeof(collision),file)!=sizeof(collision))return 2;fclose(file);
    stage_t stage;if(stage_open(&stage,data,size) || scd_player_init(&stage,collision,sizeof(collision),era))return 2;
    scd_player_objects_lead();  /* src/main.c level start */
    /* act2 SCORE LIVES NEXT_LIFE: progress carried from Act 1 (Act 1 to Act 2 sequence). */
    if(act && argc==5)scd_player_progress_set((scd_player_progress){(uint32_t)strtoul(argv[2],NULL,10),(uint32_t)strtoul(argv[4],NULL,10),(uint8_t)strtoul(argv[3],NULL,10)});
    scd_world_reset(era);
    /* The Saturn runs a title card on every act/era entry, and the host must
       run it too or its act clock gains the updates the Saturn holds. The
       card's length is not uniform on the Act 2 debug entry, though: measured
       first accepted input is update 131 for Present, Past and Act 3, but 128
       in the Good Future and 117 in the Bad Future. That difference predates
       V0.057, which shifted all of them by the same two updates (129/126/115
       before). The host has no stage loading and models one 130-update card,
       so start it only where the two agree. The Future eras are tracked in
       NEXT-SESSION.md; until their length is explained, the host must not
       claim a card it cannot reproduce. */
    if(era==0 || act==2 || era==1)scd_title_card_start(act);
    const char *trace_path=getenv("SCD_ACT_TRACE");
    file=fopen(trace_path?trace_path:act==2?"build/act3-qa/player-target-trace.txt":act?"build/act2-qa/player-target-trace.txt":"build/act-qa/player-target-trace.txt","r");if(!file)return 2;
    unsigned base=0,count=0,sequence,buttons,finish_time=0,finish_score=0,bonus=0,hurt=0,ramp=0,phases=0;
    int camera_y=scd_camera_v_begin(0,act,era,scd_player_get().y/65536,scd_player_get().resets),camera_x=scd_camera_h();
    while(fscanf(file,"%u %u",&sequence,&buttons)==2){
        uint32_t expected[16],actual[16];for(unsigned i=0;i<16;i++)if(fscanf(file,"%x",&expected[i])!=1)return 2;
        /* Act 2 traces start after the debug entry: sequences are relative to the first record. */
        if(act && !count)base=sequence-1;
        if(sequence-base!=++count || (buttons&~(SCD_UP|SCD_DOWN|SCD_LEFT|SCD_RIGHT|SCD_JUMP))){fprintf(stderr,"Non-controller act input/sequence\n");return 1;}
        scd_world_state travel=scd_world_get();scd_objects_travel_protection(travel.ticks>0);
        scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
        scd_player_hold_clock(scd_title_card_locked());
        if(scd_title_card_locked() && buttons){fprintf(stderr,"Input during title lock\n");return 1;}
        scd_player_step(buttons);
        scd_title_card_step();
        scd_player_state p=scd_player_get();
        /* src/main.c: LevEvents_PPZ3 after the update. */
        if(act==2 && !bossflag && p.x/65536>=0xD70){int left=p.x/65536-160;if(left>=scralim_left)scralim_left=left>scralim_right?scralim_right:left;}
        if(scd_objects_generator())scd_world_generator_destroyed();
        int destination=scd_world_step(p);
        int post=scd_objects_timepost();if(post)scd_world_activate(post);
        scd_object_stats snapshot;
        scd_replay_words_snapshot(p,actual,&snapshot);
        scd_object_stats fresh=scd_objects_get();
        if(memcmp(&snapshot,&fresh,sizeof(snapshot))){fprintf(stderr,"Act object snapshot mismatch frame=%u\n",count);return 1;}
        for(unsigned i=0;i<16;i++)if(actual[i]!=expected[i]){fprintf(stderr,"Act state mismatch frame=%u word=%u host=%08x Saturn=%08x input=%u\n",count,i,actual[i],expected[i],buttons);return 1;}
        if(p.resets || p.routine>=6 || destination>=0 || scd_world_get().ticks>=210){fprintf(stderr,"Act died/reset/left its era\n");return 1;}
        hurt+=p.routine==4;ramp+=!!p.ramp;
        scd_act_state a=scd_act_get();phases|=1u<<a.phase;
        if(a.phase && !finish_time){finish_time=p.elapsed;finish_score=p.score;bonus=scd_act_time_bonus(p.elapsed)+p.rings*100u;}
        if(a.phase && p.elapsed!=finish_time)return 1;
        /* src/main.c camera: Act 3 follows scra_vline; scr_dir_tbl limits as the boss moves them. */
        camera_y=scd_camera_v_follow(p.y/65536,p.resets);camera_x=scd_camera_h();
        if(camera_x<0)camera_x=0;if(camera_x>16064)camera_x=16064;
        if(camera_y<0)camera_y=0;if(camera_y>(act?scralim_down:1824))camera_y=act?scralim_down:1824;
        if(camera_x>scralim_right)camera_x=scralim_right;if(camera_x<scralim_left)camera_x=scralim_left;
        if(a.goal && camera_x<a.left)camera_x=a.left;
        if(a.phase && !a.sign){camera_x=a.camera_x;camera_y=a.camera_y;}
        scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
    }
    /* Act 3 has no signpost spin: the capsule starts the results at the delay phase. */
    fclose(file);scd_player_state p=scd_player_get();scd_act_state a=scd_act_get();
    if(count<2000 || (!act && !ramp) || phases!=(act==2?125u:127u) || a.phase!=SCD_ACT_DONE || a.time_bonus || a.ring_bonus || a.total_bonus!=bonus || p.score!=finish_score+bonus || (act<2 && era==0 && !scd_player_checkpoint().id) || (era!=0 && scd_player_checkpoint().id)){fprintf(stderr,"Incomplete act replay: states=%u phase=%u phases=%u ramp=%u score=%u expected=%u bonus=%u\n",count,a.phase,phases,ramp,p.score,finish_score+bonus,bonus);return 1;}
    printf("Full act host/Saturn match: %u states, %u words; elapsed=%u score=%u bonus=%u lives=%u hurt_ticks=%u ramp_ticks=%u checkpoint=%u\n",count,count*16,p.elapsed,p.score,bonus,p.lives,hurt,ramp,scd_player_checkpoint().id);
    return 0;
}
