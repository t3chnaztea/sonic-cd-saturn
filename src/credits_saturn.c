/* "Thank You" screen (THANKS_M.MMD) on VDP1/VDP2: src/credits.c runs the program in
   its Sega CD mode and scd_credits_md_frame gives each frame as the Mega Drive VDP
   shows it. The H40 screen maps one to one: plane A on NBG0 and plane B on NBG1 as
   4-bit cells from the VRAM image in cd/THANKS.BIN (tools/credits_assets.py), the 64
   colours in CRAM lines 0-3, and each sprite table entry as a VDP1 sprite cut from
   the same image, whose CLUT holds palette codes (src/title_view.inc does the same).
   Front-end overlay code: every symbol is renamed into .zone_R0 at build time
   (tools/credits_sections.py), so the names here stay plain. */
#include <yaul.h>
#include <string.h>
#include "audio.h"
#include "cd_root.h"
#include "credits.h"
#include "credits_saturn.h"
#include "frontend.h"
#include "save.h"
#include "stage.h"
#include "time_attack.h"

/* Low work RAM: the pack, then the work area (the movie's region, PPZ0-PPZ1). */
#define THANKS_PACK 0x00200000u
#define THANKS_PACK_MAX 0xE000u
#define THANKS_WORK 0x0020E000u
#define THANKS_WORK_END 0x00220000u
/* VDP1 VRAM: the CLUTs, then sprite textures up to the Sonic arena. */
#define THANKS_CLUT 0x8000u
#define THANKS_TEXTURES 0x8100u
#define THANKS_TEXTURES_END 0x10000u
/* VDP2 VRAM bank A0: cells from 0, plane maps (64x64 cells, two words each). */
#define THANKS_MAP_A 0x10000u
#define THANKS_MAP_B 0x14000u
#define THANKS_TEXTURE_SLOTS 160
/* Visible line runs a masked sprite is drawn in (more are dropped). */
#define THANKS_RUNS 3
/* Clip, local, user clip, clear; per sprite a clip and a sprite per run and a clip back;
   end. The list stays below VDP1 VRAM 0x2800, where the HUD font lives (src/main.c). */
#define THANKS_COMMANDS (0x2800 / 32)
_Static_assert(4 + SCD_CREDITS_MD_SPRITES + 1 <= THANKS_COMMANDS, "every unmasked sprite fits");

typedef struct {uint16_t tile; uint8_t width, height; uint32_t address;} texture;
typedef struct {
    scd_credits st;
    scd_credits_config config;
    scd_credits_md md;
    char names[SCD_CREDITS_NAMES][4];
    scd_ta_records records;
    texture textures[THANKS_TEXTURE_SLOTS];
    unsigned texture_count;
    uint32_t texture_next;
} work;
_Static_assert(THANKS_WORK + sizeof(work) <= THANKS_WORK_END, "THANKS work area");

/* The VDP1 list goes out by SCU DMA, which cannot read low work RAM: it lives in the
   overlay (high work RAM; a named .data section, as .bss would stay resident). */
static vdp1_cmdt_t commands[THANKS_COMMANDS] __attribute__((section(".data.fe_cr_commands"), aligned(32)));
static vdp1_cmdt_list_t list __attribute__((section(".data.fe_cr_list")));

static uint16_t be(const uint8_t *p) { return (uint16_t)(p[0] << 8 | p[1]); }

static void cram_write(const uint16_t cram[64])
{
    volatile uint16_t *out = (volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0, 0, 0);
    for (unsigned i = 0; i < 64; i++) {
        unsigned c = cram[i];
        out[i] = (uint16_t)(0x8000 | ((c >> 1) & 7) * 31 / 7 | (((c >> 5) & 7) * 31 / 7) << 5 | (((c >> 9) & 7) * 31 / 7) << 10);
    }
    /* Register 7: the backdrop is line 0 colour 0. */
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3, 0x1bffe), (rgb1555_t){.raw = out[0]});
}

