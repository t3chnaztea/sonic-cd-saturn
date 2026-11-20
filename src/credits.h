/* "Thank You" ending screen (TITLE/THANKS): Sonic, Amy, Metal Sonic, the
   animals, the Amy hearts, the palette cycle and the best time-attack name.

   Port of the PC reconstruction (ACT.C, BM_M.C, CHRSET.C, DATA_SP.C, ETC_M.C,
   FADE.C, GAME.C, IO.C, SPM.C, SPRMOVE.C, THANKS_TYPES.H), frame for frame.
   tools/test_credits.py runs it against those sources compiled on the host.
   The retail program is THANKS_M.MMD; tools/credits_assets.py checks the
   shared tables against it.  The staff roll itself is not code: it is part of
   the GOODEND.STM / BADEND.STM ending FMV streams.

   Host-portable: no Yaul, no allocation.  Output is a Mega Drive-style frame
   description (two 64x32 name tables, an 80-slot sprite table, a 64-colour
   palette and sound requests) for a renderer to draw. */
#ifndef SCD_CREDITS_H
#define SCD_CREDITS_H

#include <stdint.h>

#define SCD_CREDITS_ACTORS 66
#define SCD_CREDITS_SPRITES 80
#define SCD_CREDITS_NAMES 84      /* timeattack[7][3][3], then special[7][3] */
#define SCD_CREDITS_MAP_WORDS 2048
#define SCD_CREDITS_PLANE_W 64
#define SCD_CREDITS_PLANE_H 32
#define SCD_CREDITS_SOUNDS 8

/* EndingMesType bits (game_info.EndingMesType on the PC). */
#define SCD_CREDITS_MESSAGE_GOOD 1  /* message, then the screen after a button */
#define SCD_CREDITS_MESSAGE_BAD 2   /* message, then exit after a button */
/* The Sega CD program (THANKS_M.MMD): no EndingMes stage (the PC's 360 idle frames
   when it has no message) and the screen palette (colortbl) from the start. */
#define SCD_CREDITS_SEGA_CD 4

/* Pad word as SWdataSet receives it; the low byte's high nibble is A/B/C/Start. */
#define SCD_CREDITS_PAD_BUTTONS 0x00F0

typedef struct {
    int16_t index;       /* sprite cell (PC SprBmp index) */
    uint8_t etc;         /* flip bits XORed into the sprite attributes */
    int16_t hoffs, hrevoffs, voffs, vrevoffs;
} scd_credits_piece;

typedef struct { uint8_t count; uint16_t first; } scd_credits_mapping;
typedef struct { int16_t timer; uint16_t mapping; } scd_credits_pattern_frame;
typedef struct { uint8_t count; uint16_t first; } scd_credits_pattern;

/* sprite_status_thanks. free[4..5] doubles as the little-endian short at
   PC byte offset 62 (the pit-in counter) and free[4] as the signed byte
   there (heart spawn timer), exactly as the PC casts alias them. */
typedef struct {
    uint16_t act_no, exe_no;
    int32_t x, y, x_speed, y_speed, x_accel, y_accel;
    int16_t x_offset, y_offset, sin_cnt, tm_cnt, spr_timer, pat_no, cgbase;
    uint8_t pattern;     /* SCD_CREDITS_PAT_* (PAT_ADR) */
    uint8_t spr_flg, act_flg;
    int16_t end_x, end_y, x_wide, y_wide;
    uint8_t free[8];
} scd_credits_actor;

typedef struct { int16_t x, y; uint16_t index, flags; } scd_credits_sprite;

typedef struct {
    const int16_t *map_a;              /* VA_MAP: 2048 words, NULL when absent */
    const int16_t *map_b;              /* VB_MAP */
    const char (*names)[4];            /* SCD_CREDITS_NAMES save-data initials, NULL = none */
    uint8_t ending_type;               /* SCD_CREDITS_MESSAGE_* bits */
} scd_credits_config;

