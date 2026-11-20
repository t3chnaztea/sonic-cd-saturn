/* Player and object frontend for the selected reconstructed player routines. */
#include "time_attack.h"
#include "EQU.H"
#include "PLAYER.H"
#include "ACTION.H"
#include "ETC.H"
#include "FCOL.H"
#include "scd_player.h"
#include "scd_objects.h"
#include "scd_actor.h"
#include "act.h"
#include "world.h"
#include "sonic_animation.h"
#include "scroll_limits.h"
#include "water.h"
#include "player_plus.h"
/* The standalone player trace has no world clock; the game links the real
   time-warp cancellation used when Sonic grabs a WW hanging bar. */
__attribute__((weak)) void scd_world_abort(void){}
/* Tidal Tempest water lives in src/water.c. Host fixtures that link the player
   without it get these inert defaults (water is zone 2 only). */
__attribute__((weak)) void water_reset(unsigned zone,unsigned act,unsigned era){(void)zone;(void)act;(void)era;}
__attribute__((weak)) void water_tick(void){}
__attribute__((weak)) void water_player_check(void){}
__attribute__((weak)) void water_objects_step(void){}
__attribute__((weak)) void water_air_refill(void){}
/* CD++ preset moves live in src/player_plus.c. A build without it links these
   no-ops and is Classic by construction (tools/test-player.sh). */
__attribute__((weak)) void scd_plus_act_start(void){}
__attribute__((weak)) void scd_plus_classic_hold(int on){(void)on;}
__attribute__((weak)) void scd_plus_place(void){}
__attribute__((weak)) int scd_plus_charge_buffer_off(void){return 0;}
__attribute__((weak)) int scd_plus_ground(void){return 0;}
__attribute__((weak)) void scd_plus_air(void){}
__attribute__((weak)) void scd_plus_air_end(void){}
__attribute__((weak)) void scd_plus_enemy_defeat(unsigned slot, short vx, short vy){(void)slot;(void)vx;(void)vy;}
__attribute__((weak)) int scd_plus_jumpmove(void){return 0;}
#include <assert.h>
#include <string.h>

unsigned char mapwka[8][64];
unsigned char scdtblwk[257][16],scdtblwk2[257][16],scddirtbl[256];
static unsigned char collision_index[1024];
static const stage_t *level;
static unsigned current_era,current_act,previous_buttons;
void scd_player_act(unsigned act){current_act=act;}
/* Zone 0 is Palmtree Panic. Zone 1 is Wacky Workbench, whose retail round index
   is 4: GAME.C's da_tbl[7][4] is indexed by stageno.b.h over the seven playable
   rounds R1,R3,R4,R5,R6,R7,R8. At 4 the compiled loopchk returns immediately,
   matching PLAYER6.C's empty body, so the PPZ loop-chunk hack stays dormant. */
static unsigned current_zone;
/* The retail round index that GAME.C's da_tbl is subscripted by: 0 Palmtree Panic,
   1 Collision Chaos, 2 Tidal Tempest, 3 Quartz Quadrant, 4 Wacky Workbench,
   5 Stardust Speedway, 6 Metallic Madness.  It goes straight into stageno.b.h. */
void scd_player_zone(unsigned zone){current_zone=zone<7?zone:0;}
/* Tidal Tempest Act 2 (SCR42*.C scrv_up_ch/scrv_down_ch) wraps the 2048-line map:
   the camera rewrites Sonic's Y (src/camera_v.c) and FCOL.C scramapad reads map
   rows as (y>>8)&7, so Sonic lives past 2048 until the camera wraps him. */
/* Tidal Tempest Acts 2 and 3 wrap vertically at 2048: SCR42*.C and SCR43C/D.C
   scrv_down_ch mask actwk[0].yposi with 2047 (scralim_down 2048; BOSS_4.C
   egg4_air_tbl1 routes egg4air through the wrap, 2176 -> 128). */
static int map_y_wraps(void){return current_zone==2 && (current_act==1 || current_act==2);}
extern void soundset(short);
extern unsigned scd_r6_palette_count(unsigned script) __attribute__((weak));
extern unsigned scd_r6_sparks_active(void) __attribute__((weak));
static uint32_t player_frame,reset_count,elapsed;
static scd_checkpoint checkpoint;
static unsigned game_over,clock_stopped,clock_held;
/* Time Attack run state (src/time_attack.h). Defined here so host builds of the
   player and objects link without the front end. */
scd_ta_resident scd_ta;
static uint8_t display_hidden;
static uint32_t next_life;
scd_player_progress scd_player_progress_get(void){return (scd_player_progress){(uint32_t)plscore,next_life,pl_suu};}
void scd_player_progress_set(scd_player_progress progress){plscore=progress.score;next_life=progress.next_life;pl_suu=progress.lives;}
static uint16_t invinc_ticks,shoes_ticks,shield_age;
static scd_player_effect_sample effect_sample;
scd_player_effect_sample scd_player_effects(void){return effect_sample;}
static void effect_record(void){
    effect_sample.record_x=actwk[0].xposi.w.h;effect_sample.record_y=actwk[0].yposi.w.h;
    effect_sample.record=1;
}
static void effect_context(void){
    effect_sample.x=actwk[0].xposi.w.h;effect_sample.y=actwk[0].yposi.w.h;
    effect_sample.flags=actwk[0].cddat;effect_sample.shield=plpower_b;
    effect_sample.invincible=!!plpower_m;effect_sample.resets=reset_count;effect_sample.valid=1;
}
static void powerups_step(void);
/* Sonic/Main.asm ObjSonic_TimeWarp (PLAYER.C backto_chk): the first update with
   timeWarpTimer >= 210 runs SaveTimeWarpData (playsave) once and sets
   scrollLock (scroll_start); Sonic, the objects and the timer keep running,
   unseen, until 230 starts the warp. The arrival restores the saved data
   (Level/Main LoadTimeWarpData), not where Sonic got to. */
static struct{int valid;sprite_status actor;unsigned rings,ring_lives;uint32_t elapsed;} warp_save;
static void player_display(void){
    sprite_status *p=actwk;unsigned hurt=scd_word_get(p,26);
    /* ObjSonic_Display: from timeWarpTimer 210 Sonic is not drawn and the hurt
       timer stops (PLAYER.C playpowercnt, backto_cnt < 157). */
    if(warp_save.valid){display_hidden=1;powerups_step();return;}
    /* ObjSonic_Display tests bit 2 of the incoming hurt timer, not the global
       simulation frame. Capture before later actors can change hurt/control. */
    display_hidden=!!(p->actfree[2]&64);
    if(hurt){scd_word_set(p,26,hurt-1);if(!(hurt&4))display_hidden=1;}
    /* ObjSonic_Display then runs the invincibility and speed shoes timers,
       after the mode routine moved Sonic (Sonic/Main.asm ObjSonic_Main). */
    powerups_step();
}
static uint8_t time_stop_active;
int scd_player_time_stop(void){return time_stop_active;}
/* Updates since this level program started: GAME.C game_init (Level/Main.asm
   LevelStart) runs at act start, on a death restart and on a time-warp
   arrival, and clears the palette-cycle timers (clchgtim/clchgcnt) that
   clchgctr then steps once per update. player_frame keeps counting. */
