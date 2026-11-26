/* Saturn movie playback; see fmv_saturn.h for the design and what it takes over. */
#include <yaul.h>
#include <string.h>

#include "fmv_fe_names.h"
#include "fmv_saturn.h"
#include "fmv_stm.h"
#include "cd_root.h"

#ifndef SCD_ZONE_OVERLAY
volatile uint32_t scd_fmv_mailbox[16];
volatile uint16_t scd_fmv_log[FMV_LOG_ENTRIES];
#endif

/* ---- Memory ------------------------------------------------------------ */
#define GFX_SECTORS (FMV_SAT_PACKET_SECTORS - FMV_SAT_PCM_SECTORS)
#define GFX_BYTES (GFX_SECTORS * 2048u)
#define LWRAM_GFX(b) (0x00200000u + (b) * GFX_BYTES)
#define LWRAM_RES (LWRAM_GFX(2))
#define RES_MAX 0x8000u
#define SOUND_RAM(x) (0x25A00000UL + (x))
#define SCSP_REG(x) (*(volatile uint16_t *)SCSP(x))

/* VDP2 VRAM bank A0 (the layout of src/special_game_view.inc: cells and maps
 * in one bank, both read in its cycle pattern). */
#define VRAM(x) VDP2_VRAM_ADDR(0, (x))
#define CELL_BUF(b) ((b) ? 0x4000u : 0x0200u)   /* 448 cells each */
#define CELL_MD(t) (0x8000u + (t) * 32u)          /* plane B: MD tile t (t < CELL_MD_TILES) */
/* The Japanese ENDING.MMD's SR loads tiles $A6-$483 (US $A6-$375): plane B's MD tiles
 * take 0x8000-0x13FFF, and the three map pages follow. */
#define CELL_MD_TILES 0x600u
#define PAGE_NBG0(b) (0x14000u + (b) * 0x4000u)  /* 64 x 64 cells, 2-word names */
#define PAGE_NBG1 0x1C000u
#define LS_TABLE 0x7800u                          /* unused (type 0); after buffer 1 */
_Static_assert(CELL_MD(CELL_MD_TILES) <= PAGE_NBG0(0), "plane B tiles overlap the NBG0 pages");
_Static_assert(CELL_BUF(1) + 448u * 32u <= LS_TABLE && LS_TABLE + 0x800u <= CELL_MD(0), "cell buffers overlap");
#define BACK_COLOR VDP2_VRAM_ADDR(3, 0x1bffe)    /* where the game keeps it */
#define PAL_BUF(b) (b)                            /* 16-colour CRAM banks */
#define PAL_MD(line) (4u + (line))
#define CRAM16(bank, i) (*(volatile uint16_t *)VDP2_CRAM_ADDR((bank) * 16u + (i)))

/* ---- Timing -------------------------------------------------------------- */
/* SCSP: 44,100 Hz x 2^OCT x (1 + FNS / 1024); OCT -1, FNS 497 = 32,752 Hz. */
#define PITCH_WORD ((0xFu << 11) | 497u)
#define PLAY_RATE 32752u
/* FRT: the SH-2 clock in 320-pixel NTSC mode (26.8741 MHz) / 8 (user_init). */
#define FRT_HZ 3359264u
#define FRT_TO_SAMPLES 5112u               /* PLAY_RATE / FRT_HZ x 2^19, rounded */
#define FRT_BLOCK_TICKS 420112u            /* one 4,096-sample block: no overflow below it */
_Static_assert((uint64_t)FRT_BLOCK_TICKS * FRT_TO_SAMPLES < 0x100000000ull, "audio clock product overflows");
#define FIELD_SAMPLES 546u                 /* one Saturn field of audio */
#define MD_VBLANK_X100 54657u               /* PLAY_RATE (32,752.1 Hz) / 59.9227 Hz, x100: a Mega
                                               Drive V-blank of real time on the slot's clock */
#define VIDEO_STEP 4095u                    /* 32760 / 8 */
#define ANIM_STEP 2184u                     /* 32760 / 15 */

typedef enum { PIC_NONE, PIC_VIDEO, PIC_ANIM, PIC_SR } pic_kind_t;
typedef enum { LAYOUT_NONE, LAYOUT_VIDEO, LAYOUT_WINDOW, LAYOUT_PTEST } layout_t;

typedef struct {
    /* disc */
    uint32_t fad;              /* first packet sector */
    unsigned packets, kind, ending_id;
    unsigned packet_sectors, pcm_sectors;  /* 75 and 16; pencil test 5 and 0 */
    uint32_t pcm_samples;
    uint32_t res_off[FMV_RES_COUNT], res_len[FMV_RES_COUNT];
    uint8_t table[2048 - 128]; /* per packet: fmv_packet_type_t << 4 | frames */
    const uint8_t *res;
    /* CD reader */
    uint32_t next_sector;      /* packet-relative sector still in the CD block */
    int gfx_packet[2];         /* packet held by each LWRAM buffer, -1 none */
    unsigned gfx_have[2];      /* its sectors transferred */
    uint32_t sectors_read;
    int cd_error;
    /* audio clock */
    uint32_t frt_ext, frt_prev_poll, anchor, blocks, pos_last;
    uint16_t frt_last;
    unsigned ca_last;
    int playing;
    /* timeline cursor: next item to prepare */
    unsigned cur_packet, cur_item;
    uint32_t pic_index;        /* global index of the next picture */
    /* display */
    int visible, target;       /* NBG0 buffer shown / committed at next V-blank */
    layout_t layout[2];
    int queued;                /* a picture waits in buffer !visible */
    uint32_t queued_due, queued_index, queued_packet;
    uint16_t buf_color0[2];    /* palette[0] of each buffer (RGB555) */
    int back_pending;
    uint16_t back_value;
    uint32_t shown_index, shown_packet;
    uint32_t field;
    /* ending */
    int credits_active, credits_started;
    uint32_t credits_start, credits_steps;
    uint32_t credits_acc;      /* MD $C08A: 16.16 scroll */
    uint32_t roll_speed;       /* added to it each MD V-blank (FMV_SAT_ROLL_SPEED) */
    unsigned still_tiles;      /* tiles the SR packet loads from $A6 (FMV_SAT_STILL_TILES) */
    uint16_t credits_row_scroll;  /* MD $C08E */
    uint32_t credits_ptr;      /* byte offset into the credits table */
    uint32_t credits_rows;
    int rs_pending, rs_applied;
    uint32_t rs_due;
    int fade_active;
    unsigned fade_step;
    uint16_t fade_colors[2];
    int fade_pending;
    uint16_t nbg1_scroll;
    uint16_t md_cram[8][16];   /* the Mega Drive colours in CRAM banks 0-7 (fades) */
    unsigned card_row, card_col, card_w, card_h, card_hold;
    unsigned end_wait;         /* V-blanks between the stream's end and the card */
    /* stats */
    uint32_t shown, dropped, late_fields, not_ready, max_error;
} fmv_state_t;

#ifdef SCD_ZONE_OVERLAY
/* The player state and the header sector live in low work RAM after the
   resources, inside the range the movie owns: no resident RAM. */
