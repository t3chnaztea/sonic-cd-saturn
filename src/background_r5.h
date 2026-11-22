#ifndef SCD_BACKGROUND_R5_H
#define SCD_BACKGROUND_R5_H

#include <stdint.h>

/* Source-derived Quartz Quadrant scroll programs. id = act*4+era:
   0-3 SCR51A-D, 4-7 SCR52A-D, 10-11 SCR53C-D.
   enkeino (0-2, from the player X thresholds in enkeichg) selects the scroll
   variant, background Y, plane row table and COL5 scripts.  The R5 state
   (layers scrb/scrc/scrz in 16.16, enkeino, the palette event log) lives here:
   scd_r5_reset at level (re)start, scd_r5_step once per simulation update,
   scd_r5_background_y once per displayed frame (it records player X). */
int scd_r5_valid(unsigned id);
void scd_r5_reset(int camera_x);
void scd_r5_step(unsigned id, int camera_x);
int scd_r5_background_y(unsigned id, int camera_y, int player_x);
int scd_r5_enkei(void);
/* Force enkeino and scrbinit(camera_x) (tests and fixtures). */
void scd_r5_set_enkei(unsigned id, int enkei, int camera_x);
/* scra_hz (camera X delta, 8.8) the line builders' fraction seed reads;
   scd_r5_step sets it. */
void scd_r5_set_hz(int hz);
/* Camera Y delta of this update (SCR51D/52D/53D builders' fraction seed). */
void scd_r5_set_vy(int dy);
/* layers: scrb/scrc/scrz 16.16, or NULL for the tracked layers. */
int scd_r5_raster_x(unsigned id, int camera_x, const int32_t *layers, int world_y);
void scd_r5_lines_layers(unsigned id, int camera_x, const int32_t *layers, int background_y,
                         int32_t *background, int32_t *foreground, unsigned count);
int scd_r5_row_layer(unsigned id, int y);
int scd_r5_row_start(unsigned id, int camera_x, const int32_t *layers, int y);
const int32_t *scd_r5_layers(void);
/* BELTSW5 colrevflag and bossflag for COL5A-D; applies from the update in
   progress (call during the object update, before scd_r5_step). */
void scd_r5_set_colrev(int on);
void scd_r5_set_boss(int on);
/* COL5A-D clchgctr: out[64] holds the base palette; entries the scripts or
   enkeichg's colorset2 have written are replaced.  frame counts clchgctr calls
   (0 = none); a smaller frame or another id restarts the replay. */
void scd_r5_palette(unsigned id, unsigned frame, uint16_t *out);
/* Runtime background art (assets/generated/qq_terrain.inc): the tile run
   to hold for the current enkeino (returns its band, -1 when none), the tile
   count the background may reference, one tile's art for a band (NULL: the
   pack's), a layout cell for a band, and the layout switch: writes the band's
   cells into the pack's background layout and chunk table and clears
   world_rows of the BG rows that must redraw (returns how many). */
int scd_r5_tile_run(unsigned id, unsigned *first, unsigned *count, const uint8_t **art);
unsigned scd_r5_tile_limit(unsigned id, unsigned tiles);
const uint8_t *scd_r5_art(unsigned id, int enkei, unsigned tile);
int scd_r5_map_cell(unsigned id, int enkei, int row, int col, int value);
const uint8_t *scd_r5_chunk(unsigned id, int enkei, unsigned chunk);
int scd_r5_map_update(unsigned id, uint8_t *map, uint8_t *chunks, int *world_rows, int top_row);
#endif