static uint32_t level_frames;
uint32_t scd_player_level_frames(void){return level_frames;}
void scd_player_stop_clock(void){clock_stopped=1;}
void scd_player_hold_clock(int held){clock_held=!!held;}
static int force_right;
void scd_player_force_right(int active){force_right=active;}
static uint8_t ring_lives;
static int music_event=-1;
scd_powerup_state scd_player_powerups(void){return (scd_powerup_state){invinc_ticks,shoes_ticks,shield_age,ring_lives};}
int scd_player_music_event(void){int event=music_event;music_event=-1;return event;}
static void clear_powerups(void){invinc_ticks=shoes_ticks=0;plpower_m=plpower_s=0;plmaxspdwk=1536;pladdspdwk=12;plretspdwk=128;music_event=0;}
void scd_player_finish(void){clock_stopped=1;invinc_ticks=shoes_ticks=0;plpower_m=plpower_s=0;music_event=-1;}
static void extra_life(void){if(pl_suu<255)pl_suu++;soundset(180);}
void scd_player_rings_lost(void){ring_lives=0;}
void scd_player_rings(unsigned count){
    unsigned rings=plring+count;plring=rings>999?999:rings;
    if(plring>=100 && !(ring_lives&2)){ring_lives|=2;extra_life();}
    else if(plring>=200 && !(ring_lives&4)){ring_lives|=4;extra_life();}
    else soundset(149);
}
void scd_player_powerup(unsigned kind){
    switch(kind){
    case 0:extra_life();break;
    case 1:scd_player_rings(10);break;
    case 2:plpower_b=1;shield_age=0;soundset(151);break;
    case 3:invinc_ticks=1320;plpower_m=1;music_event=6;break;
    case 4:shoes_ticks=1320;plpower_s=1;plmaxspdwk=3072;pladdspdwk=24;plretspdwk=128;music_event=5;break;
    case 5:time_stop_active=1;break;
    /* "S": shield, invincibility, then speed shoes. */
    case 7:scd_player_powerup(2);scd_player_powerup(3);scd_player_powerup(4);break;
    default:break;
    }
}
static void powerups_step(void){
    if(plpower_b && !plpower_m)shield_age++;
    if(invinc_ticks && !--invinc_ticks){plpower_m=0;if(!shoes_ticks)music_event=0;}
    if(shoes_ticks && !--shoes_ticks){plpower_s=0;plmaxspdwk=1536;pladdspdwk=12;plretspdwk=128;if(!invinc_ticks)music_event=0;}
}
void scd_player_points(unsigned points){
    unsigned total=(unsigned)plscore+points;plscore=total>9999990?9999990:total;
    if((unsigned)plscore>=next_life){next_life+=50000;if(pl_suu<255)pl_suu++;soundset(180);}
}
scd_checkpoint scd_player_checkpoint(void){return checkpoint;}
/* PLAYSUB.C playsave0 keeps chibi_flag in chibi_s; SAVE.C playload restores
   it on round 6 only. */
static unsigned char checkpoint_chibi;
int scd_player_checkpoint_activate(unsigned id){
    if(current_era || !id || id>255 || id<=checkpoint.id || actwk[0].r_no0>=4)return 0;
    checkpoint=(scd_checkpoint){.x=actwk[0].xposi.w.h,.y=actwk[0].yposi.w.h,.elapsed=elapsed>18000?18000:elapsed,.id=id};
    checkpoint_chibi=chibi_flag;
    soundset(174);return 1;
}
static unsigned death_ticks,charge_buffer;
static int arriving;
static unsigned arrival_adjusted;
unsigned scd_player_arrival_adjusted(void){return arrival_adjusted;}
static void (*audio_sink)(short);
void scd_player_audio_set(void (*sink)(short)) {audio_sink=sink;}
extern short playdieset(sprite_status *);
void scd_player_statics_reset(void);
void scd_player_brake_begin(void);
void scd_player_brake_end(void);
void soundset(short request) {if(audio_sink)audio_sink(request);}
static void wave_stop(void) {soundset(171);}
/* COLI1.C pcol comes with the Act 3 boss sources; host tools without them link this no-op. */
__attribute__((weak)) short pcol(sprite_status *actor){(void)actor;return 0;}
void (*WaveAllStop)(void)=wave_stop;

/* PLAYER.C scr_h, compiled verbatim with the camera (src/camera_v.c); hosts
   without the camera link this no-op. */
__attribute__((weak)) void scr_h(void){}
/* ObjSonic_Animate changes the actual actor (including FD animation changes),
   not a renderer-local clock. Objects may write patcnt AFTER this call; their
   new cursor selects a mapping on the NEXT player update. */
static void player_animate(void){
    sprite_status *p=&actwk[0];
    scd_sonic_animation state={p->mstno.b.h,p->mstno.b.l,p->patcnt,
        p->pattim,p->patno,p->actflg};
#ifdef SCD_PLAYER_ANIMATION_AUDIT
    scd_sonic_animation before=state;
    extern void scd_player_animation_audit(const scd_sonic_animation *,
        const scd_sonic_animation *,int16_t,uint8_t,uint8_t,uint8_t);
#endif
    /* ObjSonic_GetMiniAnim/.MiniSonicRun: chibi_flag is set only by the R8
       shrink beam (BEAM.C), so other rounds always take the normal branch. */
    int result=(chibi_flag?scd_sonic_animate_mini:scd_sonic_animate)(&state,p->mspeed.w,p->direc.b.h,p->cddat,p->actfree[2]);
    assert(result>=0);if(result<0)return;
    if(result){p->cddat|=4;p->sprvsize=10;p->sprhs=5;}
    p->mstno.b.h=state.animation;p->mstno.b.l=state.previous;
    p->patcnt=state.cursor;p->pattim=state.timer;
    p->patno=state.mapping;p->actflg=state.sprite_flags;
#ifdef SCD_PLAYER_ANIMATION_AUDIT
    scd_player_animation_audit(&before,&state,p->mspeed.w,p->direc.b.h,p->cddat,p->actfree[2]);
#endif
}

/* Collision Chaos terrain bumper blocks (R3/PLAYSP3.C, generated by
   tools/prepare_playsp3.py). Host tools without it link this no-op, like the
   original's empty PLAYSP.C playsp for rounds without special blocks. */
__attribute__((weak)) void scd_playsp3(void){}
/* Quartz Quadrant conveyor belts (R5/PLAYSP5.C belt): the block under either
   foot edge in the era's table pushes Sonic at the era's speed; a wall stops
   him (dircol). Tables are count-1 followed by the block numbers.
   tools/test-playsp5.sh checks scd_playsp5 against the compiled original. */
