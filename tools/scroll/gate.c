/* Scroll IR gate: the generic evaluator (evaluate.c, driven only by IR tables
   extracted from the retail C) against the REAL src/background.c, for the
   twelve zone-0 background ids.

   Build and run: sh tools/scroll/run_gate.sh

   Three builds of the port are linked side by side, their public functions
   renamed with -D (run_gate.sh):
     literal     src/background.c exactly as it is
     wrap        a copy with `y&=511` added to the era 1/2/3 branch
                 (tools/scroll/patch_port.py)
     wrap+floor  that copy, plus the era 0 ramps rounding down as retail's
                 16.16 accumulator does

   Sweep per id: background Y 0..2047 x camera X x frame x ramp for the
   raster, camera Y 0..4095 x player X for the background Y.  An id is exact
   when both have zero mismatches.  Every mismatch is counted; the first one
   is printed.  Exit status is 0 only when the `wrap` build is exact for
   all 12 ids. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "evaluate.h"

extern const scroll_ir *const scroll_ir_slots[];
extern const char *const scroll_ir_slot_source[];

#define PORT(P) int P##_raster_x(unsigned,int,int,unsigned,int32_t); int P##_y(unsigned,int,int);
PORT(lit) PORT(wrap) PORT(wrapfloor)

typedef int (*raster_fn)(unsigned, int, int, unsigned, int32_t);
typedef int (*bgy_fn)(unsigned, int, int);
static const struct { const char *name; raster_fn raster; bgy_fn bgy; } ports[] = {
    {"literal", lit_raster_x, lit_y},
    {"wrap", wrap_raster_x, wrap_y},
    {"wrap+floor", wrapfloor_raster_x, wrapfloor_y},
};
#define NPORTS 3
#define NIDS 12

static const int xs[] = {0, 0x400, 0x800, 0x1000, 0x1800, 0x2000, 0x2800, 0x3000, 0x3c00};
static const unsigned frames[] = {0, 1, 2, 17, 60, 255, 256, 1000, 4095, 65535};
static const int32_t ramps[] = {0, 1, 255, 256, 0x1234, 0x4000, 0x7fff, -1, -256, -0x1234, -0x4000};
static const int pxs[] = {0, 0x400, 0x7ff, 0x800, 0x801, 0x1000, 0x2000, 0x3000};
/* outside the gate grid: camera X that is not a multiple of 256 */
static const int odd_xs[] = {1, 7, 0x155, 0x7ff, 0x801, 0x1fff, 0x2345, 0x3fff};
#define N(a) (sizeof(a) / sizeof((a)[0]))

typedef struct {
    long raster_bad, raster_bad_hi, bgy_bad, raster_n, bgy_n;
    long by_x[16], ramp_pos, ramp_neg, ramp_zero;
    int ymin, ymax;
    int first_kind;                 /* 0 none, 1 raster, 2 bgy */
    int fx, fy, fport, fir; unsigned ff; int32_t fr;
} tally;

static const scroll_ir *ir_for(int id, int *aliased) {
    const scroll_ir *ir = scroll_ir_slots[id];
    *aliased = 0;
    /* ALIAS: act 3 has no Present or Past program in any round (the file
       does not exist).  Such an id is compared against the act-1 program of
       the same era.  Not retail-derived; applies to ids 8 and 9 here. */
    if (!ir && id / 4 == 2 && id % 4 < 2 && !strcmp(scroll_ir_slot_source[id], "no program file")) {
        ir = scroll_ir_slots[id % 4];
        *aliased = 1;
    }
    return ir;
}

static void run(int id, const scroll_ir *ir, int p, tally *t, const int *xv, size_t nx) {
    memset(t, 0, sizeof(*t));
    for (size_t xi = 0; xi < nx; xi++)
        for (size_t fi = 0; fi < N(frames); fi++)
            for (size_t ri = 0; ri < N(ramps); ri++)
                for (int y = 0; y < 2048; y++) {
                    int x = xv[xi];
                    int a = ports[p].raster((unsigned)id, x, y, frames[fi], ramps[ri]);
                    int b = scroll_ir_raster_x(ir, x, y, frames[fi], ramps[ri]);
                    t->raster_n++;
                    if (a != b) {
                        if (!t->raster_bad) t->ymin = t->ymax = y;
                        t->raster_bad++;
                        if (y >= 512) t->raster_bad_hi++;
                        if (xi < 16) t->by_x[xi]++;
                        if (ramps[ri] > 0) t->ramp_pos++; else if (ramps[ri] < 0) t->ramp_neg++; else t->ramp_zero++;
                        if (y < t->ymin) t->ymin = y;
                        if (y > t->ymax) t->ymax = y;
                        if (!t->first_kind) {
                            t->first_kind = 1; t->fx = x; t->fy = y; t->ff = frames[fi];
                            t->fr = ramps[ri]; t->fport = a; t->fir = b;
                        }
                    }
                }
    for (size_t pi = 0; pi < N(pxs); pi++)
        for (int y = 0; y < 4096; y++) {
            int a = ports[p].bgy((unsigned)id, y, pxs[pi]);
            int b = scroll_ir_background_y(ir, y, pxs[pi]);
            t->bgy_n++;
            if (a != b) {
                t->bgy_bad++;
                if (t->first_kind != 2 && !t->raster_bad && !(t->first_kind == 2)) {
                    t->first_kind = 2; t->fx = pxs[pi]; t->fy = y; t->fport = a; t->fir = b;
                }
            }
        }
}

