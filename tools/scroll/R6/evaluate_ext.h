/* Generic evaluator for scroll IR (tools/scroll/ir.md) plus the R6
   extensions (tools/scroll/R6/ir_ext.md).  This is tools/scroll/evaluate.h
   copied and extended; changes are marked R6-EXT.  The shared file is not
   modified.  Nothing here is specific to a zone, act, era or program. */
#ifndef SCROLL_EVALUATE_EXT_H
#define SCROLL_EVALUATE_EXT_H
#include <stdint.h>

enum { SCROLL_ZERO, SCROLL_LAYER, SCROLL_CLOUD, SCROLL_RAMP,
       SCROLL_LERP, SCROLL_STEP };                                /* R6-EXT */
enum { SCROLL_BGY_RATE, SCROLL_BGY_CAMERA,
       SCROLL_BGY_SHIFT };                                        /* R6-EXT */

/* A layer's 16.16 position advances by C*(camera delta, 8.8) plus
   U*(player X speed, 8.8) per frame, so after the camera has moved x pixels
   and the gated player speed has summed to `ramp` its pixel position is
   floor((C*x + U*ramp) / 256).  Index 0 of every layer table is the camera
   itself: {256, 0}. */
typedef struct { int32_t C, U; } scroll_layer;

/* LAYER  a = layer
   CLOUD  a = layer, k = accumulator speed (16.16 per frame)
   RAMP   a = from layer, b = to layer, k = D, plus the two operand widths
   LERP   a = from, b = to, k = w, diff_bits = prod_bits, p[0] = shift   (R6-EXT)
   STEP   a = from, b = to, k = D, p[0] = num, p[1] = m, p[2] = frac     (R6-EXT)
   ZERO   nothing */
typedef struct { uint8_t op, a, b, diff_bits, step_bits; int32_t k; int32_t p[4]; } scroll_expr;

typedef struct { uint16_t lines; scroll_expr e; } scroll_run;           /* lines = entries*8 */
typedef struct { uint16_t start, lines; scroll_expr e; } scroll_band;

/* RATE    background Y = floor(C*camera_y / 256)
   CAMERA  background Y = camera_y, folded to (y - y_min)/div + y_min when
           (uint16)player_x >= player_x_min and (uint16)camera_y >= y_min
           (div == 0: no fold)
   SHIFT   background Y = sum of ((uint16)camera_y >> shift[i]), i < nshift  (R6-EXT)
   Like the raster values, results are not reduced to 16 bits; retail holds
   them in 16-bit words (ir.md, "Values"). */
typedef struct { uint8_t op; int32_t C, player_x_min, y_min, div; uint8_t nshift, shift[4]; } scroll_bgy;

typedef struct {
    const char *program;
    uint16_t buffer_lines;
    uint8_t nlayers; const scroll_layer *layers;
    uint16_t nruns; const scroll_run *runs;
    uint16_t nbands; const scroll_band *bands;
    scroll_bgy bgy;
} scroll_ir;

/* Background X of background line bg_y, as scd_background_raster_x. */
int scroll_ir_raster_x(const scroll_ir *ir, int camera_x, int bg_y, unsigned frame, int32_t ramp);
/* Background Y for a camera Y, as scd_background_y. */
int scroll_ir_background_y(const scroll_ir *ir, int camera_y, int player_x);

#endif
