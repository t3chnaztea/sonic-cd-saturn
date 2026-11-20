/* Compiled R4 originals versus native Tidal Tempest actors.
   Native slots 1..28 mirror original actors 100..127; the original COLI4.C
   pcol scans only that range. Real Tidal Tempest maps and collision. */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
short pcol(sprite_status*);
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);
static unsigned checks,updates,contacts,subtype,frame,original_hits,fail_alloc,children,defeats,era_now;
static const char *fixture_name="tt";
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL %s era %u sub %u frame %u updates %u line %d: %s\n",fixture_name,era_now,subtype,frame,updates,__LINE__,#v);exit(1);}}while(0)
/* Per-fixture hooks. */
static void (*original_actor)(sprite_status*);
static unsigned test_kind,test_kind2;
static void (*original_actor2)(sprite_status*);
/* Air refills: PLAYSUB4.C plairset is src/water.c water_air_refill. */
static unsigned air_original,native_generator;
void water_air_refill(void);
void plairset(void){air_original++;water_air_refill();}
static void (*normalize_original)(sprite_status*);
static int compare_explosions;
/* Original environment stubs. */
int actwkchk(sprite_status **out){if(fail_alloc)return -1;for(unsigned i=100;i<128;i++)if(!actwk[i].actno){*out=&actwk[i];return 0;}return -1;}
int actwkchk2(sprite_status *parent,sprite_status **out){if(fail_alloc)return -1;for(sprite_status *a=parent+1;a<actwk+128;a++)if(!a->actno){*out=a;return 0;}return -1;}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
/* ACTSET.C frameout_s00 without the placement reload flag. */
int frameout_s00(sprite_status *o,short x){
    if(o->actflg&128)return 0;
    int16_t d=(int16_t)((x&-128)-((scd_act_view_x()-128)&-128));
    if((uint16_t)d<=640)return 0;
    frameout(o);return -1;
}
int frameout_s(sprite_status *o){return frameout_s00(o,o->xposi.w.h);}
/* ACTION.C actionsub bounds plus the DrawObject visibility bit, using the
   same camera the native cc_object_draw reads. */