int main(void) {
    int exact[NPORTS] = {0};
    tally tallies[NIDS][NPORTS];
    printf("scroll IR gate: evaluator vs src/background.c, zone 0 (ids 0..11)\n");
    printf("raster grid: y 0..2047 x %zu camera X x %zu frames x %zu ramps; bg Y grid: camera Y 0..4095 x %zu player X\n\n",
           N(xs), N(frames), N(ramps), N(pxs));
    printf("id  source                 %-26s %-26s %-26s\n", ports[0].name, ports[1].name, ports[2].name);
    for (int id = 0; id < NIDS; id++) {
        int aliased;
        const scroll_ir *ir = ir_for(id, &aliased);
        char label[64];
        snprintf(label, sizeof label, "%s%s", aliased ? "ALIAS " : "", ir ? ir->program : scroll_ir_slot_source[id]);
        printf("%2d  %-22s", id, label);
        for (int p = 0; p < NPORTS; p++) {
            char cell[64];
            if (!ir) { printf(" %-26s", "NO IR"); continue; }
            tally *t = &tallies[id][p];
            run(id, ir, p, t, xs, N(xs));
            if (!t->raster_bad && !t->bgy_bad) { exact[p]++; snprintf(cell, sizeof cell, "exact"); }
            else snprintf(cell, sizeof cell, "raster %ld, bgY %ld", t->raster_bad, t->bgy_bad);
            printf(" %-26s", cell);
        }
        printf("\n");
    }
    printf("\nsamples per id: raster %ld, bg Y %ld\n", tallies[0][0].raster_n, tallies[0][0].bgy_n);
    printf("\nFIRST MISMATCH PER FAILING CELL (port value vs IR value)\n");
    for (int id = 0; id < NIDS; id++) {
        int aliased;
        const scroll_ir *ir = ir_for(id, &aliased);
        if (!ir) continue;
        for (int p = 0; p < NPORTS; p++) {
            tally *t = &tallies[id][p];
            if (!t->raster_bad && !t->bgy_bad) continue;
            if (t->raster_bad) {
                printf("  id %2d %-10s raster: %ld bad (%ld at y>=512, %ld below); first x=%d y=%d frame=%u ramp=%d port=%d ir=%d\n",
                       id, ports[p].name, t->raster_bad, t->raster_bad_hi, t->raster_bad - t->raster_bad_hi,
                       t->fx, t->fy, t->ff, t->fr, t->fport, t->fir);
                printf("         y %d..%d; ramp >0: %ld, <0: %ld, =0: %ld; by camera X:", t->ymin, t->ymax,
                       t->ramp_pos, t->ramp_neg, t->ramp_zero);
                for (size_t xi = 0; xi < N(xs); xi++) if (t->by_x[xi]) printf(" 0x%x:%ld", xs[xi], t->by_x[xi]);
                printf("\n");
            }
            if (t->bgy_bad) {
                int bad_y = -1, bad_px = 0, pv = 0, iv = 0;
                for (size_t pi = 0; pi < N(pxs) && bad_y < 0; pi++)
                    for (int y = 0; y < 4096; y++) {
                        int a = ports[p].bgy((unsigned)id, y, pxs[pi]), b = scroll_ir_background_y(ir, y, pxs[pi]);
                        if (a != b) { bad_y = y; bad_px = pxs[pi]; pv = a; iv = b; break; }
                    }
                printf("  id %2d %-10s bg Y:   %ld bad; first camera_y=%d player_x=%d port=%d ir=%d\n",
                       id, ports[p].name, t->bgy_bad, bad_y, bad_px, pv, iv);
            }
        }
    }
    printf("\nDIAGNOSTIC (not part of the gate): camera X not a multiple of 256, against wrap+floor\n");
    for (int id = 0; id < NIDS; id++) {
        int aliased;
        const scroll_ir *ir = ir_for(id, &aliased);
        if (!ir) continue;
        tally t;
        run(id, ir, 2, &t, odd_xs, N(odd_xs));
        if (t.raster_bad)
            printf("  id %2d raster: %ld of %ld differ; first x=%d y=%d frame=%u ramp=%d port=%d ir=%d\n",
                   id, t.raster_bad, t.raster_n, t.fx, t.fy, t.ff, t.fr, t.fport, t.fir);
        else
            printf("  id %2d raster: 0 of %ld differ\n", id, t.raster_n);
    }
    int real[NPORTS] = {0}, nreal = 0;
    for (int id = 0; id < NIDS; id++) {
        if (!scroll_ir_slots[id]) continue;
        nreal++;
        for (int p = 0; p < NPORTS; p++) real[p] += !tallies[id][p].raster_bad && !tallies[id][p].bgy_bad;
    }
    printf("\nids with a retail program (%d):  literal %d/%d   with wrap %d/%d   with wrap+floor %d/%d\n",
           nreal, real[0], nreal, real[1], nreal, real[2], nreal);
    printf("GATE  literal: %d/%d exact   with wrap: %d/%d exact   with wrap+floor: %d/%d exact\n",
           exact[0], NIDS, exact[1], NIDS, exact[2], NIDS);
    if (exact[1] != NIDS) {
        printf("GATE FAIL: the wrap build is exact for %d of %d ids (see the mismatches above)\n", exact[1], NIDS);
        return 1;
    }
    printf("GATE PASS\n");
    return 0;
}