#define FMV_LWRAM_HEAD (FMV_LWRAM_STATE + 64u)
#define st (*(fmv_state_t *)(FMV_LWRAM_HEAD + 2048u))
_Static_assert(LWRAM_RES + RES_MAX <= FMV_LWRAM_STATE, "FMV resources overlap the player state");
_Static_assert(FMV_LWRAM_HEAD + 2048u + sizeof(fmv_state_t) <= FMV_LWRAM_LOG, "FMV state overlaps the picture log");
_Static_assert(FMV_LWRAM_LOG + 2u * FMV_LOG_ENTRIES <= FMV_LWRAM_END, "FMV picture log leaves the movie's low work RAM");
#else
static fmv_state_t st;
#endif

/* ---- Small helpers ----------------------------------------------------- */
static uint16_t be16(const uint8_t *p) { return (uint16_t)(p[0] << 8 | p[1]); }
static uint32_t be32(const uint8_t *p) { return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3]; }

static void vram_copy(uint32_t dst, const void *src, uint32_t bytes)
{
    volatile uint32_t *d = (volatile uint32_t *)VRAM(dst);
    const uint32_t *s = src;
    for (uint32_t i = 0; i < bytes / 4u; i++)
        d[i] = s[i];
}

static void vram_fill(uint32_t dst, uint32_t value, uint32_t bytes)
{
    volatile uint32_t *d = (volatile uint32_t *)VRAM(dst);
    for (uint32_t i = 0; i < bytes / 4u; i++)
        d[i] = value;
}

/* One colour, kept as its Mega Drive word for the card's fades. */
static void cram_md(unsigned bank, unsigned i, uint16_t md)
{
    st.md_cram[bank][i] = md;
    CRAM16(bank, i) = fmv_md_to_rgb555(md);
}

static void palette_write(unsigned bank, const uint8_t *md16)
{
    for (unsigned i = 0; i < 16; i++)
        cram_md(bank, i, be16(md16 + i * 2));
}

/* 2-word pattern name, 16 colours, CRAM mode 0/1 bank numbering. */
static uint32_t pnd(uint32_t cell_addr, unsigned bank, unsigned hf, unsigned vf)
{
    return (uint32_t)vf << 31 | (uint32_t)hf << 30 | (uint32_t)(bank & 0x7F) << 16 | ((cell_addr >> 5) & 0x7FFF);
}

/* Mega Drive plane B name word to NBG1 (the MD tile keeps its number). */
static uint32_t md_name(uint16_t w)
{
    unsigned t = w & 0x7FF;
    if (t >= CELL_MD_TILES)
        t = 0;
    return pnd(CELL_MD(t), PAL_MD((w >> 13) & 3), (w >> 11) & 1, (w >> 12) & 1);
}

/* MD plane B is 128 x 32 cells; NBG1 is one 64 x 64 page, so every MD row is
 * written to rows r and r + 32: the 256-line vertical wrap is kept. */
static void nbg1_put(unsigned row, unsigned col, uint16_t w)
{
    if (col >= 64)
        return;
    volatile uint32_t *page = (volatile uint32_t *)VRAM(PAGE_NBG1);
    uint32_t v = md_name(w);
    page[(row & 31) * 64 + col] = v;
    page[((row & 31) + 32) * 64 + col] = v;
}

static void layout_set(int b, layout_t layout)
{
    if (st.layout[b] == layout)
        return;
    volatile uint32_t *page = (volatile uint32_t *)VRAM(PAGE_NBG0(b));
    const unsigned w = layout == LAYOUT_WINDOW ? FMV_ANIM_TILES_W : layout == LAYOUT_PTEST ? FMV_MUTE_TILES_W : FMV_TILES_W;
    const unsigned h = layout == LAYOUT_WINDOW ? FMV_ANIM_TILES_H : FMV_TILES_H;
    /* Picture origin: plane A column 4, row 6 (DrawFMVTilemaps and ENDING.MMD's
     * window map both start at $C608); the pencil test's column 9, row 7
     * (PTEST.MMD $FF23C0, $C712). Every other cell is the blank cell 0. */
    const unsigned r0 = layout == LAYOUT_PTEST ? 7u : 6u, c0 = layout == LAYOUT_PTEST ? 9u : 4u;
    for (unsigned r = 0; r < 64; r++)
        for (unsigned c = 0; c < 64; c++) {
            uint32_t v = 0;
            if (layout != LAYOUT_NONE && r >= r0 && r < r0 + h && c >= c0 && c < c0 + w)
                v = pnd(CELL_BUF(b) + ((r - r0) * w + (c - c0)) * 32u, PAL_BUF(b), 0, 0);
            page[r * 64 + c] = v;
        }
    st.layout[b] = layout;
}

/* ---- Audio clock ------------------------------------------------------- */
static uint32_t frt_now(void)
{
    uint16_t n = cpu_frt_count_get();
    st.frt_ext += (uint16_t)(n - st.frt_last);
    st.frt_last = n;
    return st.frt_ext;
}

static unsigned slot_ca(void)
{
    SCSP_REG(0x408) = (uint16_t)(FMV_SLOT << 11);
    return (SCSP_REG(0x408) >> 7) & 15u;
}

/* Samples played since key-on: 4 KB blocks from the slot's address counter,
 * plus the FRT since the block was seen to change (at most one block). */
static uint32_t audio_pos(void)
{
    if (!st.playing)
        return 0;
    uint32_t t = frt_now();
    unsigned ca = slot_ca();
    unsigned d = (ca - st.ca_last) & 15u;
    if (d) {
        st.blocks += d;
        st.ca_last = ca;
        /* The change happened between the previous poll and this one. */
        st.anchor = st.frt_prev_poll + (t - st.frt_prev_poll) / 2u;
    }
    st.frt_prev_poll = t;
    /* Samples = FRT ticks x PLAY_RATE / FRT_HZ, in 32 bits (a 64-bit divide would
     * pull libgcc's __udivdi3 into resident RAM): x 5112 / 2^19 is within 0.3
     * samples over the one block it covers. */
    uint32_t ticks = t - st.anchor;
    uint32_t frac = ticks >= FRT_BLOCK_TICKS ? 4095u : (ticks * FRT_TO_SAMPLES) >> 19;
    if (frac > 4095u)
        frac = 4095u;
    uint32_t pos = st.blocks * 4096u + frac;
    if (pos < st.pos_last)
        pos = st.pos_last;
    st.pos_last = pos;
    return pos;
}

static void slot_start(void)
{
    volatile uint16_t *slot = (volatile uint16_t *)SCSP(FMV_SLOT * 32u);
    slot[0] = 0;
    slot[1] = (uint16_t)(FMV_RING_ADDR & 0xFFFF);
    slot[2] = 0;          /* LSA */
    slot[3] = 0xFFFF;     /* LEA: the 16-bit address wraps, a 65,536-sample loop */
    slot[4] = 31;         /* AR max, no decay */
    slot[5] = 31;         /* RR */
    slot[6] = 0;          /* TL: full level */
    slot[7] = 0;
    slot[8] = PITCH_WORD;
    slot[9] = 0;
    slot[10] = 0;
    slot[11] = 0xE000;    /* DISDL 7, centre */
    /* MEM4MB, DAC18B and MVOL are write-only (SCSP manual, 4.2).
     * A read/modify/write can clear MEM4MB and invalidate the live driver and
     * PCM addresses. Keep 512 KB sound RAM, 16-bit DAC and full master gain. */
    SCSP_REG(0x400) = 0x020Fu;
    st.frt_last = cpu_frt_count_get();
    st.frt_ext = 0;
    st.blocks = 0;
    st.ca_last = 0;
    st.pos_last = 0;
    /* Key on: KYONEX | KYONB | forward loop | PCM8B | SA[19:16]. */
    slot[0] = (uint16_t)(0x1800 | 0x0020 | 0x0010 | ((FMV_RING_ADDR >> 16) & 15u));
    st.anchor = st.frt_prev_poll = frt_now();
    st.playing = 1;
}