typedef struct {
    scd_credits_actor actors[SCD_CREDITS_ACTORS];
    uint8_t pribuf[4][65];             /* slot + 1, 0 terminates (PC pribuf0..3) */
    scd_credits_sprite sprites[SCD_CREDITS_SPRITES];
    uint16_t link;                     /* ACT.C LinkData */
    uint16_t sprite_overflow;          /* EAsprset calls with link >= 80 */
    uint16_t plane[2][SCD_CREDITS_PLANE_H * SCD_CREDITS_PLANE_W];
    uint8_t palette[64][3];            /* lpcolorwk0, PC 0..255 channels */
    uint16_t sounds[SCD_CREDITS_SOUNDS];  /* original sound IDs requested this frame */
    uint8_t sound_count;
    int16_t actset_tm[8];
    int16_t end_timer, heart_tm, animal_timer, posetimer;
    int16_t coltimer, colorno, coltimer2, colorno2, prg_mode;
    uint16_t message_timer;            /* gEndingMesTimer */
    uint16_t swdata1;
    uint8_t animal_flg, poseno, quit_flg, ending_type;
    int32_t ranum;
    struct { int16_t pts; char name[4]; } score[SCD_CREDITS_NAMES];
    char greatest[4];
    /* SCD_CREDITS_SEGA_CD: 0 fade from black, 1 running, 2 fade to black, 3 done; the
       step count and the colours shown (Mega Drive words) and faded towards. */
    uint8_t md_phase, md_count;
    uint16_t md_cram[64], md_target[64];
    const scd_credits_config *config;
} scd_credits;

/* One Mega Drive sprite piece of THANKS_M.MMD's mappings (12 bytes there). */
typedef struct {
    uint8_t size, etc;
    uint16_t tile;
    int16_t hoffs, hrevoffs, voffs, vrevoffs;
} scd_credits_md_piece;

#define SCD_CREDITS_MD_SPRITES 80

/* The Sega CD picture of one frame: what THANKS_M.MMD's V-int sends to the VDP. */
typedef struct {
    uint16_t sat[SCD_CREDITS_MD_SPRITES][4];   /* y+128, size<<8 | link, attr, x+128 */
    uint8_t sprites;                           /* linked entries 0..sprites-1 */
    uint16_t cram[64];                         /* Mega Drive colours of the palette */
    /* Plane A rows 12-15, columns 17-22 (dsp_usrname's name): tile words, 0 = the map's. */
    uint16_t names[4][6];
} scd_credits_md;

/* game_init: clears the work RAM, draws both planes, loads the message
   palette and arms the timers.  The config must outlive the state. */
void scd_credits_init(scd_credits *st, const scd_credits_config *config);
/* SWdataSet(pad) + game(): 0 while running, -1 when the screen ends.  In
   SCD_CREDITS_SEGA_CD mode one call is one Mega Drive frame of THANKS_M.MMD from its
   fade from black to the end of its fade to black. */
int scd_credits_frame(scd_credits *st, uint16_t pad);
/* PC random() (THANKS_M.MMD $FF3CF6 in SCD_CREDITS_SEGA_CD mode): returns the next value and advances ranum. */
int32_t scd_credits_random(scd_credits *st);
/* The frame just run as THANKS_M.MMD draws it: the sprite list rebuilt from the
   actors with the retail Mega Drive mappings (THANKS_M.MMD's pattern counts; its
   m_furi_map holds one frame), the palette as Mega Drive words and the name tiles
   with the Sega CD tile base.  No sprites when the tables were built without the disc. */
void scd_credits_md_frame(const scd_credits *st, scd_credits_md *out);
/* One step of THANKS_M.MMD's fades ($FF3EB8, $FF3F2E; Sonic 1's FadeIn_AddColour and
   FadeOut_DecColour on whole words): from black a colour takes +$200 while that does
   not pass its target, else +$20 while that does not, else +2; to black it loses 2
   while it has red, else $20 while it has green, else $200 while it has blue. */
void scd_credits_md_fade_in(uint16_t cram[64], const uint16_t target[64]);
void scd_credits_md_fade_out(uint16_t cram[64]);
#define SCD_CREDITS_MD_FADE_STEPS 22

#endif
