/* Prints what the generic scroll-ir/1+r5 evaluator returns for every document
   in the generated tables, for check_r5.py to compare with the retail
   routine.  Output, one record per line:
     R <program> <when> <x> <frame> <ramp> <v0> <v1> ... <v(buffer_lines-1)>
     Y <program> <when> <player_x> <bgY(0)> ... <bgY(65535)>
   Nothing here is specific to a program. */
#include <stdio.h>
#include "evaluate_r5.h"

extern const scroll_ir5 *const scroll_ir5_slots[];
extern const unsigned scroll_ir5_slot_count;

static const int xs[] = {0, 1, 2, 3, 5, 7, 11, 100, 255, 256, 257, 1000, 1023, 1024, 3071, 3072, 3584,
                         4095, 4096, 6143, 6144, 6145, 7168, 8960, 10000, 10903, 12288, 16383, 16384,
                         24575, 32767, -1, -2, -100, -1024, -32768};
static const unsigned frames[] = {0, 1, 4096};
static const int ramps[] = {0, 256, -256};

int main(void) {
    for (unsigned s = 0; s < scroll_ir5_slot_count; s++) {
        const scroll_ir5 *ir = scroll_ir5_slots[s];
        if (!ir) continue;
        for (unsigned v = 0; v < ir->nvariants; v++) {
            int flag = ir->variants[v].when < 0 ? 0 : ir->variants[v].when;
            const scroll5_body *b = ir->variants[v].body;
            for (unsigned i = 0; i < sizeof xs / sizeof xs[0]; i++)
                for (unsigned f = 0; f < 3; f++) {
                    printf("R %s %d %d %u %d", ir->program, ir->variants[v].when, xs[i], frames[f], ramps[f]);
                    for (int y = 0; y < b->buffer_lines; y++)
                        printf(" %d", scroll_ir5_raster_x(ir, flag, xs[i], y, frames[f], ramps[f]));
                    printf("\n");
                }
            for (int px = 0; px < 2; px++) {
                printf("Y %s %d %d", ir->program, ir->variants[v].when, px ? 0x7fff : 0);
                for (int y = 0; y < 65536; y++)
                    printf(" %d", scroll_ir5_background_y(ir, flag, y, px ? 0x7fff : 0));
                printf("\n");
            }
        }
    }
    return 0;
}
