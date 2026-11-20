/* Checks for the round 8 IR, linked with R8/evaluate.c and the tables
   R8/irc.py emits, built as a shared library that R8/validate.py loads.
   Nothing here names a program: every function takes a background id. */
#include <stdint.h>
#include "evaluate.h"

extern const scroll_ir *const scroll_ir_slots[];
extern const unsigned scroll_ir_slot_count;

static const scroll_ir *ir_of(int slot) {
    if (slot < 0 || (unsigned)slot >= scroll_ir_slot_count) return 0;
    return scroll_ir_slots[slot];
}

int r8_present(int slot) { return ir_of(slot) != 0; }
int r8_buffer(int slot) { return ir_of(slot)->buffer_lines; }
int r8_nlayers(int slot) { return ir_of(slot)->nlayers; }
int r8_raster(int slot, int x, int y, unsigned f, int ramp) { return scroll_ir_raster_x(ir_of(slot), x, y, f, ramp); }
int r8_bgy(int slot, int cy, int px) { return scroll_ir_background_y(ir_of(slot), cy, px); }
long long r8_layer(int slot, int i, int x) { return (long long)scroll_ir_layer_x(ir_of(slot), (unsigned)i, x, 0); }

/* Line classes: 0 run, 1 band, 2 unwritten.  Returns -1 when a line is in
   two bands (the IR forbids it; irc.py checks it too). */
int r8_line_class(int slot, int line) {
    const scroll_ir *ir = ir_of(slot);
    int hits = 0, end = 0;
    for (unsigned i = 0; i < ir->nbands; i++)
        if (line >= ir->bands[i].start && line < ir->bands[i].start + ir->bands[i].lines) hits++;
    if (hits > 1) return -1;
    if (hits) return 1;
    for (unsigned i = 0; i < ir->nruns; i++) end += ir->runs[i].lines;
    return line < end ? 0 : 2;
}

/* Sweep camera X x0..x1, every line of two buffer heights, three frames.
   out[0]  samples on written lines
   out[1]  samples outside [min layer - 1, max layer + 1] (camera included)
   out[2]  line y and y + buffer_lines disagree
   out[3]  the value depends on the frame (no cloud op in round 8)
   out[4]  unwritten-line samples (value 0 by convention; not range-checked)
   out[5], out[6]  smallest and largest camera X with an out-of-range sample
   out[7], out[8]  smallest and largest line with an out-of-range sample
   out[9]  largest distance outside the range, in pixels */
void r8_sweep(int slot, int x0, int x1, long long *out) {
    const scroll_ir *ir = ir_of(slot);
    int B = ir->buffer_lines;
    static const unsigned frames[3] = {0, 1, 65535};
    for (int i = 0; i < 10; i++) out[i] = 0;
    out[5] = out[7] = 1 << 30;
    out[6] = out[8] = -1;
    for (int x = x0; x <= x1; x++) {
        long long lo = 0, hi = 0;
        for (int i = 0; i < ir->nlayers; i++) {
            long long v = scroll_ir_layer_x(ir, (unsigned)i, x, 0);
            if (i == 0 || v < lo) lo = v;
            if (i == 0 || v > hi) hi = v;
        }
        for (int y = 0; y < 2 * B; y++) {
            int line = y & (B - 1);
            int v = scroll_ir_raster_x(ir, x, y, 0, 0);
            if (r8_line_class(slot, line) == 2) { out[4]++; continue; }
            out[0]++;
            if (y < B && v != scroll_ir_raster_x(ir, x, y + B, 0, 0)) out[2]++;
            for (int f = 1; f < 3; f++)
                if (v != scroll_ir_raster_x(ir, x, y, frames[f], 0)) { out[3]++; break; }
            if (v < lo - 1 || v > hi + 1) {
                long long d = v < lo - 1 ? lo - v : v - hi;
                out[1]++;
                if (x < out[5]) out[5] = x;
                if (x > out[6]) out[6] = x;
                if (line < out[7]) out[7] = line;
                if (line > out[8]) out[8] = line;
                if (d > out[9]) out[9] = d;
            }
        }
    }
}
