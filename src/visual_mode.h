#ifndef SCD_VISUAL_MODE_H
#define SCD_VISUAL_MODE_H
/* Visual Mode (src/visual_mode.c): front-end overlay code (fe_ names, src/saturn.x
   .zone_R0), reached through fe_frontend_zone_ops (src/frontend.c) only. */

/* IPX.asm VisualMode: the menu, then the chosen movie, until EXIT. Returns when the
   menu exits (or cd/VISMODE.BIN is missing); the caller goes back to the title. */
void fe_visual_mode(void);

/* IPX.asm VisualMode_GoodEnd 1184-1185: RunMMD(SCMD_THANKYOU) after the good
   ending. The weak default does nothing; the "Thank You" screen (src/credits.c)
   provides the real one. */
void fe_vm_thanks(void);

/* Sound Test Image.asm: secret picture n (1 Fun is infinite, 2 M.C. Sonic, 3 Tails,
   4 Batman, 5 Cute Sonic) from cd/SECRET<n>.BIN until Start, then faded to black.
   Returns -1 when the file is missing. */
int fe_secret_image(unsigned n);
#endif
