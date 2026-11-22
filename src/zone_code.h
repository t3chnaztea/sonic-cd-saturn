#ifndef SCD_ZONE_CODE_H
#define SCD_ZONE_CODE_H
/* Zone code overlays (heap plan B, src/saturn.x): the zone (stage_zone numbering, 0 PPZ ..
   6 MM) whose overlay src/main.c zone_tables_load has loaded, ~0u while one loads. Every
   resident dispatch into overlay code checks it: boss ops (src/boss.c), the R5 background
   ops (src/background.c) and the object zone ops (src/objects.c, asserted). Host builds
   have no overlay, so every zone counts as loaded there. */
/* The front-end overlay (src/saturn.x .zone_R0, fe_ symbols) shares the zone range.
   scd_frontend_overlay_load() (src/main.c) evicts the zone overlay and sets this id;
   the next stage load reads its zone overlay again. Front-end code checks
   scd_zone_code_ready(SCD_ZONE_FRONTEND) before it calls into fe_ code. */
#define SCD_ZONE_FRONTEND 15u
void scd_frontend_overlay_load(void);
#ifdef SCD_ZONE_OVERLAY
extern unsigned scd_zone_code_zone;
static inline int scd_zone_code_ready(unsigned zone){return zone==scd_zone_code_zone;}
#else
static inline int scd_zone_code_ready(unsigned zone){(void)zone;return 1;}
#endif
#endif
