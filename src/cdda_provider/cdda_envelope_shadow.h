#ifndef SCD_CDDA_ENVELOPE_SHADOW_H
#define SCD_CDDA_ENVELOPE_SHADOW_H
/* Source-only candidate. Requires the reviewed five-change 68000 driver.
 * Install once before registering audio VBlank or starting any PCM/CD cue. */
int scd_cdda_envelope_install_shadow(void);
/* Candidate TimerC admission query. No MMIO or new installation action. */
int scd_cdda_envelope_installed_shadow(void);
/* Only unchanged target or the next rate32 downward target is admitted.
 * Caller serializes this and reset against TimerC's SH2 handler. */
int scd_cdda_envelope_target_shadow(unsigned gain);
int scd_cdda_envelope_reset_shadow(void);
/* Next-sample state from otherwise inaudible EFREG2. -1 means malformed. */
int scd_cdda_envelope_current_shadow(void);
#endif
