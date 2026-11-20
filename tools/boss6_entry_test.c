/* R63C/D entry and first attack: generated BOSS_6.C on native and PC actor
   layouts. tools/test-boss6-entry.sh compares every update. */
#include "EQU.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

short pcol(sprite_status *p);
short emycol_d(sprite_status *p){(void)p;return 0;}
short playdieset(sprite_status *p){(void)p;return -1;}
short dircolm(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol_d(sprite_status *p,short *a,short *b,short *c){(void)p;*a=*b=64;*c=0;return 64;}
short dircol_u2(sprite_status *p){(void)p;return 64;}
sprite_pattern *bakupat[7];
static unsigned sounds,hurts;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){(void)type;(void)x;(void)y;(void)sub;(void)flags;return 0;}
void scd_objects_hurt(int x){(void)x;hurts++;}
void scd_player_points(unsigned n){(void)n;}
void soundset(short n){sounds=sounds*33+(unsigned short)n;}
static unsigned count(unsigned id){unsigned n=0;for(unsigned i=97;i<128;i++)n+=actwk[i].actno==id;return n;}
static sprite_status *find(unsigned id){for(unsigned i=97;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}

int main(int argc,char **argv){
    generate_flag=argc>1 && !strcmp(argv[1],"good");time_flag=2;
    memset(actwk,0,sizeof(actwk));scd_boss_reset();
    const short door[][4]={{2568,650,128,7},{2567,1162,128,6},{2566,1610,0,5},
        {2936,1674,129,5},{2937,1162,129,6},{2938,650,1,7}};
    for(unsigned i=0;i<6;i++)scd_boss6_door(door[i][0],door[i][1],door[i][2],door[i][3]);
    scd_boss_create_sub(2752,1408,0,6);
    actwk[0].xposi.w.h=2700;actwk[0].yposi.w.h=1408;
    unsigned entered=0,attack=0,hover=0,retreat=0,event=0,meca=0,beam=0,doors=0;
    for(unsigned t=0;t<800;t++){
        scd_boss_camera(2528,1280);scra_v_posit.w.h=1280;
        scd_boss_step();
        sprite_status *boss=find(52);
        if(!boss){fprintf(stderr,"boss vanished at %u\n",t);return 1;}
        if(bossstart==6 && !entered)entered=t+1;
        if(boss->r_no0>=4 && !attack)attack=t+1;
        if(boss->r_no0==6 && !hover)hover=t+1;
        if(boss->r_no0==8 && !retreat)retreat=t+1;
        if(boss->r_no0==10 && !event)event=t+1;
        if(count(53)+count(54)+count(55)>meca)meca=count(53)+count(54)+count(55);
        if(count(64)>beam)beam=count(64);
        if(count(62)>doors)doors=count(62);
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64),drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*33u+(unsigned)views[i].kind*256u+views[i].frame;
        printf("%u %08x %08x %u %u %u %u %u %u %u %u %u %u\n",t,scd_boss_hash(),scd_boss_position(),
               boss->r_no0,boss->patno,bossflag,bossstart,count(53),count(54),count(55),count(64),drawn,sounds);
    }
    printf("summary era=%s entered=%u attack=%u hover=%u retreat=%u event=%u meca=%u beam=%u doors=%u hurts=%u round=%u\n",
           generate_flag?"good":"bad",entered,attack,hover,retreat,event,meca,beam,doors,hurts,scd_boss_round());
    return entered && attack && hover && retreat && event && meca && doors==6 && scd_boss_round()==6?0:1;
}
