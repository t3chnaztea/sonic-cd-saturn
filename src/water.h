#ifndef SCD_WATER_H
#define SCD_WATER_H
/* Tidal Tempest water (retail round index 2): water level, player water
   entry/exit, currents, air countdown, breath bubbles and countdown numbers.
   Ports PLAYER.C plwaterchk, R4/GAME4.C game_init (water part), water1chk..
   water3chk, watercntsub, watercnt, watercoli, and R4/PLAYSUB4.C plairset,
   plawamaster, plawa (bubbles/numbers) and exit2 (entry splash).

   State lives in the original EQU.C globals (waterposi, hintposi, waterflag,
   watercoliflag, pl_air, plmaxspdwk...), so the compiled player core sees it.
   Every entry point is inert outside zone 2. */
#include <stdint.h>

/* Retail frame order (GAME4.C game): ++gametimer; action() [player slot 0
   (water_player_check inside), then actwk[7] master and the dynamic slots
   (water_objects_step)]; scroll(); watercoli (water_currents); patset
   (water_objects_visible); watercnt (water_level_step). */
/* The native camera (top-left world position) as the PC scra_h/v_posit. */
void water_camera(int x,int y);
void water_reset(unsigned zone,unsigned act,unsigned era);
int water_active(void);
void water_tick(void);          /* ++gametimer, before the player */
void water_player_check(void);  /* plwaterchk, player slot */
void water_objects_step(void);  /* actwk[7] master, bubbles, numbers, splash */
void water_currents(void);      /* watercoli, after scroll */
void water_objects_visible(void); /* patset: marks this frame's drawn bubbles */
void water_level_step(void);    /* watercnt, uses scra_v_posit */

/* PLAYSUB4.C plairset: breathe. For AWA.C big bubbles and COLI4.C. */
void water_air_refill(void);
/* Sound requests go through soundset(); plairset's music restore through
   this sink (bgmset ids 130 zone, 134 R43 unused, 135 invincible, 140 boss). */
void water_bgm_sink_set(void (*sink)(short));

/* Raster state for the VDP2 line switch: the first screen line drawn with
   the water palette, 0..224 (224: none). */
unsigned water_screen_line(void);
const uint16_t *water_palette(void); /* RGB1555, 64 entries, current era */

typedef struct {
    int16_t x,y;       /* screen position of the sprite origin */
    uint8_t frame;     /* awapat index (patno) */
    uint8_t line;      /* palette line (sproffset bits 13-14) */
    uint8_t flip;      /* actflg bits 0-1 */
    uint8_t kind;      /* 0 plawa bubble/number, 1 exit2 splash */
} water_sprite;
unsigned water_sprites(water_sprite *out,unsigned capacity);

/* Fixture view of the object state. */
typedef struct {
    uint8_t used,actno,r_no0,actflg,mstno,patno,patcnt,pattim,userflag,direc;
    uint16_t sproffset;
    int32_t x,y;
    int16_t yspeed;
    uint8_t actfree[22];
} water_object;
#define WATER_OBJECT_CAPACITY 24
/* Slot 0 is the actwk[7] master; 1.. are dynamic slots in processing order. */
const water_object *water_objects(void);
/* 1 while dynamic slot I (1..WATER_OBJECT_CAPACITY-1; slot 0 is actwk[7]) holds an
   actor: src/boss.c counts these actwkchk slots in its retail slot order. */
int water_slot_live(unsigned i);
#endif