/* A sprite piece's texture: its tiles (column-major, as the VDP reads them) row-major. */
static int texture_get(work *w, const uint8_t *vram, uint32_t vram_bytes, unsigned tile, unsigned width, unsigned height, uint32_t *address)
{
    for (unsigned i = 0; i < w->texture_count; i++) {
        const texture *t = &w->textures[i];
        if (t->tile == tile && t->width == width && t->height == height) { *address = t->address; return 0; }
    }
    uint32_t bytes = width * height * 32;
    if (w->texture_count == THANKS_TEXTURE_SLOTS || w->texture_next + bytes > THANKS_TEXTURES_END) return -1;
    volatile uint32_t *out = (volatile uint32_t *)VDP1_VRAM(w->texture_next);
    for (unsigned row = 0; row < height * 8; row++)
        for (unsigned col = 0; col < width; col++) {
            uint32_t at = ((tile + col * height + row / 8) & 0x7FF) * 32 + (row & 7) * 4;
            out[row * width + col] = at + 4 <= vram_bytes ?
                (uint32_t)vram[at] << 24 | (uint32_t)vram[at + 1] << 16 | (uint32_t)vram[at + 2] << 8 | vram[at + 3] : 0;
        }
    w->textures[w->texture_count++] = (texture){(uint16_t)tile, (uint8_t)width, (uint8_t)height, w->texture_next};
    *address = w->texture_next;
    w->texture_next += bytes;
    return 0;
}

/* The sprite table as VDP1 sprites: later entries first, so earlier ones stay on top. */
static vdp1_cmdt_t *clip_put(vdp1_cmdt_t *cmd, int top, int bottom)
{
    memset(cmd, 0, sizeof(*cmd));
    vdp1_cmdt_user_clip_coord_set(cmd);
    vdp1_cmdt_vtx_user_clip_coord_set(cmd, INT16_VEC2(0, top), INT16_VEC2(319, bottom));
    return cmd;
}

/* The sprite table as VDP1 sprites: later entries first, so earlier ones stay on top.
   Sprite masking as the Mega Drive VDP does it (Genesis Plus GX render_obj_m5): on a
   line, a sprite at X 0 after one at another X hides itself and every later sprite
   there. A sprite hidden on some of its lines is drawn once per visible run of lines,
   each inside a user clip window of those lines. */
static void sprites_put(work *w, const scd_credits_md *md, const uint8_t *vram, uint32_t vram_bytes)
{
    vdp1_cmdt_t *cmds = commands;
    unsigned count = 4;
    uint8_t seen[224], masked[224];
    memset(seen, 0, sizeof(seen));
    memset(masked, 0, sizeof(masked));
    /* Per sprite: up to THANKS_RUNS visible runs of screen lines (first, last). */
    int16_t runs[SCD_CREDITS_MD_SPRITES][THANKS_RUNS][2];
    uint8_t run_count[SCD_CREDITS_MD_SPRITES];
    for (unsigned i = 0; i < md->sprites; i++) {
        const uint16_t *e = md->sat[i];
        int top = (int)(e[0] & 0x3FF) - 128, rows = ((e[1] >> 8 & 3) + 1) * 8, x = e[3] & 0x1FF;
        int first = top < 0 ? 0 : top, last = top + rows - 1 > 223 ? 223 : top + rows - 1;
        run_count[i] = 0;
        int open = -1;
        for (int line = first; line <= last + 1; line++) {
            int visible = 0;
            if (line <= last) {
                if (!masked[line]) {
                    if (x) seen[line] = 1;
                    else if (seen[line]) masked[line] = 1;
                }
                visible = !masked[line];
            }
            if (visible && open < 0) open = line;
            if (!visible && open >= 0) {
                if (run_count[i] < THANKS_RUNS) {
                    runs[i][run_count[i]][0] = (int16_t)open;
                    runs[i][run_count[i]][1] = (int16_t)(line - 1);
                    run_count[i]++;
                }
                open = -1;
            }
        }
        /* Off the screen vertically: drawn whole, VDP1 clips it. */
        if (first > last) { runs[i][0][0] = 0; runs[i][0][1] = 223; run_count[i] = 1; }
    }
    for (int i = (int)md->sprites - 1; i >= 0; i--) {
        const uint16_t *e = md->sat[i];
        unsigned size = e[1] >> 8, width = ((size >> 2) & 3) + 1, height = (size & 3) + 1, attr = e[2];
        uint32_t address;
        if (count + 2 * run_count[i] + 2 > THANKS_COMMANDS) break;
        if (!run_count[i] || texture_get(w, vram, vram_bytes, attr & 0x7FF, width, height, &address)) continue;
        int top = (int)(e[0] & 0x3FF) - 128;
        int whole = run_count[i] == 1 && runs[i][0][0] <= (top < 0 ? 0 : top) &&
                    runs[i][0][1] >= (top + (int)height * 8 - 1 > 223 ? 223 : top + (int)height * 8 - 1);
        for (unsigned r = 0; r < run_count[i]; r++) {
            if (!whole) clip_put(&cmds[count++], runs[i][r][0], runs[i][r][1]);
            vdp1_cmdt_t *cmd = &cmds[count++];
            memset(cmd, 0, sizeof(*cmd));
            vdp1_cmdt_normal_sprite_set(cmd);
            const vdp1_cmdt_draw_mode_t mode = {.color_mode = VDP1_CMDT_CM_CLUT_16, .end_code_disable = true, .user_clipping_mode = 2};
            vdp1_cmdt_draw_mode_set(cmd, mode);
            vdp1_cmdt_char_size_set(cmd, (uint16_t)(width * 8), (uint16_t)(height * 8));
            vdp1_cmdt_char_base_set(cmd, VDP1_VRAM(address));
            vdp1_cmdt_char_flip_set(cmd, (attr & 0x0800 ? VDP1_CMDT_CHAR_FLIP_H : 0) | (attr & 0x1000 ? VDP1_CMDT_CHAR_FLIP_V : 0));
            cmd->cmd_colr = (uint16_t)((THANKS_CLUT + ((attr >> 15 & 1) * 4 + (attr >> 13 & 3)) * 32) / 8);
            cmd->cmd_xa = (int16_t)((e[3] & 0x1FF) - 128);
            cmd->cmd_ya = (int16_t)top;
            if (whole) break;
        }
        if (!whole) clip_put(&cmds[count++], 0, 223);
    }
    memset(&cmds[count], 0, sizeof(cmds[count]));
    vdp1_cmdt_end_set(&cmds[count]);
    list.cmdts = cmds;
    list.count = (uint16_t)(count + 1);
    vdp1_sync_cmdt_list_put(&list, 0);
    vdp1_sync_render();
    while (!vdp1_transfer_status_get().cef) {}
    vdp1_sync();
}