void scd_playsp5(void);short dircol(sprite_status*,char*);
/* GetLevelBlock's word as the zone code reads it (scddisasm Level/Collision
   Floor.asm:451-500, retail R51C $200EFC): a blank chunk returns the
   LevelChunks base, so a direct (a1) read gets chunk 1's first block word.
   The floor and wall finders skip blank chunks (cmpi.l #LevelChunks,d1,
   :671/:762/:860/:942), as FCOL.C scramapad's 0 does; the belt, WW floor,
   spark and beam checks do not. QQ1C's empty column at X 11264 reads block
   12, a Good Future belt block, so retail Sonic is carried there. */
static int scramapad_direct;
static short level_block(sprite_status *actor,short x,short y){
    int cx=x<0?0:x,cy=y;
    if(map_y_wraps())cy&=2047;
    if(cy<0)cy=0;
    if(cx<16384 && cy<2048 && !mapwka[cy>>8][cx>>8] && level->size[2]>=2)
        return (short)(((unsigned)level->part[2][0]<<8)|level->part[2][1]);
    scramapad_direct=1;short b=scramapad(actor,x,y);scramapad_direct=0;return b;
}
static const short belt_a[]={44,1,2,3,4,5,6,7,8,9,14,15,17,18,19,35,36,37,38,39,49,61,62,63,64,71,72,73,74,400,403,404,405,406,407,408,409,410,411,413,415,422,423,424,448,450};
static const short belt_b[]={49,1,2,3,4,5,6,7,8,9,10,11,14,15,17,18,19,35,36,37,38,39,49,59,60,61,62,63,64,71,72,73,74,400,403,404,405,406,407,408,409,410,411,413,415,422,423,424,483,484,485};
static const short belt_c[]={51,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,17,18,19,35,36,37,38,39,49,61,62,63,64,71,72,73,74,75,400,403,404,405,406,407,408,409,410,411,413,414,415,423,424,487,488,490,493};
static const short belt_d[]={49,1,2,3,4,5,6,7,8,9,10,11,14,15,17,18,19,35,36,37,38,39,49,61,62,63,64,71,72,73,74,75,400,403,404,405,406,407,408,409,410,411,413,414,415,423,424,488,489,491,500};
static int belt_chk(short block){
    static const short *const belt_tbl[4]={belt_b,belt_a,belt_d,belt_c};
    unsigned char kind=time_flag&127;if(kind==2)kind+=generate_flag;
    const short *t=belt_tbl[kind];
    for(short i=1,n=t[0];n>=0;--n)if(block==t[i++])return 1;
    return 0;
}
void scd_playsp5(void){
    sprite_status *p=&actwk[0];
    if(bossflag)return;
    short y=p->yposi.w.h+(short)(unsigned short)p->sprvsize+2;
    if(!belt_chk(level_block(p,p->xposi.w.h-(short)(unsigned short)p->sprhs,y)&2047) &&
       !belt_chk(level_block(p,p->xposi.w.h+(short)(unsigned short)p->sprhs,y)&2047))return;
    int speed=time_flag==0?32768:time_flag==1?65536:131072;char direction=-64;
    if(colrevflag){speed=-speed;direction=-direction;}
    p->xposi.l+=speed;
    short d=dircol(p,&direction);
    if(d<0){if(colrevflag)d=-d;p->xposi.w.h+=d;}
}
/* R8 PLAYSP8.C playsp (retail R82A $206340, R82B-D the same): a belt block
   (270-276) under either foot edge moves Sonic 1 pixel, left when the
   block's flip bit (2048) is set, reversed on 276. Act 3 returns
   (stageno.b.l == 2) and the R81 programs have no belt check, so only Act 2
   (retail MM2A row 4191: 1 pixel back per update from X 5225). */
static int belt8_chk(short block){return block>=270 && block<=276;}
static void playsp8(void){
    sprite_status *p=&actwk[0];
    if(current_act!=1)return;
    short y=(short)(p->yposi.w.h+(signed char)p->sprvsize+2);
    short b=level_block(p,(short)(p->xposi.w.h-(signed char)p->sprhs),y);
    if(!belt8_chk(b&2047)){
        b=level_block(p,(short)(p->xposi.w.h+(signed char)p->sprhs),y);
        if(!belt8_chk(b&2047))return;
    }
    short add=(b&2048)?-1:1;
    if((b&2047)==276)add=-add;
    p->xposi.w.h+=add;
}
static void playsp(void){if(current_zone==1)scd_playsp3();else if(current_zone==3)scd_playsp5();else if(current_zone==6)playsp8();}
/* WW ObjSonic_CheckBouncyFloor runs after the normal movement mode. The
   electric floor is block $21F; its inactive palette step depends on era. */
static void ww_bouncy_floor(void){
    if(current_zone!=4 || bossflag)return;
    sprite_status *p=&actwk[0];
    if(p->mstno.b.h==43)return;
    if(current_era<2 && scd_r6_palette_count &&
       (uint8_t)scd_r6_palette_count(3)==(current_era==0?90:60))return;
    short y=p->yposi.w.h+(short)p->sprvsize+2;
    short left=p->xposi.w.h-(short)p->sprhs,right=p->xposi.w.h+(short)p->sprhs;
    if(((unsigned)level_block(p,left,y)&2047)!=0x21f &&
       ((unsigned)level_block(p,right,y)&2047)!=0x21f)return;
    p->yspeed.w=-5632;p->cddat=(p->cddat|2)&~(16|32);p->actfree[18]=0;
    if(!(p->cddat&4)){
        p->cddat|=4;p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;
        p->mstno.b.h=2;soundset(218);
    }
}
/* WW Sonic/Main.asm ObjSonic_CheckRotPole and ObjSonic_RotPole. Block $103
   catches Sonic at its center; subsequent updates rotate him around that
   center until a jump press releases him at either far end. */
static void ww_rot_pole_step(sprite_status *p){
    unsigned char *ctrl=&p->actfree[2],*angle=&p->actfree[1];
    if((*ctrl&16) && !(*angle&127)){
        p->xspeed.w=(*angle&128)?-3072:3072;
        p->sproffset&=0x7fff;*ctrl&=~(8|16);
        p->actfree[20]=p->actfree[21]=0;
        return;
    }
    if(swdata.b.l&SCD_JUMP)*ctrl|=16;
    *angle+=8;
    if(*angle&128)p->sproffset&=0x7fff;
    else p->sproffset|=0x8000;
    short sn,cs;sinset(*angle,&sn,&cs);
    short center=(short)scd_word_get(p,31);
    p->xposi.w.h=center+((int32_t)cs*23>>8);
    p->yposi.l+=(int32_t)p->yspeed.w*256;
    if(((unsigned)level_block(p,center,p->yposi.w.h)&2047)!=0x103)
        p->yspeed.w=-p->yspeed.w;
}
static void ww_check_rot_pole(void){
    if(current_zone!=4)return;
    sprite_status *p=&actwk[0];
    if(p->mstno.b.h==43 || p->r_no0>=4 || (p->actfree[2]&8))return;
    if(((unsigned)level_block(p,p->xposi.w.h,p->yposi.w.h)&2047)!=0x103)return;
    p->actfree[2]|=8;p->xspeed.w=0;
    p->yspeed.w=p->yspeed.w<0?-512:512;
    p->actfree[1]=64;
    p->xposi.w.h=(p->xposi.w.h&~15)+8;
    scd_word_set(p,31,(uint16_t)p->xposi.w.h);
    p->mstno.b.h=2;p->cddat|=4;p->sprvsize=14;p->sprhs=7;
}
/* WW Sonic/Main.asm ObjSonic_HangBar: an already held bar replaces air
   movement for this update. The head block is checked before a jump tap. */
