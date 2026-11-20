/* Credits ("Thank You" screen) parity harness.  Built twice by
   tools/test_credits.py: natively against src/credits.c, and with
   -DSCD_CREDITS_REFERENCE against the PC TITLE/THANKS sources
   (tools/credits_reference.c).  Both print one FNV-1a hash of the whole
   screen state per frame; the logs must be identical.

   credits_test <scenario>            per-frame log
   credits_test <scenario> dump <n>   every snapshot value after frame n
   credits_test md <frames> <press> [name]   native only: the Sega CD mode
       (SCD_CREDITS_SEGA_CD, every save name 'name', default AAA) with Start held 4
       frames from <press> (-1 none); per frame "md <frame> <result> <sat> <cram>
       <names>" as hex words (sat: the linked entries), for tools/test_credits.py's
       comparison with the retail THANKS_M.MMD frames (tools/credits_retail.py). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "credits.h"
#include "credits_side.h"

#ifndef SCD_CREDITS_REFERENCE
static scd_credits native;
static uint16_t coverage[12][16];

void side_init(const credits_side_config *config)
{
    static scd_credits_config c;
    c = (scd_credits_config){config->map_a, config->map_b, config->names, config->ending_type};
    scd_credits_init(&native, &c);
    if (config->seeded) native.ranum = config->seed;
}

int side_frame(uint16_t pad)
{
    int r = scd_credits_frame(&native, pad);
    for (int i = 0; i < 64; i++) {
        const scd_credits_actor *a = &native.actors[i];
        if (a->act_no && a->act_no < 12 && a->exe_no < 16) coverage[a->act_no][a->exe_no]++;
    }
    return r;
}

unsigned side_snapshot(int32_t *out)
{
    unsigned n = 0;
    for (int i = 0; i < SCD_CREDITS_ACTORS; i++) {
        const scd_credits_actor *a = &native.actors[i];
        int32_t v[] = {a->act_no, a->exe_no, a->x, a->y, a->x_speed, a->y_speed, a->x_accel, a->y_accel,
                       a->x_offset, a->y_offset, a->sin_cnt, a->tm_cnt, a->spr_timer, a->pat_no, a->cgbase,
                       /* PAT_ADR is NULL until the first init; pattern 0 is also s_stand1_map. */
                       a->pattern, a->spr_flg, a->act_flg, a->end_x, a->end_y, a->x_wide, a->y_wide};
        for (unsigned k = 0; k < sizeof(v) / sizeof(v[0]); k++) out[n++] = v[k];
        for (int k = 0; k < 8; k++) out[n++] = a->free[k];
    }
    for (int p = 0; p < 4; p++)
        for (int i = 0; i < 64; i++) out[n++] = native.pribuf[p][i];
    for (int i = 0; i < SCD_CREDITS_SPRITES; i++) {
        out[n++] = native.sprites[i].x; out[n++] = native.sprites[i].y;
        out[n++] = native.sprites[i].index; out[n++] = native.sprites[i].flags;
    }
    out[n++] = native.sprite_overflow;
    for (int i = 0; i < 64; i++)
        for (int k = 0; k < 3; k++) out[n++] = native.palette[i][k];
    out[n++] = native.sound_count;
    for (int i = 0; i < SCD_CREDITS_SOUNDS; i++) out[n++] = i < native.sound_count ? native.sounds[i] : 0;
    for (int i = 0; i < 8; i++) out[n++] = native.actset_tm[i];
    const char *g = native.greatest;
    int32_t t[] = {native.end_timer, native.heart_tm, native.animal_timer, native.posetimer, native.coltimer,
                   native.colorno, native.coltimer2, native.colorno2, native.prg_mode, native.swdata1,
                   native.animal_flg, native.poseno, native.quit_flg, native.ranum,
                   (int32_t)((uint32_t)(uint8_t)g[0] | (uint32_t)(uint8_t)g[1] << 8 | (uint32_t)(uint8_t)g[2] << 16)};
    for (unsigned k = 0; k < sizeof(t) / sizeof(t[0]); k++) out[n++] = t[k];
    for (int p = 0; p < 2; p++)
        for (int i = 0; i < SCD_CREDITS_PLANE_H * SCD_CREDITS_PLANE_W; i++) out[n++] = native.plane[p][i];
    return n;
}
#endif

