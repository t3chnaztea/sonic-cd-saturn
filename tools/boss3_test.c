/* Runs BOSS_3.C, GATE.C and the COLI3.C touch response through src/boss.c and
 * src/boss_r3.c twice: against build/probe-source (little-endian accessors, the
 * Saturn source) and build/player-reference (original PC casts on the 68-byte
 * PC actor). tools/test-boss.sh requires identical per-update traces.
 * A scripted Sonic rolls into egg3dai_s (the entrance lift), walks past it to
 * close the arena gate, waits under the cannon for punch bombs (touching one),
 * rolls into egg3dai_l until it is beaten, then climbs past the four shaft
 * gates until jaba_last raises bossflag. */
#include "EQU.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* A box arena for the punch bombs: floor Y 600, ceiling Y 300, walls X 800/1000. */
short emycol_d(sprite_status *p){return (short)(600-(p->yposi.w.h+p->sprvsize));}
short emycol_u(sprite_status *p){return (short)(p->yposi.w.h-p->sprvsize-300);}
short emycol_l(sprite_status *p,unsigned char hs){return (short)(p->xposi.w.h-hs-800);}
short emycol_r(sprite_status *p,unsigned char hs){return (short)(1000-(p->xposi.w.h+hs));}
short pcol(sprite_status *p);
short playdieset(sprite_status *p){(void)p;return -1;}
/* RIDECHK.C's pushes and crush checks see open space: no terrain in the arena box. */
short dircolm(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol_d(sprite_status *p,short *d0,short *d1,short *d3){(void)p;*d0=*d1=64;*d3=0;return 64;}
short dircol_u2(sprite_status *p){(void)p;return 64;}
static uint32_t explosions,hurts,points,sounds;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){
    explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;
}
void scd_objects_hurt(int source_x){hurts++;(void)source_x;}
void scd_player_points(unsigned value){points+=value;}
void soundset(short request){sounds=sounds*33+(uint16_t)request;}

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->direc.w,p->cddat,p->mstno.w,p->r_no0,p->actfree[18],p->actfree[19]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    return h;
}
static sprite_status *find(unsigned id){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}
static unsigned count(unsigned id){unsigned n=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)n+=actwk[i].actno==id;return n;}
static void place(int x,int y,int rolling){
    sprite_status *p=&actwk[0];
    p->xposi.w.h=x;p->yposi.w.h=y;p->cddat=rolling?6:0;p->mstno.b.h=rolling?2:0;p->yspeed.w=rolling?256:0;
}
/* argv[1] "good": the Good Future (generate_flag set, R33C); otherwise the Bad Future (R33D). */
int main(int argc,char **argv){
    memset(actwk,0,sizeof(actwk));
    generate_flag=argc>1 && !strcmp(argv[1],"good");
    sprite_status *p=&actwk[0];
    p->actno=1;p->sprvsize=19;p->sprhs=9;place(1000,1340,0);
    scra_vline=96;scralim_left=0;scralim_right=1175;scralim_down=1296;
    scd_boss_reset();scd_boss_create_sub(1072,1344,SCD_BOSS_EGG3DAI_S,3);scd_boss_create_sub(896,448,SCD_BOSS_EGG3DAI_L,3);
    unsigned seen[64][8]={{0}},hits=0,last_hits=0,defeated=0,bombs=0,bomb_touches=0,gates=0,last_bossflag=0,flag_frame=0,small_gone=0,max_vline=0;
    for(unsigned frame=0;frame<4200;frame++){
        sprite_status *small=find(48),*large=find(49),*bomb=find(62);
        p->xspeed.w=p->yspeed.w=0;
        if(frame<60)place(1000+frame,1340,0);
        else if(frame==60 && small)place(small->xposi.w.h,small->yposi.w.h-20,1);
        else if(frame<240)place(1000,1400,0);
        else if(frame<300)place(1200,1290,0);             /* jaba_s_chk: gate and boss music */
        else if(frame<1500){
            /* Under the cannon (Y < 1024, no shaft gate yet); one bomb touches Sonic. */
            if(frame==1100 && bomb){place(bomb->xposi.w.h,bomb->yposi.w.h,0);bomb_touches++;}
            else place(900,560,0);
        }else if(frame<3000){
            if(large && large->r_no0==4 && large->colino && frame%60==0)place(large->xposi.w.h,large->yposi.w.h-24,1);
            else place(900,560,0);
        }else if(frame<3300)place(896,420,0);             /* second and third shaft gates */
        else if(frame<3600)place(896,350,0);
        else place(896,260,0);                            /* jaba_last: bossflag 3, fourth gate */
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        /* actionsub marks actors inside the view as drawn, and pcol touches only
           drawn actors: the arena view is fixed once Sonic leaves the entrance. */
        if(frame<300)scd_boss_camera(p->xposi.w.h-160,p->yposi.w.h-140);else scd_boss_camera(736,frame<3000?300:160);
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        scd_boss_step();
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64);uint32_t drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags^(views[i].kind<<20));
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){unsigned id=actwk[i].actno;if(id)seen[id&63][(actwk[i].r_no0/2)&7]=1;}
        large=find(49);
        if(large && large->actfree[17]!=last_hits){hits++;last_hits=large->actfree[17];}
        if(frame>60 && !find(49) && !defeated)defeated=frame;
        if(!small && !small_gone && frame>60)small_gone=frame;
        unsigned b=count(62);if(b>bombs)bombs=b;
        unsigned g=count(63);if(g>gates)gates=g;
        if(bossflag!=last_bossflag){last_bossflag=bossflag;flag_frame=frame;}
        if((unsigned)scra_vline>max_vline)max_vline=scra_vline;
        printf("%u %08x %08x %08x %08x %08x %u %u %d %d %d %08x %08x %02x%02x\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,scd_boss_palette(),scd_boss_music(),bossflag,
            scd_boss_status(),scd_boss_position(),large?large->colino:0,large?large->colicnt:0);
    }
    unsigned states=0;for(unsigned i=0;i<64;i++)for(unsigned r=0;r<8;r++)states+=seen[i][r];
    printf("summary defeated=%u hit_phases=%u bossflag=%u flag_frame=%u small_gone=%u states=%u max_bombs=%u bomb_touches=%u max_gates=%u points=%u hurts=%u vline=%u round=%u\n",
        defeated,hits,last_bossflag,flag_frame,small_gone,states,bombs,bomb_touches,gates,points,hurts,max_vline,scd_boss_round());
    printf("era=%s\n",generate_flag?"good":"bad");
    return defeated && hits==3 && last_bossflag==3 && small_gone && bombs && gates>=4 && max_vline==178?0:1;
}