static void ww_hang_bar_step(sprite_status *p){
    if(((unsigned)level_block(p,p->xposi.w.h,p->yposi.w.h-24)&2047)!=0x159 ||
       (swdata.b.l&SCD_JUMP)){
        p->actfree[2]&=~4;p->yposi.w.h+=16;p->sprvsize=19;p->sprhs=9;return;
    }
    short dx=0;
    if(swdata.b.h&SCD_LEFT){dx=-2;p->cddat|=1;p->actflg|=1;}
    else if(swdata.b.h&SCD_RIGHT){dx=2;p->cddat&=~1;p->actflg&=~1;}
    if(!dx)return;
    p->xposi.w.h+=dx;
    if((int8_t)--p->pattimm>=0)return;
    p->pattimm=7;if(++p->patcnt>=4)p->patcnt=0;
}
/* WW Sonic/Main.asm ObjSonic_CheckHangBar follows sparks and electric beam
   checks. Its block $159 test uses Sonic's center, 24 px above his feet. */
static void ww_check_hang_bar(void){
    if(current_zone!=4 || scd_player_warp_saved())return;
    sprite_status *p=&actwk[0];
    if(p->mstno.b.h==43 || (p->actfree[2]&(1|4)))return;
    short y=p->yposi.w.h;
    if(((unsigned)level_block(p,p->xposi.w.h,y-24)&2047)!=0x159)return;
    scd_world_abort();
    p->cddat&=~4;p->xspeed.w=p->yspeed.w=p->mspeed.w=0;
    p->mstno.b.h=44;p->actfree[2]|=4;p->pattimm=7;
    p->yposi.w.h=((y-24)&~15)+24;
}
/* Sonic/Main.asm ObjSonic_CheckSparks reads the block under Sonic's center.
   Good Future R61C/R62C use aniArtFrames+2 to switch the hazard off. */
static void ww_check_sparks(void){
    if(current_zone!=4)return;
    sprite_status *p=&actwk[0];
    if(p->mstno.b.h==43 || p->r_no0>=4 || plpower_m ||
       (p->actfree[2]&128) || scd_word_get(p,26))return;
    int x=p->xposi.w.h;
    if(x>=0x980 && x<0xa20)return;
    if(bossflag&128)return;
    if(current_act==2 && x<0xa10 && !bossstart)return;
    if(current_era==2 && (!scd_r6_sparks_active || !scd_r6_sparks_active()))return;
    unsigned block=(unsigned)level_block(p,x,p->yposi.w.h)&2047;
    unsigned first=current_era==3?0x287:0x243;
    /* HurtPlayer compares Sonic with stale oX(a2). Retail WW2B at X3081
       and WW1D at X5723 enter with A2=$2347F6 (oX=0). */
    if(block>=first && block<first+3)
        scd_objects_hurt(current_era==3 || (current_act==1 && current_era==1)?0:current_era==0?0x1010:x+1);
}
/* ObjSonic_CheckElecBeam: the BEEM6 controller sets one of three active
   color/beam modes. Sonic is tested against the block at his center. */
static void ww_check_elec_beam(void){
    if(current_zone!=4 || !st6clrchg)return;
    sprite_status *p=&actwk[0];
    if(p->mstno.b.h==43 || p->r_no0>=4 || plpower_m || scd_word_get(p,26))return;
    unsigned block=(unsigned)level_block(p,p->xposi.w.h,p->yposi.w.h)&2047;
    int hit=st6clrchg==1?block==0x1aa:
            st6clrchg==2?block==0x1c1:
            st6clrchg==3?(block==0x1bc || block==0x1db || block==0x1d4 ||
                            block==0x1d1 || block==0x1a3 || block==0x199 ||
                            block==0x198 || block==0x1a2):0;
    /* WW1A's sampled beam contact recoils right. WW1B's sampled contacts at
       X=3724 and X=7035 recoil left. WW2B X4472 enters playdamageset with
       A2=$FF1200, oX=0. The assembly source uses stale A2. */
    if(hit)scd_objects_hurt(current_era==3 || (current_act==1 && current_era==1)?0:current_era==0?0x1010:p->xposi.w.h+1);
}
/* SCR3xx.C block_wrt: PLAYSP3.C's breakable bumpers clear their block in the
   chunk the map places there (shared by every copy of that chunk, as in the
   original). The original reloads the stage after a death; the log restores
   the written blocks when Sonic is placed again, and main.c redraws both. */
#define BLOCK_LOG 512
static struct {uint16_t x,y,old;} block_log[BLOCK_LOG];
static unsigned block_log_count,block_dirty_count;
static struct {uint16_t x,y;} block_dirty[64];
static void block_mark(unsigned x,unsigned y){
    if(block_dirty_count<64){block_dirty[block_dirty_count].x=(uint16_t)x;block_dirty[block_dirty_count].y=(uint16_t)y;}
    block_dirty_count++;
}
static uint8_t *block_address(unsigned x,unsigned y){
    if(map_y_wraps())y&=2047;
    if(!level || x>=16384 || y>=2048)return NULL;
    unsigned chunk=mapwka[y>>8][x>>8]&127;
    if(!chunk)return NULL;
    unsigned offset=(chunk-1)*512+((y>>4)&15)*32+((x>>4)&15)*2;
    return offset+2<=level->size[2]?(uint8_t *)(uintptr_t)(level->part[2]+offset):NULL;
}
void block_wrt(unsigned short block,unsigned short x,unsigned short y){
    uint8_t *at=block_address(x,y);
    if(!at)return;
    if(block_log_count<BLOCK_LOG){block_log[block_log_count].x=x;block_log[block_log_count].y=y;block_log[block_log_count++].old=(uint16_t)(at[0]<<8|at[1]);}
    at[0]=(uint8_t)(block>>8);at[1]=(uint8_t)block;block_mark(x,y);
}
static void block_restore(void){
    while(block_log_count){
        block_log_count--;uint8_t *at=block_address(block_log[block_log_count].x,block_log[block_log_count].y);
        if(at){at[0]=(uint8_t)(block_log[block_log_count].old>>8);at[1]=(uint8_t)block_log[block_log_count].old;}
        block_mark(block_log[block_log_count].x,block_log[block_log_count].y);
    }
}
/* Blocks written since the last call (x, y in pixels); more than capacity asks
   for a full redraw with a count above it. */
unsigned scd_player_block_writes(uint16_t (*out)[2],unsigned capacity){
    unsigned n=block_dirty_count;
    for(unsigned i=0;i<n && i<capacity && i<64;i++){out[i][0]=block_dirty[i].x;out[i][1]=block_dirty[i].y;}
    block_dirty_count=0;
    return n;
}

