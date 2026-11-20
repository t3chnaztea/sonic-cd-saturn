/* Reference side of tools/credits_test.c: the PC TITLE/THANKS module
   (prepared by tools/test_credits.py into build/credits/reference) driven
   through its DLL interface with host stand-ins for the PC imports. */
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "../../TYPES.H"
#include "../COMMON/SCORE_DATA_TYPES.H"
#include "THANKS_TYPES.H"
#include "GAME.H"
#include "credits.h"
#include "credits_tables.h"
#include "credits_side.h"

#define X(name) extern sprite_patterns_title name;
SCD_CREDITS_PATTERN_NAMES
#undef X
#define X(name) &name,
static sprite_patterns_title *const patterns[] = {SCD_CREDITS_PATTERN_NAMES};
#undef X

extern sprite_status_thanks actwk[66];
extern sprite_status_thanks *pribuf0[64], *pribuf1[64], *pribuf2[64], *pribuf3[64];
extern short actset_tm[8];
extern short end_timer, heart_tm, animal_timer, posetimer, coltimer, colorno, coltimer2, colorno2, prg_mode;
extern unsigned char animal_flg, poseno, quit_flg;
extern short_union swdata1;
extern int ranum;
extern char GreatestPlayer[4];
extern bmp_info SprBmp[700];

/* The prepared source rewrites ((short*)p)[31] to free[4]; it must be aligned. */
_Static_assert(offsetof(sprite_status_thanks, free) % 2 == 0, "free[4] short alias");

static PALETTEENTRY colorwk[4][64];
static char *colorwk_ptr[4] = {(char *)colorwk[0], (char *)colorwk[1], (char *)colorwk[2], (char *)colorwk[3]};
static int_union hscroll[256];
static char *hscroll_ptr = (char *)hscroll;
static int fade_flag;
static game_info keep;
static score_data scores;
static unsigned int surf, wnd;

static struct {
    scd_credits_sprite sprites[SCD_CREDITS_SPRITES];
    uint16_t overflow;
    uint16_t plane[2][SCD_CREDITS_PLANE_H * SCD_CREDITS_PLANE_W];
    uint16_t sounds[SCD_CREDITS_SOUNDS];
    uint8_t sound_count;
} host;
static const credits_side_config *cfg;

static int set_grid(int plane, int x, int y, int tile, int unused)
{
    (void)unused;
    if (plane >= 0 && plane < 2 && (unsigned)x < SCD_CREDITS_PLANE_W && (unsigned)y < SCD_CREDITS_PLANE_H)
        host.plane[plane][y * SCD_CREDITS_PLANE_W + x] = (uint16_t)tile;
    return 0;
}
static void eas_prset(short x, short y, unsigned short index, unsigned short link, unsigned short flags)
{
    if (link >= SCD_CREDITS_SPRITES) { host.overflow++; return; }
    host.sprites[link] = (scd_credits_sprite){x, y, index, flags};
}
static void clr_sprite_debug(void) {}
static void wave_request(short wav)
{
    /* SeToWavTbl maps 144..154 to 0..10; soundset only requests 144 and 146. */
    if (host.sound_count < SCD_CREDITS_SOUNDS) host.sounds[host.sound_count++] = wav >= 0 && wav <= 10 ? (uint16_t)(wav + 144) : 0xFFFF;
}
static void cd_play(short track) { (void)track; }
static void change_tile_bmp(int a, int b) { (void)a; (void)b; }
static void mem_set(void *p, unsigned char v, int n) { memset(p, v, (size_t)n); }
static void mem_cpy(void *d, void *s, int n) { memcpy(d, s, (size_t)n); }
static int mem_cmp(void *a, void *b, int n) { return memcmp(a, b, (size_t)n); }
static int host_random(void) { return 0; }
static char *str_cpy(char *d, char *s) { return strcpy(d, s); }
static void host_printf(char *d, char *f) { (void)d; (void)f; }
static void debug_string(char *s) { (void)s; }
static int open_file(char *name)
{
    const char *base = strrchr(name, '\\');
    base = base ? base + 1 : name;
    if (!strcmp(base, "VA_MAP.BIN")) return cfg->map_a ? 1 : -1;
    if (!strcmp(base, "VB_MAP.BIN")) return cfg->map_b ? 2 : -1;
    return -1;
}
static int read_file(int handle, void *buffer, int size)
{
    const int16_t *map = handle == 1 ? cfg->map_a : cfg->map_b;
    int bytes = size < SCD_CREDITS_MAP_WORDS * 2 ? size : SCD_CREDITS_MAP_WORDS * 2;
    memcpy(buffer, map, (size_t)bytes);
    return bytes;
}
static void close_file(int handle) { (void)handle; }

