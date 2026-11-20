/* Generic scroll IR evaluator with the R6 extensions.  Semantics:
   tools/scroll/ir.md and tools/scroll/R6/ir_ext.md.  This is
   tools/scroll/evaluate.c copied and extended (R6-EXT); the only inputs are
   the IR tables; there is no per-program code. */
#include "evaluate_ext.h"

static int64_t floor_div(int64_t a, int64_t b) {
    int64_t q = a / b;
    if ((a % b) != 0 && ((a < 0) != (b < 0))) q--;
    return q;
}

static int64_t layer_x(const scroll_ir *ir, unsigned i, int x, int32_t ramp) {
    const scroll_layer *l = &ir->layers[i];
    return floor_div((int64_t)l->C * x + (int64_t)l->U * ramp, 256);
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
    case SCROLL_LERP: {                       /* R6-EXT */
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int64_t p = (int64_t)e->k * (to - from);
        if (e->diff_bits == 16) p &= 0xFFFF;  /* the product narrowed to 16 bits, unsigned */
        return from + floor_div(p, (int64_t)1 << e->p[0]);
    }
    case SCROLL_STEP: {                       /* R6-EXT */
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int64_t q = ((int64_t)e->p[0] * (to - from)) / e->k;      /* C division: toward zero */
        /* high word of the 16.16 accumulator 65536*from + frac + m*q: floor */
        return floor_div(65536 * from + e->p[2] + (int64_t)e->p[1] * q, 65536);
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
    if (g->op == SCROLL_BGY_SHIFT) {          /* R6-EXT */
        int s = 0;
        for (unsigned i = 0; i < g->nshift; i++) s += (uint16_t)y >> g->shift[i];
        return s;
    }
    if (g->div && (uint16_t)player_x >= g->player_x_min && (uint16_t)y >= g->y_min)
        return (y - g->y_min) / g->div + g->y_min;
    return y;
}
