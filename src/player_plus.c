/* CD++-style preset moves (docs/CDPP-PRESET-SPEC.md). Native reimplementations
   from public references; no Sonic CD++ code or data. Classic (flags 0) never
   reaches any of this: every hook below returns 0 before touching state.
   Values marked "design" have no source: the spec's table records them as
   design choices, not CD++ parity. */
#include "player_plus.h"
#include "EQU.H"
#include "ETC.H"
#include "scd_player.h"
#include "scd_objects.h"
#include <stddef.h>

#ifndef SCD_PLUS_HOST_FLAGS
#define SCD_PLUS_HOST_FLAGS 0
#endif
/* Host route tools build with -DSCD_PLUS_HOST_FLAGS=<flags>; the Saturn build
   starts at 0 and src/save_saturn.c sets it from SCDSATURNCF. */
uint8_t scd_preset_flags=SCD_PLUS_HOST_FLAGS;
/* src/main.c's save mailbox; slot 11 is the preset. Host builds without
   src/main.c get this weak copy. */
__attribute__((weak)) volatile uint32_t scd_save_mailbox[12];
extern void soundset(short);

/* The jump buttons as PLAYER.C reads them (jumpchk swdata.b.l & 112). */
#define JUMP_PRESS 112
/* F1/F5: Sonic 2 Sonic_UpdateSpindash (SPG Special Abilities). */
#define REV_STEP 512        /* +2 px/f of spinrev per press */
#define REV_MAX 2048        /* spinrev cap 8 */
#define DASH_BASE 2048      /* release 8 px/f + floor(spinrev)/2 */
#define DASH_STEP 128
/* F4 homing attack: all design (no CD++ capture, spec section 4 F4). */
#define HOMING_RANGE_X 160  /* px ahead of Sonic */
#define HOMING_RANGE_UP 64  /* px above Sonic */
#define HOMING_RANGE_DOWN 128
#define HOMING_SPEED 2048   /* 8 px/f along the aim */
#define HOMING_FRAMES 40    /* re-aim this many updates at most */
#define AIR_DASH_SPEED 2048 /* no target: forward air dash */

static uint8_t active,charging,roll_used,homing_used,homing_left,homing_defeated,target_actno;
/* The speed the player's own air update left while homing (scd_plus_air_end). */
static short homing_vx,homing_vy;static uint8_t homing_tracked;
static uint16_t rev;
static sprite_status *target;

unsigned scd_plus_active(void){return active;}
void scd_plus_publish(void){scd_save_mailbox[11]=active|(unsigned)scd_preset_flags<<8;}
static uint8_t classic_hold;
void scd_plus_classic_hold(int on){classic_hold=on?1:0;}
void scd_plus_act_start(void){active=classic_hold?0:scd_preset_flags&SCD_PLUS_ALL;scd_plus_publish();}
void scd_plus_place(void){charging=roll_used=homing_used=homing_left=homing_tracked=homing_defeated=0;rev=0;target=NULL;}
static unsigned dash_flag(void){return chibi_flag?SCD_PLUS_MINIDASH:SCD_PLUS_SPINDASH2;}
/* src/player.c charge_buffer repeats a Down+jump press for the CD dash; a
   repeated press would add a second rev, so F1/F5 turn it off. */
int scd_plus_charge_buffer_off(void){return (active&dash_flag())!=0;}
/* PLAYER.C ballset's sizes, without its minimum ground speed. */
static void ball_on(sprite_status *p){
    if(!(p->cddat&4)){
        p->cddat|=4;
        if(chibi_flag){p->sprvsize=8;p->sprhs=5;p->yposi.w.h+=2;}
        else{p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;}
    }
    p->mstno.b.h=2;
}
/* Ground update before PLAYER.C jumpchk. Returns 1 when the spin dash used the
   update: src/player.c then skips jumpchk, keispd and levermove/balllmove and
   runs only the bound, move and floor checks (Sonic 2 Sonic_UpdateSpindash
   runs Sonic_LevelBound and AnglePos only). */
