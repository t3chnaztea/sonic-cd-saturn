/* "Thank You" screen on the Saturn (THANKS_M.MMD; IPX.asm VisualMode_GoodEnd runs it
   after the good ending, IPX.asm:1176-1186; GameDone does not, IPX.asm:300-326).
   The screen code (src/credits.c, src/credits_saturn.c) is front-end overlay code
   (src/saturn.x .zone_R0, cd/ZTR0.BIN): front-end code calls fe_credits_thanks()
   directly; resident code goes through scd_credits_thanks_play() (src/ending.c). */
#ifndef SCD_CREDITS_SATURN_H
#define SCD_CREDITS_SATURN_H
#include <stdint.h>

/* Front-end overlay entry. Runs the screen from its fade from black to the end of its
   fade to black: Start, A, B or C quits, or the 3-minute end timer. The best Time
   Attack initials come from the "SCDSATURNTA" save (all "AAA" without one).
   Returns 0 when it ran, -1 without cd/THANKS.BIN. Takes low work RAM
   0x200000-0x21FFFF (sets scd_low_packs_lost), VDP2 VRAM bank A0 and B0, CRAM lines
   0-7, VDP1 VRAM 0x8000-0xFFFF (the HUD art; stage loads upload it again) and the
   sprite priorities. VDP1 must be in the front end's manual mode (interval -1) and
   stays in it; on return the display is off and sprite priority 0 is 4. */
int fe_credits_thanks(void);
/* Visual Mode's hook after the good-ending replay (src/visual_mode.c): runs it. */
void fe_vm_thanks(void);

/* Resident entry: loads the front-end overlay and runs fe_credits_thanks. */
int scd_credits_thanks_play(void);
typedef struct {
    int (*thanks)(void);
} scd_credits_zone_ops;
extern const scd_credits_zone_ops fe_credits_zone_ops;

/* Emulator test entry: SCD_CREDITS_REQUEST in [0] at the title runs the screen
   (src/main.c, scd_credits_test_entry), then the title again. While the screen runs: [1] 'THKP' then 'THKD',
   [2] the most FRT ticks (clock/8) one call of src/credits.c took (low half) and one
   VDP1 list build (high half), [3] the call whose picture shows (~0 before the first),
   [4] the phase after it (src/credits.h md_phase), [5] its sprites, [6] frames shown,
   [7] the last pad edge (Mega Drive bits: Start $80, A $40, C $20, B $10). */
#define SCD_CREDITS_REQUEST 0x54484E4Bu   /* "THNK" */
/* The same entry plays an ending movie (scd_ending_play, src/ending.h). */
#define SCD_CREDITS_REQUEST_GOODEND 0x454E4447u   /* "ENDG" */
#define SCD_CREDITS_REQUEST_BADEND 0x454E4442u    /* "ENDB" */
/* And the opening movie, alone (tools/test_credits_roll_emulator.py opening: its picture times). */
#define SCD_CREDITS_REQUEST_OPENING 0x4F504E47u   /* "OPNG" */
void scd_credits_test_entry(void);
extern volatile uint32_t scd_credits_mailbox[8];
#endif
