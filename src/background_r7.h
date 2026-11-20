#ifndef SCD_BACKGROUND_R7_H
#define SCD_BACKGROUND_R7_H

#include <stdint.h>

/* Stardust Speedway scroll programs, as the retail scroll() code runs them
   (src/background_r7_tables.inc from tools/background_r7_assets.py).
   id = act*4+era: 0-3 R71A-D, 4-7 R72A-D, 10-11 R73C-D.
   layers[4] = scrb/scrc/scrz X in 16.16 and the high word the first
   hscrollwork chain inherits in d3 (scroll()'s hz*32). */
int scd_r7_valid(unsigned id);
void scd_r7_layers_reset(unsigned id, int camera_x, int32_t *layers);
void scd_r7_layers_step(unsigned id, int delta_x, int32_t *layers);
/* BOSS_7.C egg7_hscr: while forced, the race drives scra_hz itself; pass the
   8.8 hz the boss sets (0x7fffffff = normal camera delta). */
void scd_r7_force_hz(int32_t hz);
int scd_r7_background_y(unsigned id, int camera_y);
/* waterdirec: the R71B/R72B wave phase word before this scroll() (+128 per call). */
void scd_r7_lines_layers(unsigned id, int camera_x, const int32_t *layers, int background_y,
                         unsigned waterdirec, int32_t *background, int32_t *foreground, unsigned count);
int scd_r7_raster_x(unsigned id, int camera_x, const int32_t *layers, int world_y);
int scd_r7_row_layer(unsigned id, int y);
int scd_r7_row_start(unsigned id, int x, const int32_t *layers, int y);
/* Level state for background.c. */
void scd_r7_reset(unsigned id, int camera_x);
void scd_r7_step(unsigned id, int camera_x);
const int32_t *scd_r7_layers(void);
const int32_t *scd_r7_layers_for(unsigned id);
unsigned scd_r7_waterdirec(void);
/* COL7A-D palette scripts over out[64] (the base palette); frame counts clchgctr calls. */
void scd_r7_palette(unsigned id, unsigned frame, uint16_t *out);
/* Metallic Madness runs on the same engine: scroll ids 12-23 (12 + act*4+era);
   COL8A-D palette and animated tiles take the zone-local id 0-11. */
void scd_r8_palette(unsigned id, unsigned frame, uint16_t *out);
uint64_t scd_r8_palette_entries(unsigned id);
#endif
