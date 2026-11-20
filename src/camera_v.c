/* Original camera. The per-program scroll_h and scroll_v texts are compiled
   verbatim in build/probe-source/camera_v_variants.inc (tools/camera_source.py);
   this file selects the program's texts and runs the parts of GAME.C/GAME4.C,
   scr_set/playposiset and PLAYER.C scr_h around them. */
#include "EQU.H"
#include "camera_v.h"

/* One translation unit: every host that links this file gets the same texts. */
#include "camera_v_variants.inc"
static void (*scroll_v)(void),(*scroll_h)(void);
/* Background Y hooks (src/main.c defines them for Tidal Tempest): bg_reset is
   scrbinit after playposiset, bg_scroll is scroll()'s scrollb_hv after each
   scroll_v. Hosts without a background link these no-ops. */
__attribute__((weak)) void scd_camera_v_bg_reset(int32_t *scrb,int camera_top){(void)scrb;(void)camera_top;}
__attribute__((weak)) void scd_camera_v_bg_scroll(int32_t *scrb,int16_t vz){(void)scrb;(void)vz;}
static void scroll_v_bg(void){scroll_v();scd_camera_v_bg_scroll((int32_t *)&scrb_v_posit.l,scra_vz);}

/* SCRCHK.C scrchk for Quartz Quadrant (retail R51A-R53D $203586 via the round
   table at $2033CE): zone51chk aims the bottom bound at 784 in acts 1 and 2;
   zone53chk aims it at 800, or holds it at 504 once BOSS_5.C sets bossflag,
   and past X 3600 bossclr_scr(3600,504) locks the left bound behind Sonic.
   scrchk then moves the bottom bound 4 lines per update toward the aim. The
   other rounds run their scrchk in src/main.c and the hosts. Runs where the
   SCR5*.C scroll() calls it: before scroll_h/scroll_v. */
static int scrchk_act=-1;
static void scrchk_bottom(void){
    if(actwk[0].mstno.b.h==43)scralim_down=scralim_n_down=scra_v_posit.w.h;
    short d1=4;
    if(scralim_n_down==scralim_down)return;
    if((unsigned short)scralim_n_down<(unsigned short)scralim_down){
        d1=-d1;
        if((unsigned short)scralim_n_down<(unsigned short)scra_v_posit.w.h)scralim_down=scra_v_posit.w.h&65534;
        scralim_down+=d1;limmoveflag=1;return;
    }
    if((unsigned short)(scra_v_posit.w.h+8)>=(unsigned short)scralim_down && (actwk[0].cddat&2))d1*=4;
    scralim_down+=d1;limmoveflag=1;
}
static void scrchk_r5(void){
    if(scrchk_act<2)scralim_n_down=784;
    else{
        int locked=0;
        if(actwk[0].xposi.w.h>=3600){
            unsigned short d=(unsigned short)(504-scralim_down);
            scralim_n_down=504;
            if((short)d<0)d=(unsigned short)-(short)d;
            if(d<4)scralim_down=scralim_n_down;
            unsigned short x=(unsigned short)actwk[0].xposi.w.h-160;
            if(scralim_left<=(short)x){
                if(scralim_right<(short)x)x=(unsigned short)scralim_right;
                scralim_left=scralim_n_left=(short)x;
            }
            locked=1;
        }
        if(!locked){
            if(bossflag)scralim_down=scralim_n_down=504;
            else scralim_n_down=800;
        }
    }
    scrchk_bottom();
}

/* SCRCHK.C zone7chk / _Events.asm LevEvents_SSZ: Act 2 extends down to
   1808, including the lower tube/spring route. Act 3 tightens the camera
   while approaching Metal Sonic, then restores the race track boundary. */
static int scrchk_r7_act=-1;
static void scrchk_r7(void){
    if(scrchk_r7_act==0)scralim_n_down=1296;
    else if(scrchk_r7_act==1)scralim_n_down=1808;
    else if(actwk[0].xposi.w.h<2352 || actwk[0].xposi.w.h>=3520)scralim_n_down=528;
    else{
        scralim_n_down=288;
        unsigned short d=(unsigned short)(288-scralim_down);
        if((short)d<0)d=(unsigned short)-(short)d;
        if(d<4)scralim_down=288;
    }
    scrchk_bottom();
}
/* _Events.asm LevEvents_PPZ1 (US order: before ScrollCamX/Y): in the Present,
   while Sonic is within the second 3D ramp (X $1C16-$21C5) the camera Y centre
   is $88; Sonic's move routines then ease it back to 96. */
