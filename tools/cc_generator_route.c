/* Generate an ordinary pad recording from the CC1 Past spawn. This is a
   native-host route, not an original-game oracle; Saturn replays must compare
   each observed position before accepting it. No placement/velocity writes. */
#include "scd_player.h"
#include "camera_v.h"
#include "scd_objects.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include "arrival_camera.h"
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char data[4][400000], collision[4][9472], raw[10240];
static scd_placement placements[1024];
static int clamp(int n,int low,int high){return n<low?low:n>high?high:n;}
static size_t read_file(const char *name,void *buffer,size_t capacity){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    size_t n=fread(buffer,1,capacity,f);
    if(ferror(f) || fgetc(f)!=EOF){fprintf(stderr,"Invalid input: %s\n",name);exit(2);}
    fclose(f);return n;
}
int main(int argc,char **argv){
    if(argc<2 || argc>3 || (argc==3 && strcmp(argv[2],"--travel") && strcmp(argv[2],"--good-future") && strcmp(argv[2],"--act2"))){fprintf(stderr,"usage: cc_generator_route OUTPUT [--travel|--good-future|--act2]\n");return 2;}
    int travel=argc==3,finish=travel && !strcmp(argv[2],"--act2");
    int good=finish || (travel && !strcmp(argv[2],"--good-future"));
    unsigned era=1,warps=0,journey=0,journey_ticks=0;
    stage_t stages[4];size_t bytes;
    for(unsigned e=0;e<4;e++){
        char path[128];snprintf(path,sizeof(path),"assets/generated/cc31%c.bin","ABCD"[e]);
        bytes=read_file(path,data[e],sizeof(data[e]));if(stage_open(&stages[e],data[e],bytes))return 2;
        snprintf(path,sizeof(path),"assets/generated/cccollision31%c.bin","ABCD"[e]);
        if(read_file(path,collision[e],sizeof(collision[e]))!=9472)return 2;
    }
    bytes=read_file("assets/generated/ccobj31.bin",raw,sizeof(raw));
    if(bytes%10)return 2;
    for(unsigned i=0;i<bytes/10;i++){
        placements[i].x=raw[i*10]*256+raw[i*10+1];
        placements[i].y=raw[i*10+2]*256+raw[i*10+3];
        memcpy(&placements[i].type,raw+i*10+4,5);
    }
    scd_player_zone(1);scd_player_act(0);scd_objects_zone(1);scd_objects_act(0);
    scd_objects_layout(placements,bytes/10);
    if(scd_player_init(&stages[1],collision[1],sizeof(collision[1]),1))return 2;scd_player_objects_lead();
    scd_world_zone(1);scd_world_act(0);scd_world_reset(1);scd_title_card_start(0);
    FILE *out=fopen(argv[1],"w");if(!out){perror(argv[1]);return 2;}
    int camera_y=scd_camera_v_begin(1,0,1,scd_player_get().y/65536,scd_player_get().resets),camera_x=scd_camera_h();
    unsigned buttons=0,delayed=0,last_x=0,stuck=0,jumps=0,hold=0,back=0,runup=0,backjump=0;
    unsigned turn=0,phase=0,phase_ticks=0,destroyed=0;
    scd_act_camera(camera_x,camera_y);scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    unsigned observations=finish?18000:good?6600:travel?6000:4200,recorded=0;
    for(unsigned sequence=2;sequence<=observations+1;sequence++){
        scd_act_camera(camera_x,camera_y);
        int locked=scd_title_card_locked();scd_player_hold_clock(locked);
        scd_objects_travel_protection(scd_world_get().ticks>0);
        scd_player_step(locked?0:delayed);
        scd_title_card_step();
        scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
        unsigned flags=p.flags;
        camera_y=clamp(scd_camera_v_follow(y,p.resets),0,scralim_down);camera_x=clamp(scd_camera_h(),scralim_left,scralim_right);
        scd_act_state result=scd_act_get();
        if(result.goal && camera_x<result.left)camera_x=result.left;
        if(result.phase && !result.sign){camera_x=result.camera_x;camera_y=result.camera_y;}
        scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
        if(x>(int)last_x+1 || x+1<(int)last_x || back || runup)stuck=0;else stuck++;
        last_x=x;unsigned pad=128;
        /* Existing Past route: back out of the two tower dead ends and jump
           toward the preceding ledge before approaching again. */
        if(stuck>=30 && !(flags&2) && !back && !runup){
            static const unsigned holds[]={1,20,10};hold=holds[jumps%3];jumps++;stuck=0;
            if(jumps%4==0){back=warps>=2?60:100;hold=0;backjump=abs(x-2229)<=64 || abs(x-2485)<=64;}
        }
        if(finish && warps>=2 && sequence>6601 && !hold && !back && !runup && !(flags&3) &&
           (abs(x-6620)<16 || abs(x-9650)<16 || abs(x-9900)<16))hold=20;
        if(back){pad=64;if(backjump && back==90)hold=20;if(hold){pad|=1;hold--;}if(!--back)runup=20;}
        else if(runup){if(!--runup)hold=20;}else if(hold){pad|=1;hold--;}
        unsigned base_pad=pad;
        /* Turn during the high spring launch, enter the upper loop, then
           brake over its left approach. The recorded Down/Jump interval
           rolls through the curve and launches toward the generator. */
        if(x>=5680 && y<700)turn=1;
        if(turn){pad=64;if(hold){pad|=1;hold--;}}
        if(!phase && turn && x<5552 && y<350){phase=1;phase_ticks=0;}
        if(phase==1){pad=p.vx<0?128:0;if(!(flags&2)){phase=2;phase_ticks=0;}}
        else if(phase==2){pad=64;if(++phase_ticks>=24){phase=3;phase_ticks=0;}}
        else if(phase==3){pad=32|1;if(++phase_ticks>=45){phase=4;phase_ticks=0;}}
        else if(phase==4){pad=64;if(++phase_ticks>=5){phase=5;phase_ticks=0;}}
        else if(phase==5){
            pad=64|(phase_ticks++<20?1:0);
            if(x<5060 && y<580){phase=6;phase_ticks=0;}
            else if(x<5100 && y>590 && !(flags&2)){phase=7;phase_ticks=0;}
        }
        else if(phase==6){pad=p.vx<0?128:0;if(!(flags&2)){phase=7;phase_ticks=0;}}
        else if(phase==7){pad=64|(phase_ticks++%40<20?1:0);}
        if(scd_objects_generator()){
            if(destroyed){fprintf(stderr,"Repeated generator event\n");return 1;}
            destroyed=sequence;scd_world_generator_destroyed();
            fprintf(stderr,"Generator: sequence=%u x=%d y=%d score=%u\n",sequence,x,y,p.score);
        }
        int destination=scd_world_step(p);
        int post=scd_objects_timepost();if(post)scd_world_activate(post);
        if(destination>=0 && (!travel || !destroyed)){fprintf(stderr,"Route warped before completion at %u\n",sequence);return 1;}
        if(destroyed)pad=p.vx<0?128:p.vx>48?64:0;
        if(travel && destroyed && sequence>destroyed+120 && !warps){
            /* Drop to the middle path, touch its unused Future post, then
               wait until low enough to pass beneath the spiked ledges. */
            if(!journey && x>5200 && y>800)journey=1;
            if(journey==1 && y>1020)journey=2;
            pad=journey==1?64:128;
            if(journey==2 && x>=5700 && y<700){journey=10;journey_ticks=0;}
            if(journey==10){pad=64;if(x<5548 && y<350){journey=11;journey_ticks=0;}}
            else if(journey==11){pad=p.vx<0?128:0;if(!(flags&2)){journey=12;journey_ticks=0;}}
            else if(journey==12){pad=64;if(++journey_ticks>=4){journey=13;journey_ticks=0;}}
            else if(journey==13){pad=33;if(++journey_ticks>=45){journey=14;journey_ticks=0;}}
            else if(journey==14){pad=64;if(++journey_ticks>=5){journey=15;journey_ticks=0;}}
            else if(journey==15){pad=64|(journey_ticks++<20?1:0);}
            if(hold)pad|=1;
        }
        if(good && warps==1){
            /* Return left to the Present-era Future post, then turn right
               below its ledge. The lower springs sustain the second warp. */
            if(!journey && x<4500 && y>940)journey=1;
            pad=journey?128:64;
        }
        if(destination>=0 || warps>=(good?2u:1u))pad=0;
        if(finish && warps>=2 && sequence>6601)pad=base_pad;
        if(finish && sequence==6601){hold=back=runup=stuck=jumps=0;}
        if(p.resets || p.routine>=6){fprintf(stderr,"Route died\n");return 1;}
        /* Libretro's pad request is sampled two observations later. */
        delayed=buttons;
        buttons=(pad&128?SCD_RIGHT:0)|(pad&64?SCD_LEFT:0)|(pad&1?SCD_JUMP:0)|(pad&32?SCD_DOWN:0);
        fprintf(out,"%u %u %d %d\n",sequence,pad,x,y);
        recorded++;
        if(finish && result.phase==SCD_ACT_DONE){
            fprintf(stderr,"Tally complete: sequence=%u good_future=%u score=%u\n",sequence,scd_world_get().good_future,p.score);
            break;
        }
        if(destination>=0){
            fprintf(stderr,"Warp: sequence=%u era=%u destination=%d good_future=%u\n",sequence,era,destination,scd_world_get().good_future);
            era=destination;
            if(scd_player_arrive(&stages[era],collision[era],sizeof(collision[era]),era))return 1;scd_player_objects_lead();
            scd_world_arrived(era);warps++;journey=journey_ticks=0;
            scd_player_state arrived=scd_player_get();
            scd_arrival_camera(arrived.x/65536,arrived.y/65536,0,scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&camera_y);
            camera_y=scd_camera_v_begin(1,0,era,arrived.y/65536,arrived.resets);
            /* The cutscene keeps sampling the last pad command while the
               gameplay observation sequence is stopped. */
            delayed=buttons;hold=back=runup=stuck=jumps=0;
        }
    }
    if(fclose(out))return 2;
    if(!destroyed || !scd_world_get().good_future)return 1;
    if(travel && (warps!=(good?2u:1u) || era!=(good?2u:0u)))return 1;
    if(finish && scd_act_get().phase!=SCD_ACT_DONE)return 1;
    fprintf(stderr,"Recorded %u controller observations; generator=%u warps=%u\n",recorded,destroyed,warps);
    return 0;
}
