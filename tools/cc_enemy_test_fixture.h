/* Independent GA3.C and COLI3.C oracle. Native slots 1..28 mirror 100..127. */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void ga(sprite_status*);short pcol(sprite_status*);
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);
static unsigned test_kind=SCD_OBJ_GA;
static void (*original_actor)(sprite_status*)=ga;
static void (*original_bomb_effect)(sprite_status*);
static unsigned test_child_kind,parent_priority=1;
static void (*original_child)(sprite_status*);
static void (*original_draw)(sprite_status*);
static short (*original_special)(sprite_status*,sprite_status*);
static int verify_audio;
static int zero_original_allocation;
static void (*normalize_original)(sprite_status*);
static int (*original_frameout)(sprite_status*);
static short audio_log[256];static unsigned audio_count;
static void audio_record(short request){if(audio_count>=256)abort();audio_log[audio_count++]=request;}
static unsigned checks,updates,contacts,subtype,frame,original_hits,fail_alloc,sparkles,defeats;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL sub %u frame %u line %d: %s\n",subtype,frame,__LINE__,#v);exit(1);}}while(0)
int actwkchk(sprite_status **out){if(fail_alloc)return -1;for(unsigned i=100;i<128;i++)if(!actwk[i].actno){*out=&actwk[i];if(!zero_original_allocation){actwk[i].actflg=132;actwk[i].sprhsize=actwk[i].sprvsize=test_child_kind?0:16;}return 0;}return -1;}
int frameout_s(sprite_status *o){return original_frameout?original_frameout(o):0;}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
void actionsub(sprite_status *o){if(original_draw)original_draw(o);else if(o->actno)o->actflg|=128;}
void scoreup(int points){scd_player_points(points*10);}
short pcolplay(sprite_status *p,sprite_status *o){
    if(plpower_m || scd_word_get(p,26))return -1;
    original_hits++;if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);
}
short pcolspecial(sprite_status *p,sprite_status *o){if(original_special)return original_special(p,o);abort();}
short pcolitem(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
static unsigned char data[300000],collision[9472];static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static void load(unsigned era){
    char path[128];snprintf(path,sizeof(path),"assets/generated/cc31%c.bin",'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/cccollision31%c.bin",'A'+era);
    REQUIRE(read_file(path,collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);
    REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),era));
}
static sprite_status player(int x,int y,unsigned mode){
    sprite_status p={0};p.actno=1;p.r_no0=2;p.xposi.w.h=x;p.yposi.w.h=y;
    p.sprvsize=19;p.sprhs=9;p.cddat=2;p.yspeed.w=300;p.xspeed.w=512;
    if(mode&1)p.mstno.b.h=2;
    if(mode&2)p.yspeed.w=-300;
    if(mode&4)p.patno=57;
    if(mode&8)scd_word_set(&p,26,120);
    if(mode&16)p.actfree[2]=64;
    return p;
}
static void setup(unsigned era,unsigned sub,unsigned flags){
    subtype=sub;scd_objects_reset(era,0);memset(actwk+100,0,28*sizeof(*actwk));
    actwk[0]=player(200,100,0);plpower_a=plpower_m=0;plpower_b=1;plring=0;emyscorecnt=0;
    time_flag=era==0?1:era==1?0:2;generate_flag=era==2;
    REQUIRE(scd_objects_spawn(test_kind,1000,800,sub,flags)==0);actwk[100]=actwk[1];
}
static void compare(sprite_status *a,sprite_status *b){
    sprite_status normalized;
    if(test_child_kind && b->actno==test_child_kind){
        normalized=*b;
        unsigned parent=scd_word_get(b,26);if(parent>=100 && parent<128)scd_word_set(&normalized,26,parent-99);
        b=&normalized;
    }
    if(normalize_original){normalized=*b;normalize_original(&normalized);b=&normalized;}
#define FIELD(f) REQUIRE(a->f==b->f)
    FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);FIELD(r_no0);FIELD(r_no1);
    FIELD(actflg);FIELD(cddat);FIELD(sprhsize);FIELD(sprhs);FIELD(sprvsize);FIELD(sprpri);
    FIELD(patno);FIELD(colino);FIELD(colicnt);FIELD(sproffset);FIELD(mstno.w);FIELD(patcnt);FIELD(pattim);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
