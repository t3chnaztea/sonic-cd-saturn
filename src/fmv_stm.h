/* Sonic CD STM (FMV stream) decoder.
 *
 * Layout follows the scddisasm reference and the retail ENDING.MMD program:
 *   CD System Program/SP.asm ReadFMVSectors: a packet of 75 sectors (1 s at
 *     1x). Sectors 0-15 go to the PCM buffer, sectors 16-74 to a Word RAM bank.
 *   FMV/Main (Opening).asm: 8 frames per Word RAM bank. A frame is a 16-color
 *     palette line (32 bytes, Mega Drive 0000BBB0GGG0RRR0 words) and three DMA
 *     sections ($12C0 + $12C0 + $1280 bytes) of 4bpp tiles, 448 tiles in all.
 *     DrawFMVTilemaps lays them row-major, 32 x 14 tiles (256 x 112 pixels).
 *   FMV/Sub (Opening).asm, Sub (Ending).asm: each packet streams 8 wave banks
 *     of $FFF bytes (RF5C164 sign-magnitude 8-bit) at FD $080C.
 *   ENDING.MMD (Main CPU, not in the disassembly; see tools/fmv_extract.py):
 *     every Word RAM bank starts with a 16-byte header whose first word is an
 *     ASCII tag:
 *       "08" 8 frames as above.
 *       "SR" credits font: 4 x 5760 bytes (720 tiles) to VRAM $14C0 (tile
 *            $A6 on); the palette comes from ENDING.MMD, not the stream.
 *       "15" 15 frames of 32-byte palette + 4800 bytes (150 tiles) to VRAM
 *            $0200 at 15 fps. ENDING.MMD's plane A map (file offset $C06)
 *            shows tiles $10-$A5 as a 15 x 10 tile window (120 x 80 pixels)
 *            at the top left of the picture area; the credits scroll on
 *            plane B beside it.
 *       "NO" no picture data (the credits scroll continues).
 *       "RS" end screen (ENDING.MMD V-int job 11: CRAM cleared, the
 *            end text drawn on plane B and faded in); "08" packets follow.
 * PTEST.STM (the pencil test) is the mute format:
 *   CD System Program/SP.asm ReadMuteFMVSectors (1001-1139): no PCM part;
 *     every 5 sectors (.GfxDone, feFMVSectFrame = 5) fill one Word RAM bank
 *     of $2800 bytes, then the banks swap: 15 banks a second at 1x.
 *     FileEngine_LoadMuteFMV counts the file's sectors as size / $800 - 1
 *     (.GetSectors), so the last sector is never read and the last bank is
 *     never handed over.
 *   PTEST.MMD (Main CPU, not in the disassembly; tools/fmv_convert.py checks
 *     the code it relies on): each bank is a 16-byte header (tag "15", not
 *     acted on), a 32-byte palette and 294 tiles (4800 + 4608 bytes in two
 *     DMAs) to VRAM $0200 or $26C0, shown as 21 x 14 tiles (168 x 112) at
 *     plane A column 9, row 7, over a plane B border (palette line 1).
 *
 * Portable C: the host tools and src/fmv_saturn.c (Saturn playback) share it. */
#ifndef FMV_STM_H
#define FMV_STM_H

#include <stddef.h>
#include <stdint.h>

#define FMV_SECTOR_BYTES 2048u
#define FMV_CYCLE_SECTORS 75u
#define FMV_PCM_SECTORS 16u
#define FMV_GFX_SECTORS (FMV_CYCLE_SECTORS - FMV_PCM_SECTORS)
#define FMV_CYCLE_BYTES (FMV_CYCLE_SECTORS * FMV_SECTOR_BYTES)
#define FMV_GFX_OFFSET (FMV_PCM_SECTORS * FMV_SECTOR_BYTES)
#define FMV_GFX_BYTES (FMV_GFX_SECTORS * FMV_SECTOR_BYTES)
#define FMV_HEADER_BYTES 16u /* ending streams only */
#define FMV_PALETTE_BYTES 32u
#define FMV_TILES_W 32u
#define FMV_TILES_H 14u
#define FMV_TILE_BYTES 32u
#define FMV_TILE_COUNT (FMV_TILES_W * FMV_TILES_H)
#define FMV_FRAME_BYTES (FMV_PALETTE_BYTES + FMV_TILE_COUNT * FMV_TILE_BYTES)
#define FMV_FRAMES_PER_CYCLE 8u
#define FMV_ANIM_TILES_W 15u
#define FMV_ANIM_TILES_H 10u
#define FMV_ANIM_TILES (FMV_ANIM_TILES_W * FMV_ANIM_TILES_H)
#define FMV_ANIM_FRAME_BYTES (FMV_PALETTE_BYTES + FMV_ANIM_TILES * FMV_TILE_BYTES)
#define FMV_ANIM_FRAMES 15u
#define FMV_MUTE_BANK_SECTORS 5u
#define FMV_MUTE_BANK_BYTES (FMV_MUTE_BANK_SECTORS * FMV_SECTOR_BYTES)
#define FMV_MUTE_TILES_W 21u
#define FMV_MUTE_TILES_H 14u
#define FMV_MUTE_TILES (FMV_MUTE_TILES_W * FMV_MUTE_TILES_H)
#define FMV_MUTE_FRAME_BYTES (FMV_PALETTE_BYTES + FMV_MUTE_TILES * FMV_TILE_BYTES)
#define FMV_WIDTH (FMV_TILES_W * 8u)
#define FMV_HEIGHT (FMV_TILES_H * 8u)
#define FMV_PCM_BANKS 8u
#define FMV_PCM_BANK_BYTES 0xFFFu /* original copies $FFF of every $1000 */
#define FMV_PCM_CYCLE_BYTES (FMV_PCM_BANKS * FMV_PCM_BANK_BYTES)
#define FMV_PCM_FD 0x080Cu
/* RF5C164 base rate 12.5 MHz / 384; output rate = base * FD / 2048. */
#define FMV_PCM_RATE_NUM (12500000u * FMV_PCM_FD)
#define FMV_PCM_RATE_DEN (384u * 2048u)

