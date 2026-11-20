/* Generic scroll IR evaluator: ROUND 8 COPY of tools/scroll/evaluate.c with
   the extensions of tools/scroll/R8/EXTENSIONS.md.  The only inputs are the
   IR tables; there is no per-program code. */
#include "evaluate.h"

static int64_t floor_div(int64_t a, int64_t b) {
    int64_t q = a / b;
    if ((a % b) != 0 && ((a < 0) != (b < 0))) q--;
    return q;
}

int64_t scroll_ir_layer_x(const scroll_ir *ir, unsigned i, int x, int32_t ramp) {
    const scroll_layer *l = &ir->layers[i];
    return floor_div((int64_t)l->C * x + (int64_t)l->U * ramp, 256) + l->K;
}

static int64_t interp_x(const scroll_ir *ir, const scroll_interp *p, int x, int32_t ramp) {
    int64_t base = scroll_ir_layer_x(ir, p->base, x, ramp);
    uint32_t n = 0, q, seed = 0, s;
    for (unsigned i = 0; i < p->nterms; i++) {
        int16_t v = (int16_t)(uint16_t)(uint64_t)scroll_ir_layer_x(ir, p->layer[i], x, ramp);
        n += (uint32_t)p->coef[i] * (uint32_t)(int32_t)v;          /* modulo 2^32 */
    }
    if (p->is_signed) q = (uint32_t)((int32_t)n / p->D);           /* C: toward zero */
    else q = n / (uint32_t)p->D;
    switch (p->seed) {
    case SCROLL_SEED_NEG_CAMERA: seed = (uint16_t)(-x); break;
    case SCROLL_SEED_BASE_SIGN: seed = (int16_t)(uint16_t)(uint64_t)base < 0 ? 0xFFFFu : 0u; break;
    default: seed = 0; break;                                        /* ZERO, UNSET */
    }
    s = seed + p->k * q;                                             /* modulo 2^32 */
    return base + floor_div((int64_t)(int32_t)s, 65536);
}

static int64_t expr_x(const scroll_ir *ir, const scroll_expr *e, int x, unsigned frame, int32_t ramp, int k) {
    switch (e->op) {
    case SCROLL_ZERO:
        return 0;
    case SCROLL_LAYER:
        return scroll_ir_layer_x(ir, e->a, x, ramp);
    case SCROLL_CLOUD:
        /* the accumulator is a 32-bit word advanced once per frame; the
           routine adds its high half */
        return scroll_ir_layer_x(ir, e->a, x, ramp) + (int64_t)(((uint32_t)frame * (uint32_t)e->k) >> 16);
    case SCROLL_RAMP: {
        int64_t from = scroll_ir_layer_x(ir, e->a, x, ramp), to = scroll_ir_layer_x(ir, e->b, x, ramp);
        int64_t d = to - from, q;
        if (e->diff_bits == 16) d = (int16_t)d;
        q = (256 * d) / e->k;                 /* C division: toward zero */
        if (e->step_bits == 16) q = (int16_t)q;
        /* 16.16 accumulator stepped once per line: floor */
        return from + floor_div((int64_t)k * q, 256);
    }
    case SCROLL_INTERP:
        return interp_x(ir, &ir->interps[e->a], x, ramp);
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
    if (g->op == SCROLL_BGY_SHIFT) {
        int sum = 0;
        for (unsigned i = 0; i < g->nshift; i++) sum += (uint16_t)y >> g->shift[i];
        return sum;
    }
    if (g->div && (uint16_t)player_x >= g->player_x_min && (uint16_t)y >= g->y_min)
        return (y - g->y_min) / g->div + g->y_min;
    return y;
}
