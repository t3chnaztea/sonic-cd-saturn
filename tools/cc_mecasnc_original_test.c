/* Compiled R3/MECASNC.C beside the native linked scene. */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void emie3(sprite_status*);void hari3x(sprite_status*);void mecasnc3(sprite_status*);void heart3(sprite_status*);void msnc3fire(sprite_status*);
PALETTEENTRY zone3colora[16];static PALETTEENTRY colors[64];
void actionsub(sprite_status *o){(void)o;}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
void frameout_s(sprite_status *o){(void)o;}
void sub_sync(short n){(void)n;}
static int contact_mode,damage_calls;static int32_t damage_y;
short hitchk(sprite_status *o,sprite_status *p){if(!contact_mode)return 0;p->yposi.w.h=o->yposi.w.h-o->sprvsize-p->sprvsize;p->yspeed.w=0;o->cddat|=8;return 1;}
short ride_on_clr(sprite_status *o,sprite_status *p){(void)o;(void)p;return 0;}
void playdamageset(sprite_status *p,sprite_status *o){(void)o;damage_calls++;damage_y=p->yposi.l;}
int actwkchk(sprite_status **out){for(unsigned i=105;i<128;i++)if(!actwk[i].actno){*out=&actwk[i];memset(*out,0,sizeof(**out));return 0;}return -1;}
void patchg(sprite_status *o,unsigned char **table){
    unsigned char *script=table[(unsigned char)o->mstno.b.h];
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((char)--o->pattim>=0)return;o->pattim=script[0];unsigned v=script[1+o->patcnt++];if(v==255){o->patcnt=1;v=script[1];}o->patno=v&31;
}
static unsigned char data[300000],collision[9472];static stage_t stage;static unsigned checks;
static void require(int okay,unsigned frame,unsigned slot,const char *why){checks++;if(!okay){fprintf(stderr,"FAIL frame %u slot %u: %s\n",frame,slot,why);exit(1);}}
static size_t read_file(const char *name,void *out,size_t cap){FILE *f=fopen(name,"rb");require(f!=NULL,0,0,name);size_t n=fread(out,1,cap,f);fclose(f);return n;}
static unsigned original_type(const sprite_status *o){return o->actno==50?SCD_OBJ_EMIE3:o->actno==48?SCD_OBJ_HARI3X:o->actno==49?SCD_OBJ_MECASNC3:o->actno==51?SCD_OBJ_EMIE3:o->actno==52?SCD_OBJ_MECASNC3:0;}
static unsigned original_sub(const sprite_status *o){return o->actno==51?128:o->actno==52?1:(unsigned char)o->userflag.b.h;}
static void source_step(sprite_status *o){switch(o->actno){case 48:hari3x(o);break;case 49:mecasnc3(o);break;case 50:emie3(o);break;case 51:heart3(o);break;case 52:msnc3fire(o);break;}}
static void compare(unsigned frame){
    for(unsigned n=0;n<23;n++){
        sprite_status *a=&actwk[n+1],*b=&actwk[n+100];unsigned bt=original_type(b),bs=original_sub(b);
        require(a->actno==bt,frame,n,"actor allocation/type");if(!a->actno)continue;
        require((unsigned char)a->userflag.b.h==bs,frame,n,"subtype");
#define SAME(f) do{if(a->f!=b->f)fprintf(stderr,#f " native=%d original=%d (r %u/%u x %d/%d a16 %u/%u a17 %u/%u)\n",(int)a->f,(int)b->f,a->r_no0,b->r_no0,a->xposi.w.h,b->xposi.w.h,a->actfree[16],b->actfree[16],a->actfree[17],b->actfree[17]);require(a->f==b->f,frame,n,#f);}while(0)
        SAME(xposi.l);SAME(yposi.l);SAME(xspeed.w);SAME(yspeed.w);SAME(r_no0);SAME(sprhsize);SAME(sprvsize);SAME(sprpri);SAME(patno);
        for(unsigned k=6;k<=19;k++)if(k!=7 && k!=8 && k!=9 && k!=10 && k!=11 && k!=12 && k!=13 && k!=14 && k!=15){if(a->actfree[k]!=b->actfree[k])fprintf(stderr,"actfree[%u] native=%u original=%u\n",k,a->actfree[k],b->actfree[k]);require(a->actfree[k]==b->actfree[k],frame,n,"key actfree timer");}
#undef SAME
    }
}
static void contact_test(void){
    sprite_status *p=&actwk[0],*original=&actwk[100];memset(original,0,sizeof(*original));
    original->actno=48;original->xposi.w.h=400;original->yposi.w.h=400;original->userflag.b.h=1;original->actflg=128;
    p->actno=1;p->r_no0=2;p->xposi.w.h=400;p->yposi.w.h=376;p->sprvsize=16;p->yspeed.w=256;scd_word_set(p,26,0);
    contact_mode=1;damage_calls=0;hari3x(original);require(damage_calls==1,0,0,"compiled original ride hazard damages");int32_t expected_y=damage_y;
    memset(original,0,sizeof(*original));contact_mode=0;
    scd_objects_reset(0,0);p=&actwk[0];p->actno=1;p->r_no0=2;p->xposi.w.h=400;p->yposi.w.h=376;p->sprhsize=8;p->sprvsize=16;p->yspeed.w=256;scd_word_set(p,26,0);plring=1;
    require(scd_objects_spawn(SCD_OBJ_HARI3X,400,400,1,0)==0,0,0,"native ride hazard spawns");scra_h_posit.w.h=300;scra_v_posit.w.h=300;scd_objects_step(0,0);
    require(scd_objects_get().hits==1,0,0,"native ride hazard damages");if(p->yposi.l!=expected_y)fprintf(stderr,"contact y native=%d original=%d\n",(int)p->yposi.l,(int)expected_y);require(p->yposi.l==expected_y,0,0,"ride hazard rewinds the same contact position");
}
int main(void){
    size_t bytes=read_file("assets/generated/cc31A.bin",data,sizeof(data));require(!stage_open(&stage,data,bytes),0,0,"stage opens");bytes=read_file("assets/generated/cccollision31A.bin",collision,sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);require(!scd_player_init(&stage,collision,bytes,0),0,0,"player initializes");scd_objects_reset(0,0);
    lpcolorwk=colors;ta_flag=emie3end=plpower_a=plpower_m=0;contact_test();
    require(!scd_player_init(&stage,collision,bytes,0),0,0,"player reinitializes");scd_objects_reset(0,0);emie3end=0;
    unsigned types[]={SCD_OBJ_EMIE3,SCD_OBJ_HARI3X,SCD_OBJ_HARI3X,SCD_OBJ_HARI3X,SCD_OBJ_HARI3X};int xs[]={640,1048,1080,1106,1176},ys[]={1004,1008,1008,800,1008};unsigned subs[]={0,2,3,1,0},ids[]={50,48,48,48,48};
    for(unsigned n=0;n<5;n++){require(scd_objects_spawn(types[n],xs[n],ys[n],subs[n],0)==(int)n,0,n,"native spawn order");sprite_status *o=&actwk[100+n];memset(o,0,sizeof(*o));o->actno=ids[n];o->xposi.w.h=xs[n];o->yposi.w.h=ys[n];o->userflag.b.h=subs[n];}
    unsigned updates=0;
    for(unsigned frame=1;frame<=700;frame++){
        actwk[0].xposi.w.h=frame<180?1100:900;actwk[0].yposi.w.h=900;actwk[0].sprhsize=8;actwk[0].sprvsize=16;actwk[0].actno=1;actwk[0].r_no0=2;scra_h_posit.w.h=900;scra_v_posit.w.h=896;
        for(unsigned n=100;n<128;n++)if(actwk[n].actno)source_step(&actwk[n]);
        scd_objects_step(0,0);compare(frame);updates++;
        if(emie3end && !actwk[100].actno && !actwk[105].actno)break;
    }
    require(emie3end,updates,0,"original scene reached its end");
    printf("PASS: %u assertions; %u compiled-original/native MECASNC updates\n",checks,updates);
}