static void slot_stop(void)
{
    volatile uint16_t *slot = (volatile uint16_t *)SCSP(FMV_SLOT * 32u);
    slot[0] = (uint16_t)((slot[0] & ~0x0800u) | 0x1000u);
    st.playing = 0;
}

/* Wait for the V-blank that commits this iteration's registers, reading the
 * slot address all the while so a block change is timed to microseconds
 * (polling only between jobs left the clock +-8 ms). TVSTAT bit 3 is VBLANK. */
#define FMV_TVSTAT (*(volatile uint16_t *)0x25F80004UL)
#define FMV_PRELOAD_VBLANKS 600u   /* 10 s */
#define FMV_CD_TIMEOUT 0xAA         /* libyaul cd-block_init.c CD_STATUS_TIMEOUT (private) */
static void wait_vblank(void)
{
    vdp2_sync();
    while (FMV_TVSTAT & 8u)
        audio_pos();
    while (!(FMV_TVSTAT & 8u))
        audio_pos();
    vdp2_sync_wait();
}

/* ---- CD reader ----------------------------------------------------------- */
/* Packet p is sectors [75p, 75p + 75): 16 PCM sectors (chunk p, ring half
 * p & 1), then 59 graphics sectors (LWRAM buffer p & 1). A sector leaves the
 * CD block only when its destination is free; until then the block holds it
 * and pauses the drive when full. */
static int sector_ready(uint32_t s, uint32_t pos)
{
    unsigned p = s / st.packet_sectors, r = s % st.packet_sectors;
    if (r < st.pcm_sectors) {
        /* Ring half p & 1 held chunk p - 2: wait until it has played, with a
         * 4 KB block of margin for the slot's read-ahead. */
        if (p < 2)
            return 1;
        return st.playing && pos >= (p - 1) * FMV_SAT_CHUNK_BYTES + 4096u;
    }
    int b = (int)(p & 1);
    if (st.gfx_packet[b] == (int)p)
        return 1;
    /* The buffer still holds a packet the timeline has not finished with. */
    return st.gfx_packet[b] < 0 || (unsigned)st.gfx_packet[b] < st.cur_packet;
}

static void cd_service(unsigned budget)
{
    uint32_t total = st.packets * st.packet_sectors;
    while (budget && st.next_sector < total && !st.cd_error) {
        uint32_t pos = audio_pos();
        if (!sector_ready(st.next_sector, pos))
            return;
        int ready = cd_block_cmd_sector_number_get(0);
        if (ready <= 0)
            return;
        uint32_t s = st.next_sector;
        unsigned p = s / st.packet_sectors, r = s % st.packet_sectors;
        /* Contiguous run to one destination. */
        unsigned run = r < st.pcm_sectors ? st.pcm_sectors - r : st.packet_sectors - r;
        if (run > (unsigned)ready)
            run = (unsigned)ready;
        if (run > budget)
            run = budget;
        uint8_t *dst;
        if (r < st.pcm_sectors) {
            dst = (uint8_t *)SOUND_RAM(FMV_RING_ADDR + (p & 1) * FMV_SAT_CHUNK_BYTES + r * 2048u);
        } else {
            int b = (int)(p & 1);
            if (st.gfx_packet[b] != (int)p) {
                st.gfx_packet[b] = (int)p;
                st.gfx_have[b] = 0;
            }
            dst = (uint8_t *)(LWRAM_GFX(b) + (r - st.pcm_sectors) * 2048u);
        }
        int ret = cd_block_transfer_data(0, 0, dst, run * 2048u);
        if (ret) {
            st.cd_error = ret;
            scd_fmv_mailbox[13] = (uint32_t)ret;
            return;
        }
        if (r >= st.pcm_sectors)
            st.gfx_have[p & 1] += run;
        st.next_sector += run;
        st.sectors_read += run;
        budget -= run;
    }
}

static int gfx_loaded(unsigned p)
{
    int b = (int)(p & 1);
    return st.gfx_packet[b] == (int)p && st.gfx_have[b] >= st.packet_sectors - st.pcm_sectors;
}

/* ---- Timeline --------------------------------------------------------- */
static void credits_begin(uint32_t due)
{
    st.credits_active = 1;
    st.credits_started = 1;
    st.credits_start = due + (7u * MD_VBLANK_X100) / 100u;
    st.credits_steps = 0;
    st.credits_acc = 0;
    st.credits_row_scroll = 0;
    st.credits_ptr = 0;
}

/* Put the next picture into the hidden buffer. Returns 1 when it did,
 * 0 when there is nothing to do or its data has not arrived. */
static int prepare_next(void)
{
    int h = st.visible ^ 1;
    if (st.queued || st.target != st.visible)
        return 0;
    while (st.cur_packet < st.packets) {
        unsigned p = st.cur_packet;
        if (!gfx_loaded(p))
            return 0;
        /* Ending packets start with the 16-byte tag header. */
        const uint8_t *gfx = (const uint8_t *)LWRAM_GFX(p & 1) + (st.kind ? FMV_HEADER_BYTES : 0);
        fmv_packet_type_t type = (fmv_packet_type_t)(st.table[p] >> 4);
        uint32_t base = p * FMV_SAT_PCM_PER_PACKET;
        fmv_packet_t packet = {.type = type, .gfx = gfx, .gfx_bytes = GFX_BYTES, .frames = st.table[p] & 15u};
        if ((type == FMV_PACKET_VIDEO || type == FMV_PACKET_ANIM) && st.cur_item < packet.frames) {
            fmv_frame_t frame;
            fmv_packet_frame(&packet, st.cur_item, &frame);
            unsigned tiles = frame.tiles_w * frame.tiles_h;
            layout_set(h, type == FMV_PACKET_VIDEO ? LAYOUT_VIDEO : LAYOUT_WINDOW);
            vram_copy(CELL_BUF(h), frame.tiles, tiles * FMV_TILE_BYTES);
            palette_write(PAL_BUF(h), frame.tiles - FMV_PALETTE_BYTES);
            st.buf_color0[h] = fmv_md_to_rgb555(frame.palette[0]);
            /* "08" frame i at its slot; ENDING.MMD's "15" frames, like its SR, RS and
             * end events, start one video slot before the packet's audio (measured
             * against the retail roll and window: JP good, JP bad, US good). */
            st.queued_due = type == FMV_PACKET_VIDEO ? base + st.cur_item * VIDEO_STEP
                                                     : base - VIDEO_STEP + st.cur_item * ANIM_STEP;
            st.queued_packet = p;
            st.queued_index = st.pic_index++;
            st.queued = 1;
            st.cur_item++;
            return 1;
        }
        if (type == FMV_PACKET_STILL && st.cur_item == 0) {
            /* SR: the roll's text tiles to MD VRAM $14C0 (tile $A6; US 720, JP 990),
             * then job 10: ENDING.MMD's window picture with its palette in plane A. */
            vram_copy(CELL_MD(0xA6), gfx, st.still_tiles * FMV_TILE_BYTES);
            layout_set(h, LAYOUT_WINDOW);
            vram_copy(CELL_BUF(h), st.res + st.res_off[FMV_RES_SR_WINDOW], FMV_ANIM_TILES * FMV_TILE_BYTES);
            palette_write(PAL_BUF(h), st.res + st.res_off[FMV_RES_SR_PALETTE]);
            st.buf_color0[h] = fmv_md_to_rgb555(be16(st.res + st.res_off[FMV_RES_SR_PALETTE]));
            /* The job runs when the packet arrives, one video slot before its audio:
             * the slot of the previous packet's last "08" frame, which shows first.
             * The window follows one field later (the roll starts on time below). */
            st.queued_due = base - VIDEO_STEP + FIELD_SAMPLES;
            st.queued_packet = p;
            st.queued_index = st.pic_index++;
            st.queued = 1;
            st.cur_item = 1;
            credits_begin(base - VIDEO_STEP);
            return 1;
        }
        if (type == FMV_PACKET_RESUME && st.cur_item == 0) {
            /* RS: ENDING.MMD sets the fade flag and waits for the next bank;
             * job 11 (the end screen) runs at that bank's first V-blank, while
             * the roll finishes (retail GOODEND: RS at V-blank 9412 of the roll,
             * roll ends +30, job 11 +59; the first "08" frame shows one video
             * slot after job 11). On the audio clock the first frame of the
             * next packet is due at its start, so job 11 goes one slot before. */
            st.rs_due = base + FMV_SAT_PCM_PER_PACKET - VIDEO_STEP;
            st.rs_pending = 1;
            st.cur_item = 1;
            continue;
        }
        /* Packet finished (NO, empty, or all items taken): release it. */
        st.cur_packet++;
        st.cur_item = 0;
    }
    return 0;
}