static void tick(sprite_status before){
    scd_player_progress score=scd_player_progress_get();unsigned char shield=plpower_b;original_hits=0;
    audio_count=0;
    /* Both worlds start from the same chain count (the shared original
       emyscorecnt); only jumpcolsub/jumpcolsub0 clear it, and no landing runs here. */
    actwk[0]=before;short chain=emyscorecnt;
    if(before.r_no0<4)pcol(actwk);
    for(unsigned n=100;n<128;n++){
        if(actwk[n].actno==test_kind)original_actor(&actwk[n]);
        else if(test_child_kind && actwk[n].actno==test_child_kind)original_child(&actwk[n]);
        /* PLAYSUB.C baku_init clears colino before the next player scan.
           Explosion animation/points/flower children are outside this oracle. */
        else if(actwk[n].actno==SCD_OBJ_EXPLOSION){
            if(original_bomb_effect && actwk[n].r_no1==1)original_bomb_effect(actwk+n);
            else actwk[n].colino=0;
        }
    }
    sprite_status expected=actwk[0];unsigned char expected_shield=plpower_b;
    scd_player_progress expected_score=scd_player_progress_get();short expected_chain=emyscorecnt;
    short expected_audio[256];unsigned expected_audio_count=audio_count;
    memcpy(expected_audio,audio_log,audio_count*sizeof(*audio_log));audio_count=0;
    plpower_b=shield;scd_player_progress_set(score);actwk[0]=before;emyscorecnt=chain;
    unsigned hits=scd_objects_get().hits;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));REQUIRE(plpower_b==expected_shield);
    REQUIRE(scd_objects_get().hits-hits==original_hits);
    if(verify_audio){
        if(audio_count!=expected_audio_count){
            fprintf(stderr,"audio mismatch kind %u updates %u player %d,%d routine %u animation %u: native",test_kind,updates,before.xposi.w.h,before.yposi.w.h,before.r_no0,before.mstno.b.h);
            for(unsigned n=0;n<audio_count;n++)fprintf(stderr," %d",audio_log[n]);
            fprintf(stderr," original");for(unsigned n=0;n<expected_audio_count;n++)fprintf(stderr," %d",expected_audio[n]);fputc('\n',stderr);
        }
        REQUIRE(audio_count==expected_audio_count);REQUIRE(!memcmp(audio_log,expected_audio,audio_count*sizeof(*audio_log)));
    }
    score=scd_player_progress_get();REQUIRE(score.score==expected_score.score && score.next_life==expected_score.next_life && score.lives==expected_score.lives);REQUIRE(emyscorecnt==expected_chain);
    for(unsigned n=0;n<28;n++){
        sprite_status *a=&actwk[n+1],*b=&actwk[n+100];
        /* Collision Chaos explosions run PLAYSUB.C bakuha natively (objects.c
           tt_bakuha_type, as tt_actor_fixture.h): the SCORE.C popup takes a free
           actor and the explosion becomes a flower in place. The oracle's
           explosions stay until cleared here. */
        if(!a->actno && b->actno==SCD_OBJ_EXPLOSION){memset(b,0,sizeof(*b));continue;}
        if(a->actno==SCD_OBJ_SCORE && !b->actno)continue;
        if(a->actno==SCD_OBJ_FLOWER && b->actno==SCD_OBJ_EXPLOSION)continue;
        if(a->actno!=b->actno)fprintf(stderr,"actor mismatch: slot %u native %u original %u updates %u full %u\n",n,a->actno,b->actno,updates,fail_alloc);
        REQUIRE(a->actno==b->actno);
        if(a->actno==test_kind){compare(a,b);if(a->userflag.b.h>0)sparkles++;}
        else if(test_child_kind && a->actno==test_child_kind){compare(a,b);sparkles++;}
        else if(a->actno==SCD_OBJ_EXPLOSION){
            defeats++;
            if(original_bomb_effect && b->r_no1==1)compare(a,b);
        }
    }
    scd_object_view views[96];unsigned count=scd_objects_views(views,96);
    for(unsigned n=0;n<count;n++)if(views[n].type==test_kind)REQUIRE(scd_ppz_priority(views[n])==(test_kind==SCD_OBJ_TENTOU && (signed char)views[n].subtype>0?2:(int)parent_priority));
    updates++;
}
