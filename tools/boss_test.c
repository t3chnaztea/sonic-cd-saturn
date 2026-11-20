/* Runs BOSS_1.C and the COLI1.C touch response through src/boss.c twice:
 * against build/probe-source (little-endian accessors, the Saturn source) and
 * build/player-reference (original PC casts on the 68-byte PC actor).
 * tools/test-boss.sh requires identical per-update traces. A scripted Sonic
 * walks into the arena, rolls into the arms, touches a leg, then jumps rolling
 * onto Robotnik until the boss leaves. */
#include "EQU.H"
#include "COLI1.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* Flat arena floor at Y 440 for the legs (DIRCOL.C emycol_d distance). */
short emycol_d(sprite_status *p){return (short)(440-(p->yposi.w.h+p->sprvsize));}
static uint32_t explosions,hurts,points,sounds;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){
    explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;
}
void scd_objects_hurt(int source_x){hurts++;(void)source_x;}
void scd_player_points(unsigned value){points+=value;}
void soundset(short request){sounds=sounds*33+(uint16_t)request;}

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->direc.w,p->cddat,p->mstno.w,p->r_no0,p->actfree[6],p->actfree[7]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    return h;
}
static sprite_status *find(unsigned id){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}
int main(void){
    memset(actwk,0,sizeof(actwk));
    sprite_status *p=&actwk[0];
    p->actno=1;p->xposi.w.h=2600;p->yposi.w.h=420;p->sprvsize=19;p->sprhs=9;
    scra_vline=96;scralim_left=0;scralim_right=3479;scralim_down=784;
    scd_boss_reset();scd_boss_create(3088,104);
    unsigned seen[64]={0},hits=0,last_state=0,defeated=0;
    for(unsigned frame=0;frame<6000;frame++){
        sprite_status *robotnik=find(42),*arm=find(49),*leg=find(46);
        p->xspeed.w=p->yspeed.w=0;
        if(frame<420){
            if(p->xposi.w.h<2940)p->xposi.w.h+=2;
            p->yposi.w.h=420;p->cddat=0;p->mstno.b.h=0;
        }else if(frame<2400 && arm && frame%48==24){
            /* Rolling contacts with arm 3 (colino 255) detach the arms (egg1_coliude). */
            p->xposi.w.h=arm->xposi.w.h;p->yposi.w.h=arm->yposi.w.h-8;p->cddat=6;p->mstno.b.h=2;p->yspeed.w=256;
        }else if(frame<2400 && leg && frame%96==60){
            /* A standing contact with a leg (colino 189/190) hurts Sonic. */
            p->xposi.w.h=leg->xposi.w.h;p->yposi.w.h=leg->yposi.w.h;p->cddat=0;p->mstno.b.h=0;
        }else if(frame>=2400 && robotnik && frame%48==0){
            p->xposi.w.h=robotnik->xposi.w.h;p->yposi.w.h=robotnik->yposi.w.h-12;p->cddat=6;p->mstno.b.h=2;p->yspeed.w=256;
        }else if(frame%48==6){
            p->xposi.w.h=2900;p->yposi.w.h=420;p->cddat=0;p->mstno.b.h=0;
        }
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        scd_boss_camera(p->xposi.w.h-160,p->yposi.w.h-140);
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        scd_boss_step();
        scd_boss_view views[64];unsigned count=scd_boss_views(views,64);uint32_t drawn=count;
        for(unsigned i=0;i<count;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags);
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno>=42 && actwk[i].actno<=50)seen[(actwk[i].actno-42)*6+(actwk[i].r_no0/2)%6]=1;
        if(robotnik && robotnik->actfree[1]!=last_state){hits++;last_state=robotnik->actfree[1];}
        if(frame>600 && !find(42) && !defeated)defeated=frame;
        printf("%u %08x %08x %08x %08x %08x %u %u %d %d\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,scd_boss_palette(),scd_boss_music());
    }
    unsigned states=0;for(unsigned i=0;i<64;i++)states+=seen[i];
    printf("summary defeated=%u states=%u hit_changes=%u points=%u hurts=%u\n",defeated,states,hits,points,hurts);
    return defeated && states>=30 && hurts?0:1;
}