/* One Mega Drive V-blank of the staff roll (ENDING.MMD V-int and $FF25C6). */
static void credits_step(void)
{
    const uint8_t *table = st.res + st.res_off[FMV_RES_CREDITS];
    st.credits_acc += st.roll_speed;   /* US $9100, JP $A000 */
    uint16_t scroll = (uint16_t)(st.credits_acc >> 16);
    if ((int16_t)(scroll - st.credits_row_scroll) >= 8) {
        st.credits_row_scroll = scroll;
        unsigned row = (((unsigned)scroll + 224u) & 0xF8u) >> 3;
        uint16_t fill = be16(table + st.credits_ptr);
        if (fill == 0xFFFF) {
            st.credits_active = 0;
        } else {
            unsigned count = be16(table + st.credits_ptr + 2);
            uint32_t at = st.credits_ptr + 4;
            unsigned col = 0;
            int rest = 40 - (int)count;
            for (unsigned i = 0; i <= count; i++)
                nbg1_put(row, col++, fill);
            for (;;) {
                uint16_t w = be16(table + at);
                at += 2;
                if (w == 0xFFFF)
                    break;
                nbg1_put(row, col++, w);
                rest--;
            }
            for (; rest > 0; rest--)
                nbg1_put(row, col++, 0);
            st.credits_ptr = at;
            st.credits_rows++;
        }
    }
    st.nbg1_scroll = scroll;
}

/* RS, job 11 of ENDING.MMD's V-int: plane A back to the video maps (done per
 * buffer as frames arrive), CRAM cleared, V-scroll 0, the end screen drawn on
 * plane B, and the fade timer restarted. */
static void ending_rs(void)
{
    /* Job 11 loads the end-screen tiles to VRAM $76C0 (tile $3B6) itself
     * (ENDING.MMD $FF2AD0): the Japanese roll's text tiles run to $483, so
     * they must not go in before. */
    vram_copy(CELL_MD(0x3B6), st.res + st.res_off[FMV_RES_END_TILES], st.res_len[FMV_RES_END_TILES] & ~3u);
    for (unsigned line = 0; line < 4; line++)
        for (unsigned i = 0; i < 16; i++)
            cram_md(PAL_MD(line), i, 0);
    for (unsigned i = 0; i < 16; i++)
        cram_md(PAL_BUF(st.visible), i, 0);
    st.buf_color0[st.visible] = 0;
    if (!st.queued)
        for (unsigned i = 0; i < 16; i++)
            cram_md(PAL_BUF(st.visible ^ 1), i, 0);
    *(volatile uint16_t *)BACK_COLOR = 0;
    const uint8_t *rows = st.res + st.res_off[FMV_RES_END_ROWS];
    if (st.ending_id == 0x7F) {
        for (unsigned r = 0; r < 2; r++)
            for (unsigned c = 0; c < 16; c++)
                nbg1_put(21 + r, 12 + c, be16(rows + (r * 16 + c) * 2));
    } else {
        for (unsigned r = 0; r < 5; r++)
            for (unsigned c = 0; c < 30; c++)
                nbg1_put(21 + r, 5 + c, be16(rows + (r * 30 + c) * 2));
    }
    st.fade_active = 1;
    st.fade_step = 0;
}

