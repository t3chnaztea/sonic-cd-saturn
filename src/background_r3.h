#ifndef SCD_BACKGROUND_R3_H
#define SCD_BACKGROUND_R3_H

#include <stdint.h>

/* Source-derived Collision Chaos scroll programs (SCR31A-D.C and SCR32A-D.C; ids 0-3 and 4-7). */
int scd_r3_background_y(unsigned era, int camera_y);
int scd_r3_raster_x(unsigned era, int camera_x, int world_y, unsigned frame);
int scd_r3_raster_x_layers(unsigned era, int camera_x, const int32_t layers[4], int world_y, unsigned frame);
void scd_r3_lines(unsigned era, int camera_x, int camera_y, int background_y,
                  unsigned frame, int32_t *background, int32_t *foreground,
                  unsigned count);
void scd_r3_lines_layers(unsigned era, int camera_x, const int32_t layers[4], int camera_y,
                         int background_y, unsigned frame, int32_t *background,
                         int32_t *foreground, unsigned count);

int scd_r3_row_layer(unsigned era,int y);
int scd_r3_row_start(unsigned era,int x,const int32_t *layers,int y);
#endif
