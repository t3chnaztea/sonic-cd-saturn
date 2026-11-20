/* Record an ordinary CC2 pad route from the level-select spawn of one era
   through the Act 2 tally. Native-host model only: Saturn acceptance replays
   the pad with tools/test_cc2_route.py and compares every observed position.
   The input strategy mirrors tools/emulator_test.c's local CC route (Right,
   stuck jumps, retreats) plus optional observed takeoff/backjump points.
   No placement or velocity writes. */
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

static unsigned char data[400000], collision[9472], raw[10240];
static scd_placement placements[1024];
static int clamp(int n,int low,int high){return n<low?low:n>high?high:n;}
static size_t read_file(const char *name,void *buffer,size_t capacity){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    size_t n=fread(buffer,1,capacity,f);
    if(ferror(f) || fgetc(f)!=EOF){fprintf(stderr,"Invalid input: %s\n",name);exit(2);}
    fclose(f);return n;
}
static unsigned points(const char *list,int out[16]){
    unsigned n=0;if(!list || !*list)return 0;
    for(const char *s=list;*s && n<16;){out[n++]=(int)strtol(s,(char**)&s,10);if(*s==',')s++;else break;}
    return n;
}
static int near(const int *p,unsigned n,int x,int radius){for(unsigned i=0;i<n;i++)if(abs(x-p[i])<radius)return 1;return 0;}
int main(int argc,char **argv){
    /* cc2_route_host OUTPUT ERA RETREAT LIMIT [JUMP_AT] [BACKJUMP_AT] [X:RETREAT,..] [RULES] */
    if(argc<5 || argc>9 || strlen(argv[2])!=1 || argv[2][0]<'A' || argv[2][0]>'D'){
        fprintf(stderr,"usage: cc2_route_host OUTPUT A|B|C|D RETREAT LIMIT [JUMP_AT,..] [BACKJUMP_AT,..] [X:RETREAT,..] [X0:X1:Y0:Y1:PAD;..]\n");return 2;
    }
    unsigned era=(unsigned)(argv[2][0]-'A'),retreat=(unsigned)atoi(argv[3]),limit=(unsigned)atoi(argv[4]);
    int jump_at[16],backjump_at[16];
    unsigned jump_count=points(argc>5?argv[5]:NULL,jump_at),backjump_count=points(argc>6?argv[6]:NULL,backjump_at);
    /* Optional local retreat lengths: a stall within 64 pixels of X backs
       off for its own interval instead of the global one. */
    int local_x[16],local_retreat[16];unsigned local_count=0;
    if(argc>7 && *argv[7])for(const char *s=argv[7];*s && local_count<16;){
        local_x[local_count]=(int)strtol(s,(char**)&s,10);if(*s++!=':')return 2;
        local_retreat[local_count++]=(int)strtol(s,(char**)&s,10);if(*s==',')s++;else break;
    }
    for(unsigned i=0;i<local_count;i++)if(local_retreat[i]<11 || local_retreat[i]>300)return 2;
    unsigned active_retreat=retreat;
    /* Optional observed areas with a fixed pad command (bit 7 Right, 6 Left,
       5 Down, 0 Jump, 1 jump pulsed ten on/ten off); the first matching area
       replaces the heuristic. */
    int rule[16][5];unsigned rule_count=0;
    if(argc>8 && *argv[8])for(const char *s=argv[8];*s && rule_count<16;){
        for(unsigned k=0;k<5;k++){rule[rule_count][k]=(int)strtol(s,(char**)&s,10);if(k<4 && *s++!=':')return 2;}
        if(rule[rule_count][4]&~0xe3)return 2;
        rule_count++;if(*s==';')s++;else break;
    }
    if(retreat<1 || retreat>300 || limit<200 || limit>24000)return 2;
    stage_t stage;char path[128];
    snprintf(path,sizeof(path),"assets/generated/cc32%c.bin","ABCD"[era]);
    size_t bytes=read_file(path,data,sizeof(data));if(stage_open(&stage,data,bytes))return 2;
    snprintf(path,sizeof(path),"assets/generated/cccollision32%c.bin","ABCD"[era]);
    if(read_file(path,collision,sizeof(collision))!=9472)return 2;
    bytes=read_file("assets/generated/ccobj32.bin",raw,sizeof(raw));
    if(bytes%10)return 2;
    for(unsigned i=0;i<bytes/10;i++){
        placements[i].x=(int16_t)(raw[i*10]*256+raw[i*10+1]);
        placements[i].y=(int16_t)(raw[i*10+2]*256+raw[i*10+3]);
        memcpy(&placements[i].type,raw+i*10+4,5);
    }
    scd_player_zone(1);scd_player_act(1);scd_objects_zone(1);scd_objects_act(1);
    scd_objects_layout(placements,bytes/10);
    if(scd_player_init(&stage,collision,sizeof(collision),era))return 2;scd_player_objects_lead();
    scd_world_zone(1);scd_world_act(1);scd_world_reset(era);scd_title_card_start(1);
    FILE *out=fopen(argv[1],"w");if(!out){perror(argv[1]);return 2;}
    int camera_y=scd_camera_v_begin(1,1,era,scd_player_get().y/65536,scd_player_get().resets),camera_x=scd_camera_h();
    unsigned buttons=0,delayed=0,last_x=0,stuck=0,jumps=0,hold=0,back=0,runup=0,backjump=0,generator=0,max_x=0;
    scd_act_camera(camera_x,camera_y);scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    for(unsigned sequence=2;sequence<=limit+1;sequence++){
        scd_act_camera(camera_x,camera_y);
        int locked=scd_title_card_locked();scd_player_hold_clock(locked);
        scd_objects_travel_protection(scd_world_get().ticks>0);
        scd_player_step(locked?0:delayed);
        scd_title_card_step();
        scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
        unsigned flags=p.flags;if((unsigned)x>max_x)max_x=(unsigned)x;
        camera_y=clamp(scd_camera_v_follow(y,p.resets),0,scralim_down);camera_x=clamp(scd_camera_h(),scralim_left,scralim_right);
        scd_act_state result=scd_act_get();
        if(result.goal && camera_x<result.left)camera_x=result.left;
        if(result.phase){camera_x=result.camera_x;camera_y=result.camera_y;}
        scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
        if(x>(int)last_x+1 || x+1<(int)last_x || back || runup)stuck=0;else stuck++;
        last_x=(unsigned)x;unsigned pad=128;
        if(stuck>=30 && !(flags&2) && !back && !runup){
            static const unsigned holds[]={1,20,10};hold=holds[jumps%3];jumps++;stuck=0;
            if(jumps%4==0){
                active_retreat=retreat;
                for(unsigned i=0;i<local_count;i++)if(abs(x-local_x[i])<64)active_retreat=(unsigned)local_retreat[i];
                back=active_retreat;hold=0;backjump=near(backjump_at,backjump_count,x,64);
            }
        }
        if(jump_count && !hold && !back && !runup && !(flags&3) && near(jump_at,jump_count,x,16))hold=20;
        if(back){
            pad=64;
            if(backjump && active_retreat>10 && back==active_retreat-10)hold=20;
            if(hold){pad|=1;hold--;}
            if(!--back)runup=20;
        }else if(runup){if(!--runup)hold=20;}
        else if(hold){pad|=1;hold--;}
        for(unsigned i=0;i<rule_count;i++)
            if(x>=rule[i][0] && x<=rule[i][1] && y>=rule[i][2] && y<=rule[i][3]){
                pad=(unsigned)rule[i][4];
                if(pad&2)pad=(pad&~3u)|((sequence/10)%2?0u:1u);
                stuck=hold=back=runup=0;break;
            }
        if(scd_objects_generator()){
            if(generator){fprintf(stderr,"Repeated generator event\n");return 1;}
            generator=sequence;scd_world_generator_destroyed();
            fprintf(stderr,"Generator: sequence=%u x=%d y=%d\n",sequence,x,y);
        }
        int destination=scd_world_step(p);
        int post=scd_objects_timepost();if(post)scd_world_activate(post);
        if(destination>=0){fprintf(stderr,"Route warped at %u x=%d y=%d max_x=%u\n",sequence,x,y,max_x);return 1;}
        if(p.resets || p.routine>=6){fprintf(stderr,"Route died at %u x=%d y=%d max_x=%u\n",sequence,x,y,max_x);return 1;}
        /* Libretro's pad request is sampled two observations later. */
        delayed=buttons;
        buttons=(pad&128?SCD_RIGHT:0)|(pad&64?SCD_LEFT:0)|(pad&1?SCD_JUMP:0)|(pad&32?SCD_DOWN:0);
        fprintf(out,"%u %u %d %d\n",sequence,pad,x,y);
        if(result.phase==SCD_ACT_DONE){
            if(fclose(out))return 2;
            fprintf(stderr,"Tally complete: sequence=%u era=%u good_future=%u generator=%u score=%u\n",
                    sequence,era,scd_world_get().good_future,generator,p.score);
            return 0;
        }
    }
    fclose(out);
    fprintf(stderr,"Route incomplete: limit=%u max_x=%u\n",limit,max_x);
    return 1;
}