static void display_init(const uint8_t *vram, uint32_t vram_bytes, const uint8_t *planes)
{
    vdp2_scrn_display_set(0);
    const vdp2_vram_usage_t usage = {0};
    vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;
    memset(&cycles, 0xff, sizeof(cycles));
    cycles.pt[0].t0 = cycles.pt[0].t1 = VDP2_VRAM_CYCP_PNDR_NBG0;
    cycles.pt[0].t2 = cycles.pt[0].t3 = VDP2_VRAM_CYCP_PNDR_NBG1;
    cycles.pt[0].t4 = VDP2_VRAM_CYCP_CHPNDR_NBG0;
    cycles.pt[0].t5 = VDP2_VRAM_CYCP_CHPNDR_NBG1;
    vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0, 0), 0, 0x18000);
    memcpy((void *)VDP2_VRAM_ADDR(0, 0), vram, vram_bytes);
    for (unsigned i = 0; i < 2; i++) {
        vdp2_scrn_t screen = i ? VDP2_SCRN_NBG1 : VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt = {.scroll_screen = screen, .ccc = VDP2_SCRN_CCC_PALETTE_16,
            .char_size = VDP2_SCRN_CHAR_SIZE_1X1, .pnd_size = 2, .aux_mode = 0, .plane_size = VDP2_SCRN_PLANE_SIZE_1X1,
            .cpd_base = VDP2_VRAM_ADDR(0, 0), .palette_base = VDP2_CRAM_MODE_0_OFFSET(0, 0, 0)};
        vdp2_vram_t base = VDP2_VRAM_ADDR(0, i ? THANKS_MAP_B : THANKS_MAP_A);
        const vdp2_scrn_normal_map_t map = {.plane_a = base, .plane_b = base, .plane_c = base, .plane_d = base};
        vdp2_scrn_cell_format_set(&fmt, &map);
        /* Equal base priority keeps plane A over plane B; the cell bit raises high
           tiles over low sprites (priority register 0 = 2) as on the Mega Drive. */
        vdp2_scrn_priority_set(screen, 2);
        vdp2_scrn_sf_set(screen, VDP2_SCRN_SF_MODE_1, VDP2_SCRN_SF_TYPE_CELL_PRIORITY, VDP2_SCRN_SF_CODE_A);
        const vdp2_scrn_ls_format_t ls = {.scroll_screen = screen};
        vdp2_scrn_ls_set(&ls);
        vdp2_scrn_scroll_x_set(screen, 0);
        vdp2_scrn_scroll_y_set(screen, 0);
        const uint8_t *plane = planes + i * 4096;
        volatile uint32_t *out = (volatile uint32_t *)base;
        for (unsigned n = 0; n < 2048; n++) out[n] = stage_saturn_pnd(be(plane + n * 2), 0);
    }
    vdp2_sprite_priority_set(0, 2);
    vdp2_sprite_priority_set(1, 7);
    volatile uint16_t *clut = (volatile uint16_t *)VDP1_VRAM(THANKS_CLUT);
    for (unsigned high = 0; high < 2; high++)
        for (unsigned line = 0; line < 4; line++)
            for (unsigned i = 0; i < 16; i++) clut[(high * 4 + line) * 16 + i] = i ? (uint16_t)((high ? 0x4000 : 0) | (line * 16 + i)) : 0;
}