/* ---- Display setup ------------------------------------------------------- */
static void display_init(void)
{
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NONE);
    const vdp2_vram_usage_t usage = {0};
    vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;
    memset(&cycles, 0xff, sizeof(cycles));
    cycles.pt[0].t0 = cycles.pt[0].t1 = VDP2_VRAM_CYCP_PNDR_NBG0;
    cycles.pt[0].t2 = cycles.pt[0].t3 = VDP2_VRAM_CYCP_PNDR_NBG1;
    cycles.pt[0].t4 = VDP2_VRAM_CYCP_CHPNDR_NBG0;
    cycles.pt[0].t5 = VDP2_VRAM_CYCP_CHPNDR_NBG1;
    vdp2_vram_cycp_set(&cycles);
    for (unsigned i = 0; i < 2; i++) {
        vdp2_scrn_t screen = i ? VDP2_SCRN_NBG1 : VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt = {.scroll_screen = screen, .ccc = VDP2_SCRN_CCC_PALETTE_16,
            .char_size = VDP2_SCRN_CHAR_SIZE_1X1, .pnd_size = 2, .aux_mode = 0,
            .plane_size = VDP2_SCRN_PLANE_SIZE_1X1, .cpd_base = VRAM(0),
            .palette_base = VDP2_CRAM_MODE_0_OFFSET(0, 0, 0)};
        /* NBG0: planes A/C = buffer 0's page, B/D = buffer 1's, side by side,
         * so X scroll 0 or 512 picks the buffer (plane A H-scroll 0 / $200). */
        vdp2_scrn_normal_map_t map;
        if (i)
            map = (vdp2_scrn_normal_map_t){.plane_a = VRAM(PAGE_NBG1), .plane_b = VRAM(PAGE_NBG1),
                                           .plane_c = VRAM(PAGE_NBG1), .plane_d = VRAM(PAGE_NBG1)};
        else
            map = (vdp2_scrn_normal_map_t){.plane_a = VRAM(PAGE_NBG0(0)), .plane_b = VRAM(PAGE_NBG0(1)),
                                           .plane_c = VRAM(PAGE_NBG0(0)), .plane_d = VRAM(PAGE_NBG0(1))};
        vdp2_scrn_cell_format_set(&fmt, &map);
        vdp2_scrn_priority_set(screen, i ? 2 : 3);
        const vdp2_scrn_ls_format_t ls = {.scroll_screen = screen, .table_base = VRAM(LS_TABLE), .interval = 0, .type = 0};
        vdp2_scrn_ls_set(&ls);
        /* NBG0 starts on buffer 1's blank page; the first picture goes to 0. */
        vdp2_scrn_scroll_x_set(screen, i ? 0 : (fix16_t)(512 * 65536));
        vdp2_scrn_scroll_y_set(screen, 0);
        vdp2_scrn_coff_unset(screen);
    }
    vdp2_scrn_coff_unset(VDP2_SCRN_BACK);
    /* Mosaic: nothing in the game sets it, so it is already off. */
    for (unsigned i = 0; i < 8; i++)
        vdp2_sprite_priority_set(i, 0);
    /* Cells: blank cell 0, both buffers, the MD tiles of plane B; maps. */
    vram_fill(0, 0, 0x20000);
    st.layout[0] = st.layout[1] = LAYOUT_NONE;
    for (unsigned b = 0; b < 8; b++)
        for (unsigned i = 0; i < 16; i++)
            cram_md(b, i, 0);
    if (st.kind == FMV_MUTE_KIND) {
        /* PTEST.MMD $FF25AE: 200 border tiles to VRAM $7D00 (tile $3E8, here
         * cell CELL_MD(0) on), 40 x 28 names to plane B $A000 (palette line 1). */
        vram_copy(CELL_MD(0), st.res + st.res_off[FMV_PRES_TILES], st.res_len[FMV_PRES_TILES]);
        volatile uint32_t *page = (volatile uint32_t *)VRAM(PAGE_NBG1);
        const uint8_t *map = st.res + st.res_off[FMV_PRES_MAP];
        for (unsigned i = 0; i < 40u * 28u; i++) {
            uint16_t w = be16(map + i * 2u);
            page[(i / 40u) * 64u + i % 40u] = pnd(CELL_MD((w & 0x7FFu) - 0x3E8u), PAL_MD(1), (w >> 11) & 1, (w >> 12) & 1);
        }
    } else if (st.kind == FMV_STREAM_ENDING) {
        /* ENDING.MMD init: all four CRAM lines from its table (plane B uses
         * line 2); lines 0/1 are the picture palettes on the Saturn. */
        const uint8_t *cram = st.res + st.res_off[FMV_RES_CRAM];
        for (unsigned line = 0; line < 4; line++)
            palette_write(PAL_MD(line), cram + line * 32);
    }
    vdp2_scrn_back_color_set(BACK_COLOR, (rgb1555_t){.raw = 0x8000});
    *(volatile uint16_t *)BACK_COLOR = 0;
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0 | VDP2_SCRN_DISPTP_NBG1);
}

/* ---- Open the file --------------------------------------------------- */
static const char fmv_stream_names[4][12] = {"OPN.FMV", "GOODEND.FMV", "BADEND.FMV", "PTEST.FMV"};
static int stream_open(fmv_id_t id)
{
    const cdfs_filelist_t *root = scd_cd_root_read();
    const cdfs_filelist_entry_t *e = NULL;
    for (unsigned i = 0; i < root->entries_count; i++)
        if (!strcmp(root->entries[i].name, fmv_stream_names[id]))
            e = &root->entries[i];
    if (!e)
        return -1;
#ifdef SCD_ZONE_OVERLAY
    uint8_t *const head = (uint8_t *)FMV_LWRAM_HEAD;
    const uint32_t head_bytes = 2048u;
#else
    static uint8_t head[2048] __aligned(4);
    const uint32_t head_bytes = sizeof head;
#endif
    if (cd_block_sectors_read(e->starting_fad, head, head_bytes))
        return -2;
    if (be32(head) != FMV_SAT_MAGIC || be16(head + 4) != FMV_SAT_VERSION)
        return -3;
    st.kind = be16(head + 6);
    st.packets = be32(head + 8);
    uint32_t header_sectors = be32(head + 12);
    const unsigned mute = id == FMV_PTEST;
    if (be32(head + 16) != (mute ? 0u : FMV_SAT_PCM_PER_PACKET) ||
        st.kind != (mute ? FMV_MUTE_KIND : id == FMV_OPENING ? 0u : 1u))
        return -3;
    st.packet_sectors = mute ? FMV_MUTE_BANK_SECTORS : FMV_SAT_PACKET_SECTORS;
    st.pcm_sectors = mute ? 0u : FMV_SAT_PCM_SECTORS;
    st.pcm_samples = be32(head + 20);
    st.ending_id = be16(head + 24);
    unsigned count = be16(head + 26);
    /* Endings: ENDING.MMD's roll step and SR tile count (tools/fmv_convert.py). */
    st.roll_speed = be32(head + FMV_SAT_ROLL_SPEED);
    st.still_tiles = be16(head + FMV_SAT_STILL_TILES);
    st.card_row = head[FMV_SAT_CARD];
    st.card_col = head[FMV_SAT_CARD + 1];
    st.card_w = head[FMV_SAT_CARD + 2];
    st.card_h = head[FMV_SAT_CARD + 3];
    st.card_hold = be16(head + FMV_SAT_CARD_HOLD);
    st.end_wait = be16(head + FMV_SAT_END_WAIT);
    if (st.kind == FMV_STREAM_ENDING && (!st.roll_speed || !st.still_tiles || !st.end_wait || st.packets < 2 || 0xA6u + st.still_tiles > CELL_MD_TILES ||
                                         st.still_tiles * FMV_TILE_BYTES + FMV_HEADER_BYTES > GFX_BYTES))
        return -3;
    if (st.packets > sizeof st.table)
        return -3;
    memcpy(st.table, head + 128, st.packets);
    if (header_sectors > 1) {
        const unsigned want = mute ? (unsigned)FMV_PRES_COUNT : (unsigned)FMV_RES_COUNT;
        if ((header_sectors - 1) * 2048u > RES_MAX || count != want)
            return -3;
        if (cd_block_sectors_read(e->starting_fad + 1, (void *)LWRAM_RES, (header_sectors - 1) * 2048u))
            return -2;
        for (unsigned i = 0; i < want; i++) {
            st.res_off[i] = be32(head + 32 + i * 8) - 2048u;
            st.res_len[i] = be32(head + 36 + i * 8);
            if (st.res_off[i] + st.res_len[i] > (header_sectors - 1) * 2048u)
                return -3;
        }
        st.res = (const uint8_t *)LWRAM_RES;
    } else if (st.kind != FMV_STREAM_OPENING) {
        return -3;
    }
    st.fad = e->starting_fad + header_sectors;
    if (cd_block_cmd_selector_reset(0, 0) || cd_block_cmd_cd_dev_connection_set(0) ||
        cd_block_cmd_disk_play(0, st.fad, (int32_t)(st.packets * st.packet_sectors)))
        return -2;
    return 0;
}

static void stream_close(void)
{
    cd_block_cmd_disk_seek(0xffffff);
    cd_block_cmd_selector_reset(0, 0);
}

/* ---- Player ------------------------------------------------------------ */
static void publish(uint32_t pos)
{
    volatile uint32_t *m = scd_fmv_mailbox;
    m[3] = st.shown_index;
    m[4] = pos;
    m[5] = st.shown;
    m[6] = st.dropped;
    m[7] = st.late_fields;
    m[8] = st.field;
    m[9] = st.max_error;
    m[10] = st.sectors_read;
    m[11] = st.not_ready;
    m[12] = st.credits_steps;
    m[15] = st.shown_packet;
}

