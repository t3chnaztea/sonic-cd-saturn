#ifndef SCD_BOSS_H
#define SCD_BOSS_H
#include <stdint.h>
/* Act 3 boss actors live in PC actor slots 97-127; the native object pool owns 1-96. */
#define SCD_BOSS_FIRST_SLOT 97
/* kind 0: frame is an offset from OBJECT_BASE_66 (0-10 Robotnik, 11/12 body,
   13-24 legs and arms). SCD_BOSS_KIND_EXPLOSION: an OBJECT_BASE_24 frame.
   Otherwise kind is a Collision Chaos (240-249) or Tidal Tempest (240-246) zone
   art kind and frame its pose. */
typedef struct {int16_t x,y;uint8_t frame,flags,priority;uint16_t kind;} scd_boss_view;
#define SCD_BOSS_KIND_EXPLOSION 24u
/* Placement subtype bits (tools/object_layouts.py) for the Collision Chaos boss actors. */
#define SCD_BOSS_EGG3DAI_L 64u
#define SCD_BOSS_EGG3DAI_S 32u
/* Tidal Tempest: egg4air (actor 74), egg4 (76) and the layout wall4 (71). */
#define SCD_BOSS_EGG4AIR 16u
#define SCD_BOSS_EGG4 8u
#define SCD_BOSS_WALL4 4u
/* Quartz Quadrant: the layout egg5meca1 (51) and egg5hari (33). */
#define SCD_BOSS_EGG5MECA1 2u
#define SCD_BOSS_EGG5HARI 1u
/* Line 1 overrides: BOSS is COL1C/D.C's boss palette, BOSS3/FLASH3 COL3C/D.C's
   zone3colboss1 and zone3colboss0, BOSS4 COL4C/D.C's boss4color. */
enum {SCD_BOSS_PALETTE_LEVEL,SCD_BOSS_PALETTE_BOSS,SCD_BOSS_PALETTE_CAPSULE,SCD_BOSS_PALETTE_BOSS3,SCD_BOSS_PALETTE_FLASH3,SCD_BOSS_PALETTE_BOSS4,SCD_BOSS_PALETTE_BOSS5,SCD_BOSS_PALETTE_BOSS6,SCD_BOSS_PALETTE_BOSS7,SCD_BOSS_PALETTE_BOSS8};
/* FINAL: LOADER2.C sub_sync(104), CD track 25 (BOSS_8.C egg8_open1). */
enum {SCD_BOSS_MUSIC_NONE=-1,SCD_BOSS_MUSIC_ZONE,SCD_BOSS_MUSIC_BOSS,SCD_BOSS_MUSIC_FINAL};
void scd_boss_reset(void);
/* R7 changes six boss colors, then Amy replaces line 1. */
void scd_boss7_palette(uint16_t *line,unsigned bad,int restore);
void scd_boss_create(int x,int y);
/* round: the original round number (1, 3, 4, ...); subtype bits pick the actor. */
void scd_boss_create_sub(int x,int y,unsigned subtype,unsigned round);
void scd_boss_set_round(unsigned round);
/* R6 BOSS_6.C egg6door (src/boss_r6.c): kind = userflag.b.h, floor = userflag.b.l. */
void scd_boss6_door(int x,int y,unsigned kind,unsigned floor);
/* 1 while no boss or the Palmtree Panic boss runs, 3 for Collision Chaos, 4 for Tidal Tempest. */
unsigned scd_boss_round(void);
/* Updates since BOSS_6.C set bossstart=6; zero during the entry scene. */
unsigned scd_boss6_art_age(void);
void scd_boss_camera(int x,int y);
void scd_boss_step(void);
/* SS3 merged actor pass: run boss slots below each ordinary actor slot. */
void scd_boss_step_begin(void);
void scd_boss_step_before(unsigned upper);
unsigned scd_boss_views(scd_boss_view *views,unsigned capacity);
int scd_boss_palette(void);
void scd_boss_palette_set(int state);
int scd_boss_music(void);
/* BOSS_8.C's PLC request (4 fight bank, 5 Amy), once; 0 for none (src/zone_object_view.inc). */
int scd_boss_fight_art(void);
void scd_boss8_plc(int plc);
/* EMIE8.C has ended the game (Metallic Madness Act 3). */
int scd_boss8_game_end(void);
/* 1 and EMIE8.C's held buttons while it steers Sonic (plautoflag). */
int scd_boss8_auto_control(unsigned *buttons);
/* Entries BOSS_8.C/EMIE8.C wrote to lpcolorwk replace the 64-entry CRAM image. */
void scd_boss8_palette(uint16_t *pal);
/* R8 overlay (src/boss_r8.c): MM3 explosion CLUT copies that follow palette line 0;
   src/main.c mm3_palette calls it while round 8 is loaded. */
extern void (*const volatile r8_explosion_cluts)(const uint16_t *pal,uint8_t *state,volatile uint16_t *copies,const volatile uint16_t *atlas,
    const unsigned *offsets,const unsigned *widths,const unsigned char *heights,unsigned first,unsigned count);
int scd_boss_active(void);
/* Robotnik (actor 42; Collision Chaos egg3dai_l, 49; Tidal Tempest egg4air, 74,
   then egg4, 76): X<<16|Y, and 1<<16|r_no0<<8|hit count (actfree[1]; R3
   actfree[17]; R4 colicnt, hits left, with 1<<17 for egg4); 0 when absent. */
uint32_t scd_boss_position(void);
uint32_t scd_boss_status(void);
uint32_t scd_boss_hash(void);
#endif