short scramapad(sprite_status *actor,short x,short y) {
    if(x<0)x=0;
    if(map_y_wraps())y&=2047;
    if(y<0)y=0;
    if(x>=16384 || y>=2048)return 0;
    unsigned raw=mapwka[y>>8][x>>8],chunk=raw&127;
    if(!chunk)return 0;
    /* GetLevelBlock: WW's high-bit layout chunks select a second collision
       path. Chunk $14 enters that path; $15/$1E/$1F/$32 use $60-$63 there.
       An ordinary chunk returns the actor to the lower path. */
    if(current_zone==4){
        if(!(raw&128))actor->actflg&=~64;
        else if(actor->actflg&64){
            if(chunk==0x15)chunk=0x60;
            else if(chunk==0x1e)chunk=0x61;
            else if(chunk==0x1f)chunk=0x62;
            else if(chunk==0x32)chunk=0x63;
        }else if(chunk==0x14)actor->actflg|=64;
    }
    /* GetLevelBlock .NotWWZ2: SS uses the switch-board layer except for
       loop chunks 4/6, which follow the actor's path bit. */
    if(current_zone==5){
        actor->sproffset&=32767;
        if(raw&128){
            actor->sproffset|=32768;
            if(chunk==4 || chunk==6){
                actor->sproffset&=32767;
                if(actor->actflg&64)++chunk;
            }else if(prio_flag){
                actor->sproffset&=32767;
                if(chunk==40 || chunk==60 || chunk==55 || chunk==47 || chunk==22)++chunk;
            }
        }
    }
    /* FCOL.C:834-836 and :1070-1100 st_metalDataChk (retail R83C $2011B2):
       MM clears the priority bit on an ordinary chunk; on a high-bit chunk a
       player (actno < 3) gets it, and on the upper layer (prio_flag) loses it
       again and reads the layer's chunk (70/72/74/16/99/67 -> 106-111).
       Other actors keep the chunk. No path-bit +1 in MM. */
    if(current_zone==6){
        if(!(raw&128))actor->sproffset&=32767;
        else if(actor->actno<3){
            actor->sproffset|=32768;
            if(prio_flag){
                actor->sproffset&=32767;
                switch(chunk){
                case 70:chunk=106;break;case 72:chunk=107;break;case 74:chunk=108;break;
                case 16:chunk=109;break;case 99:chunk=110;break;case 67:chunk=111;break;
                }
            }
        }
    }
    /* WW, SS and MM use their own chunk mapping above. */
    if(current_zone!=4 && current_zone!=5 && current_zone!=6 && (raw&128) && (actor->actflg&64)) {
        if(++chunk==41)chunk=81;
    }
    unsigned offset=(chunk-1)*512+((y>>4)&15)*32+((x>>4)&15)*2;
    if(offset+2>level->size[2])return 0;
    /* GetLevelBlock's pointer for chunk 1's first block equals LevelChunks,
       the blank-chunk value, so the floor and wall finders skip it
       (retail R81C FindLevelWall $2013C6 cmpil #$210000,d1; Collision
       Floor.asm:671/:762/:860/:942). Retail MM1C passes the $6042 wall at
       x 5376, y 1792. Direct block reads (level_block) still see the word.
       Zone 6 only. */
    if(!offset && current_zone==6 && !scramapad_direct)return 0;
    return ((unsigned)level->part[2][offset]<<8)|level->part[2][offset+1];
}

void scd_player_velocity(int x,int y){actwk[0].xspeed.w=x;actwk[0].yspeed.w=y;}
/* Level/Main.asm runs SpawnObjects/RunObjects from the first level frame;
   on that frame Sonic only runs ObjSonic_Init (Sonic/Main.asm:135-155), which
   scd_player_place does at once. The placed actors therefore get one update
   before Sonic's first ObjSonic_Main (retail TT1B pillars, TIDAL-TEMPEST-PLAN.md).
   The level start (src/main.c, route hosts) asks for it after scd_player_init;
   actor fixtures that step one update against a compiled original do not. */
static int object_first_update;
void scd_player_objects_lead(void){object_first_update=1;}
/* Run the pending lead update now (src/main.c time-warp arrival, while the
   display is still off). The result is the update scd_player_step would run
   first; only its Saturn cost moves out of the first gameplay update. */