void side_init(const credits_side_config *config)
{
    static void *funcs[25];
    static char **buffers[11];
    cfg = config;
    memset(&host, 0, sizeof(host));
    memset(&scores, 0, sizeof(scores));
    if (config->names)
        for (int i = 0; i < SCD_CREDITS_NAMES; i++) {
            char *dst = i < 63 ? scores.timeattack[i / 9][i / 3 % 3][i % 3].name : scores.special[(i - 63) / 3][(i - 63) % 3].name;
            memcpy(dst, config->names[i], 4);
        }
    keep.EndingMesType = config->ending_type;
    funcs[0] = (void *)set_grid; funcs[1] = (void *)eas_prset; funcs[2] = (void *)clr_sprite_debug;
    funcs[3] = (void *)wave_request; funcs[4] = (void *)cd_play; funcs[6] = (void *)change_tile_bmp;
    funcs[13] = (void *)mem_set; funcs[14] = (void *)mem_cpy; funcs[15] = (void *)mem_cmp;
    funcs[16] = (void *)host_random; funcs[17] = (void *)str_cpy; funcs[20] = (void *)host_printf;
    funcs[21] = (void *)debug_string; funcs[22] = (void *)open_file; funcs[23] = (void *)read_file;
    funcs[24] = (void *)close_file;
    for (int i = 0; i < 4; i++) buffers[1 + i] = &colorwk_ptr[i];
    buffers[5] = &hscroll_ptr;
    buffers[6] = (char **)&fade_flag;
    buffers[7] = (char **)&keep;
    buffers[8] = (char **)&surf;
    buffers[9] = (char **)&wnd;
    buffers[10] = (char **)&scores;
    DLL_meminit((char ***)buffers, funcs);
    game_init();
    if (config->seeded) ranum = config->seed;
}

int side_frame(uint16_t pad)
{
    ushort_union sw1, sw2;
    sw1.w = pad;
    sw2.w = 0;
    host.sound_count = 0;
    SWdataSet(sw1, sw2);
    return game();
}

static int slot_of(const sprite_status_thanks *a) { return a ? (int)(a - actwk) + 1 : 0; }

static int pattern_id(const sprite_patterns_title *p)
{
    if (!p) return 0;
    for (unsigned i = 0; i < SCD_CREDITS_PATTERN_COUNT; i++)
        if (patterns[i] == p) return (int)i;
    return -1;
}

unsigned side_snapshot(int32_t *out)
{
    unsigned n = 0;
    for (int i = 0; i < SCD_CREDITS_ACTORS; i++) {
        const sprite_status_thanks *a = &actwk[i];
        int32_t v[] = {a->ACT_NO, a->EXE_NO, a->XPOSI.l, a->YPOSI.l, a->X_SPEED.l, a->Y_SPEED.l, a->X_ACCEL.l,
                       a->Y_ACCEL.l, a->X_OFFSET, a->Y_OFFSET, a->SIN_CNT, a->TM_CNT, a->SPR_TIMER, a->PAT_NO,
                       a->CGBASE, pattern_id(a->PAT_ADR), a->SPR_FLG, a->ACT_FLG, a->END_XPOSI, a->END_YPOSI,
                       a->X_WIDE, a->Y_WIDE};
        for (unsigned k = 0; k < sizeof(v) / sizeof(v[0]); k++) out[n++] = v[k];
        for (int k = 0; k < 8; k++) out[n++] = a->free[k];
    }
    sprite_status_thanks **lists[4] = {pribuf0, pribuf1, pribuf2, pribuf3};
    for (int p = 0; p < 4; p++)
        for (int i = 0; i < 64; i++) out[n++] = slot_of(lists[p][i]);
    for (int i = 0; i < SCD_CREDITS_SPRITES; i++) {
        out[n++] = host.sprites[i].x; out[n++] = host.sprites[i].y;
        out[n++] = host.sprites[i].index; out[n++] = host.sprites[i].flags;
    }
    out[n++] = host.overflow;
    for (int i = 0; i < 64; i++) {
        out[n++] = colorwk[0][i].peRed; out[n++] = colorwk[0][i].peGreen; out[n++] = colorwk[0][i].peBlue;
    }
    out[n++] = host.sound_count;
    for (int i = 0; i < SCD_CREDITS_SOUNDS; i++) out[n++] = i < host.sound_count ? host.sounds[i] : 0;
    for (int i = 0; i < 8; i++) out[n++] = actset_tm[i];
    int32_t t[] = {end_timer, heart_tm, animal_timer, posetimer, coltimer, colorno, coltimer2, colorno2, prg_mode,
                   (uint16_t)swdata1.w, animal_flg, poseno, quit_flg, ranum,
                   (int32_t)((uint32_t)(uint8_t)GreatestPlayer[0] | (uint32_t)(uint8_t)GreatestPlayer[1] << 8 |
                             (uint32_t)(uint8_t)GreatestPlayer[2] << 16)};
    for (unsigned k = 0; k < sizeof(t) / sizeof(t[0]); k++) out[n++] = t[k];
    for (int p = 0; p < 2; p++)
        for (int i = 0; i < SCD_CREDITS_PLANE_H * SCD_CREDITS_PLANE_W; i++) out[n++] = host.plane[p][i];
    (void)SprBmp;
    return n;
}
