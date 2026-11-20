/* Independently compiled R3/BOBIN.C compared with production object updates.
   This checks actor state, impulse, animation, draw view and score, not a route. */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void bobin(sprite_status *);
void frip(sprite_status *);
unsigned char frip_spd(int *,unsigned char *);
static unsigned original_score,original_sounds,native_sounds,checks;
void actionsub(sprite_status *o){(void)o;}
int frameout_s00(sprite_status *o,short x){(void)o;(void)x;return 0;}
int frameout_s(sprite_status *o){(void)o;return 0;}
void tensuu0(sprite_status *o,unsigned char n){(void)o;(void)n;}
void scoreup(unsigned n){original_score+=n*10;}
void sub_sync(short n){if(n!=127)abort();original_sounds++;}
static void audio_sink(short n){if(n==127)native_sounds++;else if(n!=180 && n!=171)abort();}
#define REQUIRE(v) do {checks++;if(!(v)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#v);exit(1);}}while(0)

static void compare(sprite_status *a,sprite_status *b){
#define FIELD(f) REQUIRE(a->f==b->f)
    FIELD(xposi.l);FIELD(yposi.l);FIELD(r_no0);FIELD(actflg);FIELD(cddat);
    FIELD(sprhs);FIELD(sprhsize);FIELD(sprvsize);FIELD(sprpri);FIELD(sproffset);
    FIELD(colino);FIELD(colicnt);FIELD(mstno.w);FIELD(patno);FIELD(patcnt);FIELD(pattim);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
static void run(unsigned subtype,unsigned flags,unsigned era,int contact){
    scd_objects_zone(1);scd_objects_act(0);scd_objects_reset(era,0);
    memset(actwk,0,sizeof(*actwk));
    scd_player_progress_set((scd_player_progress){0,50000,3});
    REQUIRE(scd_objects_spawn(SCD_OBJ_BOBIN,1000,800,subtype,flags)==0);
    sprite_status original=actwk[1];original_score=original_sounds=native_sounds=0;
    for(unsigned frame=0;frame<600;frame++){
        /* Explicit contact fixture exercises all directions, including coincident
           centers; no contact is inferred from a debug jump or a route. */
        int hit=contact && frame && frame%37==0;
        sprite_status before={0};before.actno=1;before.r_no0=2;before.sprvsize=19;
        before.xposi.w.h=hit?actwk[1].xposi.w.h+(int)(frame%41)-20:200;
        before.yposi.w.h=hit?actwk[1].yposi.w.h+(int)(frame%43)-21:100;
        before.cddat=hit?0x36:2;before.actfree[18]=1;
        /* Force colicnt exactly as pcolspecial does. Native's overlap frontend
           may also increment it; bobin only tests nonzero, then clears it. */
        actwk[1].colicnt=original.colicnt=hit;
        actwk[0]=before;bobin(&original);sprite_status expected_player=actwk[0];
        actwk[0]=before;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
        compare(&actwk[1],&original);
        REQUIRE(!memcmp(&actwk[0],&expected_player,sizeof(before)));
        REQUIRE(scd_player_progress_get().score==original_score);
        REQUIRE(native_sounds==original_sounds);
        scd_object_view v;REQUIRE(scd_objects_views(&v,1)==1);
        REQUIRE(v.type==SCD_OBJ_BOBIN && v.frame==original.patno && v.flags==(original.actflg&3));
        REQUIRE(scd_ppz_priority(v)==original.sprpri);
    }
    REQUIRE(original_score==(contact?500:0));
}
static void bounds(void){
    for(int dx=-18;dx<=18;dx++)for(int dy=-27;dy<=27;dy++){
        scd_objects_reset(0,0);memset(actwk,0,sizeof(*actwk));
        actwk[0].xposi.w.h=100;actwk[0].yposi.w.h=100;actwk[0].r_no0=2;actwk[0].sprvsize=19;
        REQUIRE(scd_objects_spawn(SCD_OBJ_BOBIN,1000,800,0,0)==0);
        scd_objects_step(100,100); /* colino becomes live after initialization. */
        actwk[0].xposi.w.h=1000+dx;actwk[0].yposi.w.h=800+dy;
        /* The touch is in pcol (cc_touch_arbitrate via collision_begin), as in
           the game frame, before the object's own update. */
        native_sounds=0;scd_objects_collision_begin();scd_objects_collision_end();
        scd_objects_step(1000+dx,800+dy);
        REQUIRE(native_sounds==(unsigned)(abs(dx)<=16 && abs(dy)<=24));
    }
}
static unsigned flipper_cases;
static void flippers(void){
    /* Every table position, both directions of approach, both orientations,
       and each player radius/state; compare actual original ride helpers. */
    for(unsigned flip=0;flip<2;flip++)for(int dx=-33;dx<=33;dx++)
    for(int dy=-41;dy<=41;dy++)for(unsigned state=0;state<4;state++){
        scd_objects_reset(0,0);memset(actwk,0,sizeof(*actwk));
        REQUIRE(scd_objects_spawn(SCD_OBJ_FRIP,1000,800,0,flip)==0);
        actwk[100]=actwk[1];
        sprite_status before={0};before.actno=1;before.r_no0=state==3?4:2;
        before.xposi.w.h=1000+dx;before.yposi.w.h=800+dy;
        before.sprvsize=state==2?14:19;before.cddat=state==2?6:2;
        before.yspeed.w=state==1?-300:300;before.xspeed.w=512;
        before.actfree[18]=1;
        actwk[0]=before;frip(&actwk[100]);sprite_status expected=actwk[0];
        if(expected.actfree[19]==100)expected.actfree[19]=1;
        actwk[0]=before;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
        compare(&actwk[1],&actwk[100]);REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
        if(actwk[0].cddat&8){
            int jump=0;unsigned char direction=0;
            REQUIRE(frip_spd(&jump,&direction)==0);
            int distance=dx+32;if(!flip)distance=64-distance;
            REQUIRE(jump==-(distance*2560/64)-2560);
            REQUIRE(actwk[1].mstno.b.h==1);
            /* Trigger both animations and compare all 20 return-to-idle ticks.
               Move Sonic away so this tests release as well as pose timing. */
            actwk[100].mstno.b.h=1;
            for(unsigned f=0;f<20;f++){
                before=actwk[0];before.xposi.w.h=200;
                actwk[0]=before;if(actwk[0].actfree[19]==1)actwk[0].actfree[19]=100;
                frip(&actwk[100]);expected=actwk[0];
                if(expected.actfree[19]==100)expected.actfree[19]=1;
                actwk[0]=before;scd_objects_step(200,before.yposi.w.h);
                compare(&actwk[1],&actwk[100]);REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
            }
        }
        flipper_cases++;
    }
}
int main(void){
    scd_player_audio_set(audio_sink);
    unsigned subtypes[]={0,3,8,67,131,195};
    for(unsigned era=0;era<4;era++)for(unsigned s=0;s<sizeof(subtypes)/sizeof(*subtypes);s++)
        for(unsigned flip=0;flip<4;flip++)for(int hit=0;hit<2;hit++)run(subtypes[s],flip,era,hit);
    bounds();flippers();printf("PASS: %u assertions; 115200 bumper updates, 2035 hitbox cases, %u flipper contact cases\n",checks,flipper_cases);
    return 0;
}
