/* Generic scroll IR evaluator, scroll-ir/1+R3.  Semantics: tools/scroll/ir.md
   and tools/scroll/R3/ir-extension.md.  This is tools/scroll/evaluate.c with
   the INTERP and WAVE expressions and the CLAMP background Y added; the four
   scroll-ir/1 expressions and two background Y rules are unchanged.  The only
   inputs are the IR tables; there is no per-program code. */
#include "evaluate_r3.h"

static int64_t floor_div(int64_t a, int64_t b) {
    int64_t q = a / b;
    if ((a % b) != 0 && ((a < 0) != (b < 0))) q--;
    return q;
}

static int64_t layer_x(const scroll_ir *ir, unsigned i, int x, int32_t ramp) {
    const scroll_layer *l = &ir->layers[i];
    return floor_div((int64_t)l->C * x + (int64_t)l->U * ramp, 256);
}

/* trunc(n * [s16](layer b - layer a) / D): C division, toward zero */
static int64_t step_q(const scroll_ir *ir, unsigned a, unsigned b, unsigned diff_bits,
                      int32_t n, int32_t D, int x, int32_t ramp) {
    int64_t d = layer_x(ir, b, x, ramp) - layer_x(ir, a, x, ramp);
    if (diff_bits == 16) d = (int16_t)d;
    return ((int64_t)n * d) / D;
}

static int64_t expr_x(const scroll_ir *ir, const scroll_expr *e, int x, unsigned frame, int32_t ramp, int k) {
    switch (e->op) {
    case SCROLL_ZERO:
        return 0;
    case SCROLL_LAYER:
        return layer_x(ir, e->a, x, ramp);
    case SCROLL_CLOUD:
        /* the accumulator is a 32-bit word advanced once per frame; the
           routine adds its high half */
        return layer_x(ir, e->a, x, ramp) + (int64_t)(((uint32_t)frame * (uint32_t)e->k) >> 16);
    case SCROLL_RAMP: {
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int64_t d = to - from, q;
        if (e->diff_bits == 16) d = (int16_t)d;
        q = (256 * d) / e->k;                 /* C division: toward zero */
        if (e->step_bits == 16) q = (int16_t)q;
        /* 16.16 accumulator stepped once per line: floor */
        return from + floor_div((int64_t)k * q, 256);
    }
    case SCROLL_INTERP: {
        /* 16.16 accumulator seeded with (from, F) and stepped per table row:
           its integer half is the high word, which rounds down */
        int64_t q = step_q(ir, e->a, e->b, e->diff_bits, e->n, e->k, x, ramp), F = 0;
        if (e->has_seed) {
            const scroll_step *s = &e->seed;
            int64_t sq = step_q(ir, s->a, s->b, s->diff_bits, s->n, s->D, x, ramp);
            F = (int64_t)((uint64_t)((int64_t)s->m * sq) & 0xFFFF);
        }
        return layer_x(ir, e->a, x, ramp) + floor_div(F + (int64_t)e->m * q, 65536);
    }
    case SCROLL_WAVE: {
        /* a 16-bit phase accumulator advanced by phase_speed per frame from 0;
           the routine reads its high byte and indexes the table from the
           band's first line */
        unsigned acc = ((uint32_t)frame * (uint32_t)e->phase_speed) & 0xFFFF;
        unsigned idx = ((acc >> 8) + (unsigned)e->offset + (unsigned)k) & (unsigned)e->mask;
        return layer_x(ir, e->a, x, ramp) + (int64_t)e->scale * ir->tables[e->table].v[idx];
    }
    }
    return 0;
}

int scroll_ir_raster_x(const scroll_ir *ir, int x, int y, unsigned frame, int32_t ramp) {
    int line = y & (ir->buffer_lines - 1);
    for (unsigned i = 0; i < ir->nbands; i++) {
        const scroll_band *b = &ir->bands[i];
        if (line >= b->start && line < b->start + b->lines)
            return (int)expr_x(ir, &b->e, x, frame, ramp, line - b->start);
    }
    int end = 0;
    for (unsigned i = 0; i < ir->nruns; i++) {
        end += ir->runs[i].lines;
        if (line < end) return (int)expr_x(ir, &ir->runs[i].e, x, frame, ramp, 0);
    }
    return 0;      /* beyond the table: rows the routine never writes */
}

int scroll_ir_background_y(const scroll_ir *ir, int y, int player_x) {
    const scroll_bgy *g = &ir->bgy;
    if (g->op == SCROLL_BGY_RATE) return (int)floor_div((int64_t)g->C * y, 256);
    if (g->op == SCROLL_BGY_CLAMP) {
        unsigned yu = (uint16_t)y;
        if (yu <= (unsigned)g->ref) {
            int v = (int16_t)(g->base - (int)(((unsigned)g->ref - yu) >> g->shift));
            return v < g->min ? g->min : v;
        }
        return g->base;
    }
    if (g->div && (uint16_t)player_x >= g->player_x_min && (uint16_t)y >= g->y_min)
        return (y - g->y_min) / g->div + g->y_min;
    return y;
}