static int start_pressed(void)
{
    smpc_peripheral_digital_t pad;
    smpc_peripheral_process();
    smpc_peripheral_digital_port(1, &pad);
    /* Yaul's "held" is the new press (see main.c). */
    return pad.held.button.start;
}

/* noipa: LTO must not inline overlay code into a resident caller. */
/* The VDP2 state fmv_play changes, saved around the movie in the front-end overlay's
   data (R0, not resident): Yaul's register shadow (cycle patterns, RAMCTL, cell
   formats, line scroll, priorities including the sprite ones, colour offsets, scroll,
   back screen) and CRAM banks 0-7, so the caller's screen comes back as it was.
   VDP2 VRAM bank A0 and the line scroll table stay overwritten: the title and the
   stages load theirs again; the front-end HUD screens do not use them. */
static vdp2_ioregs_t fe_fmv_saved_regs __attribute__((section(".data.fe_fmv_saved_regs")));
static uint16_t fe_fmv_saved_cram[128] __attribute__((section(".data.fe_fmv_saved_cram")));
/* ---- Pencil test ---------------------------------------------------------- */
/* PTEST.MMD's timing in Mega Drive V-blanks, one per Saturn field, as
 * tools/fmv_retail.py ptest measures it: fade step s ($FF2244) shows 8s after
 * step 0, picture 0 90 after step 0, fade-out step 7 ($FF2100: 61 V-blanks
 * after the sub's end flag, then $FF2282) 64 after the last picture, the
 * return 8 after step 0. Pictures follow the 1x CD: one 5-sector bank in 1/15 s. */
#define PT_STEP_FIELDS 8u
#define PT_FIRST_FIELD 90u
#define PT_HOLD_FIELDS 64u
#define PT_BANK_TICKS(k) ((uint32_t)(k) * (FRT_HZ / 15u) + (uint32_t)(k) * (FRT_HZ % 15u) / 15u)
#define PT_HALF_FIELD 28022u                 /* FRT_HZ / 59.94 / 2 */

/* One step of PTEST.MMD's fade table: palette line 1 (the border and the back
 * screen, register $87 = $10) and, fading out, line 0 (the picture shown). */
static void ptest_fade(unsigned step, int picture)
{
    const uint8_t *colors = st.res + st.res_off[FMV_PRES_FADE] + step * 32u;
    palette_write(PAL_MD(1), colors);
    *(volatile uint16_t *)BACK_COLOR = fmv_md_to_rgb555(be16(colors));
    if (picture)
        palette_write(PAL_BUF(st.visible), colors);
}

/* Put the next bank's picture into the hidden buffer (PTEST.MMD states 4/6 and
 * 10/12: palette, then 294 tiles); its LWRAM buffer is free once copied. */
static void ptest_prepare(void)
{
    unsigned p = st.cur_packet;
    if (st.queued || st.target != st.visible || p >= st.pcm_samples || !gfx_loaded(p))
        return;
    int h = st.visible ^ 1;
    fmv_packet_t packet = {.type = FMV_PACKET_MUTE, .gfx = (const uint8_t *)LWRAM_GFX(p & 1) + FMV_HEADER_BYTES,
                           .gfx_bytes = FMV_MUTE_BANK_BYTES - FMV_HEADER_BYTES, .frames = 1};
    fmv_frame_t frame;
    fmv_packet_frame(&packet, 0, &frame);
    layout_set(h, LAYOUT_PTEST);
    vram_copy(CELL_BUF(h), frame.tiles, FMV_MUTE_TILES * FMV_TILE_BYTES);
    palette_write(PAL_BUF(h), frame.tiles - FMV_PALETTE_BYTES);
    st.queued_index = st.queued_packet = p;
    st.queued = 1;
    st.cur_packet = p + 1;
}

static int ptest_play(void)
{
    const unsigned pictures = st.pcm_samples;   /* header bytes 20-23 */
    uint32_t t0 = 0, last = 0, now = 0;
    int pend_step = -1, pend_picture = 0;
    st.visible = st.target = 1;   /* buffer 1's page is blank; picture 0 goes to buffer 0 */
    for (;;) {
        /* Right after the V-blank that committed last iteration's scroll: what
         * the iteration decided shows from this field on. */
        if (st.target != st.visible) {
            st.visible = st.target;
            /* PTEST.MMD V-int, state 12: line 1 colour 5 = $0644 (from bank 0 on). */
            CRAM16(PAL_MD(1), 5) = fmv_md_to_rgb555(0x0644);
        }
        if (pend_step >= 0) {
            ptest_fade((unsigned)pend_step, pend_picture);
            pend_step = -1;
        }
        uint32_t f = st.field++;
        now = frt_now();
        unsigned phase = 1, step = f / PT_STEP_FIELDS;
        if (f < 8u * PT_STEP_FIELDS) {
            if (f % PT_STEP_FIELDS == 0)
                pend_step = (int)step;
        } else if (st.shown < pictures) {
            phase = 2;
            step = 7;
            /* Picture k's slot: field 90 for picture 0, then k banks of the 1x CD. */
            if (st.queued && f >= PT_FIRST_FIELD &&
                (st.shown == 0 || now - t0 + PT_HALF_FIELD >= PT_BANK_TICKS(st.queued_index))) {
                if (st.shown == 0)
                    t0 = now;
                uint32_t late = now - t0 - (st.shown ? PT_BANK_TICKS(st.queued_index) : 0);
                if (st.shown && (int32_t)late > 0 && late > st.max_error)
                    st.max_error = late;
                if (st.shown && (int32_t)late > (int32_t)PT_HALF_FIELD)
                    st.late_fields += late / (2u * PT_HALF_FIELD);
                st.target = st.visible ^ 1;
                vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG0, (fix16_t)((int32_t)st.target * 512 * 65536));
                st.shown_index = st.shown_packet = st.queued_index;
                if (st.queued_index < FMV_LOG_ENTRIES)
                    scd_fmv_log[st.queued_index] = (uint16_t)f;
                st.shown++;
                st.queued = 0;
                scd_fmv_mailbox[14] = f;
                last = f;
            } else if (!st.queued && f >= PT_FIRST_FIELD &&
                       now - t0 + PT_HALF_FIELD >= PT_BANK_TICKS(st.cur_packet)) {
                st.not_ready++;
            }
        } else {
            /* Fade-out: step 7 at last + 64, one step every 8 fields, return 8 after step 0. */
            phase = 3;
            uint32_t d = f - last;
            step = d < PT_HOLD_FIELDS ? 7u : 7u - (d - PT_HOLD_FIELDS) / PT_STEP_FIELDS;
            if (d >= PT_HOLD_FIELDS + 8u * PT_STEP_FIELDS)
                break;
            if (d >= PT_HOLD_FIELDS && (d - PT_HOLD_FIELDS) % PT_STEP_FIELDS == 0) {
                pend_step = (int)step;
                pend_picture = 1;
            }
        }
        publish(st.shown ? now - t0 : 0);
        scd_fmv_mailbox[12] = phase << 8 | step;
        ptest_prepare();
        cd_service(12);
        if (st.cd_error)
            return -2;
        wait_vblank();
    }
    return 0;
}

