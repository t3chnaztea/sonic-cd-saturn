#ifndef SCD_BACKGROUND_H
#define SCD_BACKGROUND_H
#include <stdint.h>
typedef struct { int32_t ramp; int camera_x; int32_t r3_layers[4]; } scd_background_scroll;
void scd_background_reset(scd_background_scroll *scroll,int camera_x);
void scd_background_step(scd_background_scroll *scroll,unsigned era,int camera_x,int velocity,int ramp);
int scd_background_raster_x(unsigned era,int camera_x,int world_y,unsigned frame,int32_t ramp);
int scd_background_raster_x_state(unsigned era,const scd_background_scroll *scroll,int camera_x,int world_y,unsigned frame);
void scd_background_lines(unsigned era,int camera_x,int world_y,unsigned frame,int32_t ramp,int32_t *out,unsigned count);
void scd_background_lines_pair(unsigned era,int camera_x,int camera_y,int world_y,unsigned frame,int32_t ramp,int32_t *background,int32_t *foreground,unsigned count);
void scd_background_lines_state(unsigned era,const scd_background_scroll *scroll,int camera_x,int camera_y,int world_y,unsigned frame,int32_t *background,int32_t *foreground,unsigned count);
int scd_background_y(unsigned era,int camera_y,int player_x);
int scd_background_x(unsigned era,int camera_x,int world_y,unsigned frame);
int scd_background_static(unsigned era,int world_y);
/* First world tile of a non-static BG ring row. */
int scd_background_row_start(unsigned era,const scd_background_scroll *scroll,int camera_x,int world_y,unsigned frame);
void scd_background_palette(unsigned era,unsigned frame,const uint8_t *base,uint16_t *out);
/* Retail R32A/C/D UpdateAnimTiles drum cycles. tick counts level vblank
   calls after the level-setup call (tick 0). Returns the slot count (0 when
   the era has no animated cells) and fills out[] with the cells to hold. */
typedef struct { uint16_t cell, cells; const uint8_t *art; unsigned frame; } scd_tile_write;
/* out[] must hold 3 entries (R41A fire slots; CC2 uses 2). */
unsigned scd_background_tile_cycle(unsigned era,unsigned tick,scd_tile_write *out);
/* Tiles the background layout may reference (>= the pack's art count). */
unsigned scd_background_tile_limit(unsigned era,unsigned tiles);
/* Background layout switches (R5 enkeino): patches map (the pack's BG
   layout, 8x64 chunk ids) and chunks (its chunk table) and clears world_rows of paced rows to redraw.  A negative result holds the switch frame.
   The N+1 mapwrtb redraw invalidates the complete 64-slot cache ring; its
   caller redraws the 30 currently visible rows. */
#define SCD_BACKGROUND_R5_FULL_REDRAW_SLOTS 64
int scd_background_map_update(unsigned era,uint8_t *map,uint8_t *chunks,int *world_rows,int top_row);
/* QA-only R5 enkeino event ledger.  It records actual enkeichg transitions
   separately from camera-line and mapwrtb deferrals; readers must treat it as
   diagnostic state, never as rendering input. */
extern volatile uint32_t scd_r5_event_mailbox[10];
#endif
