/* Extended scroll IR evaluator.  Semantics: tools/scroll/ir.md for the shared
   ops, tools/scroll/R4/ir-extensions.md for INTERP, PIECES and WATER.  The
   only inputs are the IR tables; there is no per-program code. */
#include "evaluate_x.h"

static int64_t floor_div(int64_t a, int64_t b) {
    int64_t q = a / b;
    if ((a % b) != 0 && ((a < 0) != (b < 0))) q--;
    return q;
}

static int64_t layer_x(const scrollx_ir *ir, unsigned i, int x, int32_t ramp) {
    const scroll_layer *l = &ir->layers[i];
    return floor_div((int64_t)l->C * x + (int64_t)l->U * ramp, 256);
}

static int64_t expr_x(const scrollx_ir *ir, const scrollx_expr *e, int x, unsigned frame, int32_t ramp, int k) {
    switch (e->op) {
    case SCROLL_ZERO:
        return 0;
    case SCROLL_LAYER:
        return layer_x(ir, e->a, x, ramp);
    case SCROLL_CLOUD:
        return layer_x(ir, e->a, x, ramp) + (int64_t)(((uint32_t)frame * (uint32_t)e->k) >> 16);
    case SCROLL_RAMP: {
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int64_t d = to - from, q;
        if (e->diff_bits == 16) d = (int16_t)d;
        q = (256 * d) / e->k;
        if (e->step_bits == 16) q = (int16_t)q;
        return from + floor_div((int64_t)k * q, 256);
    }
    case SCROLL_INTERP: {
        /* the high word of 65536*from + m*trunc(k*(to - from)/D) */
        int64_t from = layer_x(ir, e->a, x, ramp), to = layer_x(ir, e->b, x, ramp);
        int64_t d = to - from, q;
        if (e->diff_bits == 16) d = (int16_t)d;
        q = ((int64_t)e->k2 * d) / e->k;      /* C division: toward zero */
        return from + floor_div((int64_t)e->m * q, 65536);
    }
    }
    return 0;
}

int scroll_irx_raster_x(const scrollx_ir *ir, int x, int y, unsigned frame, int32_t ramp) {
    int line = y & (ir->buffer_lines - 1);
    for (unsigned i = 0; i < ir->nbands; i++) {
        const scrollx_band *b = &ir->bands[i];
        if (line >= b->start && line < b->start + b->lines)
            return (int)expr_x(ir, &b->e, x, frame, ramp, line - b->start);
    }
    int end = 0;
    for (unsigned i = 0; i < ir->nruns; i++) {
        end += ir->runs[i].lines;
        if (line < end) return (int)expr_x(ir, &ir->runs[i].e, x, frame, ramp, 0);
    }
    return 0;
}

static int cond_holds(const scrollx_cond *c, int camera_x, int camera_y, int player_x) {
    int v = c->var == SCROLLX_CAMERA_X ? camera_x : c->var == SCROLLX_CAMERA_Y ? camera_y : player_x;
    int32_t x = c->is_unsigned ? (int32_t)(uint16_t)v : (int32_t)(int16_t)v;
    switch (c->op) {
    case SCROLLX_LT: return x < c->value;
    case SCROLLX_GT: return x > c->value;
    case SCROLLX_LE: return x <= c->value;
    case SCROLLX_GE: return x >= c->value;
    case SCROLLX_EQ: return x == c->value;
    default: return x != c->value;
    }
}

int scroll_irx_background_y(const scrollx_ir *ir, int camera_x, int y, int player_x) {
    const scroll_bgy *g = &ir->bgy;
    if (g->op == SCROLL_BGY_RATE) return (int)floor_div((int64_t)g->C * y, 256);
    if (g->op == SCROLLX_BGY_PIECES) {
        for (unsigned i = 0; i < ir->npieces; i++) {
            const scrollx_piece *p = &ir->pieces[i];
            unsigned j;
            for (j = 0; j < p->nconds; j++)
                if (!cond_holds(&p->cond[j], camera_x, y, player_x)) break;
            if (j == p->nconds)
                return (int)floor_div(p->mul * (int64_t)(uint16_t)y + p->add, (int64_t)1 << p->shift);
        }
        return -1;       /* unreachable for a validated document: the pieces cover every input */
    }
    if (g->div && (uint16_t)player_x >= g->player_x_min && (uint16_t)y >= g->y_min)
        return (y - g->y_min) / g->div + g->y_min;
    return y;
}

int scroll_irx_water_first_line(int camera_y, int surface) {
    int c = (int16_t)camera_y, w = (int16_t)surface;
    if (c > w) return 0;
    if (w == 32767) return -1;
    return w - c + 1;
}

int scroll_irx_water_x(const scrollx_ir *ir, int y, unsigned frame) {
    if (!ir->water.present) return 0;
    unsigned phase = ((uint32_t)ir->water.step * (uint32_t)(frame - 1u)) & 0xFFFFu;
    return ir->water.sign * ir->water.table[((phase >> 8) + (unsigned)y) & 255u];
}

int scroll_irx_screen_x(const scrollx_ir *ir, int camera_x, int camera_y, int bg_top, int line,
                        unsigned frame, int32_t ramp, int surface) {
    int v = scroll_irx_raster_x(ir, camera_x, bg_top + line, frame, ramp);
    if (ir->water.present) {
        int first = scroll_irx_water_first_line(camera_y, surface);
        if (first >= 0 && line >= first) v += scroll_irx_water_x(ir, bg_top + line, frame);
    }
    return v;
}
