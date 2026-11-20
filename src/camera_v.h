#ifndef SCD_CAMERA_V_H
#define SCD_CAMERA_V_H
#include <stdint.h>
/* Original vertical camera (SCR*.C scroll_v family) on scra_v_posit.
   zone is the retail round index (stageno.b.h), era 0 Present .. 3 Bad Future. */
void scd_camera_v_select(unsigned zone,unsigned act,unsigned era);
int scd_camera_v_start(int player_y);  /* playposiset + game_init's scroll() */
void scd_camera_v_set(int camera_y);
int scd_camera_v_step(void);           /* per gameplay update, after the player */
/* One call per load and per update, for src/main.c and every host copy of it. */
int scd_camera_v_begin(unsigned zone,unsigned act,unsigned era,int player_y,unsigned resets);
int scd_camera_v_follow(int player_y,unsigned resets);
void scd_camera_v_sync(int camera_y);
/* Original horizontal camera on scra_h_posit: scd_camera_v_start/step run
   scroll_h before scroll_v; PLAYER.C scr_h (src/player.c) moves scra_hline. */
int scd_camera_h_step(void);      /* scroll_h alone (fixtures) */
int scd_camera_v_scroll(void);    /* scroll_v alone (fixtures) */
int scd_camera_h(void);
void scd_camera_h_sync(int camera_x);
/* Background Y hooks (weak no-ops in camera_v.c; src/main.c defines them):
   scrbinit after playposiset, and scroll()'s scrollb_hv after each scroll_v. */
void scd_camera_v_bg_reset(int32_t *scrb_v_posit,int camera_top);
void scd_camera_v_bg_scroll(int32_t *scrb_v_posit,int16_t scra_vz);
#endif
