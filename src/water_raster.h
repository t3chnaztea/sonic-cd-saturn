#ifndef SCD_WATER_RASTER_H
#define SCD_WATER_RASTER_H
/* Saturn water line (Tidal Tempest). The Mega Drive original DMAs
   waterPalette to CRAM from the H-INT at the water line (hintposi). Here CRAM
   bank 1 (colours 256..511) holds the frame's bank 0 image with the stage
   palette slots (0..63 and the sprite alias 128..191) replaced by the water
   palette, and SCU timer 0 fires at the water line, where a short handler
   switches CRAOFA (NBG0/NBG1) and CRAOFB (sprites) to bank 1. The VBLANK
   register commit restores bank 0 (the shadow value) for the next frame.
   Water over the whole screen writes bank 1 right after that commit.

   Sprites follow the switch only through palette codes: Sonic's CLUT is
   rewritten to line-0 codes 1..15 (water_raster_sonic_clut). RGB CLUT
   sprites keep their colours (line 1, rings and shared objects, is the same
   in both palettes). */
#include <stdint.h>

void water_raster_enable(int on);            /* stage load: on only in Tidal Tempest */
int water_raster_active(void);
/* Stage load, after the stage palette and HUD colours are in CRAM bank 0. */
void water_raster_palette(const uint16_t water[64]);
/* Per frame, before sync: the first water line from water_screen_line(). */
void water_raster_commit(unsigned line);
/* Per frame, right after sync (inside VBLANK): arm the timer for this frame. */
void water_raster_latch(void);
/* Sonic's 16-entry CLUT (RGB) to line-0 palette codes, when active. */
void water_raster_sonic_clut(uint16_t clut[16]);

/* [0] 'WATR' [1] latch count [2] armed line for the frame now displayed
   [3] timer compare written [4] handler count [5] VCNT at the last handler
   [6] full-screen frames [7] enabled. */
extern volatile uint32_t scd_water_mailbox[8];
#endif