static int16_t map_a[SCD_CREDITS_MAP_WORDS], map_b[SCD_CREDITS_MAP_WORDS];
static char names[SCD_CREDITS_NAMES][4];

static uint32_t lcg(uint32_t *s) { *s = *s * 1664525u + 1013904223u; return *s >> 8; }

static void make_names(int set, uint32_t seed)
{
    static const char *pool[4][6] = {
        {"SEG", "AAA", "B9Q", "ZZ1", "KAZ", "NAO"},
        {"", "", "", "", "", ""},
        {"a b", "sOn", "  X", "t.t", "q12", "-Q-"},
        {"0Q9", "Q00", "90Q", "ZYX", "0Q9", "Q00"}};
    for (int i = 0; i < SCD_CREDITS_NAMES; i++) {
        const char *pick = pool[set][lcg(&seed) % 6];
        memset(names[i], 0, 4);
        memcpy(names[i], pick, strlen(pick));
    }
}

/* Scenario table: ending type, button frame, names set (-1 none), maps, seed. */
typedef struct { uint8_t type; int press, hold, names, maps, seeded; int32_t seed; int frames; } scenario;
static const scenario scenarios[] = {
    {1, 400, 0, 0, 1, 0, 0, 12000},          /* good ending message, press, full screen */
    {2, 365, 0, 0, 1, 0, 0, 1000},           /* bad ending message, press, exit */
    {0, 4000, 0, 2, 0, 0, 0, 5000},          /* no message: 360 idle frames, then the screen */
    {1, 1, 1, 3, 1, 0, 0, 1000},             /* button held: message skipped, then quit */
    {1, 360, 0, 0, 1, 1, 1, 12000},
    {1, 360, 0, -1, 0, 1, 0x12345678, 12000},
    {1, 360, 0, 2, 1, 1, -1, 12000},
    {1, 360, 0, 3, 1, 1, 0x7FFFFFFF, 12000},
    {1, 360, 0, 0, 0, 1, 987654321, 12000},
    {1, 360, 0, 1, 1, 1, 42, 12000},
    {1, 360, 0, 2, 1, 1, 0x0BADF00D, 12000},
    {1, 360, 0, 3, 0, 1, 31337, 12000},
};

#ifndef SCD_CREDITS_REFERENCE
static void hex_words(const uint16_t *w, unsigned n)
{
    putchar(' ');
    if (!n) putchar('-');
    for (unsigned i = 0; i < n; i++) printf("%04x", w[i]);
}