/* ---- The "PRESENTED BY SEGA" card (ENDING.MMD $FFC100) ------------------- */
/* One step of its fades on every colour, then the V-blank ($FFC308, $FFC398): the
 * channel at bit `shift` (1 red, 5 green, 9 blue) becomes max(c - d, 0) fading out,
 * min(target, d) fading in. */
/* Card progress in mailbox [3] (FMV_CARD_PICTURE): phase << 16 | V-blank count. */
static void card_publish(unsigned phase, unsigned n)
{
    publish(st.pos_last);
    scd_fmv_mailbox[3] = FMV_CARD_PICTURE | phase << 16 | n;
}

static void card_step(int in, unsigned shift, unsigned d, const uint8_t *target)
{
    for (unsigned b = 0; b < 8; b++)
        for (unsigned i = 0; i < 16; i++) {
            if (in && b >= 4)
                continue;
            uint16_t c = in ? st.md_cram[PAL_MD(b)][i] : st.md_cram[b][i];
            unsigned ch = (c >> shift) & 7u, keep = c & ~(7u << shift);
            if (in) {
                unsigned t = (be16(target + (b * 16u + i) * 2u) >> shift) & 7u;
                ch = t <= d / 2u ? t : d / 2u;
                st.md_cram[PAL_MD(b)][i] = (uint16_t)(keep | ch << shift);
            } else {
                ch = ch > d / 2u ? ch - d / 2u : 0;
                st.md_cram[b][i] = (uint16_t)(keep | ch << shift);
            }
        }
    /* The buffer goes to CRAM in the V-blank (the card's V-int DMA), so no field
     * shows half a step. The backdrop is line 0 colour 0: the picture's bank, then
     * the card's line 0. */
    wait_vblank();
    for (unsigned b = 0; b < 8; b++)
        for (unsigned i = 0; i < 16; i++)
            CRAM16(b, i) = fmv_md_to_rgb555(st.md_cram[b][i]);
    *(volatile uint16_t *)BACK_COLOR = in ? CRAM16(PAL_MD(0), 0) : CRAM16(PAL_BUF(st.visible), 0);
}

/* Three channels, eight steps each, d = 0, 2, ..., 14: out red, green, blue; in blue,
 * green, red. */
static void card_fade(int in, const uint8_t *target, unsigned phase)
{
    static const uint8_t shifts[2][3] = {{1, 5, 9}, {9, 5, 1}};
    for (unsigned c = 0; c < 3; c++)
        for (unsigned d = 0; d <= 14; d += 2) {
            card_step(in, shifts[in][c], d, target);
            card_publish(phase, c * 8u + d / 2u);
        }
}

static int start_held(void)
{
    smpc_peripheral_digital_t pad;
    smpc_peripheral_process();
    smpc_peripheral_digital_port(1, &pad);
    /* Yaul's "pressed" is the current level ($A1201E bit 7: Start held). */
    return pad.pressed.button.start;
}

static void card_play(void)
{
    /* Fade the end screen out, then (5 V-blanks: VDP setup, VRAM clear, Nemesis art)
     * the card on plane A, black. */
    card_fade(0, NULL, 1);
    layout_set(0, LAYOUT_NONE);
    layout_set(1, LAYOUT_NONE);
    vram_fill(PAGE_NBG1, 0, 0x4000);
    st.nbg1_scroll = 0;
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1, 0);
    vram_copy(CELL_MD(0), st.res + st.res_off[FMV_RES_CARD_TILES], st.res_len[FMV_RES_CARD_TILES] & ~3u);
    const uint8_t *map = st.res + st.res_off[FMV_RES_CARD_MAP];
    volatile uint32_t *page = (volatile uint32_t *)VRAM(PAGE_NBG1);
    for (unsigned r = 0; r < st.card_h; r++)
        for (unsigned c = 0; c < st.card_w; c++)
            page[(st.card_row + r) * 64u + st.card_col + c] = md_name(be16(map + (r * st.card_w + c) * 2u));
    for (unsigned b = 0; b < 8; b++)
        for (unsigned i = 0; i < 16; i++)
            cram_md(b, i, 0);
    for (unsigned n = 0; n < 5; n++) {
        wait_vblank();
        card_publish(2, n);
    }
    card_fade(1, st.res + st.res_off[FMV_RES_CARD_PALETTE], 3);
    /* The hold: the V-int counts the US timer down; Start held ends it early. */
    for (unsigned n = 0; !st.card_hold || n < st.card_hold; n++) {
        wait_vblank();
        card_publish(4, n);
        if (start_held())
            break;
    }
    card_fade(0, NULL, 5);
}

