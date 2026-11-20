/* Real player arrival, serialized in retail field order (mapping pointer omitted). */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "EQU.H"
#include "scd_player.h"
#include "scd_objects.h"
#include "scd_actor.h"
static stage_t stages[4];
static unsigned char data[4][300000],collision[4][9472];
static void word(unsigned char *p,unsigned v){p[0]=v>>8;p[1]=v;}
static void longword(unsigned char *p,unsigned v){word(p,v>>16);word(p+2,v);}
static void actor_hex(const sprite_status *p){
    unsigned char b[64]={0};b[0]=p->actno;b[1]=p->actflg;word(b+2,p->sproffset);
    longword(b+8,p->xposi.l);longword(b+12,p->yposi.l);
    word(b+16,p->xspeed.w);word(b+18,p->yspeed.w);word(b+20,p->mspeed.w);
    b[22]=p->sprvsize;b[23]=p->sprhs;b[24]=p->sprpri;b[25]=p->sprhsize;
    b[26]=p->patno;b[27]=p->patcnt;b[28]=p->mstno.b.h;b[29]=p->mstno.b.l;
    b[30]=p->pattim;b[31]=p->pattimm;b[32]=p->colino;b[33]=p->colicnt;
    b[34]=p->cddat;b[35]=p->cdsts;b[36]=p->r_no0;b[37]=p->r_no1;
    b[38]=p->direc.b.h;b[39]=p->direc.b.l;b[40]=p->userflag.b.h;b[41]=p->userflag.b.l;
    memcpy(b+42,p->actfree,22);
    /* PC scratch words use little-endian bytes; serialize the semantic hurt
       word in the retail actor's big-endian field order. */
    word(b+48,scd_word_get(p,26));
    for(unsigned i=0;i<64;i++)printf("%02x",b[i]);
}
int main(void){
    for(unsigned era=0;era<4;era++){
        char path[100];snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",era);
        FILE *f=fopen(path,"rb");assert(f);size_t n=fread(data[era],1,sizeof(data[era]),f);assert(feof(f));fclose(f);
        assert(!stage_open(stages+era,data[era],n));
        snprintf(path,sizeof(path),"assets/generated/collision%u.bin",era);f=fopen(path,"rb");assert(f);
        assert(fread(collision[era],1,9472,f)==9472);fclose(f);
    }
    unsigned random=0x41525249;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<512;n++){
        unsigned origin=(era+1)&3;
        assert(!scd_player_init(stages+origin,collision[origin],9472,origin));scd_objects_reset(origin,0);
        scd_player_place(3000,64,0,0,2);actwk[0].actfree[2]=1;
        for(unsigned t=0;t<(n%4)*33;t++)scd_player_step(0);
        unsigned mask=(n>>6)&7;
        scd_player_inventory(23+n%177,mask&1);
        if(mask&2)scd_player_powerup(3);
        if(mask&4)scd_player_powerup(4);
        scd_player_points(50000+n);
        sprite_status *p=actwk;
        random=random*1664525u+1013904223u;p->xposi.l=3000*65536+(random&65535);
        random=random*1664525u+1013904223u;p->yposi.l=64*65536+(random&65535);
        p->xspeed.w=random;p->yspeed.w=random>>16;p->mspeed.w=1536+n;
        p->actflg=255;p->cddat=n&255;p->direc.w=random;
        p->mstno.w=random;p->patno=77;p->patcnt=15;p->pattim=9;p->pattimm=8;
        p->r_no1=4;p->userflag.w=0x4321;p->cdsts=17;p->colino=0x12;p->colicnt=23;
        for(unsigned j=0;j<22;j++){random=random*1664525u+1013904223u;p->actfree[j]=random>>24;}
        scd_player_state before=scd_player_get();scd_player_progress progress=scd_player_progress_get();
        printf("arrival %u %u %u %u %u %u %u %u ",era,n,before.rings,before.lives,before.score,before.elapsed,before.frame,mask);
        actor_hex(p);putchar(' ');
        assert(!scd_player_arrive(stages+era,collision[era],9472,era));assert(!scd_player_arrival_adjusted());
        actor_hex(actwk);scd_player_state after=scd_player_get();scd_powerup_state power=scd_player_powerups();
        assert(scd_player_progress_get().next_life==progress.next_life);
        printf(" %u %u %u %u %u %u %u %u %u %u\n",after.rings,after.lives,after.score,after.elapsed,after.frame,
            after.shield,power.invincible,power.shoes,plmaxspdwk,scd_word_get(actwk,26));
    }
    for(unsigned phase=0;phase<8;phase++)for(unsigned hidden=0;hidden<2;hidden++)for(unsigned h=0;h<130;h++){
        assert(!scd_player_init(stages,collision[0],9472,0));scd_objects_reset(0,0);
        scd_player_place(3000,64,0,0,2);actwk[0].actfree[2]=1;
        for(unsigned n=0;n<phase;n++)scd_player_step(0);
        unsigned hurt=h<128?h:h==128?511:65535,control=1|hidden*64;
        actwk[0].actfree[2]=control;scd_word_set(actwk,26,hurt);
        scd_player_step(0);scd_player_state after=scd_player_get();
        printf("display %u %u %u %u %u\n",phase,hurt,control,after.hurt,after.display_hidden);
    }
}