static int md_run(int frames, int press, const char *name)
{
    static char md_names[SCD_CREDITS_NAMES][4];
    for (int i = 0; i < SCD_CREDITS_NAMES; i++) {
        memset(md_names[i], 0, 4);
        strncpy(md_names[i], name, 3);
    }
    static scd_credits_config c;
    c = (scd_credits_config){0, 0, (const char (*)[4])md_names, SCD_CREDITS_SEGA_CD};
    scd_credits_init(&native, &c);
    static scd_credits_md md;
    for (int frame = 0; frame < frames; frame++) {
        uint16_t pad = press >= 0 && frame >= press && frame < press + 4 ? 0x0080 : 0;
        int r = scd_credits_frame(&native, pad);
        scd_credits_md_frame(&native, &md);
        printf("md %d %d", frame, r);
        hex_words(&md.sat[0][0], md.sprites * 4u);
        hex_words(md.cram, 64);
        hex_words(&md.names[0][0], 24);
        putchar('\n');
        if (getenv("CREDITS_MD_ACTORS")) {
            /* The 64 actors in THANKS_M.MMD 64-byte layout ($FF9200); PAT_ADR holds
               the pattern index. */
            printf("act %d", frame);
            for (int i = 0; i < 64; i++) {
                const scd_credits_actor *a = &native.actors[i];
                uint16_t w[32];
                const int32_t l[6] = {a->x, a->y, a->x_speed, a->y_speed, a->x_accel, a->y_accel};
                w[0] = a->act_no; w[1] = a->exe_no;
                for (int k = 0; k < 6; k++) { w[2 + 2 * k] = (uint16_t)((uint32_t)l[k] >> 16); w[3 + 2 * k] = (uint16_t)l[k]; }
                const int16_t sh[7] = {a->x_offset, a->y_offset, a->sin_cnt, a->tm_cnt, a->spr_timer, a->pat_no, a->cgbase};
                for (int k = 0; k < 7; k++) w[14 + k] = (uint16_t)sh[k];
                w[21] = 0; w[22] = a->pattern;
                w[23] = (uint16_t)(a->spr_flg << 8 | a->act_flg);
                /* The retail record has no END_XPOSI/END_YPOSI: X_WIDE follows the flags.
                   Words 30-31 (past free[]) carry them here. */
                w[24] = (uint16_t)a->x_wide; w[25] = (uint16_t)a->y_wide;
                for (int k = 0; k < 4; k++) w[26 + k] = (uint16_t)(a->free[2 * k] << 8 | a->free[2 * k + 1]);
                /* free[4..5]: the PC's little-endian short (pit counter), a word on the 68000. */
                w[28] = (uint16_t)(a->free[5] << 8 | a->free[4]);
                w[30] = (uint16_t)a->end_x; w[31] = (uint16_t)a->end_y;
                hex_words(w, 32);
            }
            putchar('\n');
        }
        if (r) break;
    }
    return 0;
}
#endif

int main(int argc, char **argv)
{
#ifndef SCD_CREDITS_REFERENCE
    if (argc >= 4 && !strcmp(argv[1], "md")) return md_run(atoi(argv[2]), atoi(argv[3]), argc > 4 ? argv[4] : "AAA");
#endif
    if (argc < 2) {
        printf("%u\n", (unsigned)(sizeof(scenarios) / sizeof(scenarios[0])));
        return 0;
    }
    unsigned index = (unsigned)atoi(argv[1]);
    if (index >= sizeof(scenarios) / sizeof(scenarios[0])) return 2;
    int dump = argc >= 4 && !strcmp(argv[2], "dump") ? atoi(argv[3]) : -1;
    const scenario *s = &scenarios[index];
    uint32_t seed = 0xC0FFEE + index;
    for (int i = 0; i < SCD_CREDITS_MAP_WORDS; i++) {
        uint32_t r = lcg(&seed);
        map_a[i] = (int16_t)(r % 5 == 0 ? 0 : r);
        map_b[i] = (int16_t)(r % 7 == 0 ? 0 : r >> 3);
    }
    if (s->names >= 0) make_names(s->names, seed);
    credits_side_config c = {s->maps ? map_a : 0, s->maps ? map_b : 0,
                             s->names >= 0 ? (const char (*)[4])names : 0, s->type, s->seeded, s->seed};
    side_init(&c);
    static int32_t snap[CREDITS_SNAPSHOT_MAX];
    int frame = 0, result = 0;
    for (; frame < s->frames; frame++) {
        uint16_t pad = frame == s->press || (s->hold && frame >= s->press) ? 0x0080 : 0;
        result = side_frame(pad);
        unsigned n = side_snapshot(snap);
        if (frame == dump) {
            for (unsigned i = 0; i < n; i++) printf("%u %d\n", i, snap[i]);
            return 0;
        }
        uint32_t h = 2166136261u;
        for (unsigned i = 0; i < n; i++)
            for (int b = 0; b < 32; b += 8) h = (h ^ ((uint32_t)snap[i] >> b & 0xFF)) * 16777619u;
        printf("%d %d %08x\n", frame, result, h);
        if (result) break;
    }
    printf("summary scenario=%u frames=%d result=%d\n", index, frame + 1, result);
#ifndef SCD_CREDITS_REFERENCE
    for (int a = 1; a < 12; a++)
        for (int e = 0; e < 16; e++)
            if (coverage[a][e]) fprintf(stderr, "coverage %d %d %u\n", a, e, coverage[a][e]);
#endif
    return 0;
}