int scd_plus_ground(void){
    if(!active)return 0;
    roll_used=homing_used=homing_left=homing_tracked=homing_defeated=0;target=NULL;
    sprite_status *p=&actwk[0];
    if(!(active&dash_flag())){charging=0;return 0;}
    if(charging){
        /* An object, a slope or a hit took the charge pose away. */
        if((p->cddat&6)!=4 || p->mspeed.w || p->actfree[0]){charging=0;rev=0;return 0;}
        if(!(swdata.b.h&SCD_DOWN)){
            int speed=DASH_BASE+(rev>>8)*DASH_STEP;
            p->mspeed.w=(short)((p->cddat&1)?-speed:speed);
            charging=0;rev=0;soundset(145);
            return 1;
        }
        rev-=rev>>5;
        if(swdata.b.l&JUMP_PRESS){rev+=REV_STEP;if(rev>REV_MAX)rev=REV_MAX;soundset(156);}
        p->xspeed.w=p->yspeed.w=0;p->mstno.b.h=2;
        return 1;
    }
    /* Start: crouching still on flat ground (the CD dash's own conditions in
       PLAYER.C levermove), Down held without Left, Right or Up, jump pressed. */
    if((p->cddat&6) || p->mspeed.w || p->actfree[0] || mizuflag ||
       (((unsigned char)p->direc.b.h+32)&192) || !(swdata.b.l&JUMP_PRESS) ||
       (swdata.b.h&(SCD_UP|SCD_DOWN|SCD_LEFT|SCD_RIGHT))!=SCD_DOWN)return 0;
    charging=1;rev=0;ball_on(p);p->xspeed.w=p->yspeed.w=0;soundset(156);
    return 1;
}
/* Native objects (src/objects.c) keep pool slot i in actwk[i+1] with the
   object type as actno; a destroyed badnik becomes an explosion in place.
   src/objects.c's enemy() predicate (scd_objects_enemy_type) picks badniks. */
