#ifndef SCD_SPECIAL_MODES_H
#define SCD_SPECIAL_MODES_H
/* Special stage mode entries (IPX.asm): attract demos (temporary), Time Attack and
   Special Stage 8 (temporary + secret). The mode code is front-end overlay code
   (src/special_modes.c, fe_ names, src/saturn.x .zone_R0): resident code reaches it
   only through fe_special_zone_ops, read through a volatile pointer, and only while a
   mode run is active, which the front end starts with the overlay loaded. */
#include "special_game.h"
enum {SCD_SPECIAL_TEMPORARY=1,SCD_SPECIAL_TIME_ATTACK=2,SCD_SPECIAL_SECRET=4};
/* attract() results that are not special stages: zone demo n (0 R11A, 1 R43C, 2 R82A;
   src/frontend_view.inc) and the opening FMV. */
enum {SCD_ATTRACT_ZONE_DEMO=0x1000,SCD_ATTRACT_FMV=0x2000};
/* The last mode run: Time Attack time in frames (Sub.asm 9'59"59 cap), aborted when
   UFOs were left (time out, pause exit or Start); pending until the front end takes it. */
typedef struct {uint32_t frames;uint8_t stage,flags,aborted,pending;} scd_special_mode_result;
typedef struct {
    /* scd_special_game_vint for a mode run (flags != 0): the overlay copy of
       src/special_game.c with the mode code. */
    int (*vint)(scd_special_game *game,unsigned pad);
    /* Before the start: the world's mode, the time attack timer and the 1024-byte demoData. */
    void (*begin)(scd_special_world *world,unsigned flags,const uint8_t *demo);
    /* IPX.asm Demo at a title time-out: the run to start as stage | flags << 8, or 0
       for a scene not built (FMV, zone demos). held: bit 0 Saturn X, bit 1 Saturn Y
       (debug entry: X runs Special Stage 8, Y the next Time Attack special stage). */
    unsigned (*attract)(unsigned held);
    /* Fills the result of a finished mode run. */
    void (*finish)(const scd_special_game *game,scd_special_mode_result *result);
    /* Special Stage 8 credits after a won secret stage (src/ss8_credits.c); 0 after
       Start and the fade to black, -1 without cd/SS8CRED.BIN. NULL on the host. */
    int (*credits)(void);
} scd_special_mode_ops;
extern const scd_special_mode_ops fe_special_zone_ops;
extern const scd_special_mode_ops *const volatile scd_special_mode_ops_ref;
static inline const scd_special_mode_ops *scd_special_modes(void){return scd_special_mode_ops_ref;}
/* Resident front-end entry (src/special_game_view.inc): starts special stage 1-8 with
   specStageFlags (SCD_SPECIAL_SECRET|SCD_SPECIAL_TEMPORARY with stage 8 for the sound
   test secret, SCD_SPECIAL_TIME_ATTACK with 1-7 for Time Attack entries 21-27).
   Load the front-end overlay first. Returns 0 when the stage runs; when it ends,
   scd_special_mode_last is filled and the main loop returns to the title. */
int scd_special_mode_start(unsigned stage,unsigned flags);
/* The two front-end entries; 0 when the stage runs. SS8 returns to the title. A Time
   Attack special stage (n 1-7) sets scd_ta.entry; when it ends the main loop sets
   scd_ta.frames, aborted and pending=1 and opens the Time Attack menu (src/time_attack.h). */
int scd_special_ss8_start(void);
int scd_special_ta_start(unsigned n);
extern scd_special_mode_result scd_special_mode_last;
#endif
