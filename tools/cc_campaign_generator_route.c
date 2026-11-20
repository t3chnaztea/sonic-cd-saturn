/* Record the CC1 campaign route from Present spawn to Past generator.
   The host model includes the real pcol implementation from boss_1.c.
   Saturn acceptance requires replaying this pad with test_cc_campaign_route.py. */
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
    int milestone=argc==3 && !strcmp(argv[2],"--generator")?1:
                  argc==3 && !strcmp(argv[2],"--present")?2:
                  argc==3 && !strcmp(argv[2],"--good-future")?3:
                  argc==3 && !strcmp(argv[2],"--act2")?4:0;
    if(!milestone){
        fprintf(stderr,"usage: cc_campaign_generator_route OUTPUT --generator|--present|--good-future|--act2\n");return 2;
    }
    unsigned era=0,warps=0,journey=0;
    /* Optional Present-leg tuning (defaults reproduce the original route):
       CC1_RETREAT stall back-off, CC1_JUMP_AT observed takeoff X list used
       before the first warp, CC1_CHARGE_JUMP first sequence of the 20-update
       jump-only charge command. */
    unsigned present_retreat=getenv("CC1_RETREAT")?(unsigned)atoi(getenv("CC1_RETREAT")):60;
    unsigned charge_jump=getenv("CC1_CHARGE_JUMP")?(unsigned)atoi(getenv("CC1_CHARGE_JUMP")):5200;
    int present_jump[16];unsigned present_jumps=0;
    if(getenv("CC1_JUMP_AT"))for(const char *s=getenv("CC1_JUMP_AT");*s && present_jumps<16;){
        present_jump[present_jumps++]=(int)strtol(s,(char**)&s,10);if(*s==',')s++;else break;
    }
    if(present_retreat<1 || present_retreat>300)return 2;
    unsigned align_phase=0,align_ticks=0,returning_to_post=0;
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
    if(scd_player_init(&stages[0],collision[0],sizeof(collision[0]),0))return 2;scd_player_objects_lead();
    scd_world_zone(1);scd_world_act(0);scd_world_reset(0);scd_title_card_start(0);
    FILE *out=fopen(argv[1],"w");if(!out){perror(argv[1]);return 2;}
    int camera_y=scd_camera_v_begin(1,0,0,scd_player_get().y/65536,scd_player_get().resets),camera_x=scd_camera_h();
    unsigned buttons=0,delayed=0,last_x=0,stuck=0,jumps=0,hold=0,back=0;
    unsigned turn=0,phase=0,phase_ticks=0,destroyed=0,armed=0,returning=0,return_hold=0,return_last=0,return_leg=0,west_turn=0,hazard_jump=0;
    scd_act_camera(camera_x,camera_y);scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    unsigned observations=30000,recorded=0;
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
        if(era==1){if(x>(int)last_x+1 || x+1<(int)last_x || back)stuck=0;else stuck++;last_x=x;}else if(x>(int)last_x+1){stuck=0;last_x=x;}else stuck++;
        unsigned pad=128;
        /* Existing Past route: back out of the two tower dead ends and jump
           toward the preceding ledge before approaching again. */
        if(stuck>=30 && !(flags&2) && !back){
            static const unsigned holds[]={1,20,10};hold=holds[jumps%3];jumps++;stuck=0;
            if(jumps%4==0){back=present_retreat;hold=0;}
        }
        if(era==0 && !warps && !hold && !back && !(flags&3))
            for(unsigned n=0;n<present_jumps;n++)if(abs(x-present_jump[n])<16)hold=20;
        if(back){pad=64;if(!--back)hold=20;}else if(hold){pad|=1;hold--;}
        unsigned base_pad=pad;
        /* Turn during the high spring launch, enter the upper loop, then
           brake over its left approach. The recorded Down/Jump interval
           rolls through the curve and launches toward the generator. */
        if(x>=5680 && y<700)turn=1;
        if(turn){pad=64;if(hold){pad|=1;hold--;}}
        if(!phase && turn && x<5552 && y<350){phase=1;phase_ticks=0;}
        if(phase==1){pad=p.vx<0?128:0;if(!(flags&2)){phase=2;phase_ticks=0;}}
        else if(phase==2){pad=64;if(++phase_ticks>=20){phase=3;phase_ticks=0;}}
        else if(phase==3){pad=32|1;if(++phase_ticks>=68){phase=4;phase_ticks=0;}}
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
        int post=scd_objects_timepost();if(post){scd_world_activate(post);fprintf(stderr,"POST %u x=%d y=%d dir=%d era=%u\n",sequence,x,y,post,era);}
        
        if(destroyed)pad=p.vx<0?128:p.vx>48?64:0;
        if(destination>=0)pad=0;
        if(!destroyed && era==0){
            if(scd_world_get().direction==-1)armed=1;
            if(armed && x<5440)journey=1;
            if(journey)pad=base_pad;
        }
        if(era==1 && !destroyed && !phase){
            if(x>(int)last_x+1 || x+1<(int)last_x || back)stuck=0;
            last_x=x;
            if(x>8200 && y<1000)returning=1;
            if(returning){
                if(!(flags&2) && !return_hold && !return_last){
                    if(x>7100)return_hold=20;
                    else if(return_leg==0 && x<6970){return_leg=1;return_hold=20;}
                    else if(return_leg==1 && x<6880){return_leg=2;return_hold=20;}
                    else if(return_leg==2 && x<6490){return_leg=3;return_hold=20;}
                }
                pad=64|(return_hold?1:0);if(return_hold)return_hold--;return_last=pad&1;
            }else pad=base_pad;
            if(return_leg==3 && x<6320 && y>860)return_leg=4;
            if(return_leg==4){pad=128;if(x>6360 && y>1000)return_leg=5;}
            if(return_leg==5)pad=64;
            if(!west_turn && x<6300 && y>1300)
                pad=64|((sequence%36)<12?1:0);
            if(x<4900 && y>1000)west_turn=1;
            if(west_turn && !turn)pad=base_pad;
        }
        if(p.resets || p.routine>=6){
            fprintf(stderr,"Route died: sequence=%u era=%u x=%d y=%d vx=%d vy=%d flags=%u routine=%u resets=%u pad=%u\n",
                    sequence,era,x,y,p.vx,p.vy,flags,p.routine,p.resets,pad);
            return 1;
        }
        /* A jump-only command during the Present charge shifts the warp
           landing past the fatal lip without changing the warp sequence. */
        if(sequence>=charge_jump && sequence<charge_jump+20)pad=1;
        if(milestone>1 && destroyed && sequence>destroyed){
            /* Settle on the Past floor before reversing to the Future post. */
            if(align_phase==0){pad=128;if(x>=5018 && y==636)align_phase=1;}
            else if(align_phase==1){pad=64;if(p.vx<=0){align_phase=2;align_ticks=0;}}
            else if(align_phase==2){
                pad=0;
                if(++align_ticks>=119){
                    if(x!=5034 || y!=636 || p.vx){fprintf(stderr,"Past alignment changed\n");return 1;}
                    align_phase=3;
                }
            }else{
                if(!returning_to_post && x<4500 && y>940)returning_to_post=1;
                pad=returning_to_post?base_pad:64;
                /* Pass below the post's ledge before approaching from left. */
                if(returning_to_post && x>=9000 && x<9250 && y<1030)pad=64;
            }
        }
        if(milestone>1 && warps==2)pad=128|((sequence%24)<8?1:0);
        if(milestone==3 && warps>=3)pad=128;
        if(milestone==4 && warps>=3)pad=base_pad;
        if(era==1 && !destroyed && !hazard_jump && x>=6503 && x<=6510 && y>=1148 && p.vx<=0){
            pad=65;hazard_jump=1;
        }
        /* Libretro's pad request is sampled two observations later. */
        delayed=buttons;
        buttons=(pad&128?SCD_RIGHT:0)|(pad&64?SCD_LEFT:0)|(pad&1?SCD_JUMP:0)|(pad&32?SCD_DOWN:0);
        fprintf(out,"%u %u %d %d\n",sequence,pad,x,y);
        recorded++;
        if((milestone==1 && destroyed) || (milestone==2 && warps>=2) ||
           (milestone==3 && warps>=3) ||
           (milestone==4 && result.phase==SCD_ACT_DONE))break;
        if(destination>=0){
            fprintf(stderr,"Warp: sequence=%u era=%u destination=%d good_future=%u\n",sequence,era,destination,scd_world_get().good_future);
            era=destination;
            if(scd_player_arrive(&stages[era],collision[era],sizeof(collision[era]),era))return 1;scd_player_objects_lead();
            scd_world_arrived(era);warps++;journey=0;turn=phase=phase_ticks=0;
            scd_player_state arrived=scd_player_get();
            scd_arrival_camera(arrived.x/65536,arrived.y/65536,0,scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&camera_y);
            camera_y=scd_camera_v_begin(1,0,era,arrived.y/65536,arrived.resets);
            /* The cutscene keeps sampling the last pad command while the
               gameplay observation sequence is stopped. */
            delayed=buttons;hold=back=stuck=jumps=0;
        }
    }
    if(fclose(out))return 2;
    if(!destroyed || !scd_world_get().good_future)return 1;
    if(warps!=(unsigned)(milestone<4?milestone:3) || era!=(milestone==1?1:milestone==2?0:2))return 1;
    if(milestone==4 && scd_act_get().phase!=SCD_ACT_DONE)return 1;
    fprintf(stderr,"Recorded %u controller observations; generator=%u warps=%u\n",recorded,destroyed,warps);
    return 0;
}