static int fmv_play_stream(fmv_id_t id);
__attribute__((noipa)) int fmv_play(fmv_id_t id)
{
    fe_fmv_saved_regs = *vdp2_regs_get();
    for (unsigned i = 0; i < 128; i++)
        fe_fmv_saved_cram[i] = CRAM16(i / 16u, i % 16u);
    int ret = fmv_play_stream(id);
    *vdp2_regs_get() = fe_fmv_saved_regs;
    for (unsigned i = 0; i < 128; i++)
        CRAM16(i / 16u, i % 16u) = fe_fmv_saved_cram[i];
    /* Returns with the display off, as before; the caller turns on what it shows. */
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NONE);
    vdp2_sync();
    vdp2_sync_wait();
    return ret;
}
static int fmv_play_stream(fmv_id_t id)
{
    if ((unsigned)id > FMV_PTEST)
        return -1;
    memset(&st, 0, sizeof st);
    st.gfx_packet[0] = st.gfx_packet[1] = -1;
    /* The Saturn build keeps the mailbox and the picture log in low work RAM
     * (FMV_LWRAM_STATE), which nothing else clears and which holds pack data
     * or power-on garbage: words written only on some paths ([13] CD error,
     * [14]) would report stale values. Words 0-2 are the caller's request. */
    for (unsigned i = 3; i < 16; i++)
        scd_fmv_mailbox[i] = 0;
    for (unsigned i = 0; i < FMV_LOG_ENTRIES; i++)
        scd_fmv_log[i] = 0;
    int ret = stream_open(id);
    if (ret)
        return ret;
    display_init();
    vdp2_sync();
    vdp2_sync_wait();
    if (st.kind == FMV_MUTE_KIND) {
        /* No SCSP slot to stop: keying it off would key off every slot. */
        int result = ptest_play();
        stream_close();
        publish(st.shown ? scd_fmv_mailbox[4] : 0);
        vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NONE);
        *(volatile uint16_t *)BACK_COLOR = 0;
        vdp2_sync();
        vdp2_sync_wait();
        return result;
    }

    /* Preload PCM chunks 0 and 1 and packet 0's graphics, then start the slot
     * with the first picture already in its buffer. */
    uint32_t need = st.packets > 1 ? FMV_SAT_PACKET_SECTORS + FMV_SAT_PCM_SECTORS : FMV_SAT_PACKET_SECTORS;
    /* A drive that delivers nothing (a failed seek or read) ends the movie as a CD
     * error after FMV_PRELOAD_VBLANKS instead of waiting forever: the callers then
     * go on as for any failed movie (ending fallback card, back to the title). At
     * 1x the preload takes about 1.2 s. */
    unsigned waited = 0, was_blank = FMV_TVSTAT & 8u;
    while (st.next_sector < need && !st.cd_error) {
        cd_service(need - st.next_sector);
        unsigned blank = FMV_TVSTAT & 8u;
        if (blank && !was_blank && ++waited >= FMV_PRELOAD_VBLANKS) {
            st.cd_error = FMV_CD_TIMEOUT;
            scd_fmv_mailbox[13] = (uint32_t)st.cd_error;
        }
        was_blank = blank;
    }
    if (st.cd_error) {
        stream_close();
        return -2;
    }
    st.visible = st.target = 1;   /* buffer 0 hidden: the first picture goes there */
    prepare_next();
    if (st.queued && st.queued_due == 0) {
        /* Picture 0 is due at sample 0: show it at the V-blank the slot keys on. */
        vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG0, 0);
        wait_vblank();
        st.visible = st.target = 0;
        *(volatile uint16_t *)BACK_COLOR = st.buf_color0[0];
        st.shown_index = st.queued_index;
        st.shown_packet = st.queued_packet;
        st.shown++;
        st.queued = 0;
    }
    slot_start();

    int result = 0, ended = 0;
    for (;;) {
        /* Right after the V-blank that committed last iteration's scroll. */
        if (st.target != st.visible) {
            st.visible = st.target;
            st.back_pending = 1;
            st.back_value = st.buf_color0[st.visible];
        }
        if (st.back_pending) {
            *(volatile uint16_t *)BACK_COLOR = st.back_value;
            st.back_pending = 0;
        }
        if (st.rs_applied == 1) {
            ending_rs();
            st.rs_applied = 2;
        }
        if (st.fade_pending) {
            cram_md(PAL_MD(2), 11, st.fade_colors[0]);
            cram_md(PAL_MD(2), 15, st.fade_colors[1]);
            st.fade_pending = 0;
        }
        st.field++;
        uint32_t pos = audio_pos();
        uint32_t pos_next = pos + FIELD_SAMPLES + FIELD_SAMPLES / 2u;  /* next field, rounded */
        publish(pos);

        /* Picture for the next field. */
        if (st.queued && st.queued_due <= pos_next) {
            st.target = st.visible ^ 1;
            vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG0, (fix16_t)((int32_t)st.target * 512 * 65536));
            uint32_t shown_at = pos + FIELD_SAMPLES;
            uint32_t err = shown_at > st.queued_due ? shown_at - st.queued_due : st.queued_due - shown_at;
            if (err > st.max_error)
                st.max_error = err;
            if (shown_at > st.queued_due + FIELD_SAMPLES)
                st.late_fields += (shown_at - st.queued_due) / FIELD_SAMPLES;
            st.shown_index = st.queued_index;
            st.shown_packet = st.queued_packet;
            st.shown++;
            st.queued = 0;
            scd_fmv_mailbox[14] = st.field;
        } else if (!st.queued && st.cur_packet < st.packets) {
            /* Nothing waiting: the next picture's data is late if it is due. */
            unsigned p = st.cur_packet;
            if (p * FMV_SAT_PCM_PER_PACKET <= pos_next && !gfx_loaded(p))
                st.not_ready++;
        }

        /* Events on the Mega Drive V-blank clock. */
        if (st.rs_pending && st.rs_due <= pos_next) {
            /* Job 11 sets V-scroll 0; a roll still running rewrites it. */
            st.rs_pending = 0;
            st.rs_applied = 1;
            st.nbg1_scroll = 0;
        }
        if (st.credits_active) {
            while (st.credits_active &&
                   st.credits_start + ((st.credits_steps + 1u) * MD_VBLANK_X100) / 100u <= pos_next) {
                st.credits_steps++;
                credits_step();
            }
        }
        if (st.fade_active && st.rs_applied) {
            /* Job 11 clears $FA44; the V-int adds 1 after it and steps the fade
             * on even counts from 44: V-blank 43 + 2j after job 11. Table words
             * d0 (colour 11), d1 (colour 15) until d0 is negative. */
            uint32_t due = st.rs_due + ((43u + 2u * st.fade_step) * MD_VBLANK_X100) / 100u;
            if (due <= pos_next) {
                /* Each fade V-int writes V-scroll 0 first ($FF28FA); a roll still
                 * running sets plane B's again after it (the Japanese roll ends
                 * after job 11, the US one before). */
                if (!st.credits_active)
                    st.nbg1_scroll = 0;
                const uint8_t *t = st.res + st.res_off[FMV_RES_FADE] + st.fade_step * 4u;
                if ((int16_t)be16(t) < 0) {
                    st.fade_active = 0;
                } else {
                    st.fade_colors[0] = be16(t);
                    st.fade_colors[1] = be16(t + 2);
                    st.fade_pending = 1;
                    st.fade_step++;
                }
            }
        }
        if (st.credits_started || st.rs_applied)
            vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1, (fix16_t)((int32_t)(st.nbg1_scroll & 0xFF) * 65536));

        /* Refill: the hidden buffer, then the CD. */
        prepare_next();
        cd_service(12);

        if (st.cd_error) {
            result = -2;
            break;
        }
        /* Endings: the Sub CPU reports the end when it takes the last packet
         * (FMV/Sub (Ending).asm .CheckStatus, .Exit: PCM muted), and ENDING.MMD
         * leaves its loop at once, so no picture of that packet shows. Retail
         * JP streams (the disc's): the report comes one video slot before the
         * last packet's first picture; the picture due then is the last one. */
        if (st.kind == FMV_STREAM_ENDING &&
            (st.packets - 1u) * FMV_SAT_PCM_PER_PACKET - VIDEO_STEP <= pos_next) {
            ended = 1;
            break;
        }
        /* Done when every sample has played and no picture is waiting. */
        if (pos >= st.pcm_samples && !st.queued && st.cur_packet >= st.packets)
            break;
        if (id == FMV_OPENING && start_pressed()) {
            result = 1;
            break;
        }
        wait_vblank();
    }
    slot_stop();
    stream_close();
    publish(st.pos_last);
    if (ended) {
        /* ENDING.MMD after the report: CRAM line 0 (the movie picture's) to black
         * at the next V-blank with this iteration's picture, then n V-blanks. */
        int flip = st.target != st.visible;
        if (flip)
            for (unsigned i = 0; i < 16; i++)
                cram_md(PAL_BUF(st.target), i, 0);
        wait_vblank();
        st.visible = st.target;
        if (!flip)
            for (unsigned i = 0; i < 16; i++)
                cram_md(PAL_BUF(st.visible), i, 0);
        *(volatile uint16_t *)BACK_COLOR = 0;
        st.buf_color0[st.visible] = 0;
        for (unsigned n = 0; n < st.end_wait; n++) {
            publish(st.pos_last);
            wait_vblank();
        }
    }
    if (!result && st.kind == FMV_STREAM_ENDING)
        card_play();
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NONE);
    *(volatile uint16_t *)BACK_COLOR = 0;
    vdp2_sync();
    vdp2_sync_wait();
    return result;
}

int fmv_test_boot(void)
{
    volatile uint32_t *m = (volatile uint32_t *)((uintptr_t)scd_fmv_mailbox | CPU_CACHE_THROUGH);
    uint32_t request = m[0];
    if ((request & 0xFFFFFF00u) != FMV_TEST_REQUEST || (request & 255u) == 0 || (request & 255u) > FMV_PTEST + 1u)
        return 0;
    m[1] = FMV_MAILBOX_PLAYING;
    int ret = fmv_play((fmv_id_t)((request & 255u) - 1));
    m[2] = (uint32_t)ret;
    m[1] = FMV_MAILBOX_DONE;
    return 1;
}