typedef enum {
    FMV_STREAM_OPENING = 0, /* OPN.STM: no packet headers */
    FMV_STREAM_ENDING = 1,  /* GOODEND.STM, BADEND.STM */
    FMV_STREAM_MUTE = 2     /* PTEST.STM: 5-sector banks, no PCM */
} fmv_stream_kind_t;

typedef enum {
    FMV_PACKET_VIDEO = 0, /* "08" or opening packet */
    FMV_PACKET_STILL,     /* "SR" */
    FMV_PACKET_ANIM,      /* "15" */
    FMV_PACKET_HOLD,      /* "NO" */
    FMV_PACKET_RESUME,    /* "RS" */
    FMV_PACKET_EMPTY,     /* zero header (end padding) */
    FMV_PACKET_UNKNOWN,
    FMV_PACKET_MUTE       /* one PTEST.STM bank: one 21 x 14 picture */
} fmv_packet_type_t;

typedef struct {
    fmv_packet_type_t type;
    const uint8_t *gfx;    /* first byte after the header */
    size_t gfx_bytes;      /* bytes of the Word RAM bank present in the file */
    unsigned frames;       /* complete frames present (VIDEO, ANIM) */
} fmv_packet_t;

typedef struct {
    uint16_t palette[16];  /* Mega Drive color words (host order) */
    const uint8_t *tiles;  /* tile_count 4bpp tiles, MD layout */
    unsigned tiles_w;      /* FMV_TILES_W, FMV_ANIM_TILES_W or FMV_MUTE_TILES_W */
    unsigned tiles_h;      /* FMV_TILES_H, FMV_ANIM_TILES_H or FMV_MUTE_TILES_H */
} fmv_frame_t;

unsigned fmv_stm_packet_count(size_t size);
/* Packets (75-sector cycles) or, for FMV_STREAM_MUTE, 5-sector banks. */
unsigned fmv_stm_kind_packet_count(size_t size, fmv_stream_kind_t kind);
int fmv_stm_packet(const uint8_t *stm, size_t size, fmv_stream_kind_t kind,
                   unsigned index, fmv_packet_t *out);
int fmv_packet_frame(const fmv_packet_t *packet, unsigned index, fmv_frame_t *out);

/* Palette index (0-15) of one pixel; x < tiles_w * 8, y < tiles_h * 8. */
unsigned fmv_frame_pixel(const fmv_frame_t *frame, unsigned x, unsigned y);

/* Whole frame as MD color words, (tiles_w * 8) * (tiles_h * 8) entries. */
void fmv_frame_render_md(const fmv_frame_t *frame, uint16_t *out);

/* Mega Drive color word to Saturn VDP2 RGB555 (0BBBBBGGGGGRRRRR). */
uint16_t fmv_md_to_rgb555(uint16_t md);

/* Mega Drive color word to 8-bit RGB with the MD DAC levels. */
void fmv_md_to_rgb888(uint16_t md, uint8_t rgb[3]);

/* One packet's PCM as the RF5C164 receives it, converted to signed 8-bit.
 * Writes FMV_PCM_CYCLE_BYTES samples; returns -1 if the packet is missing. */
int fmv_stm_pcm(const uint8_t *stm, size_t size, unsigned packet, int8_t *out);

/* RF5C164 sign-magnitude byte (bit 7 set = positive) to signed 8-bit. */
static inline int8_t fmv_pcm_sample(uint8_t b)
{
    return (b & 0x80) ? (int8_t)(b & 0x7F) : (int8_t)-(int)(b & 0x7F);
}

#endif
