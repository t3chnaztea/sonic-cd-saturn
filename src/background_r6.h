#ifndef SCD_BACKGROUND_R6_H
#define SCD_BACKGROUND_R6_H

#include <stdint.h>

/* Source-derived Wacky Workbench scroll programs. id = act*4+era:
   0-3 SCR61A-D, 4-7 SCR62A-D, 10-11 SCR63C-D. layers[4] = scrb/scrc/scrz
   X in 16.16 and the retail z81aline radwk fraction (NULL: derive from
   camera X at 48/128/64 per 256, fraction 0). */
int scd_r6_valid(unsigned id);
/* scrbinit: scrc = x/2, scrz = x/4, scrb = (x/16)*3 (unsigned words). */
void scd_r6_layers_reset(int camera_x, int32_t *layers);
/* scroll(): scrb += 48, scrc += 128, scrz += 64 per 8.8 camera X delta;
   layers[3] = the fraction that update leaves for z81aline. */
void scd_r6_layers_step(int delta_x, int32_t *layers);
int scd_r6_raster_x(unsigned id, int camera_x, const int32_t *layers, int world_y);
int scd_r6_background_y(unsigned id, int camera_y);
void scd_r6_lines_layers(unsigned id, int camera_x, const int32_t *layers, int background_y,
                         int32_t *background, int32_t *foreground, unsigned count);
int scd_r6_row_layer(unsigned id, int y);
int scd_r6_row_start(unsigned id, int x, const int32_t *layers, int y);
/* Level layer state (scd_background_reset/step). */
void scd_r6_reset(int camera_x);
void scd_r6_step(int camera_x);
const int32_t *scd_r6_layers(void);
/* COL6A-D palette scripts over out[64] (the base palette); frame counts
   clchgctr calls. scd_r6_palette_count(3) is clchgcnt[3], the flashing
   floor step PLAYER6.C bfloor reads. */
void scd_r6_palette(unsigned id, unsigned frame, uint16_t *out);
void scd_r6_palette_title_phase_set(unsigned phase);
void scd_r6_set_bossflag(unsigned bossflag);
/* R63C/D DEV63*.C cg_change: latch the cleared thunder bit after the actor pass. */
unsigned scd_r6_cg_change(unsigned id, unsigned bossflag);
unsigned scd_r6_palette_count(unsigned script);
/* R61C/R62C aniArtFrames+2: zero while the Good Future sparks are off. */
unsigned scd_r6_sparks_active(void);
/* bossflag as the palette and animated tiles see it: the R63C/R63D tile
   routine clears bit 6 and sets bit 7 (the thunder block is cleared and no
   longer updated); BOSS_6.C code must read it back from here. */
unsigned scd_r6_bossflag(void);
/* scd_background_tile_cycle for R6 is scd_r6_tile_cycle (declared in
   background.c; 0 without assets/generated/ww_terrain.inc). */
#endif
