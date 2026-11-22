/* Saturn playback of the Sonic CD movies (opening, good ending, bad ending).
 *
 * The disc carries cd/OPN.FMV, GOODEND.FMV and BADEND.FMV, built from the
 * user's STM streams by tools/fmv_convert.py (layout there). fmv_play streams
 * one from CD and plays it to the end:
 *   - PCM goes straight from the CD block into a 64 KB SCSP ring (sound RAM
 *     FMV_RING_ADDR) played by slot FMV_SLOT at the RF5C164 rate (FD $080C,
 *     32,744 Hz; the nearest SCSP pitch is OCT -1 FNS 497, 32,752 Hz). The
 *     slot's play address (SCSP $408 CA, 4 KB blocks) plus the FRT between
 *     block changes is the clock every picture and credits step is timed on.
 *   - Pictures (an "08"/opening frame: 32 x 14 tiles, 8 fps; an ending "15"
 *     frame: 15 x 10 tiles, 15 fps; the SR window) are copied into one of two
 *     VDP2 4bpp cell buffers with their palette (RGB555) in that buffer's CRAM
 *     bank; NBG0 shows one buffer, and the swap is its scroll register,
 *     committed at V-blank, as FMV/Main swaps plane A by H-scroll.
 *   - The ending tags follow ENDING.MMD's Main CPU program (tools/fmv_convert.py
 *     checks the program data it copies): SR loads the roll's text tiles (US
 *     720, JP 990), shows the window picture and starts the staff roll (NBG1,
 *     US 0.566 / JP 0.625 lines per Mega Drive V-blank, one table row every 8
 *     lines; both counts come from ENDING.MMD in the FMV header); NO holds; RS shows
 *     the end screen and fades its two colours in; "08" packets resume video. After
 *     the stream ENDING.MMD's last routine ($FFC100) fades the screen out and shows
 *     the "PRESENTED BY SEGA" card: fade in, hold (US 600 V-blanks or Start held,
 *     Japanese until Start is held), fade out.
 *   - The pencil test (cd/PTEST.FMV, no PCM) follows PTEST.MMD (Main CPU; the
 *     timing is measured from it by tools/fmv_retail.py ptest): the border
 *     (NBG1, MD palette line 1, also the back screen colour) fades in 8 steps
 *     of 8 fields; the first picture (21 x 14 tiles at plane A column 9, row
 *     7) shows 90 fields after fade step 0, then one picture per 1/15 s on
 *     the FRT (the 1x CD rate that paces retail); line 1 colour 5 becomes
 *     $0644 with the first picture (PTEST.MMD's V-int). 64 fields after the
 *     last picture, the border and the picture fade out through the same
 *     table, 8 fields a step; the movie ends 8 fields after step 0. Start
 *     does nothing (PTEST.MMD never calls its pad check).
 *
 * Resources it takes over while playing (the caller restores what it needs):
 *   low work RAM 0x00200000-0x00247FFF (stage packs PPZ0-PPZ2 and the start of
 *   PPZ3 live there; scd_low_packs_lost reloads PPZ0-COL3),
 *   sound RAM FMV_RING_ADDR..+64 KB (the tail of the zone effect bank),
 *   SCSP slot FMV_SLOT, the CD block, NBG0/NBG1, VDP2 VRAM bank A0, CRAM
 *   banks 0-7 (16-colour), the back screen colour and sprite priorities.
 * fmv_play restores the VDP2 registers (Yaul shadow) and CRAM banks 0-7 it changed;
 * VRAM bank A0 and the line scroll table stay overwritten.
 * On return the display is off (back screen black) and the drive is paused. */
#ifndef SCD_FMV_SATURN_H
#define SCD_FMV_SATURN_H

#include <stdint.h>

typedef enum {
    FMV_OPENING = 0,  /* OPN.STM, Sega logo to title */
    FMV_GOODEND = 1,  /* GOODEND.STM, endingID $7F */
    FMV_BADEND = 2,   /* BADEND.STM, endingID 0 */
    FMV_PTEST = 3     /* PTEST.STM, the pencil test (Visual Mode) */
} fmv_id_t;

/* Play one movie to its end. Returns 0 when it played out, 1 when Start
 * skipped it (opening only, as the original allows), negative on a disc
 * error (file missing or not the expected format). */
int fmv_play(fmv_id_t id);

/* Test mode for the emulator harness (tools/test_fmv_emulator.py): when
 * scd_fmv_mailbox[0] holds FMV_TEST_REQUEST | (id + 1), plays that movie and
 * returns 1; otherwise returns 0 at once. Called from the boot path by the
 * main.c patch in the FMV hand-off. */
int fmv_test_boot(void);

