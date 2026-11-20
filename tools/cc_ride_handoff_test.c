/* Two adjacent CC1 Present platforms (TRAP_R3.C for3 sub 0 at 2176,1136 and
   frdr3 sub 1 at 2224,1136), compiled original routines plus RIDECHK.C versus
   the native actors. The player walks across both tops in either slot order;
   every update compares both actors and the whole player, including which
   actor owns the rider (actfree[19]). */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void for3(sprite_status*);void frdr3(sprite_status*);
int actwkchk(sprite_status **out){for(unsigned i=102;i<128;i++)if(!actwk[i].actno){*out=&actwk[i];actwk[i].actflg=132;return 0;}return -1;}
int frameout_s(sprite_status *o){(void)o;return 0;}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
int actwkchk2(sprite_status *o,sprite_status **out){for(o++;o<actwk+128;o++)if(!o->actno){*out=o;return 0;}return -1;}
short playdamageset(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short pcolplay(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short pcolnomal(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short pcolspecial(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short pcolitem(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
void actionsub(sprite_status *o){if(o->actno)o->actflg|=128;}
void tr3_fout(sprite_status *o){(void)o;}
static unsigned checks,updates,order,start,frame,handoffs,ridden;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL order %u start %u frame %u line %d: %s\n",order,start,frame,__LINE__,#v);exit(1);}}while(0)
static unsigned char data[300000],collision[9472];
static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static void compare(sprite_status *a,sprite_status *b){
#define FIELD(f) REQUIRE(a->f==b->f)
    FIELD(actno);FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);FIELD(r_no0);FIELD(r_no1);
    FIELD(cddat);FIELD(sprhsize);FIELD(sprvsize);FIELD(patno);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
static const unsigned types[2]={SCD_OBJ_FOR3,SCD_OBJ_FRDR3};
static const int xs[2]={2176,2224},subs[2]={0,1};
static void (*const routines[2])(sprite_status*)={for3,frdr3};
static unsigned slot_type[2];
static void setup(void){
    scd_objects_reset(0,0);memset(actwk+100,0,28*sizeof(*actwk));editmode.w=0;chibi_flag=0;
    for(unsigned n=0;n<2;n++){
        unsigned k=order?1-n:n;slot_type[n]=k;
        REQUIRE(scd_objects_spawn(types[k],xs[k],1136,subs[k],0)==(int)n);
        actwk[100+n]=actwk[1+n];
    }
}
static void tick(sprite_status before){
    actwk[0]=before;if(actwk[0].actfree[19])actwk[0].actfree[19]+=99;
    if(actwk[0].colino)actwk[0].colino+=99;
    /* Viewport bit as published by the previous sprite pass. */
    for(unsigned n=0;n<2;n++){actwk[100+n].actflg=actwk[1+n].actflg;routines[slot_type[n]](&actwk[100+n]);}
    sprite_status expected=actwk[0];if(expected.actfree[19]>=100)expected.actfree[19]-=99;
    if(expected.colino>=100)expected.colino-=99;
    actwk[0]=before;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    for(unsigned n=0;n<2;n++)compare(&actwk[1+n],&actwk[100+n]);
    if(memcmp(&actwk[0],&expected,sizeof(before)))
        fprintf(stderr,"player expected xy=%d,%d cddat=%u rider=%u actual xy=%d,%d cddat=%u rider=%u\n",
                expected.xposi.w.h,expected.yposi.w.h,expected.cddat,expected.actfree[19],
                actwk[0].xposi.w.h,actwk[0].yposi.w.h,actwk[0].cddat,actwk[0].actfree[19]);
    if(memcmp(&actwk[0],&expected,sizeof(before))){
        const unsigned char *u=(const unsigned char*)&actwk[0],*v=(const unsigned char*)&expected;
        for(unsigned b=0;b<sizeof(before);b++)if(u[b]!=v[b])fprintf(stderr,"player byte %u native=%u original=%u\n",b,u[b],v[b]);
    }
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
    if(before.actfree[19] && actwk[0].actfree[19] && before.actfree[19]!=actwk[0].actfree[19])handoffs++;
    if(actwk[0].cddat&8)ridden++;
    updates++;
}
int main(void){
    size_t n=read_file("assets/generated/cc31A.bin",data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    REQUIRE(read_file("assets/generated/cccollision31A.bin",collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);
    REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),0));
    const int steps[4]={-2,-1,1,2};
    for(order=0;order<2;order++)for(start=0;start<240;start+=3)for(unsigned s=0;s<4;s++){
        setup();
        /* Let the moving floor reach phase `start` with nobody near. */
        sprite_status away={0};away.actno=1;away.r_no0=2;away.xposi.w.h=200;away.yposi.w.h=100;away.cddat=2;away.sprvsize=19;away.sprhs=9;
        for(frame=0;frame<start;frame++){actwk[1].actflg|=128;actwk[2].actflg|=128;tick(away);}
        /* Drop onto the platform the walk starts from, then walk across. */
        int x=steps[s]<0?2260:2140;
        sprite_status p={0};p.actno=1;p.r_no0=2;p.xposi.w.h=x;
        p.yposi.w.h=actwk[steps[s]<0?(order?1:2):(order?2:1)].yposi.w.h-actwk[1].sprvsize-19-4;
        p.sprvsize=19;p.sprhs=9;p.cddat=2;p.yspeed.w=256;
        for(unsigned t=0;t<150;t++,frame++){
            actwk[1].actflg|=128;actwk[2].actflg|=128;
            tick(p);
            p=actwk[0];
            if(p.cddat&8){p.yspeed.w=0;p.xspeed.w=(int16_t)(steps[s]*256);p.xposi.w.h+=steps[s];}
            else if(p.yposi.w.h>1300)break;
            else {p.yspeed.w=256;p.yposi.w.h+=1;}
        }
    }
    fprintf(stderr,"updates=%u ridden=%u handoffs=%u\n",updates,ridden,handoffs);REQUIRE(ridden>10000);
    printf("PASS: %u assertions; %u two-platform updates; %u ridden; %u rider handoffs; both slot orders\n",checks,updates,ridden,handoffs);
}
