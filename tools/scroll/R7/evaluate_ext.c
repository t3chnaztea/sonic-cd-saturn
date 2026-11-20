/* Generic scroll IR evaluator: tools/scroll/evaluate.c plus the R7
   vocabulary extensions (tools/scroll/R7/ops.md).  Every departure from the
   shared file is marked EXT.  The only inputs are the IR tables; there is no
   per-program code. */
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

/* EXT-OP-INTERP: the routine reads each layer as its 16-bit word */
static int64_t word16(const scroll_ir *ir, unsigned i, int x, int32_t ramp) {
    return (int16_t)(uint16_t)(layer_x(ir, i, x, ramp) & 0xFFFF);
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
    case SCROLL_INTERP: {                     /* EXT-OP-INTERP */
        const scroll_interp *p = &ir->interp[e->k];
        int64_t a = 0, n = 0, q = 0;
        for (unsigned i = 0; i < p->nlin; i++) a += (int64_t)p->lin_coef[i] * word16(ir, p->lin_layer[i], x, ramp);
        for (unsigned i = 0; i < p->nnum; i++) n += (int64_t)p->num_coef[i] * word16(ir, p->num_layer[i], x, ramp);
        if (p->nnum) q = n / p->D;            /* C division: toward zero */
        /* the high word of the 16.16 accumulator: floor */
        return floor_div(a + (int64_t)p->M * q, 65536);
    }
    case SCROLL_WAVE: {                       /* EXT-OP-WAVE */
        const scroll_wave *w = &ir->wave[e->k];
        unsigned phase_word = (uint16_t)((uint32_t)w->phase_speed * frame);
        unsigned p = ((phase_word >> 8) + (unsigned)w->phase_step * (unsigned)k) & 255;
        return layer_x(ir, w->layer, x, ramp) + (scroll_sinset_sin[p] >> w->shift);
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
    if (g->op == SCROLL_BGY_SHIFTS) {         /* EXT-BGY-SHIFTS */
        int sum = 0;
        for (unsigned k = 0; k < 16; k++)
            if (g->shifts >> k & 1) sum += (uint16_t)y >> k;
        return sum;
    }
    if (g->div && (uint16_t)player_x >= g->player_x_min && (uint16_t)y >= g->y_min)
        return (y - g->y_min) / g->div + g->y_min;
    return y;
}