#define FMV_TEST_REQUEST 0x464D5600u   /* "FMV" << 8 */
#define FMV_MAILBOX_PLAYING 0x464D5650u  /* "FMVP" */
#define FMV_MAILBOX_DONE 0x464D5644u     /* "FMVD" */
#define FMV_CARD_PICTURE 0xCA000000u

/* Published every V-blank while playing (read by the harness):
 *  [0] request   [1] state "FMVP"/"FMVD"   [2] result
 *  [3] picture shown this field (global index, 0-based; SR window counts)
 *  [4] audio position in samples at the field's start
 *  [5] pictures shown  [6] pictures dropped  [7] fields a picture was late
 *  [8] fields played   [9] largest |display - due| in samples
 * [10] sectors read    [11] times a picture's data was not ready when due
 * [12] staff-roll steps (MD V-blanks)  [13] last CD error  [14] field of the last swap
 * [15] packet of the picture shown
 * Endings, after the stream: [3] FMV_CARD_PICTURE | phase << 16 | count for the
 * "PRESENTED BY SEGA" card (phase 1 fading the end screen out, 2 loading, 3 fading
 * in, 4 holding, 5 fading out; count: steps or V-blanks in the phase)
 * Pencil test: [4] FRT ticks since the first picture's slot, [9] largest
 * |display - due| in FRT ticks, [12] fade: phase << 8 | step (phase 1 fading
 * in, 2 playing, 3 fading out), and FMV_LWRAM_LOG holds the field (16 bits)
 * each picture was swapped in, [8] counting from 0 at fade step 0. */
#ifdef SCD_ZONE_OVERLAY
/* Saturn build: the mailbox and the player state sit in low work RAM after the
 * stream resources (LWRAM_RES + 32 KB), cache-through for the harness. The
 * movie owns 0x00200000 up to FMV_LWRAM_END, the PPZ0-PPZ2 era pack regions
 * (src/stage_packs.h), which the caller reloads. */
#define FMV_LWRAM_STATE 0x00243000u
#define FMV_LWRAM_END 0x00248000u
#define scd_fmv_mailbox ((volatile uint32_t *)(FMV_LWRAM_STATE | 0x20000000u))
#define FMV_LWRAM_LOG (FMV_LWRAM_STATE + 0x3000u)   /* up to 2 KB, cache-through */
#define scd_fmv_log ((volatile uint16_t *)(FMV_LWRAM_LOG | 0x20000000u))
#else
extern volatile uint32_t scd_fmv_mailbox[16];
extern volatile uint16_t scd_fmv_log[1024];
#endif
#define FMV_LOG_ENTRIES 1024u

#define FMV_SLOT 31u
#define FMV_RING_ADDR 0x6F000u      /* sound RAM offset, 64 KB, below $7F000 */
#define FMV_RING_BYTES 0x10000u

/* Stream format (tools/fmv_convert.py). */
#define FMV_SAT_MAGIC 0x53464D56u   /* "SFMV" */
#define FMV_SAT_VERSION 1u
#define FMV_SAT_PACKET_SECTORS 75u
#define FMV_SAT_PCM_SECTORS 16u
#define FMV_SAT_CHUNK_BYTES (FMV_SAT_PCM_SECTORS * 2048u)
#define FMV_SAT_PCM_PER_PACKET 32760u
/* Ending header bytes 116-127 (tools/fmv_convert.py, from ENDING.MMD): the
   "PRESENTED BY SEGA" card's map row, column, width and height in plane A cells
   (bytes), the roll step (addi.l #step,$C08A; 16.16 lines per V-blank, 32-bit), the
   SR packet's tile count and the card's hold in V-blanks (0: until Start is held;
   US 600, Japanese 0), 16-bit, big endian. */
/* Ending header bytes 112-113: the V-blanks ENDING.MMD waits once the Sub CPU reports
   the stream's end, before the card ($FF214E: move.w #n,d1; VSync; dbf: n + 1). */
#define FMV_SAT_END_WAIT 112u
#define FMV_SAT_CARD 116u
#define FMV_SAT_ROLL_SPEED 120u
#define FMV_SAT_STILL_TILES 124u
#define FMV_SAT_CARD_HOLD 126u
enum {
    FMV_RES_CRAM, FMV_RES_SR_PALETTE, FMV_RES_SR_WINDOW, FMV_RES_FADE,
    FMV_RES_CREDITS, FMV_RES_END_ROWS, FMV_RES_END_TILES,
    FMV_RES_CARD_TILES, FMV_RES_CARD_MAP, FMV_RES_CARD_PALETTE, FMV_RES_COUNT
};
/* PTEST.FMV (kind 2): byte 20 of the header is the picture count, no PCM. */
enum { FMV_PRES_TILES, FMV_PRES_MAP, FMV_PRES_FADE, FMV_PRES_COUNT };
#define FMV_MUTE_KIND 2u

#endif
