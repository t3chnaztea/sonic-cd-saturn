#ifndef SCD_BACKGROUND_R4_H
#define SCD_BACKGROUND_R4_H

#include <stdint.h>

/* Source-derived Tidal Tempest scroll programs. id = act*4+era:
   0-3 SCR41A-D, 4-7 SCR42A-D, 10-11 SCR43C-D. layers[3] = scrb/scrc/scrz
   X in 16.16 (NULL: derive from camera X at 12/24/16 per 256). */
int scd_r4_valid(unsigned id);
int scd_r4_raster_x(unsigned id, int camera_x, const int32_t *layers, int world_y);
int scd_r4_background_y(unsigned id, int camera_x, int camera_y);
void scd_r4_lines_layers(unsigned id, int camera_x, const int32_t *layers, int camera_y,
                         int background_y, unsigned frame, int32_t *background,
                         int32_t *foreground, unsigned count);
/* SCR41B-D/42x/43x background Y is the original scrb_v_posit (16.16), which
   the caller owns because the verbatim camera (src/camera_v.c scrv_up_ch /
   scrv_down_ch) masks it when the camera wraps by 2048. scd_r4_scrbinit is
   scrbinit (after playposiset); scd_r4_scroll_v is scroll()'s
   scrollb_hv(.., scra_vz << 7), once per update after scroll_v. Both record
   the value scd_r4_background_y returns until scd_r4_camera_v_reset();
   unfed (host tools), background Y is camera/2. */
void scd_r4_camera_v_reset(void);
void scd_r4_scrbinit(int32_t *scrb_v_posit, int camera_y);
void scd_r4_scroll_v(unsigned id, int32_t *scrb_v_posit, int16_t scra_vz);
int scd_r4_row_layer(unsigned id, int y);
int scd_r4_row_start(unsigned id, int x, const int32_t *layers, int y);
/* Water surface (retail waterposi after this frame's watercnt) for the line wobble;
   32767 = dry. Set by the R4 water code. */
void scd_r4_set_water(int surface);
int scd_r4_water(void);
/* COL4A-D palette scripts: out[64] holds the base palette; entries the
   scripts have written are replaced. frame counts clchgctr calls (0 = none);
   a smaller frame or another id restarts the scripts. */
void scd_r4_palette(unsigned id, unsigned frame, int camera_x, int camera_y, uint16_t *out);
/* CRAM entries (bit n = entry n) the program's COL4 scripts can set. */
uint64_t scd_r4_palette_entries(unsigned id);
#endif
