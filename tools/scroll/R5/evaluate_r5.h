/* Generic evaluator for scroll-ir/1+r5 (tools/scroll/R5/irc_r5.py): the
   shared scroll-ir/1 evaluator (tools/scroll/evaluate.h) plus the three R5
   extensions a merge would fold into it:
     - a document holds one body per value of a stage flag (flag & mask);
     - run op INTERP: a table row stepped from a layer toward another layer
       once per row group, with retail's unsigned 32-bit step division;
     - bg_y op SHIFT: background Y as a sum of shifted camera Y terms.
   Nothing here is specific to a zone, act, era or program. */
#ifndef SCROLL_EVALUATE_R5_H
#define SCROLL_EVALUATE_R5_H
#include <stdint.h>

enum { SCROLL5_ZERO, SCROLL5_LAYER, SCROLL5_CLOUD, SCROLL5_RAMP, SCROLL5_INTERP };
enum { SCROLL5_BGY_RATE, SCROLL5_BGY_CAMERA, SCROLL5_BGY_SHIFT };

/* position = floor((C*camera_x + U*ramp) / 256); index 0 is the camera {256,0} */
typedef struct { int32_t C, U; } scroll5_layer;

/* LAYER   a = layer
   CLOUD   a = layer, k = accumulator speed
   RAMP    a = from, b = to, k = D, diff_bits, step_bits (scroll-ir/1)
   INTERP  a = from, b = to, k = div, mul, step = scale * row-group index
   ZERO    nothing */
typedef struct { uint8_t op, a, b, diff_bits, step_bits; int32_t k, mul, step; } scroll5_expr;

typedef struct { uint16_t lines; scroll5_expr e; } scroll5_run;             /* lines = entries*8 */
typedef struct { uint16_t start, lines; scroll5_expr e; } scroll5_band;

/* RATE    floor(C*camera_y / 256)
   CAMERA  camera_y, folded when div != 0 (scroll-ir/1)
   SHIFT   v = (uint16)camera_y, << 16 when src == 32;
           (sum of terms[i][1] * (v >> terms[i][0])) >> post; a term with
           multiplier 0 is unused */
typedef struct { uint8_t op; int32_t C, player_x_min, y_min, div; uint8_t src, post; uint8_t terms[4][2]; } scroll5_bgy;

typedef struct {
    uint16_t buffer_lines;
    uint8_t nlayers; const scroll5_layer *layers;
    uint16_t nruns; const scroll5_run *runs;
    uint16_t nbands; const scroll5_band *bands;
    scroll5_bgy bgy;
} scroll5_body;

/* when = value of (flag & mask) the body is for; -1 when there is no flag */
typedef struct { int16_t when; const scroll5_body *body; } scroll5_variant;

typedef struct {
    const char *program;
    uint8_t flag_mask;                       /* 0: no flag */
    uint8_t nvariants; const scroll5_variant *variants;
} scroll_ir5;

/* The body for a flag value (flag & mask is taken here); 0 when none. */
const scroll5_body *scroll_ir5_body(const scroll_ir5 *ir, int flag);
/* Background X of background line bg_y, as scd_background_raster_x. */
int scroll_ir5_raster_x(const scroll_ir5 *ir, int flag, int camera_x, int bg_y, unsigned frame, int32_t ramp);
/* Background Y for a camera Y, as scd_background_y. */
int scroll_ir5_background_y(const scroll_ir5 *ir, int flag, int camera_y, int player_x);

#endif