static int target_valid(const sprite_status *q){
    return q->actno && (q->actflg&128) && scd_objects_enemy_type(q->actno);
}
static sprite_status *find_target(const sprite_status *p){
    int dir=(p->cddat&1)?-1:1;long best=0;sprite_status *found=NULL;
    for(unsigned i=1;i<=96;i++){
        sprite_status *q=&actwk[i];
        if(!target_valid(q))continue;
        int dx=(q->xposi.w.h-p->xposi.w.h)*dir,dy=q->yposi.w.h-p->yposi.w.h;
        if(dx<=0 || dx>HOMING_RANGE_X || dy<-HOMING_RANGE_UP || dy>HOMING_RANGE_DOWN)continue;
        long d=(long)dx*dx+(long)dy*dy;
        if(!found || d<best){found=q;best=d;}
    }
    return found;
}
static void homing_aim(sprite_status *p){
    short s,c;
    sinset((unsigned char)atan_sonic(target->xposi.w.h-p->xposi.w.h,target->yposi.w.h-p->yposi.w.h),&s,&c);
    p->xspeed.w=(short)((long)c*HOMING_SPEED>>8);p->yspeed.w=(short)((long)s*HOMING_SPEED>>8);
    if(p->xspeed.w<0)p->cddat|=1;else if(p->xspeed.w>0)p->cddat&=~1;
}
/* Air update before PLAYER.C jumpchk2. */
void scd_plus_air(void){
    if(!active)return;
    sprite_status *p=&actwk[0];
    if(homing_left){
        /* Homing yields to object control (design; the spec cites no CD++ frame
           data): an object that took Sonic over or set his speed after the player's
           update (a bumper, launcher or spring, src/objects.c runs after him) ends
           the attack before it re-aims, so that speed stands. The attack stays used. */
        if((p->actfree[2]&(1|4|8)) || (homing_tracked && (p->xspeed.w!=homing_vx || p->yspeed.w!=homing_vy))){
            homing_left=0;homing_tracked=homing_defeated=0;target=NULL;
        }
    }
    if(homing_left){
        if(!(p->cddat&4) || homing_defeated || target->actno!=target_actno || !target_valid(target)){
            /* A destroyed target allows another homing attack (design). */
            if(homing_defeated)homing_used=0;
            homing_left=homing_tracked=homing_defeated=0;target=NULL;
        }else{homing_left--;homing_aim(p);}
    }
    if(!(swdata.b.l&JUMP_PRESS) || watercoliflag || p->actfree[0] || (p->actfree[2]&(1|4|8)))return;
    if(!(p->cddat&4)){
        /* F3: once per airtime, from the falling, running or spring pose only. */
        unsigned pose=p->mstno.b.h;
        if((active&SCD_PLUS_AIRROLL) && !roll_used && (pose==0 || pose==1 || pose==16)){roll_used=1;ball_on(p);}
        return;
    }
    if(!(active&SCD_PLUS_HOMING) || homing_used || homing_left)return;
    homing_used=1;
    homing_defeated=0;
    /* PLAYER.C jumpchk2 would cut a rising homing attack at -4 px/f. */
    p->actfree[18]=0;
    target=find_target(p);
    if(target){target_actno=target->actno;homing_left=HOMING_FRAMES;homing_aim(p);}
    else p->xspeed.w=(short)((p->cddat&1)?-AIR_DASH_SPEED:AIR_DASH_SPEED);
    soundset(145);
}
void scd_plus_air_end(void){
    if(homing_left){homing_vx=actwk[0].xspeed.w;homing_vy=actwk[0].yspeed.w;homing_tracked=1;}
    else homing_tracked=0;
}
void scd_plus_enemy_defeat(unsigned victim_slot, short before_vx, short before_vy){
    if(!(active&SCD_PLUS_HOMING) || !homing_left || !homing_tracked || homing_defeated ||
       victim_slot==0 || victim_slot>96 || target!=&actwk[victim_slot])return;
    sprite_status *p=&actwk[0];
    if((p->cddat&6)!=6 || (p->actfree[2]&(1|4|8)) ||
       before_vx!=homing_vx || before_vy!=homing_vy)return;
    /* Only the tracked victim's own bounce updates the expected speed. A
       later object impulse still cancels homing on the next air update. */
    homing_vx=p->xspeed.w;homing_vy=p->yspeed.w;homing_defeated=1;
}
/* F2: PLAYER.C jumpmove with the Sonic 3 air control rule: holding a direction
   accelerates up to plmaxspdwk but never pulls a faster Sonic back to it. */
int scd_plus_jumpmove(void){
    if(!(active&SCD_PLUS_AIRCAP_OFF))return 0;
    sprite_status *p=&actwk[0];
    short cal_speed=p->xspeed.w;
    if(time_flag==1 && stageno.w==0){
        if(p->xposi.w.h>=1736 && p->xposi.w.h<2112)return 1;
        if(p->actfree[2]&2)goto set;
    }
    if(swdata.b.h&SCD_LEFT){
        short previous=cal_speed;
        p->cddat|=1;cal_speed=(short)(cal_speed-pladdspdwk*2);
        if(cal_speed<=-plmaxspdwk)cal_speed=previous<=-plmaxspdwk?previous:(short)-plmaxspdwk;
    }
    if(swdata.b.h&SCD_RIGHT){
        short previous=cal_speed;
        p->cddat&=254;cal_speed=(short)(cal_speed+pladdspdwk*2);
        if(cal_speed>=plmaxspdwk)cal_speed=previous>=plmaxspdwk?previous:plmaxspdwk;
    }
set:
    p->xspeed.w=cal_speed;
    if(scra_vline<96)scra_vline+=2;
    else if(scra_vline>96)scra_vline-=2;
    if((unsigned short)p->yspeed.w<64512)return 1;
    cal_speed=p->xspeed.w;
    if((cal_speed>>5)==0)return 1;
    if(cal_speed>0){cal_speed=(short)(cal_speed-(cal_speed>>5));if(cal_speed<0)cal_speed=0;}
    else{cal_speed=(short)(cal_speed-(cal_speed>>5));if(cal_speed>=0)cal_speed=0;}
    p->xspeed.w=cal_speed;
    return 1;
}