void actionsub(sprite_status *o){
    o->actflg&=127;if(!o->actno)return;
    int16_t x=o->xposi.w.h-scd_act_view_x(),y=o->yposi.w.h;int cy=scd_act_view_y();
    if(x+o->sprhsize<0 || x-o->sprhsize>=320)return;
    if((uint16_t)cy<256){if((uint16_t)y>=2048)y-=2048;}
    else if((uint16_t)cy>=1792 && (uint16_t)y<256)y+=2048;
    y-=cy;if(y+o->sprvsize<0 || y-o->sprvsize>=224)return;
    o->actflg|=128;
}
void scoreup(int points){scd_player_points(points*10);}
/* COLI4.C playdamageset without the lost-ring actor. */
short playdamageset(sprite_status *p,sprite_status *o){
    original_hits++;if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);
}
short pcolplay(sprite_status *p,sprite_status *o){
    if(plpower_m || scd_word_get(p,26))return -1;
    return playdamageset(p,o);
}
short pcolitem(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
static unsigned char data[400000],collision[9472];static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
/* era: 0 Present (A), 1 Past (B), 2 Good Future (C), 3 Bad Future (D). */
static void load(unsigned act,unsigned era){
    era_now=era;
    static PALETTEENTRY palette[256];lpcolorwk=palette;
    char path[128];snprintf(path,sizeof(path),"assets/generated/tt4%u%c.bin",act+1,'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/ttcollision4%u%c.bin",act+1,'A'+era);
    REQUIRE(read_file(path,collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(2);scd_objects_zone(2);scd_player_act(act);scd_objects_act(act);
    REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),era));
}
static sprite_status player(int x,int y,unsigned mode){
    sprite_status p={0};p.actno=1;p.r_no0=2;p.xposi.w.h=x;p.yposi.w.h=y;
    p.sprvsize=19;p.sprhs=9;p.cddat=2;p.yspeed.w=300;p.xspeed.w=512;
    if(mode&1)p.mstno.b.h=2;
    if(mode&2)p.yspeed.w=-300;
    if(mode&4)p.patno=57;
    if(mode&8)scd_word_set(&p,26,120);
    if(mode&16)p.xspeed.w=-512;
    if(mode&32){p.sprvsize=14;p.cddat|=4;}
    return p;
}
static void camera_on(int x,int y){scd_act_camera(x-160,y-112);scra_h_posit.w.h=x-160;scra_v_posit.w.h=y-112;}
static void setup(unsigned era,unsigned sub,unsigned flags,int x,int y){
    subtype=sub;{extern unsigned scd_tt_wave_slot;scd_tt_wave_slot=31;}scd_objects_reset(era,0);memset(actwk+100,0,28*sizeof(*actwk));
    actwk[0]=player(x-200,y,0);plpower_a=plpower_m=0;plpower_b=1;plring=0;emyscorecnt=0;
    time_flag=era==0?1:era==1?0:2;generate_flag=native_generator=era==2;
    camera_on(x,y);
    REQUIRE(scd_objects_spawn(test_kind,x,y,sub,flags)==0);actwk[100]=actwk[1];
    /* Retail SpawnObject leaves oYRadius 0 and AWA's init never writes it
       (R41C__.MMD $A6A0); the native AWA init clears the placement default. */
    if(test_kind==SCD_OBJ_AWA)actwk[100].sprvsize=0;
}
static void compare(sprite_status *a,sprite_status *b){
    sprite_status normalized=*b;
    if(normalize_original)normalize_original(&normalized);b=&normalized;
    if(memcmp(a->actfree,b->actfree,sizeof(a->actfree)))for(unsigned i=0;i<sizeof(a->actfree);i++)
        if(a->actfree[i]!=b->actfree[i])fprintf(stderr,"actfree[%u] native=%u original=%u\n",i,a->actfree[i],b->actfree[i]);
#define FIELD(f) do{if(a->f!=b->f)fprintf(stderr,#f " native=%d original=%d\n",(int)a->f,(int)b->f);REQUIRE(a->f==b->f);}while(0)
    FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);FIELD(r_no0);FIELD(r_no1);
    FIELD(actflg);FIELD(cddat);FIELD(sprhsize);FIELD(sprhs);FIELD(sprvsize);FIELD(sprpri);
    FIELD(patno);FIELD(colino);FIELD(colicnt);FIELD(sproffset);FIELD(mstno.w);FIELD(patcnt);FIELD(pattim);FIELD(userflag.w);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
/* One update: original pcol + actors 100..127, then native step; compare
   player, score, shield, hits, random seed and every slot. */
static void tick(sprite_status before){
    scd_player_progress score=scd_player_progress_get();unsigned char shield=plpower_b;original_hits=0;
    int seed=ranum;pl_air=5;
    projector_flag=scd_objects_projector_destroyed()?255:0;
    /* Both worlds start from the same chain count (the shared original
       emyscorecnt); only jumpcolsub/jumpcolsub0 clear it, and no landing runs here. */
    actwk[0]=before;short chain=emyscorecnt;
    if(before.r_no0<4)pcol(actwk);
    for(unsigned n=100;n<128;n++){
        if(actwk[n].actno==test_kind)original_actor(&actwk[n]);
        else if(test_kind2 && actwk[n].actno==test_kind2)original_actor2(&actwk[n]);
        else if(actwk[n].actno==24)actwk[n].actno=SCD_OBJ_EXPLOSION;
    }
    int expected_air=pl_air;pl_air=5;
    sprite_status expected=actwk[0];unsigned char expected_shield=plpower_b;int expected_seed=ranum;
    scd_player_progress expected_score=scd_player_progress_get();short expected_chain=emyscorecnt;
    plpower_b=shield;scd_player_progress_set(score);actwk[0]=before;ranum=seed;emyscorecnt=chain;
    unsigned hits=scd_objects_get().hits;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    if(memcmp(&actwk[0],&expected,sizeof(before)))fprintf(stderr,"player native xy=%d,%d r=%u xs=%d ys=%d original xy=%d,%d r=%u xs=%d ys=%d\n",actwk[0].xposi.w.h,actwk[0].yposi.w.h,actwk[0].r_no0,actwk[0].xspeed.w,actwk[0].yspeed.w,expected.xposi.w.h,expected.yposi.w.h,expected.r_no0,expected.xspeed.w,expected.yspeed.w);
    if(memcmp(&actwk[0],&expected,sizeof(before)))for(unsigned k=0;k<sizeof(before);k++)
        if(((unsigned char*)&actwk[0])[k]!=((unsigned char*)&expected)[k])fprintf(stderr,"player byte %u native=%u original=%u\n",k,((unsigned char*)&actwk[0])[k],((unsigned char*)&expected)[k]);
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));REQUIRE(plpower_b==expected_shield);
    REQUIRE(ranum==expected_seed);REQUIRE(pl_air==expected_air);
    REQUIRE(!projector_flag==!scd_objects_projector_destroyed());if(scd_objects_generator())native_generator=1;REQUIRE(!generate_flag==!native_generator);
    REQUIRE(scd_objects_get().hits-hits==original_hits);
    score=scd_player_progress_get();REQUIRE(score.score==expected_score.score);REQUIRE(emyscorecnt==expected_chain);
    for(unsigned n=0;n<28;n++){
        sprite_status *a=&actwk[n+1],*b=&actwk[n+100];
        /* The original stub's playdamageset makes no lost-ring actors. */
        if(a->actno==SCD_OBJ_LOST_RING && !b->actno)continue;
        /* Explosions run only natively; the original's stay until cleared here. */
        if(!a->actno && b->actno==SCD_OBJ_EXPLOSION){memset(b,0,sizeof(*b));continue;}
        /* The native explosion also runs PLAYSUB4.C bakuha: its SCORE.C popup
           takes a free actor, and the explosion becomes a flower in place. */
        if(a->actno==SCD_OBJ_SCORE && !b->actno)continue;
        if(a->actno==SCD_OBJ_FLOWER && b->actno==SCD_OBJ_EXPLOSION)continue;
        if(a->actno!=b->actno)fprintf(stderr,"actor mismatch: slot %u native %u original %u\n",n,a->actno,b->actno);
        REQUIRE(a->actno==b->actno);
        if(a->actno==test_kind || (test_kind2 && a->actno==test_kind2)){compare(a,b);if(n)children++;}
        else if(a->actno==SCD_OBJ_EXPLOSION)defeats++;
    }
    updates++;
}
