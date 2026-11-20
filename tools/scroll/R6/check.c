/* Structural and range check of every draft IR, through the extended
   evaluator (evaluate_ext.c) and the generated tables (build/ir_ext_tables.c).

     cc -O2 -I tools/scroll/R6 tools/scroll/R6/check.c tools/scroll/R6/evaluate_ext.c \
        tools/scroll/R6/build/ir_ext_tables.c -o tools/scroll/R6/build/check

   Per document:
     cover   every buffer line is covered by exactly one of: a band, a run, or
             the unwritten tail (table_end..buffer_lines); runs sum to <= buffer
     range   camera X -4096..16383 (every value) x background line
             0..buffer_lines+7 (the wrap included): a run line's value lies
             between its two layers (layer: equals it; lerp/step: between
             `from` and `to`, inclusive); an unwritten line is 0; for camera
             X 0..16383 every value fits a signed 16-bit word
     inputs  with every U = 0 and no cloud the value may not depend on the
             ramp or the frame (checked on a sub-grid: 4 ramps x 5 frames)
     bg_y    camera Y -32768..65535: 0 <= value <= the op's maximum, and
             non-decreasing in (uint16)camera Y
   Any failure is printed and the exit status is 1. */
#include <stdio.h>
#include <stdlib.h>
#include "evaluate_ext.h"

extern const scroll_ir *const scroll_ir_ext_all[];
extern const unsigned scroll_ir_ext_count;

static int64_t fdiv(int64_t a, int64_t b) { int64_t q = a / b; if ((a % b) && ((a < 0) != (b < 0))) q--; return q; }
static int64_t lay(const scroll_ir *ir, unsigned i, int x) { return fdiv((int64_t)ir->layers[i].C * x, 256); }

/* 0: unwritten, 1: run (sets *e), 2: band (sets *e); -1 if two sources claim the line */
static int source(const scroll_ir *ir, int line, const scroll_expr **e) {
    int n = 0, kind = 0, end = 0;
    for (unsigned i = 0; i < ir->nbands; i++)
        if (line >= ir->bands[i].start && line < ir->bands[i].start + ir->bands[i].lines) { n++; kind = 2; *e = &ir->bands[i].e; }
    if (n > 1) return -1;
    if (n == 1) return kind;
    for (unsigned i = 0; i < ir->nruns; i++) {
        end += ir->runs[i].lines;
        if (line < end) { *e = &ir->runs[i].e; return 1; }
    }
    return 0;
}

int main(void) {
    int failed = 0;
    for (unsigned d = 0; d < scroll_ir_ext_count; d++) {
        const scroll_ir *ir = scroll_ir_ext_all[d];
        long long bad = 0, samples = 0, table = 0;
        int uses_input = 0;
        for (unsigned i = 0; i < ir->nlayers; i++) if (ir->layers[i].U) uses_input = 1;
        for (unsigned i = 0; i < ir->nruns; i++) { table += ir->runs[i].lines; if (ir->runs[i].e.op == SCROLL_CLOUD) uses_input = 1; }
        for (unsigned i = 0; i < ir->nbands; i++) if (ir->bands[i].e.op == SCROLL_CLOUD) uses_input = 1;
        if (table > ir->buffer_lines) { printf("check %s: runs cover %lld lines > buffer %u\n", ir->program, table, ir->buffer_lines); bad++; }
        for (int line = 0; line < ir->buffer_lines; line++) {
            const scroll_expr *e;
            int k = source(ir, line, &e);
            if (k < 0 || (k == 0 && line < table)) { printf("check %s: line %d covered %s\n", ir->program, line, k < 0 ? "twice" : "by nothing"); bad++; }
        }
        for (int x = -4096; x <= 16383; x++) {
            for (int y = 0; y < ir->buffer_lines + 8; y++) {
                const scroll_expr *e;
                int line = y & (ir->buffer_lines - 1), k = source(ir, line, &e);
                int64_t v = scroll_ir_raster_x(ir, x, y, 0, 0), lo, hi;
                samples++;
                if (k == 0) { lo = hi = 0; }
                else if (e->op == SCROLL_LAYER) { lo = hi = lay(ir, e->a, x); }
                else if (e->op == SCROLL_LERP || e->op == SCROLL_STEP || e->op == SCROLL_RAMP) {
                    int64_t f = lay(ir, e->a, x), t = lay(ir, e->b, x);
                    lo = f < t ? f : t; hi = f < t ? t : f;
                } else { lo = INT64_MIN; hi = INT64_MAX; }
                if (v < lo || v > hi || (x >= 0 && (v < -32768 || v > 32767))) {
                    if (bad < 5) printf("check %s: x=%d y=%d value %lld outside [%lld, %lld]\n", ir->program, x, y, (long long)v, (long long)lo, (long long)hi);
                    bad++;
                }
                if (!uses_input && (x % 97 == 0) && (y % 8 == 3)) {
                    static const int32_t ramps[] = {1, -777, 1 << 20, -(1 << 24)};
                    static const unsigned frames[] = {1, 60, 65535, 1u << 20, 0xFFFFFFFFu};
                    for (int r = 0; r < 4; r++) for (int f = 0; f < 5; f++)
                        if (scroll_ir_raster_x(ir, x, y, frames[f], ramps[r]) != v) {
                            if (bad < 5) printf("check %s: x=%d y=%d depends on ramp/frame\n", ir->program, x, y);
                            bad++;
                        }
                }
            }
        }
        int64_t maxbgy = 65535;
        if (ir->bgy.op == SCROLL_BGY_SHIFT) { maxbgy = 0; for (unsigned i = 0; i < ir->bgy.nshift; i++) maxbgy += 65535 >> ir->bgy.shift[i]; }
        int prev = -1;
        for (int u = 0; u <= 65535; u++) {
            int y = u >= 32768 ? u - 65536 : u;      /* the same 16-bit camera Y both ways */
            int b1 = scroll_ir_background_y(ir, u, 0), b2 = scroll_ir_background_y(ir, y, 0);
            if (b1 != b2 || b1 < 0 || b1 > maxbgy || b1 < prev) {
                if (bad < 5) printf("check %s: camera Y %d gives background Y %d/%d\n", ir->program, u, b1, b2);
                bad++;
            }
            prev = b1;
        }
        printf("check %-12s buffer %4u  table %4lld  %9lld raster samples  bg_y 0..%lld  %s\n", ir->program, ir->buffer_lines,
               table, samples, (long long)maxbgy, bad ? "FAIL" : "ok");
        failed += bad != 0;
    }
    if (failed) { printf("check: FAIL %d documents\n", failed); return 1; }
    printf("check: %u documents ok\n", scroll_ir_ext_count);
    return 0;
}