void scd_player_objects_lead_run(void){
    /* The same lead update as scd_player_step's, gametimer included (retail
       MM3D: HOTA8D.C's firefly aim at seq 3377 needs it). */
    if(object_first_update){object_first_update=0;if(current_zone==6)++gametimer.w;scd_objects_step(actwk[0].xposi.w.h,actwk[0].yposi.w.h);}
}
void scd_player_place(int x,int y,int speed,unsigned angle,unsigned flags) {
    object_first_update=0;  /* only the stage-start placement (scd_player_init) */
    scd_objects_release_control();
    display_hidden=0;
    memset(&actwk[0],0,sizeof(actwk[0]));
    memset(dirstk,0,sizeof(dirstk));
    scd_player_statics_reset();scd_plus_place();
    previous_buttons=charge_buffer=0;force_right=0;scr_cnt=0;scra_vline=96;death_ticks=0;scralim_down=1816;
    block_restore();
    actwk[0].actno=1;
    actwk[0].xposi.l=x*65536;actwk[0].yposi.l=y*65536;
    play00init();
    actwk[0].mspeed.w=speed;actwk[0].direc.b.h=angle;
    actwk[0].cddat=flags;
    if(flags&4){actwk[0].sprvsize=14;actwk[0].sprhs=7;}
    stageno.b.h=current_zone;stageno.b.l=current_act;time_flag=current_era==0?1:current_era==1?0:2;
    /* GAME.C: generate_flag marks the Good Future (PLAYSP3.C fcol table, BOSS_3.C track). */
    generate_flag=current_era==2;
    {
        /* scr_set and playposiset in the round's retail SCR<round><act><era> program
           read scr_dir_tbl and playmapnotbl.  src/scroll_limits.h carries all seventy
           of those pairs; tools/extract_scroll_limits.py checks sixty-eight of them
           against build/audit/source and recovers R42B and R42D from the disc. */
        const scroll_limits_t *limits=&scroll_limits[current_zone][current_act][current_era];
        if(!limits->valid)limits=&scroll_limits[current_zone][current_act][2];
        scralim_left=0;scralim_right=limits->right;scralim_down=limits->down;scralim_up=limits->up;
        scra_vline=limits->vline;
        loopmapno=limits->loopmapno;loopmapno2=limits->loopmapno2;
        ballmapno=limits->ballmapno;ballmapno2=limits->ballmapno2;
    }
}
int scd_player_init(const stage_t *stage,const uint8_t *collision,size_t size,unsigned era) {
    if(size!=9472 || era>3)return -1;
    /* A newly loaded stage has none of the previous one's block writes. */
    block_log_count=block_dirty_count=0;
    /* The CD++ preset is read at act start only. */
    scd_plus_act_start();
    level=stage;current_era=era;player_frame=level_frames=reset_count=elapsed=game_over=clock_held=0;
    memset(&effect_sample,0,sizeof(effect_sample));display_hidden=0;
    /* GAME.C game_init clears chibi_flag before ObjSonic_Init sizes Sonic;
       time travel keeps it (PLAYER.C playsave chibi_sb, SAVE.C round 6). */
    if(!arriving){memset(&checkpoint,0,sizeof(checkpoint));scd_player_warp_clear();chibi_flag=0;}
    memcpy(mapwka,stage->part[3],512);
    memcpy(collision_index,collision,1024);scdadr=collision_index;
    memcpy(scdtblwk,collision+1024,4096);
    memcpy(scdtblwk2,collision+5120,4096);
    memcpy(scddirtbl,collision+9216,256);
    plring=0;plpower_b=plpower_m=0;time_stop_active=0;pl_suu=3;byecnt0.w=0;plscore=0;next_life=50000;ring_lives=0;shield_age=0;clear_powerups();clock_stopped=0;scd_act_reset();arrival_adjusted=0;
    /* ObjSonic_Init (scddisasm Sonic/Main.asm:135-155) sets no oFlags: Sonic
       starts grounded and his first ObjSonic_Main sets the air bit only when
       no floor is under him (retail TT2/TT3 starts never fall). */
    scd_player_place(stage->start_x,stage->start_y,0,0,0);
    water_reset(current_zone,current_act,current_era);
    if(!arriving)scd_objects_reset(era,1);
    return 0;
}
static int arrival_clear(int x,int y) {
    sprite_status *p=&actwk[0];int radius=p->sprvsize;
    if(x<16 || x>=16368 || y<radius || y>=2048-radius)return 0;
    for(int yy=y-radius;yy<=y+radius;yy+=4)for(int xx=x-8;xx<=x+8;xx+=4){
        unsigned block=(uint16_t)scramapad(p,xx,yy);
        if(!(block&0x6000))continue;
        unsigned id=collision_index[block&1023];int column=xx&15;if(block&0x800)column=15-column;
        int height=(signed char)scdtblwk[id][column];if(block&0x1000)height=-height;
        if(height>0 && (yy&15)>=16-height)return 0;
        if(height<0 && (yy&15)<-height)return 0;
    }
    return 1;
}
int scd_player_arrival_clear(void){return arrival_clear(actwk[0].xposi.w.h,actwk[0].yposi.w.h);}
void scd_player_warp_save(void){
    warp_save.valid=1;warp_save.actor=actwk[0];warp_save.rings=plring;warp_save.ring_lives=ring_lives;warp_save.elapsed=elapsed;
    scroll_start.b.h=1;
}
int scd_player_warp_saved(void){return warp_save.valid;}
void scd_player_warp_clear(void){if(warp_save.valid)scroll_start.b.h=0;warp_save.valid=0;}
int scd_player_arrive(const stage_t *stage,const uint8_t *collision,size_t size,unsigned era) {
    if(size!=9472 || era>3)return -1;
    sprite_status saved=actwk[0];unsigned rings=plring,lives=pl_suu,saved_ring_lives=ring_lives;
    uint32_t frame=player_frame,resets=reset_count,time=elapsed,life_threshold=next_life;int score=plscore;
    if(warp_save.valid){saved=warp_save.actor;rings=warp_save.rings;saved_ring_lives=warp_save.ring_lives;time=warp_save.elapsed;}
    scd_player_warp_clear();
    arriving=1;int result=scd_player_init(stage,collision,size,era);arriving=0;
    if(result)return result;
    /* SaveTimeWarpData / LoadTimeWarpData restore integer position, velocity
       and flags into a fresh actor, not its animation, subpixels, angle, path,
       object ownership or scratch timers. Level/Main clears all power-ups;
       LoadPlayer grants 120 updates of hurt protection after a saved spawn. */
    actwk[0].xposi.l=saved.xposi.w.h*65536;actwk[0].yposi.l=saved.yposi.w.h*65536;
    actwk[0].xspeed=saved.xspeed;actwk[0].yspeed=saved.yspeed;actwk[0].mspeed=saved.mspeed;
    actwk[0].cddat=saved.cddat&~(8|64);scd_word_set(&actwk[0],26,120);
    plring=rings;pl_suu=lives;ring_lives=saved_ring_lives;plscore=score;next_life=life_threshold;
    player_frame=frame;level_frames=0;elapsed=time>18000?18000:time;reset_count=resets;
    scd_objects_change_era(era);
    int x=actwk[0].xposi.w.h,y=actwk[0].yposi.w.h;
    if(!arrival_clear(x,y)){
        int found=0;
        for(int distance=4;distance<=512 && !found;distance+=4){
            const int shifts[4][2]={{0,-distance},{-distance,0},{distance,0},{0,distance}};
            for(unsigned n=0;n<4;n++)if(arrival_clear(x+shifts[n][0],y+shifts[n][1])){
                actwk[0].xposi.l=(x+shifts[n][0])*65536;actwk[0].yposi.l=(y+shifts[n][1])*65536;
                actwk[0].cddat|=2;arrival_adjusted=distance;found=1;break;
            }
        }
        if(!found)return -2;
    }
    return 0;
}
/* ObjSonic_LevelBound's left limit: leftBound + 16 (Sonic/Main.asm:1681-1684). The
   native goal keeps the camera X it froze at (the original writes leftBound);
   a boss lock that raises leftBound after it still applies (retail TT3C: the
   capsule area's leftBound 3479 stops Sonic at 3495). */
static int player_left_bound(void){
    int left=scralim_left;
    if(scd_act_get().goal && scd_act_get().left>left)left=scd_act_get().left;
    return left+16;
}
/* PLAYER.C play00damage's motion (tools/test-water-player.sh compares it). */
void scd_player_hurt_motion(void){
    sprite_status *p=&actwk[0];
    speedset2(p);p->yspeed.w+=48;if(p->cddat&64)p->yspeed.w-=32;
}
/* PLAYER.C play00walk/play00jump/ball00walk/ball00jump movement, as the
   native step runs it (tools/test-water-player.sh compares it with the
   original bodies, underwater included). */
/* PLAYER.C limitchk sides (68k ObjSonic_LevelBound, Sonic/Main.asm:1673-1694):
   every movement mode tests X plus one xspeed step before it moves, so a
   right-bound stop clears the ground speed before the floor and fall-off checks
   (retail PPZ3D 2126 stays grounded on the slope at x 3839). */
static void player_side_bound(void){
    sprite_status *p=&actwk[0];
    int ahead=(int16_t)(((uint32_t)p->xposi.l+(uint32_t)((int32_t)p->xspeed.w*256))>>16);
    int left=player_left_bound(),right=scralim_right+304+(bossstart?0:56);
    if(ahead<left){p->xposi.l=left*65536;p->xspeed.w=p->mspeed.w=0;}
    if(ahead>=right){p->xposi.l=right*65536;p->xspeed.w=p->mspeed.w=0;}
}
/* PLAYER.C:27-41 bye_chk: three minutes (10800 frames, counted by GAME.C
   bye_cnt) in the waiting pose and Sonic says "I'm outta here": one life
   left, a jump off the screen, voice 121 (retail MM2C row 18311). */
