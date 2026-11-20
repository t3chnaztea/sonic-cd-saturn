#include "cc_enemy_test_fixture.h"
#include "act.h"
void togeA_togeball(sprite_status*);void togeB_togeball(sprite_status*);void togeD_togeball(sprite_status*);
void toge_viewport(sprite_status*);int toge_frameout_s00(sprite_status*,short);
static unsigned ball_updates,allocation_cases,lifecycle_cases;
int actwkchk2(sprite_status *parent,sprite_status **out){
    for(sprite_status *o=parent+1;o<actwk+128;o++)if(!o->actno){*out=o;return 0;}return -1;
}
static int frameout_original(sprite_status *o){return toge_frameout_s00(o,o->xposi.w.h);}
static void normalize(sprite_status *o){
    if(o->actno!=SCD_OBJ_TOGEBALL)return;
    unsigned first=o->userflag.b.h<0?33:25,last=o->userflag.b.h<0?33:28;
    for(unsigned n=first;n<=last;n++){
        unsigned link=scd_word_get(o,n);if(link>=100 && link<128)scd_word_set(o,n,link-99);
    }
}
static void camera(int x,int y){scd_act_camera(x,y);scra_h_posit.w.h=x;scra_v_posit.w.h=y;}
static unsigned balls(unsigned era){return era==0?3:era==1?2:4;}
static void observed_tick(sprite_status p){tick(p);for(unsigned n=1;n<=28;n++)ball_updates+=actwk[n].actno==SCD_OBJ_TOGEBALL && actwk[n].userflag.b.h<0;}
static void chain(unsigned era,unsigned sub,unsigned flags){
    setup(era,sub,flags);camera(840,688);observed_tick(player(200,100,16));
    REQUIRE(actwk[1].r_no0==2 && scd_word_get(actwk+1,23)==(sub?65280:256));
    for(unsigned n=0;n<balls(era);n++){
        REQUIRE(actwk[n+2].actno==SCD_OBJ_TOGEBALL && actwk[n+2].r_no0==2 && actwk[n+2].colino==139);
        REQUIRE(scd_word_get(actwk+1,25+n)==n+2 && scd_word_get(actwk+n+2,33)==1);
    }
}
static void capacity(unsigned era){
    /* Ring pickup arranges native free slots after the original 24-update
       sparkle. This oracle does not execute original RING.C. */
    verify_audio=0;
    for(unsigned room=0;room<=balls(era);room++){
        setup(era,0,0);camera(840,688);scd_objects_clear_live();
        /* Ring pickup releases exactly room+1 slots after the sparkle; the
           parent then takes the first. Check each actwkchk2 boundary. */
        for(unsigned n=0;n<96;n++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,n<=room?1000:15000,n<=room?800:100,0,0)==(int)n);
        /* pcol collects one ring per update (cc_touch_arbitrate); the last
           sparkle ends 24 updates after the last pickup. pcol skips a player
           under object control (mode 16), so the pickup uses a free player. */
        actwk[0]=player(1000,800,0);
        for(unsigned tick=0;tick<=room+24;tick++){scd_objects_collision_begin();scd_objects_collision_end();scd_objects_step(1000,800);}
        REQUIRE(scd_objects_spawn(SCD_OBJ_TOGEBALL,1000,800,0,0)==0);
        for(unsigned n=0;n<28;n++)actwk[100+n]=actwk[1+n];
        observed_tick(player(200,100,16));
        REQUIRE(!!actwk[1].actno==(room==balls(era)));allocation_cases++;
        /* Earlier lost rings leave the map before the parent's dispatch.
           Original actwkchk2 searches strictly after the parent. */
        setup(era,0,0);camera(840,688);scd_objects_clear_live();memset(actwk+100,0,28*sizeof(*actwk));
        for(unsigned n=0;n<96;n++){
            unsigned type=n==room?SCD_OBJ_TOGEBALL:n<room?SCD_OBJ_LOST_RING:SCD_OBJ_RING;
            REQUIRE(scd_objects_spawn(type,n<room?16383:n==room?1000:15000,n==room?800:100,0,0)==(int)n);
            if(n<room)actwk[n+1].xspeed.w=256;
            if(n<28 && n>=room)actwk[n+100]=actwk[n+1];
        }
        observed_tick(player(1000,800,16));
        REQUIRE(!actwk[room+1].actno);allocation_cases++;
    }
    verify_audio=1;
}
int main(void){
    test_kind=SCD_OBJ_TOGEBALL;original_draw=toge_viewport;original_frameout=frameout_original;
    normalize_original=normalize;verify_audio=1;scd_player_audio_set(audio_record);
    for(unsigned era=0;era<4;era++){
        load(era);original_actor=era==0?togeA_togeball:era==1?togeB_togeball:togeD_togeball;
        for(unsigned sub=0;sub<128;sub++)for(unsigned flags=0;flags<4;flags++){
            chain(era,sub,flags);
            for(frame=0;frame<256;frame++)observed_tick(player(200,100,16));
        }
        /* Every 16-bit phase, both directions, nonzero parent fractions. */
        for(unsigned direction=0;direction<2;direction++){
            chain(era,direction,0);
            for(unsigned phase=0;phase<65536;phase++){
                scd_word_set(actwk+1,23,phase);scd_word_set(actwk+100,23,phase);
                actwk[1].xposi.w.l=actwk[100].xposi.w.l=phase;
                actwk[1].yposi.w.l=actwk[100].yposi.w.l=65535-phase;
                frame=phase;observed_tick(player(200,100,16));
            }
        }
        /* Child hitbox edges, invulnerability/control states and reduced
           player bounds all go through the original COLI3.C. */
        for(int dx=-20;dx<=20;dx++)for(int dy=-30;dy<=30;dy++)for(unsigned mode=0;mode<32;mode++){
            chain(era,0,0);sprite_status *ball=actwk+2;
            frame=0;observed_tick(player(ball->xposi.w.h+dx,ball->yposi.w.h+dy,mode));contacts++;
        }
        for(int x=-1024;x<=1024;x++)for(unsigned vertical=0;vertical<2;vertical++){
            setup(era,0,0);camera(1000+x,vertical?100:688);frame=0;
            observed_tick(player(200,100,16));lifecycle_cases++;
        }
        capacity(era);
    }
    printf("Togeball original comparison: %u assertions, %u updates, %u contacts, %u ball updates, %u allocation cases, %u lifecycle cases\n",checks,updates,contacts,ball_updates,allocation_cases,lifecycle_cases);
    return 0;
}
