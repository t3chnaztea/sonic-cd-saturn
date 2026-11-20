/* Generic scroll-ir/1+r5 evaluator.  Semantics: tools/scroll/ir.md plus the
   extensions in tools/scroll/R5/irc_r5.py.  The only inputs are the IR
   tables; there is no per-program code.  The scroll-ir/1 part is
   tools/scroll/evaluate.c unchanged. */
#include "evaluate_r5.h"

static int64_t floor_div(int64_t a, int64_t b) {
    int64_t q = a / b;
    if ((a % b) != 0 && ((a < 0) != (b < 0))) q--;
    return q;
}

static int64_t layer_x(const scroll5_body *ir, unsigned i, int x, int32_t ramp) {
    const scroll5_layer *l = &ir->layers[i];
    return floor_div((int64_t)l->C * x + (int64_t)l->U * ramp, 256);
}

static int64_t expr_x(const scroll5_body *ir, const scroll5_expr *e, int x, unsigned frame, int32_t ramp, int k) {
    switch (e->op) {
    case SCROLL5_ZERO:
        return 0;
    case SCROLL5_LAYER:
        return layer_x(ir, e->a, x, ramp);
    case SCROLL5_CLOUD:
        return layer_x(ir, e->a, x, ramp) + (int64_t)(((uint32_t)frame * (uint32_t)e->k) >> 16);
    case SCROLL5_RAMP: {
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int64_t d = to - from, q;
        if (e->diff_bits == 16) d = (int16_t)d;
        q = (256 * d) / e->k;                 /* C division: toward zero */
        if (e->step_bits == 16) q = (int16_t)q;
        return from + floor_div((int64_t)k * q, 256);
    }
    case SCROLL5_INTERP: {
        /* retail: lHwk = to.w.h - from.w.h; lHwk = (unsigned)lHwk * mul / div;
           lHwk *= scale; the row group k shows hi(65536*from + k*lHwk) */
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int32_t d = (int32_t)(int16_t)to - (int32_t)(int16_t)from;
        uint32_t q = ((uint32_t)d * (uint32_t)e->mul) / (uint32_t)e->k;
        return from + floor_div((int64_t)e->step * (int64_t)q, 65536);
    }
    }
    return 0;
}

const scroll5_body *scroll_ir5_body(const scroll_ir5 *ir, int flag) {
    int want = ir->flag_mask ? (flag & ir->flag_mask) : -1;
    for (unsigned i = 0; i < ir->nvariants; i++)
        if (ir->variants[i].when == want) return ir->variants[i].body;
    /* a constant flag has a single variant: every flag value maps to it */
    return ir->nvariants == 1 ? ir->variants[0].body : 0;
}

int scroll_ir5_raster_x(const scroll_ir5 *doc, int flag, int x, int y, unsigned frame, int32_t ramp) {
    const scroll5_body *ir = scroll_ir5_body(doc, flag);
    if (!ir) return 0;
    int line = y & (ir->buffer_lines - 1);
    for (unsigned i = 0; i < ir->nbands; i++) {
        const scroll5_band *b = &ir->bands[i];
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

int scroll_ir5_background_y(const scroll_ir5 *doc, int flag, int y, int player_x) {
    const scroll5_body *ir = scroll_ir5_body(doc, flag);
    if (!ir) return 0;
    const scroll5_bgy *g = &ir->bgy;
    if (g->op == SCROLL5_BGY_RATE) return (int)floor_div((int64_t)g->C * y, 256);
    if (g->op == SCROLL5_BGY_SHIFT) {
        uint32_t v = (uint16_t)y;
        int64_t s = 0;
        if (g->src == 32) v <<= 16;
        for (unsigned i = 0; i < 4; i++)
            if (g->terms[i][1]) s += (int64_t)g->terms[i][1] * (int64_t)(v >> g->terms[i][0]);
        return (int)(s >> g->post);
    }
    if (g->div && (uint16_t)player_x >= g->player_x_min && (uint16_t)y >= g->y_min)
        return (y - g->y_min) / g->div + g->y_min;
    return y;
}
