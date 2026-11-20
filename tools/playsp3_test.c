/* Collision Chaos terrain bumper blocks: runs R3/PLAYSP3.C and R3/BOBINB.C
 * (tools/prepare_playsp3.py) twice, against build/probe-source (little-endian
 * accessors, the Saturn source) and build/player-reference (original PC casts
 * on the 68-byte PC actor). tools/test-playsp3.sh requires identical traces.
 * For each era's fcol table (past, present, good and bad future), each bumper
 * kind in it, both horizontal flips, eight approach directions and three
 * speeds, Sonic flies at a lone block; the trace records Sonic, the block map,
 * spawned break actors, sounds and score every update. */
#include "EQU.H"
#include "scd_boss.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

void scd_playsp3(void);
/* A 64x32-block test map; block_wrt clears blocks as SCR31A.C block_wrt does. */
static uint16_t grid[32][64];
short scramapad(sprite_status *actor,short x,short y){(void)actor;return x<0 || y<0 || x>=1024 || y>=512?0:(short)grid[y>>4][x>>4];}
static uint32_t writes;
void block_wrt(unsigned short block,unsigned short x,unsigned short y){
    writes=writes*31+(uint32_t)(block^x<<4^y<<16);
    if(x<1024 && y<512)grid[y>>4][x>>4]=block;
}
static uint32_t sounds,explosions,points;
void soundset(short request){sounds=sounds*33+(uint16_t)request;}
void scd_player_points(unsigned value){points+=value;}
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;}
void scd_objects_hurt(int source_x){(void)source_x;}
/* The boss sources link with src/boss_r3.c; no boss runs here. */
short emycol_d(sprite_status *p){(void)p;return 64;}
short emycol_u(sprite_status *p){(void)p;return 64;}
short emycol_l(sprite_status *p,unsigned char h){(void)p;(void)h;return 64;}
short emycol_r(sprite_status *p,unsigned char h){(void)p;(void)h;return 64;}
short playdieset(sprite_status *p){(void)p;return -1;}
short dircolm(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol_d(sprite_status *p,short *d0,short *d1,short *d3){(void)p;*d0=*d1=64;*d3=0;return 64;}
short dircol_u2(sprite_status *p){(void)p;return 64;}

/* Sonic's hurt timer: PC word 26 (bytes 52-53), actfree[6..7] little-endian natively. */
#ifdef SCD_BOSS_REFERENCE
#define scd_word_get_test() (((unsigned short *)&actwk[0])[26])
#else
#define scd_word_get_test() (actwk[0].actfree[6]|actwk[0].actfree[7]<<8)
#endif
static const short fcol[4][17]={
    {1,325,326},                                                              /* fcol3b: past */
    {15,316,326,411,430,131,132,137,138,119,118,128,127,126,125,124,130},       /* fcol3a: present */
    {15,316,326,357,358,131,132,137,138,119,118,128,127,126,125,124,130},       /* fcol3d: bad future */
    {15,316,326,0,0,131,132,137,138,119,118,128,127,126,125,124,130}};          /* fcol3c: good future */
static uint32_t hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->cddat,p->r_no0,p->actfree[18],p->mstno.w,scd_word_get_test()};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){
        const sprite_status *q=&actwk[i];
        const int32_t w[]={q->actno,q->r_no0,q->patno,q->xposi.w.h,q->yposi.w.h,q->actflg&127,q->mstno.w,q->patcnt,q->pattim};
        for(unsigned k=0;k<sizeof(w)/sizeof(*w);k++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)w[k]>>(8*b)&255))*16777619u;
    }
    return h;
}
int main(void){
    unsigned bounced[4][16]={{0}},runs=0,breaks=0;
    for(unsigned era=0;era<4;era++){
        time_flag=era==0?0:era==1?1:2;generate_flag=era==3;
        for(unsigned kind=0;kind<=(unsigned)fcol[era][0];kind++){
            if(!fcol[era][kind+1])continue;
            for(unsigned flip=0;flip<2;flip++)for(unsigned dir=0;dir<8;dir++)for(unsigned speed=0;speed<3;speed++){
                memset(actwk,0,sizeof(actwk));memset(grid,0,sizeof(grid));scd_boss_reset();
                /* A 2x2 group as the maps place them, at blocks (32,16)-(33,17). */
                for(unsigned y=16;y<18;y++)for(unsigned x=32;x<34;x++)grid[y][x]=(uint16_t)(fcol[era][kind+1]|(flip?0x800:0));
                static const int dx[8]={1,1,0,-1,-1,-1,0,1},dy[8]={0,1,1,1,0,-1,-1,-1};
                int v=(int)(256+speed*640);
                sprite_status *p=&actwk[0];
                p->actno=1;p->r_no0=2;p->sprvsize=14;p->sprhs=7;p->cddat=6;p->mstno.b.h=2;
                p->xposi.w.h=(short)(528-dx[dir]*80);p->yposi.w.h=(short)(272-dy[dir]*80);
                p->xspeed.w=(short)(dx[dir]*v);p->yspeed.w=(short)(dy[dir]*v);
                int16_t start_x=p->xspeed.w,start_y=p->yspeed.w;int changed=0;
                for(unsigned frame=0;frame<120;frame++){
                    p->xposi.l+=(int32_t)p->xspeed.w<<8;p->yposi.l+=(int32_t)p->yspeed.w<<8;
                    scd_boss_camera(p->xposi.w.h-160,p->yposi.w.h-112);
                    int16_t before_x=p->xspeed.w,before_y=p->yspeed.w;
                    scd_playsp3();
                    if(p->xspeed.w!=before_x || p->yspeed.w!=before_y)changed=1;
                    scd_boss_step();
                    for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==41 && actwk[i].r_no0==2 && !actwk[i].patcnt)breaks++;
                    printf("%u %u %u %u %u %u %08x %08x %08x %08x %u\n",era,kind,flip,dir,speed,frame,hash(),writes,sounds,explosions,points);
                }
                (void)start_x;(void)start_y;
                bounced[era][kind]|=changed;runs++;
            }
        }
    }
    unsigned covered=0,kinds=0;
    for(unsigned era=0;era<4;era++)for(unsigned kind=0;kind<=(unsigned)fcol[era][0];kind++)if(fcol[era][kind+1]){kinds++;covered+=bounced[era][kind];}
    printf("summary runs=%u kinds=%u bounced=%u break_frames=%u points=%u\n",runs,kinds,covered,breaks,points);
    return covered==kinds?0:1;
}
