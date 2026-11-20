/* Evaluator for extended scroll IR (`scroll-ir/1+r4`,
   tools/scroll/R4/ir-extensions.md).  It is tools/scroll/evaluate.c plus the
   three proposed extensions: the run op INTERP, the background Y op PIECES
   and the WATER record.  The shared ops keep exactly the semantics of
   tools/scroll/evaluate.c (R4/check.py compares the two on every shared-op
   document).  Nothing here is specific to a zone, act, era or program. */
#ifndef SCROLL_EVALUATE_X_H
#define SCROLL_EVALUATE_X_H
#include <stdint.h>
#include "../evaluate.h"

enum { SCROLL_INTERP = SCROLL_RAMP + 1 };
enum { SCROLLX_BGY_PIECES = SCROLL_BGY_CAMERA + 1 };
enum { SCROLLX_CAMERA_X, SCROLLX_CAMERA_Y, SCROLLX_PLAYER_X };
enum { SCROLLX_LT, SCROLLX_GT, SCROLLX_LE, SCROLLX_GE, SCROLLX_EQ, SCROLLX_NE };

/* As scroll_expr, plus INTERP's numerator scale and multiplier:
   LAYER/CLOUD/RAMP/ZERO  as in evaluate.h (k2, m unused)
   INTERP  a = from layer, b = to layer, diff_bits, k = D, k2 = k, m = m */
typedef struct { uint8_t op, a, b, diff_bits, step_bits; int32_t k, k2, m; } scrollx_expr;
typedef struct { uint16_t lines; scrollx_expr e; } scrollx_run;
typedef struct { uint16_t start, lines; scrollx_expr e; } scrollx_band;

/* PIECES: the first piece whose conditions all hold (they are disjoint by
   construction) gives (mul*(uint16)camera_y + add) >> shift, floor. */
typedef struct { uint8_t var, op, is_unsigned; int32_t value; } scrollx_cond;
typedef struct { uint8_t nconds; scrollx_cond cond[4]; int64_t mul, add; uint8_t shift; } scrollx_piece;

/* WATER: step = phase word advance per scroll() call, sign = +1/-1,
   table = 256 signed bytes. */
typedef struct { uint8_t present; uint16_t step; int8_t sign; const int8_t *table; } scrollx_water;

typedef struct {
    const char *program;
    uint16_t buffer_lines;
    uint8_t nlayers; const scroll_layer *layers;
    uint16_t nruns; const scrollx_run *runs;
    uint16_t nbands; const scrollx_band *bands;
    scroll_bgy bgy;                        /* op RATE, CAMERA or SCROLLX_BGY_PIECES */
    uint8_t npieces; const scrollx_piece *pieces;
    scrollx_water water;
} scrollx_ir;

/* Background X of background line bg_y above the water (the table and its
   bands), as scroll_ir_raster_x. */
int scroll_irx_raster_x(const scrollx_ir *ir, int camera_x, int bg_y, unsigned frame, int32_t ramp);

/* Background Y.  camera_x is needed by PIECES only. */
int scroll_irx_background_y(const scrollx_ir *ir, int camera_x, int camera_y, int player_x);

/* WATER: the first screen line (0-based) that is below the surface for a
   camera Y and a surface Y, or -1 when no line is (never below 65536 lines). */
int scroll_irx_water_first_line(int camera_y, int surface);

/* WATER: what a line below the surface adds to its background X:
   sign * table[(P + bg_y) & 255], P = high byte of step*(frame-1).
   0 when the document has no water record. */
int scroll_irx_water_x(const scrollx_ir *ir, int bg_y, unsigned frame);

/* Screen line `line` of a render whose top background line is bg_top:
   raster_x(bg_top + line), plus water_x when line >= first_line(camera_y,
   surface).  This is what the routine writes, negated, into the h-scroll
   buffer's background word for that line. */
int scroll_irx_screen_x(const scrollx_ir *ir, int camera_x, int camera_y, int bg_top, int line,
                        unsigned frame, int32_t ramp, int surface);

#endif
