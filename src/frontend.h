#ifndef SCD_FRONTEND_H
#define SCD_FRONTEND_H
#include <stdint.h>
#include "stage_select.h"
/* Front-end screens. Their code is fe_ (src/frontend.c, src/saturn.x .zone_R0);
   resident code reaches it only through fe_frontend_zone_ops after
   scd_frontend_overlay_load() (src/zone_code.h). */
enum { SCD_FE_TIME_ATTACK=1, SCD_FE_SOUND_TEST=2, SCD_FE_VISUAL=3, SCD_FE_STAFF_TIMES=4, SCD_FE_STAGE_SELECT=5, SCD_FE_COMING=6 };
/* Step results. */
enum { SCD_FE_CONTINUE, SCD_FE_TITLE, SCD_FE_TA_START, SCD_FE_SPECIAL8, SCD_FE_REDRAW, SCD_FE_STAGE_SELECT_CHOICE };
/* Mega Drive pad bits (retail ctrlHold/ctrlTap). */
enum { SCD_PAD_UP=1, SCD_PAD_DOWN=2, SCD_PAD_LEFT=4, SCD_PAD_RIGHT=8,
       SCD_PAD_B=16, SCD_PAD_C=32, SCD_PAD_A=64, SCD_PAD_START=128 };
typedef struct {
    void (*enter)(unsigned screen);
    unsigned (*step)(unsigned hold,unsigned tap);
    /* Title flags from the Time Attack file and the progress save (zones cleared). */
    unsigned (*title_flags)(unsigned zones_cleared);
    /* Copy selector data while R0 is loaded, before any program replaces it. */
    int (*stage_select_snapshot)(unsigned selected,fe_stage_select_choice *choice,unsigned *previous_hold);
    /* Existing R0 movie entry, reached only through this resident table. */
    int (*movie)(unsigned id);
} scd_frontend_ops;
extern const scd_frontend_ops fe_frontend_zone_ops;
/* Read through a volatile pointer: LTO must not devirtualize the table and inline
   overlay code into resident callers (it did, and the heap ASSERT failed). */
static inline const scd_frontend_ops *scd_frontend_ops_get(void){
    const scd_frontend_ops *volatile ops=&fe_frontend_zone_ops;return ops;
}
/* Reads cd/DEMOS.BIN into the title pack region; 1 on success (overlay code). */
int fe_demo_load(void);
/* Plays movie id (src/fmv_saturn.h) from overlay code and restores the sprite
   priorities and the effect bank; sets scd_low_packs_lost (overlay code). */
enum { FE_MOVIE_FROM_TITLE=0x100 };
int fe_frontend_movie(unsigned id);
/* Set when a movie took low work RAM (PPZ0-PPZ2 packs): new_game() reloads them. */
extern uint8_t scd_low_packs_lost;
/* Resident drawing helpers (src/main.c) for front-end screens. */
void scd_frontend_text(int x,int y,const char *text);
void scd_frontend_panel(int x,int y,int width,int height,uint16_t color);
#endif
