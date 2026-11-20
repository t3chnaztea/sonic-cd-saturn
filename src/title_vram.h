#ifndef SCD_TITLE_VRAM_H
#define SCD_TITLE_VRAM_H
/* Normal 320-dot mode, 16-color 1x1 cells, 1x reduction allowance.
   Table 3.2 requires ONE pattern-name fetch even with two-word PNDs.
   NBG0: PN T0 -> CG T4. NBG1: PN T1 -> CG T5 (table 3.4).
   The old NBG1 PN T2/T3 -> CG T5 schedule violates that timing table.
   Nibbles are T0..T7 in the SH-2/VDP2 register's big-endian order. */
#define SCD_TITLE_VRAM_A0 0x01FF45FFu
#define SCD_TITLE_VRAM_B1 0x3FFF7FFFu
#endif