void sub_sync(short request);
extern unsigned char chibi_flag;
void bye_chk(void){
    sprite_status *p=&actwk[0];
    /* GAME.C bye_cnt adds one per frame after this check: counting here, the
       check on the Nth waiting frame still reads N. */
    if(p->mstno.b.h!=5){byecnt0.w=0;return;}
    if(++byecnt0.w<10800)return;
    byecnt0.w=0;p->mstno.b.h=43;p->sproffset|=32768;p->sprpri=0;pl_suu=1;
    p->yspeed.w=-1280;p->xspeed.w=256;if(p->cddat&1)p->xspeed.w=-p->xspeed.w;
    p->mspeed.w=0;sub_sync(121);
}
void scd_player_motion(void){
    sprite_status *p=&actwk[0];
    if(current_zone==4 && (p->actfree[2]&8)){
        ww_rot_pole_step(p);jumpcolchk();return;
    }
    /* ObjSonic_MdAir / PLAYER.C play00jump selects the descending pose
       BEFORE movement/gravity. Rolling jumps, object ownership, wind tunnels
       and the bubble-breath animation must not take this transition. */
    if((p->cddat&6)==2 && !watercoliflag && p->mstno.b.h!=21 && p->yspeed.w>=0)
        p->mstno.b.h=0;
    /* PLAYER.C play00walk:507-516: bye_chk, then a Sonic leaving (animation
       43) waits for pose 23 (121 when small) and moves with gravity until
       limitchk drops him below the screen. */
    if(!(p->cddat&6)){
        bye_chk();
        if(p->mstno.b.h==43){
            if(chibi_flag?p->patno!=121:p->patno<23)return;
            /* limitchk tests the bottom before speedset moves him (retail
               MM2C: routine 6 at row 18515, Y 1972 > bound 1744 + 224). */
            player_side_bound();
            if(scralim_down+224<p->yposi.w.h){p->r_no0=6;scd_objects_death_record();}
            speedset(p);return;
        }
    }
    chk11();
    unsigned state=actwk[0].cddat&6;
    if(state&2) {
        /* PLAYER.C play00jump/ball00jump: underwater gravity is 56-40. */
        scd_plus_air();jumpchk2();if(!scd_plus_jumpmove())jumpmove();player_side_bound();speedset(&actwk[0]);if(actwk[0].cddat&64)actwk[0].yspeed.w-=40;direcchg();jumpcolchk();scd_plus_air_end();
    } else {
        /* A CD++ spin dash update replaces jumpchk and the ground input. */
        int plus=scd_plus_ground();
        if(plus || !jumpchk()) {
            if(plus) {}
            else if(state&4) {keispd2();balllmove();}
            else {keispd();levermove();ballchk();}
            player_side_bound();
            if(!(state&4) || !actwk[0].actfree[0])speedset2(&actwk[0]);
            fcol(&actwk[0]);fallchk();
        }
    }
}
void scd_player_step(unsigned buttons) {
    /* GAME.C:379-383: every game frame advances gametimer before actsetchk
       and action, the lead update too (HOTA8C.C's firefly aims at
       (gametimer & 127) + 3056). TT keeps water_tick's count. */
    if(object_first_update){object_first_update=0;if(current_zone==6)++gametimer.w;scd_objects_step(actwk[0].xposi.w.h,actwk[0].yposi.w.h);}
    scd_objects_spawn_early();
    memset(&effect_sample,0,sizeof(effect_sample));
    water_tick();
    if(current_zone==6)++gametimer.w;
    /* The Level End object runs after the player (slot 0), so its control lock
       reaches the player on the next update: force Right from the phase the
       previous update left. */
    unsigned phase=scd_act_get().phase;
    scd_act_step(scd_player_get());
    display_hidden=0;
    /* Level End/Main.asm:699-700 locks the controls with Right held ($808) and
       nothing releases them: the player keeps running through the results
       (Results/Main.asm:51-55 only waits for him to pass cameraX+336) and stops
       at the level bound. */
    if(phase>=SCD_ACT_EXIT || force_right)buttons=scd_act_stationary_results()?0:SCD_RIGHT;
    scd_objects_validate_rider();
    sprite_status *p=&actwk[0];
    int old_x=p->xposi.w.h,old_y=p->yposi.w.h;
    swdata1.b.h=buttons;swdata1.b.l=buttons&~previous_buttons;
    swdata.w=swdata1.w;previous_buttons=buttons;
    /* Keep a jump press for the crouch transition when Down + jump arrive
       together. Original levermove consumes the fresh Down edge first. */
    if((buttons&SCD_DOWN) && (swdata.b.l&SCD_JUMP) && !(p->cddat&2) && p->mspeed.w==0 && !scd_plus_charge_buffer_off())charge_buffer=2;
    if(!(buttons&SCD_DOWN))charge_buffer=0;
    if(charge_buffer){swdata.b.l|=SCD_JUMP;charge_buffer--;}
    if(p->r_no0==6) {
        if(invinc_ticks || shoes_ticks)clear_powerups();
        /* Original dead/gone split: cross bottomBound + 256, then wait. */
        if(p->yposi.w.h>scralim_down+256){
            p->r_no0=8;p->yspeed.w=-56;if(pl_suu)pl_suu--;
            /* Game Over/Main.asm:66-71: out of lives (not Time Attack), the game over
               object plays the game over song (CDDA_GAMEOVER, cue 12). */
            if(!pl_suu && !scd_ta.mode)music_event=12;
            /* Sonic/Main.asm:2429-2443: Time Attack loads no game over and waits 60. */
            death_ticks=(pl_suu || scd_ta.mode)?60:480;
        }
        speedset(p);effect_record();player_animate();effect_context();player_frame++;level_frames++;return;
    }
    if(p->r_no0==8){
        display_hidden=1;
        if(death_ticks && !--death_ticks){
            if(!pl_suu)game_over=1;
            else {
                int saved=current_era==0 && checkpoint.id;
                reset_count++;plring=0;plpower_b=0;ring_lives=0;clear_powerups();byecnt0.w=0; /* GAME.C:727 */
                /* LoadCheckpointData seeds frames=59, seconds=saved-1.
                   The first normal VInt HUD tick restores the whole second,
                   before ObjSonic_Init (no movement or hurt decrement). This
                   published reset state represents that initialized boundary. */
                elapsed=saved?checkpoint.elapsed/60*60:0;clock_stopped=0;scd_act_reset();
                scd_objects_respawn();
                level_frames=(uint32_t)-1; /* this update's ++ makes the restart update 0 */
                if(saved && current_zone==6)chibi_flag=checkpoint_chibi;
                scd_player_place(saved?checkpoint.x:level->start_x,saved?checkpoint.y:level->start_y,0,0,2);
                /* GAME4.C game_init reruns on the restart: water back to its table height. */
                water_reset(current_zone,current_act,current_era);
                /* Original LoadPlayer protects all saved spawns, including
                   checkpoints, but not a fresh start after an unsaved death. */
                if(saved)scd_word_set(&actwk[0],26,120);
            }
        }
        effect_context();player_frame++;level_frames++;return;
    }
    if(!clock_stopped && !clock_held)elapsed++;
    if(p->r_no0==4) {
        scd_player_hurt_motion();playsp();play00damage_sub();
        /* PLAYER.C play00damage then runs limitchk (68k ObjSonic_Hurt, Sonic/Main.asm:2362
           ObjSonic_LevelBound): the side bounds test the position one xspeed step ahead. */
        {
            int ahead=(int)(((uint32_t)p->xposi.l+(uint32_t)((int32_t)p->xspeed.w*256))>>16);
            int left=player_left_bound(),right=scralim_right+304+(bossstart?0:56);
            ahead=(int16_t)ahead;
            if(ahead<left){p->xposi.l=left*65536;p->xspeed.w=p->mspeed.w=0;}
            if(ahead>=right){p->xposi.l=right*65536;p->xspeed.w=p->mspeed.w=0;}
        }
        if(p->r_no0==6)scd_objects_death_record();
        effect_record();player_animate();effect_context();
        water_objects_step();scd_objects_step(old_x,old_y);player_frame++;level_frames++;return;
    }
    /* Retail WW ObjSonic_ExtCamera returns before changing camXCenter.
       Other rounds use PLAYER.C scr_h to pan the camera at high speed. */
    if(current_zone!=4)scr_h();
    /* Sonic/Main.asm: object ownership skips normal movement and terrain
       dispatch, while clocks, input, powerups and the object scheduler run. */
    if(p->actfree[2]&1){player_display();effect_record();player_animate();scd_objects_amy_idle_step();effect_context();water_objects_step();scd_objects_step(old_x,old_y);player_frame++;level_frames++;return;}
    scd_player_brake_begin();
    /* Sonic/Main.asm ObjSonic (.NormalMode): increment, then clamp to the
       current cap, so a spindash charge above 30 drops to 30 once Sonic is
       no longer rolling. */
    if(actwk[0].actfree[0]) {
        unsigned limit=(actwk[0].cddat&4)?45:30,charge=actwk[0].actfree[0]+1u;
        if(charge>=limit){if(actwk[0].actfree[0]<limit)soundset(200);charge=limit;}
        actwk[0].actfree[0]=(uint8_t)charge;
    }
    if(current_zone==4 && (p->actfree[2]&4))ww_hang_bar_step(p);
    else scd_player_motion();
    /* PLAYER.C play00move: the round's playsp follows the walk/jump dispatch. */
    playsp();
    ww_bouncy_floor();
    ww_check_sparks();
    ww_check_elec_beam();
    ww_check_hang_bar();
    ww_check_rot_pole();
    /* The native map is bounded; pit falls use the same life-loss path as hits. */
    int left=player_left_bound();
    if(actwk[0].xposi.w.h<left) {
        actwk[0].xposi.l=left*65536;actwk[0].xspeed.w=actwk[0].mspeed.w=0;
    }
    /* No right clamp here: ObjSonic_LevelBound (Sonic/Main.asm:1686-1694,
       R51C $4CD4) runs only inside the movement routines, before the move
       (player_side_bound). The round's playsp runs after it, so a Future
       belt pushes a bound-stopped Sonic 2 px past rightBound + 360: retail
       QQ1C rests at x 11265 (rightBound 10903). */
    /* Animation 43 (bye_chk) runs limitchk before its move in the ground
       routine (scd_player_motion), as PLAYER.C does; this post-move test
       would fire one update early (retail MM2C row 18515). */
    if(p->mstno.b.h!=43)
    /* PLAYER.C limitchk (68k ObjSonic_LevelBound .CheckBottom), every zone. */
    if(p->r_no0<6 && scralim_down+224<p->yposi.w.h){
        if(p->mstno.b.h!=43)playdieset(p);else p->r_no0=6;
        scd_objects_death_record();
    }
    /* Native safety for the bounded maps (the original has no map floor). */
    if(!map_y_wraps()){
        if(p->yposi.w.h>2040 && p->r_no0<6){playdieset(p);scd_objects_death_record();}
        /* MM: retail MM2C row 2938 rises past -256 (yspeed -1680); the map
           lookups clamp y < 0 themselves. */
        if(p->yposi.w.h < -256 && current_zone!=6){p->yposi.l=-256*65536;if(p->yspeed.w<0)p->yspeed.w=0;}
    }
    /* PLAYER.C play00: plwaterchk after playposiwkset, then the current's
       animation hold (watercoliflag keeps the previous animation). Zone 2 only. */
    water_player_check();
    actwk[0].actfree[12]=dirstk[0];actwk[0].actfree[13]=dirstk[2];
    if(watercoliflag && actwk[0].mstno.b.h==0)actwk[0].mstno.b.h=actwk[0].mstno.b.l;
    /* Sonic/Main.asm: Animate, then Player_ObjCollide, then SpecialChunks.
       Hurt/spring/disc animation selections made by objects apply next tick. */
    player_display();effect_record();player_animate();
    /* PLAYER.C play01: the touch response (COLI1.C pcol) runs before loopchk. */
    if((char)actwk[0].actfree[2]>=0 && actwk[0].mstno.b.h!=43){
        scd_objects_collision_begin();pcol(&actwk[0]);scd_objects_collision_end();
    }
    if(actwk[0].yposi.w.h>=0 && actwk[0].yposi.w.h<2048)loopchk();
    effect_context();
    water_objects_step();
    scd_objects_step(old_x,old_y);
    scd_player_brake_end();player_frame++;level_frames++;
}
scd_player_state scd_player_get(void) {
    sprite_status *p=&actwk[0];
    return (scd_player_state){.x=p->xposi.l,.y=p->yposi.l,.vx=p->xspeed.w,
        .vy=p->yspeed.w,.speed=p->mspeed.w,.flags=p->cddat,.angle=p->direc.b.h,
        .animation=p->mstno.b.h,.path=!!(p->actflg&64),.charge=p->actfree[0],
        .lock=p->actfree[20]|((unsigned)p->actfree[21]<<8),
        .frame=player_frame,.resets=reset_count,.elapsed=elapsed,.score=plscore,.game_over=game_over,.rings=plring,
        .hurt=scd_word_get(p,26),.routine=p->r_no0,.shield=plpower_b,.lives=pl_suu,.ramp=!!(p->actfree[2]&2),.control=p->actfree[2],.disc_angle=p->actfree[1],.disc_radius=p->actfree[15],.disc_frame=p->patcnt,
        .mapping=p->patno,.render_flags=p->actflg,.animation_previous=p->mstno.b.l,.animation_cursor=p->patcnt,.animation_timer=p->pattim,
        .display_hidden=display_hidden,.priority=p->r_no0?(uint8_t)(p->sprpri&7):2,
        .high=p->r_no0 && (p->sproffset&32768)};
}

void scd_player_inventory(unsigned rings,unsigned shield) {plring=rings>999?999:rings;plpower_b=!!shield;}
