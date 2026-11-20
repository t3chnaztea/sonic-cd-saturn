/* Generic evaluator for scroll IR scroll-ir/1+R3 (tools/scroll/ir.md plus
   tools/scroll/R3/ir-extension.md).

   This is tools/scroll/evaluate.h extended; the shared header is untouched.
   Every struct keeps evaluate.h's fields first and in the same order and only
   appends new ones, so tables that tools/scroll/irc.py emits for scroll-ir/1
   documents compile against this header unchanged (positional initialisers
   leave the new fields zero), and evaluate to the same values.

   Nothing here is specific to a zone, act, era or program. */
#ifndef SCROLL_EVALUATE_R3_H
#define SCROLL_EVALUATE_R3_H
#include <stdint.h>

enum { SCROLL_ZERO, SCROLL_LAYER, SCROLL_CLOUD, SCROLL_RAMP, SCROLL_INTERP, SCROLL_WAVE };
enum { SCROLL_BGY_RATE, SCROLL_BGY_CAMERA, SCROLL_BGY_CLAMP };

/* A layer's 16.16 position advances by C*(camera delta, 8.8) plus
   U*(player X speed, 8.8) per frame: floor((C*x + U*ramp) / 256).  Index 0 of
   every layer table is the camera itself: {256, 0}. */
typedef struct { int32_t C, U; } scroll_layer;

/* One step of an interpolation: q = trunc(n * [s16](layer b - layer a) / D),
   contribution m*q (16.16). */
typedef struct { uint8_t a, b, diff_bits; int32_t n, D, m; } scroll_step;

/* LAYER   a = layer
   CLOUD   a = layer, k = accumulator speed (16.16 per frame)
   RAMP    a = from, b = to, k = D, diff_bits, step_bits
   INTERP  a = from, b = to, k = D, diff_bits, n, m, optional seed
           value = from + floor((F + m*q) / 65536),
           q = trunc(n * [s16](to - from) / D), F = has_seed ? (seed.m * seed.q) & 0xFFFF : 0
   WAVE    a = layer, table, scale, phase_speed, offset, mask
           value = layer + scale * table[((((f*phase_speed) & 0xFFFF) >> 8) + offset + k) & mask]
   ZERO    nothing */
typedef struct {
    uint8_t op, a, b, diff_bits, step_bits; int32_t k;
    int32_t n, m;                          /* INTERP */
    uint8_t has_seed; scroll_step seed;    /* INTERP */
    uint8_t table; int32_t scale, phase_speed, offset, mask;   /* WAVE */
} scroll_expr;

typedef struct { uint16_t lines; scroll_expr e; } scroll_run;           /* lines = entries*8 */
typedef struct { uint16_t start, lines; scroll_expr e; } scroll_band;
typedef struct { uint16_t n; const int16_t *v; } scroll_table;

/* RATE    background Y = floor(C*camera_y / 256)
   CAMERA  background Y = camera_y, folded to (y - y_min)/div + y_min when
           (uint16)player_x >= player_x_min and (uint16)camera_y >= y_min
           (div == 0: no fold)
   CLAMP   (uint16)camera_y <= ref ?
               max(min, (int16)(base - ((ref - (uint16)camera_y) >> shift))) : base */
typedef struct {
    uint8_t op; int32_t C, player_x_min, y_min, div;
    int32_t ref, base, shift, min;         /* CLAMP */
} scroll_bgy;

typedef struct {
    const char *program;
    uint16_t buffer_lines;
    uint8_t nlayers; const scroll_layer *layers;
    uint16_t nruns; const scroll_run *runs;
    uint16_t nbands; const scroll_band *bands;
    scroll_bgy bgy;
    uint8_t ntables; const scroll_table *tables;
} scroll_ir;

/* Background X of background line bg_y, as scd_background_raster_x. */
int scroll_ir_raster_x(const scroll_ir *ir, int camera_x, int bg_y, unsigned frame, int32_t ramp);
/* Background Y for a camera Y, as scd_background_y. */
int scroll_ir_background_y(const scroll_ir *ir, int camera_y, int player_x);

#endif
