/* Generic evaluator for scroll IR: ROUND 8 COPY of tools/scroll/evaluate.h
   with the three extensions in tools/scroll/R8/EXTENSIONS.md (interp,
   layer_K, bg_shift).  Everything the shared evaluator computes is computed
   here identically; a document that uses no extension gives the same numbers.
   Nothing here is specific to a zone, act, era or program. */
#ifndef SCROLL_EVALUATE_H
#define SCROLL_EVALUATE_H
#include <stdint.h>

enum { SCROLL_ZERO, SCROLL_LAYER, SCROLL_CLOUD, SCROLL_RAMP, SCROLL_INTERP };
enum { SCROLL_BGY_RATE, SCROLL_BGY_CAMERA, SCROLL_BGY_SHIFT };
enum { SCROLL_SEED_ZERO, SCROLL_SEED_NEG_CAMERA, SCROLL_SEED_BASE_SIGN, SCROLL_SEED_UNSET };

/* A layer's 16.16 position advances by C*(camera delta, 8.8) plus
   U*(player X speed, 8.8) per frame from K at camera X 0 (extension
   layer_K; K = 0 in every shared document), so its pixel position is
   floor((C*x + U*ramp) / 256) + K.  Index 0 of every layer table is the
   camera itself: {256, 0, 0}. */
typedef struct { int32_t C, U, K; } scroll_layer;

/* LAYER   a = layer
   CLOUD   a = layer, k = accumulator speed (16.16 per frame)
   RAMP    a = from layer, b = to layer, k = D, plus the two operand widths
   INTERP  a = index into scroll_ir.interps
   ZERO    nothing */
typedef struct { uint8_t op, a, b, diff_bits, step_bits; int32_t k; } scroll_expr;

/* INTERP (extension interp): one table row of a 16.16 accumulator that
   starts at base (integer) + seed (fraction) and has been stepped by a
   32-bit C quotient:
     n = (uint32) sum_i coef[i] * (int16) layer(layer[i])
     q = n / D             unsigned, or (int32) n / D (toward zero) if is_signed
     s = seed + k*q        modulo 2^32; k = (group index) << (shift after /)
     value = layer(base) + floor((int32) s / 65536)
   seed: ZERO 0; NEG_CAMERA (uint16)(-x); BASE_SIGN 0xFFFF when
   (int16) layer(base) < 0, else 0; UNSET 0 (retail reads an uninitialised
   local; stated convention, like "unwritten" rows). */
#define SCROLL_INTERP_TERMS 4
typedef struct {
    uint8_t base, nterms, layer[SCROLL_INTERP_TERMS];
    int32_t coef[SCROLL_INTERP_TERMS];
    int32_t D;
    uint8_t is_signed;
    uint32_t k;
    uint8_t seed;
} scroll_interp;

typedef struct { uint16_t lines; scroll_expr e; } scroll_run;           /* lines = entries*8 */
typedef struct { uint16_t start, lines; scroll_expr e; } scroll_band;

/* RATE    background Y = floor(C*camera_y / 256)
   CAMERA  background Y = camera_y, folded to (y - y_min)/div + y_min when
           (uint16)player_x >= player_x_min and (uint16)camera_y >= y_min
           (div == 0: no fold)
   SHIFT   background Y = sum_i ((uint16)camera_y >> shift[i])  (extension bg_shift)
   Like the raster values, results are not reduced to 16 bits; retail holds
   them in 16-bit words (ir.md, "Values"). */
#define SCROLL_BGY_SHIFTS 4
typedef struct {
    uint8_t op; int32_t C, player_x_min, y_min, div;
    uint8_t nshift; uint8_t shift[SCROLL_BGY_SHIFTS];
} scroll_bgy;

typedef struct {
    const char *program;
    uint16_t buffer_lines;
    uint8_t nlayers; const scroll_layer *layers;
    uint16_t nruns; const scroll_run *runs;
    uint16_t nbands; const scroll_band *bands;
    uint16_t ninterps; const scroll_interp *interps;
    scroll_bgy bgy;
} scroll_ir;

/* Background X of background line bg_y, as scd_background_raster_x. */
int scroll_ir_raster_x(const scroll_ir *ir, int camera_x, int bg_y, unsigned frame, int32_t ramp);
/* Background Y for a camera Y, as scd_background_y. */
int scroll_ir_background_y(const scroll_ir *ir, int camera_y, int player_x);
/* Pixel position of layer i (0 = camera); used by the R8 checker. */
int64_t scroll_ir_layer_x(const scroll_ir *ir, unsigned i, int camera_x, int32_t ramp);

#endif
