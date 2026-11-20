/* Generic evaluator for scroll IR: tools/scroll/evaluate.h plus the R7
   vocabulary extensions (tools/scroll/R7/ops.md).  NOT the shared evaluator.

   This is a copy of tools/scroll/evaluate.h.  Every departure is marked EXT.
   The shared structures keep their layout; the extension fields are appended
   at the end of scroll_bgy and scroll_ir, so a table file emitted by the
   shared irc.py compiles against this header unchanged (the appended fields
   are zero) and evaluates exactly as with the shared evaluator.  sweep.c
   checks that on the ten R1 documents. */
#ifndef SCROLL_EVALUATE_EXT_H
#define SCROLL_EVALUATE_EXT_H
#include <stdint.h>

enum { SCROLL_ZERO, SCROLL_LAYER, SCROLL_CLOUD, SCROLL_RAMP,
       SCROLL_INTERP, SCROLL_WAVE };                         /* EXT */
enum { SCROLL_BGY_RATE, SCROLL_BGY_CAMERA,
       SCROLL_BGY_SHIFTS };                                   /* EXT */

/* A layer's 16.16 position advances by C*(camera delta, 8.8) plus
   U*(player X speed, 8.8) per frame, so after the camera has moved x pixels
   and the gated player speed has summed to `ramp` its pixel position is
   floor((C*x + U*ramp) / 256).  Index 0 of every layer table is the camera
   itself: {256, 0}. */
typedef struct { int32_t C, U; } scroll_layer;

/* LAYER  a = layer
   CLOUD  a = layer, k = accumulator speed (16.16 per frame)
   RAMP   a = from layer, b = to layer, k = D, plus the two operand widths
   INTERP k = index into scroll_ir.interp                     (EXT)
   WAVE   k = index into scroll_ir.wave                       (EXT)
   ZERO   nothing */
typedef struct { uint8_t op, a, b, diff_bits, step_bits; int32_t k; } scroll_expr;

typedef struct { uint16_t lines; scroll_expr e; } scroll_run;           /* lines = entries*8 */
typedef struct { uint16_t start, lines; scroll_expr e; } scroll_band;

/* EXT-OP-INTERP (ops.md 1).  With s(L) = (int16_t)layer(L):
     A = sum lin_coef[i] * s(lin_layer[i])
     q = (sum num_coef[i] * s(num_layer[i])) / D      C division, toward zero
     value = floor((A + M*q) / 65536)
   nnum == 0: q is 0. */
typedef struct {
    uint8_t nlin, nnum;
    uint8_t lin_layer[4]; int32_t lin_coef[4];
    uint8_t num_layer[4]; int32_t num_coef[4];
    int32_t D, M;
} scroll_interp;

/* EXT-OP-WAVE (ops.md 2), band line k:
     p = ((((uint16_t)(phase_speed * frame)) >> 8) + phase_step * k) & 255
     value = layer(layer) + (scroll_sinset_sin[p] >> shift)            */
typedef struct { uint8_t layer; int32_t phase_speed, phase_step, shift; } scroll_wave;
extern const uint16_t scroll_sinset_sin[256];

/* RATE    background Y = floor(C*camera_y / 256)
   CAMERA  background Y = camera_y, folded to (y - y_min)/div + y_min when
           (uint16)player_x >= player_x_min and (uint16)camera_y >= y_min
           (div == 0: no fold)
   SHIFTS  background Y = sum over the bits k of `shifts` of
           ((uint16_t)camera_y >> k)                                  (EXT)
   Like the raster values, results are not reduced to 16 bits; retail holds
   them in 16-bit words (ir.md, "Values"). */
typedef struct { uint8_t op; int32_t C, player_x_min, y_min, div; uint16_t shifts; } scroll_bgy;

typedef struct {
    const char *program;
    uint16_t buffer_lines;
    uint8_t nlayers; const scroll_layer *layers;
    uint16_t nruns; const scroll_run *runs;
    uint16_t nbands; const scroll_band *bands;
    scroll_bgy bgy;
    uint16_t ninterp; const scroll_interp *interp;           /* EXT */
    uint16_t nwave; const scroll_wave *wave;                 /* EXT */
} scroll_ir;

/* Background X of background line bg_y, as scd_background_raster_x. */
int scroll_ir_raster_x(const scroll_ir *ir, int camera_x, int bg_y, unsigned frame, int32_t ramp);
/* Background Y for a camera Y, as scd_background_y. */
int scroll_ir_background_y(const scroll_ir *ir, int camera_y, int player_x);

#endif
