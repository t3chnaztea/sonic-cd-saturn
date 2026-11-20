/* Zone placement streaming for the ACTSET-windowed zones (scd_zone_ops
   stream_windowed: Tidal Tempest, Quartz Quadrant,
   Wacky Workbench, Stardust Speedway): the player and camera
   sweep every act and era right then left at 4 px per update while the
   native objects run. Every placement's spawn count comes from the
   instrumented objects.c copy tools/test_zone_stream.py builds
   (stream_spawns[]). A placement that is framed out (ACTSET camera-chunk
   window, tp_frameout_s / FRAMEOUT_S) and reloaded by the +-480 px player
   stream every update ping-pongs; BANEIWA's init also spawns a partner each
   time. usage: zone_stream_test tt|qq|ww|ss. Built by tools/test_zone_stream.py. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "act.h"
#include "stage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
extern unsigned stream_spawns[1024];
/* The game links these from main.c/LOADER2.C; the sweep needs neither
   (as in tools/ww_actors_test.c). */
void sub_sync(short r){(void)r;}
void divdevset(int p){(void)p;}
static unsigned char data[400000],collision[16384],raw[20000];static stage_t stage;static scd_placement placements[1024];
static size_t read_file(const char *n,unsigned char *b,size_t c){FILE *f=fopen(n,"rb");if(!f){fprintf(stderr,"missing %s\n",n);exit(2);}size_t k=fread(b,1,c,f);fclose(f);return k;}
/* The zone's own actor types, whose placements the ACTSET window streams. */
static int tt_type(unsigned t){return (t>=SCD_OBJ_R4_FIRST && t<=SCD_OBJ_R4_LAST) || t==SCD_OBJ_SCREW_F;}
static int qq_type(unsigned t){return t>=SCD_OBJ_R5_DENDEN && t<=SCD_OBJ_R5_KOWASI5;}
static int ww_type(unsigned t){return t>=SCD_OBJ_R6_EGG6DOOR && t<=SCD_OBJ_R6_TOGEBALL6;}
static int ss_type(unsigned t){return t>=SCD_OBJ_R7_EMIE7 && t<=SCD_OBJ_R7_MOVIE7;}
static const struct{const char *name,*prefix;unsigned zone,round;int (*type)(unsigned);}zones[]={
    {"TT","tt",2,4,tt_type},{"QQ","qq",3,5,qq_type},{"WW","ww",4,6,ww_type},{"SS","ss",5,7,ss_type}};
int main(int argc,char **argv){
    unsigned z=0;
    while(argc==2 && z<4 && strcasecmp(argv[1],zones[z].name))z++;
    if(argc!=2 || z==4){fprintf(stderr,"usage: %s tt|qq|ww|ss\n",argv[0]);return 2;}
    const char *name=zones[z].name,*pre=zones[z].prefix;unsigned zone=zones[z].zone,round=zones[z].round;
    unsigned worst=0,worst_act=0,worst_era=0,worst_j=0,cases=0,bane_worst=0,placed=0;int fail=0;
    for(unsigned act=0;act<3;act++)for(unsigned era=act==2?2:0;era<4;era++){
        char p[128];snprintf(p,sizeof(p),"assets/generated/%s%u%u%c.bin",pre,round,act+1,"ABCD"[era]);
        size_t n=read_file(p,data,sizeof(data));if(stage_open(&stage,data,n))return 2;
        snprintf(p,sizeof(p),"assets/generated/%scollision%u%u%c.bin",pre,round,act+1,"ABCD"[era]);size_t cn=read_file(p,collision,sizeof(collision));
        snprintf(p,sizeof(p),"assets/generated/%sobj%u%u.bin",pre,round,act+1);size_t b=read_file(p,raw,sizeof(raw));unsigned count=(unsigned)(b/10);
        int maxx=0;
        for(unsigned i=0;i<count;i++){placements[i].x=(int16_t)(raw[i*10]*256+raw[i*10+1]);placements[i].y=(int16_t)(raw[i*10+2]*256+raw[i*10+3]);
            memcpy(&placements[i].type,raw+i*10+4,5);if(placements[i].x!=-1 && placements[i].x>maxx)maxx=placements[i].x;}
        scd_player_zone(zone);scd_player_act(act);scd_objects_zone(zone);scd_objects_act(act);scd_objects_layout(placements,count);
        if(scd_player_init(&stage,collision,cn,era)){fprintf(stderr,"R%u%u%c: player init failed\n",round,act+1,"ABCD"[era]);return 2;}
        scd_objects_reset(era,1);memset(stream_spawns,0,4096);cases++;
        for(int pass=0;pass<2;pass++)for(int k=0;k<=(maxx+800)/4;k++){
            int x=pass?maxx+800-k*4:k*4;
            actwk[0].xposi.w.h=(short)x;actwk[0].yposi.w.h=0;actwk[0].r_no0=2;actwk[0].cddat=2;
            scd_act_camera(x-160,0);
            scd_objects_step(x,0);
        }
        for(unsigned j=0;j<count;j++){
            unsigned t=placements[j].type,c=stream_spawns[j];
            int own=zones[z].type(t);
            if(own && c)placed++;
            if(own && c>worst){worst=c;worst_act=act;worst_era=era;worst_j=j;}
            if(zone==2 && t==SCD_OBJ_BANEIWA && c>bane_worst)bane_worst=c;
            if(own && c>3){if(fail<8)fprintf(stderr,"R%u%u%c placement %u type %u x %d: %u spawns in one sweep each way\n",round,act+1,"ABCD"[era],j,t,placements[j].x,c);fail++;}
        }
    }
    if(zone==2){
        if(fail){printf("FAIL: %d TT placements reload more than 3 times per two-way sweep (worst %u: R4%u%c placement %u); BANEIWA worst %u\n",fail,worst,worst_act+1,"ABCD"[worst_era],worst_j,bane_worst);return 1;}
        printf("PASS: TT stream: %u act/era sweeps; worst TT placement %u spawns per two-way sweep; BANEIWA worst %u\n",cases,worst,bane_worst);
        return 0;
    }
    if(zone==4){
        if(fail){printf("FAIL: %d WW placements reload more than 3 times per two-way sweep (worst %u: R6%u%c placement %u)\n",fail,worst,worst_act+1,"ABCD"[worst_era],worst_j);return 1;}
        if(!placed){printf("FAIL: WW stream: no R6 placement spawned\n");return 1;}
        printf("PASS: WW stream: %u act/era sweeps; %u R6 placements spawned; worst WW placement %u spawns per two-way sweep\n",cases,placed,worst);
        return 0;
    }
    if(zone==5 && !placed){printf("FAIL: SS stream: no R7 placement spawned\n");return 1;}
    if(fail){printf("FAIL: %d %s placements reload more than 3 times per two-way sweep (worst %u: R%u%u%c placement %u)\n",fail,name,worst,round,worst_act+1,"ABCD"[worst_era],worst_j);return 1;}
    printf("PASS: %s stream: %u act/era sweeps; worst %s placement %u spawns per two-way sweep\n",name,cases,name,worst);
    return 0;
}