static int ppz1_present;
static void scrchk_ppz1(void){
    unsigned short x=(unsigned short)actwk[0].xposi.w.h;
    if(x>=0x1C16 && x<0x21C6)scra_vline=0x88;
}
static void scroll_frame(void){if(ppz1_present)scrchk_ppz1();if(scrchk_act>=0)scrchk_r5();if(scrchk_r7_act>=0)scrchk_r7();scd_camera_h_step();if(scroll_v)scroll_v_bg();}
void scd_camera_v_select(unsigned zone,unsigned act,unsigned era){
    scrchk_act=zone==3?(int)act:-1;
    ppz1_present=zone==0 && act==0 && (era&3)==0;
    scrchk_r7_act=zone==5?(int)act:-1;
    unsigned v=scd_camera_v_variant[zone<7?zone:0][act<3?act:0][era&3];
    if(v==255)v=scd_camera_v_variant[zone<7?zone:0][act<3?act:0][2];
    scroll_v=scd_camera_v_variants[v];
    v=scd_camera_h_variant[zone<7?zone:0][act<3?act:0][era&3];
    if(v==255)v=scd_camera_h_variant[zone<7?zone:0][act<3?act:0][2];
    scroll_h=scd_camera_h_variants[v];
}
/* scroll() runs scroll_h first. */
/* scroll_v alone (fixtures). */
int scd_camera_v_scroll(void){if(scroll_v)scroll_v_bg();return scra_v_posit.w.h;}
int scd_camera_h_step(void){if(scroll_h)scroll_h();return scra_h_posit.w.h;}
int scd_camera_h(void){return scra_h_posit.w.h;}
void scd_camera_h_sync(int camera_x){if(scra_h_posit.w.h!=(short)camera_x)scra_h_posit.l=(int)(short)camera_x<<16;}
/* SCR*.C scr_set: centre 160, then playposiset: the camera left starts 160
   left of Sonic (0 when nearer), clamped to scralim_right, and the camera top
   starts 96 lines above Sonic, clamped to 0..scralim_down; GAME.C game_init
   then runs scroll() (scroll_h, scroll_v) once. */
int scd_camera_v_start(int y){
    short x=actwk[0].xposi.w.h;
    if((unsigned short)x>160)x-=160;else x=0;
    if((unsigned short)scralim_right<(unsigned short)x)x=scralim_right;
    scra_hline=160;scra_h_posit.l=(int)x<<16;scra_hz=0;
    short w=(short)y;
    if((unsigned short)w>96)w-=96;else w=0;
    if(scralim_down<w)w=scralim_down;
    scra_v_posit.l=(int)w<<16;scra_vz=0;limmoveflag=0;
    scd_camera_v_bg_reset((int32_t *)&scrb_v_posit.l,scra_v_posit.w.h);
    if(!scroll_start.b.h)scroll_frame();
    return scra_v_posit.w.h;
}
/* The camera already on screen (time travel arrival, fixtures). */
void scd_camera_v_set(int y){scra_v_posit.l=(int)(short)y<<16;}
/* GAME.C/GAME4.C game: a dead Sonic (r_no0 >= 6) freezes the camera and pins
   both bottom bounds to it; otherwise scroll(), which returns while
   scroll_start is set (drowning), runs scroll_v after scroll_h. */
int scd_camera_v_step(void){
    if(actwk[0].r_no0>=6)scralim_down=scralim_n_down=scra_v_posit.w.h;
    else if(!scroll_start.b.h){
        /* The level events (scddisasm Level/_Events.asm:12-15, SCRCHK.C:63;
           retail R82C $203580, which SCRCHK8.C lacks) pin both bottom bounds
           to the camera while Sonic gives up (animation 43, PLAYER.C bye_chk),
           after the zone's own check: he falls out of view (retail MM2C row
           18515). The zone checks run before this step in main.c and the hosts. */
        if(actwk[0].mstno.b.h==43)scralim_down=scralim_n_down=scra_v_posit.w.h;
        scroll_frame();
    }
    return scra_v_posit.w.h;
}
/* Host/main helper: select the program and start from Sonic's Y. */
static unsigned seen_resets;
int scd_camera_v_begin(unsigned zone,unsigned act,unsigned era,int player_y,unsigned resets){
    scd_camera_v_select(zone,act,era);seen_resets=resets;
    return scd_camera_v_start(player_y);
}
/* Per gameplay update: a restart (player resets changed) reruns playposiset. */
int scd_camera_v_follow(int player_y,unsigned resets){
    if(resets!=seen_resets){seen_resets=resets;return scd_camera_v_start(player_y);}
    return scd_camera_v_step();
}
/* After the caller's own locks/clamps: the camera on screen is scra_v_posit. */
void scd_camera_v_sync(int camera_y){if(scra_v_posit.w.h!=(short)camera_y)scd_camera_v_set(camera_y);}