/* Plane A rows 12-15, columns 17-22: dsp_usrname's name. */
static void names_write(const scd_credits_md *md, const uint8_t *planes)
{
    volatile uint32_t *out = (volatile uint32_t *)VDP2_VRAM_ADDR(0, THANKS_MAP_A);
    for (unsigned r = 0; r < 4; r++)
        for (unsigned c = 0; c < 6; c++) {
            unsigned n = (12 + r) * 64 + 17 + c;
            uint16_t tile = md->names[r][c] ? md->names[r][c] : be(planes + n * 2);
            out[n] = stage_saturn_pnd(tile, 0);
        }
}

/* Best Time Attack initials, records in THANKS_M.MMD's order (entry, rank). */
static void names_load(work *w)
{
    fe_ta_records_default(&w->records);
    fe_ta_file_state files;
    fe_ta_records_load(&fe_ta_saturn_io, 0, &w->records, &files); /* the Classic pair, as before */
    for (unsigned e = 0; e < SCD_TA_ENTRIES; e++)
        for (unsigned k = 0; k < SCD_TA_RANKS; k++) {
            char *name = w->names[e * SCD_TA_RANKS + k];
            for (unsigned c = 0; c < 3; c++) name[c] = fe_ta_name_char(w->records.name[e][k][c]);
            name[3] = 0;
        }
}

static unsigned pad_read(void)
{
    smpc_peripheral_digital_t pad;
    smpc_peripheral_process();
    smpc_peripheral_digital_port(1, &pad);
    /* Yaul's pressed is the current level. */
    return (pad.pressed.button.start ? 0x80u : 0) | (pad.pressed.button.a ? 0x40u : 0) |
           (pad.pressed.button.c ? 0x20u : 0) | (pad.pressed.button.b ? 0x10u : 0);
}

