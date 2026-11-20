/* Integration boundaries, separate from the isolated dispatcher tests. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "EQU.H"
#include "scd_player.h"
#include "scd_objects.h"
#include "scd_actor.h"
#include "act.h"
#include "sonic_animation.h"
extern unsigned scd_animation_audit_calls;
static unsigned collision_checks;
static int check_collision;
/* The actual actor has already been animated when normal touch collision
   executes. Select a different animation to prove it is NOT rendered early. */
short pcol(sprite_status *p){
    if(check_collision==2){p->actfree[2]|=64;scd_word_set(p,26,120);return 0;}
    if(check_collision){
        assert(scd_animation_audit_calls && p->patno==45 && p->patcnt==1);
        p->mstno.b.h=26;collision_checks++;
    }
    return 0;
}
static stage_t stage;
static unsigned char data[300000],collision[9472];
static void reset(void){
    assert(!scd_player_init(&stage,collision,sizeof(collision),0));
    scd_objects_reset(0,0);scd_player_place(500,100,0,0,2);
    assert(!scd_player_get().mapping && !scd_player_get().animation_cursor);
}
static scd_sonic_animation pose(void){
    scd_player_state p=scd_player_get();
    return (scd_sonic_animation){p.animation,p.animation_previous,p.animation_cursor,
        p.animation_timer,p.mapping,p.render_flags};
}
int main(void){
    FILE *f=fopen("assets/generated/ppz0.bin","rb");assert(f);
    size_t n=fread(data,1,sizeof(data),f);assert(feof(f));fclose(f);assert(!stage_open(&stage,data,n));
    f=fopen("assets/generated/collision0.bin","rb");assert(f);
    assert(fread(collision,1,sizeof(collision),f)==sizeof(collision));fclose(f);
    /* Real normal/hurt/death/control branches each animate exactly once. The
       gone branch and result freeze do not advance the animation. */
    for(unsigned route=0;route<4;route++){
        reset();sprite_status *p=&actwk[0];
        p->r_no0=route==1?4:route==2?6:2;
        p->mstno.b.h=route==1?26:route==2?24:2;
        if(route==0)p->cddat|=4; /* Actual rolling jump; unrolled descent selects animation 0. */
        if(route==3)p->actfree[2]=1;
        unsigned before=scd_animation_audit_calls;
        scd_player_step(0);assert(scd_animation_audit_calls==before+1);
        assert(scd_player_get().mapping==(route==1?93:route==2?106:45));
        /* Merely getting state (or rendering a paused frame) cannot tick it. */
        scd_sonic_animation a=pose();for(unsigned i=0;i<100;i++){scd_sonic_animation b=pose();assert(!memcmp(&a,&b,sizeof(a)));}
    }
    reset();actwk[0].r_no0=8;actwk[0].mstno.b.h=24;
    unsigned before=scd_animation_audit_calls;
    for(unsigned i=0;i<10;i++)scd_player_step(0);
    assert(scd_animation_audit_calls==before && scd_player_get().mapping==0);
    /* A death update that crosses into Gone still animates on that update. */
    reset();actwk[0].r_no0=6;actwk[0].mstno.b.h=24;actwk[0].yposi.w.h=2100;
    before=scd_animation_audit_calls;scd_player_step(0);
    assert(scd_player_get().routine==8 && scd_animation_audit_calls==before+1);
    scd_player_step(0);assert(scd_animation_audit_calls==before+1);
    reset();actwk[0].cddat|=4;actwk[0].mstno.b.h=2;check_collision=1;
    scd_player_step(0);check_collision=0;
    assert(collision_checks==1 && scd_player_get().animation==26 && scd_player_get().mapping==45);
    /* Keep movement out of the way while observing the next animation call. */
    actwk[0].actfree[2]=1;scd_player_step(0);assert(scd_player_get().mapping==93);
    /* FD script transitions write the actor's animation, not a shadow copy. */
    reset();actwk[0].actfree[2]=1;actwk[0].mstno.b.h=21;
    for(unsigned i=0;i<49;i++)scd_player_step(0);
    assert(scd_player_get().animation==0 && scd_player_get().animation_previous==21);
    scd_player_step(0);assert(scd_player_get().animation_previous==0);
    /* The disc writes the NEXT frozen cursor after Sonic's animation call.
       Pin the original script's mapping IDs independently of native tables. */
    static const unsigned poses[]={26,27,28,31,29,30};
    for(unsigned facing=0;facing<2;facing++){
        reset();scd_player_place(516,373,0,0,2|facing);
        assert(scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0)==0);swdata.w=0;
        before=scd_animation_audit_calls;scd_objects_step(516,373);
        assert(scd_animation_audit_calls==before && scd_player_get().animation==45);
        unsigned mismatched=0;
        for(unsigned tick=0;tick<100;tick++){
            if(!scd_player_get().control)break;
            unsigned old_cursor=scd_player_get().animation_cursor;
            scd_player_step(0);scd_player_state p=scd_player_get();
            assert(p.mapping==poses[old_cursor]);
            mismatched+=p.mapping!=poses[p.animation_cursor];
        }
        assert(mismatched>=12);
        assert(!scd_player_get().control);
        scd_player_step(0);assert(scd_player_get().animation==0);
    }
    /* Level End/Main.asm keeps Right held through results. Sonic continues
       to animate at the level bound while the panel tallies. */
    reset();scd_player_place(500,100,0,0,2);actwk[0].actfree[2]=1;
    assert(scd_act_sign(499,100,0));
    for(unsigned i=0;i<196;i++)scd_player_step(0);
    assert(scd_act_get().phase>=SCD_ACT_SLIDE);
    before=scd_animation_audit_calls;scd_sonic_animation saved=pose();
    for(unsigned i=0;i<300;i++)scd_player_step(0);
    scd_sonic_animation after=pose();assert(scd_animation_audit_calls==before+300 && memcmp(&saved,&after,sizeof(saved)));
    /* Original level loading clears object RAM; Save/LoadTimeWarpData do not
       restore the old animation. Verified separately against retail CPU code. */
    reset();actwk[0].actfree[2]=1;actwk[0].mstno.b.h=5;
    for(unsigned i=0;i<200;i++)scd_player_step(0);
    saved=pose();assert(!scd_player_arrive(&stage,collision,sizeof(collision),0));after=pose();
    const scd_sonic_animation fresh={0,0,0,0,0,4};
    assert(!memcmp(&fresh,&after,sizeof(fresh)) && !scd_player_get().control);
    /* Display submission precedes touch collision: a late control/hurt change
       must not hide an already-submitted player until the following update. */
    reset();check_collision=2;scd_player_step(0);check_collision=0;
    assert(!scd_player_get().display_hidden && scd_player_get().control==64 && scd_player_get().hurt==120);
    scd_player_step(0);assert(scd_player_get().display_hidden && scd_player_get().hurt==119);
    scd_player_place(500,100,0,0,2);assert(scd_player_get().mapping==0 && scd_player_get().animation_cursor==0 && scd_player_get().animation_timer==0);
    printf("Player animation ordering: PASS (%u observed calls; normal/hurt/death/control, delayed object poses, disc, FD transitions, results freeze, reset and travel)\n",scd_animation_audit_calls);
}