__attribute__((noipa)) int fe_credits_thanks(void)
{
    volatile uint32_t *mb = scd_credits_mailbox;
    uint8_t *pack = (uint8_t *)THANKS_PACK;
    const cdfs_filelist_t *root = scd_cd_root_read();
    int loaded = -1;
    scd_low_packs_lost = 1;
    for (unsigned i = 0; i < root->entries_count; i++)
        if (!strcmp(root->entries[i].name, "THANKS.BIN") && root->entries[i].size <= THANKS_PACK_MAX)
            loaded = cd_block_sectors_read(root->entries[i].starting_fad, pack, root->entries[i].size);
    cpu_cache_purge();
    if (loaded || memcmp(pack, "THK1", 4)) return -1;
    const uint32_t vram_bytes = (uint32_t)pack[4] << 24 | (uint32_t)pack[5] << 16 | (uint32_t)pack[6] << 8 | pack[7];
    const uint8_t *vram = pack + 8, *planes = vram + vram_bytes;
    work *w = (work *)THANKS_WORK;
    memset(w, 0, sizeof(*w));
    names_load(w);
    w->config = (scd_credits_config){0, 0, (const char (*)[4])w->names, SCD_CREDITS_SEGA_CD};
    scd_audio_stop_music();
    /* Manual frame changes (the front end's mode; the caller sets it, as setting it
       again in that mode stalls VDP1, src/frontend.c fe_frontend_movie): each list is
       drawn from the top of its frame and shown from the next V-blank, with the
       colours written then. */
    vdp1_sync_wait();
    display_init(vram, vram_bytes, planes);
    vdp1_cmdt_t *cmds = commands;
    memset(cmds, 0, sizeof(vdp1_cmdt_t) * 4);
    vdp1_cmdt_system_clip_coord_set(&cmds[0]);
    vdp1_cmdt_vtx_system_clip_coord_set(&cmds[0], INT16_VEC2(319, 223));
    vdp1_cmdt_local_coord_set(&cmds[1]);
    vdp1_cmdt_vtx_local_coord_set(&cmds[1], INT16_VEC2(0, 0));
    vdp1_cmdt_user_clip_coord_set(&cmds[2]);
    vdp1_cmdt_vtx_user_clip_coord_set(&cmds[2], INT16_VEC2(0, 0), INT16_VEC2(319, 223));
    /* Manual frame changes do not erase: a transparent polygon clears the draw bank. */
    vdp1_cmdt_polygon_set(&cmds[3]);
    const vdp1_cmdt_draw_mode_t clear = {.color_mode = VDP1_CMDT_CM_RGB_32768, .end_code_disable = true, .trans_pixel_disable = true};
    vdp1_cmdt_draw_mode_set(&cmds[3], clear);
    cmds[3].cmd_xb = cmds[3].cmd_xc = 319;
    cmds[3].cmd_yc = cmds[3].cmd_yd = 223;
    w->texture_next = THANKS_TEXTURES;
    scd_credits_init(&w->st, &w->config);
    scd_credits_md_frame(&w->st, &w->md);
    names_write(&w->md, planes);
    /* The program's first picture: black (the fade starts from it). */
    cram_write(w->md.cram);
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0 | VDP2_SCRN_DISPTP_NBG1);
    vdp2_tvmd_display_set();
    mb[0] = 0;
    mb[2] = 0;
    mb[1] = 0x54484B50u;   /* "THKP" */
    mb[3] = ~0u;   /* the black picture before the first call */
    unsigned prev = 0, call = 0, frames = 0;
    for (;;) {
        vdp1_sync_wait();
        unsigned held = pad_read(), pressed = held & ~prev;
        prev = held;
        if (pressed) mb[7] = pressed;
        uint16_t t0 = cpu_frt_count_get();
        int result = scd_credits_frame(&w->st, (uint16_t)pressed);
        scd_credits_md_frame(&w->st, &w->md);
        for (unsigned i = 0; i < w->st.sound_count; i++) scd_audio_request((short)w->st.sounds[i]);
        uint16_t t1 = cpu_frt_count_get();
        /* Drawn now; VDP1 changes to it at the next V-blank. */
        sprites_put(w, &w->md, vram, vram_bytes);
        uint16_t t2 = cpu_frt_count_get();
        if ((uint16_t)(t1 - t0) > (mb[2] & 0xFFFF)) mb[2] = (mb[2] & 0xFFFF0000u) | (uint16_t)(t1 - t0);
        if ((uint16_t)(t2 - t1) > (mb[2] >> 16)) mb[2] = (mb[2] & 0xFFFFu) | (uint32_t)(uint16_t)(t2 - t1) << 16;
        vdp2_sync();
        vdp2_sync_wait();
        /* That V-blank: the picture's colours go with its sprites. */
        cram_write(w->md.cram);
        mb[3] = call++; mb[4] = w->st.md_phase; mb[5] = w->md.sprites; mb[6] = ++frames;
        scd_audio_update();
        if (result) {
            /* Show the last fade step for its frame. */
            vdp2_sync();
            vdp2_sync_wait();
            break;
        }
    }
    vdp2_scrn_display_set(0);
    vdp2_sync();
    vdp2_sync_wait();
    vdp1_sync_wait();
    /* Leave VDP1 idle with its draw-end flag set: the main loop started a clear before
       the front end's step and waits for that flag after it (src/gameplay_video.inc
       gameplay_clear_wait); the manual frame changes here can leave it clear. */
    memset(commands, 0, sizeof(commands[0]));
    vdp1_cmdt_end_set(&commands[0]);
    memcpy((void *)VDP1_VRAM(0), commands, sizeof(commands[0]));
    MEMORY_WRITE(16, VDP1_IOREG_BASE + PTMR, 1);
    while (!vdp1_transfer_status_get().cef) {}
    vdp2_sprite_priority_set(0, 4);
    vdp2_sprite_priority_set(1, 7);
    mb[1] = 0x54484B44u;   /* "THKD" */
    return 0;
}

/* Visual Mode's good-ending replay (src/visual_mode.c, IPX.asm:1184 RunMMD(SCMD_THANKYOU))
   replaces its weak no-op with this. */
void fe_vm_thanks(void)
{
    fe_credits_thanks();
}
