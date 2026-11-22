#ifndef SCD_SPECIAL_MAIN_H
#define SCD_SPECIAL_MAIN_H
#include <stddef.h>
#include <stdint.h>
/* Special Stage Main CPU program (Main.asm) for stages 1-8: background
   scroll, palette and palette cycle, HUD tilemaps, time-stone palette, fades
   and results. Palettes and name tables keep original Mega Drive word values.
   One pack (cd/SSMn.BIN) holds one stage's LoadSSnData art and tilemaps. */
typedef struct {const uint8_t *data;uint32_t size,offset[11],length[11];uint16_t stage;} scd_special_main_pack;
typedef struct {
    uint16_t palette[64],fade[64];
    uint16_t plane_a[2048],plane_b[2048]; /* 64x32 name tables */
    uint16_t hscroll[256],hscroll_frac[256],display[256]; /* lines 0..127, A then B */
    uint32_t scroll_offset[6]; /* scrollOffset1..6 */
    uint16_t shift,cycle_index,results_timer,extra_players,icon_frame,icon_timer;
    uint8_t scroll_mode,scroll_flags,stone_delay,scroll_disable,time_attack,stage,score_tallied,time_stones;
    uint32_t ring_bonus,time_bonus,score,next_life;
    uint8_t lives;
    /* Name table rows written since the display last took them (bit per row; plane A, plane B). */
    uint32_t dirty[2];
    /* ss5BGScrollShift/ss6BGWaveTableOff (one word) and the PalCycle_SS2-7
       program-data counters, per stage (stage 1 uses cycle_index). */
    uint16_t wave,cycle[8][4];
} scd_special_main;
int scd_special_main_open(scd_special_main_pack *pack,const void *data,size_t size);
/* Main.asm Start through LoadSSnData and PrepFadeFromWhite; stage must match the pack. */
int scd_special_main_stage(scd_special_main *m,const scd_special_main_pack *pack,unsigned stage,int time_attack);
/* CheckLineScroll: stages 1, 5 and 6 scroll by line, the rest by 8-line row. */
static inline int scd_special_main_line_scroll(unsigned stage){return stage==1 || stage==5 || stage==6;}
/* BGScroll1/2/3 sections for stages 1, 5 and 6; section 1 also performs the VInt CopyHScroll_Line. */
void scd_special_main_scroll(scd_special_main *m,const scd_special_main_pack *pack,unsigned section,int stage_over);
/* CopyHScroll_SS2/3/4/7/8 (row scroll stages): offsets, then rows into the
   VDP H-scroll table (224 lines, A then B). */
void scd_special_main_copy_hscroll(scd_special_main *m,unsigned stage,uint16_t *table);
void scd_special_main_hud(scd_special_main *m,const scd_special_main_pack *pack,uint16_t rings,uint8_t ufo_count);
void scd_special_main_timer(scd_special_main *m,const scd_special_main_pack *pack,uint32_t timer);
void scd_special_main_stone_palette(scd_special_main *m,const scd_special_main_pack *pack,uint8_t ufo_count);
/* PaletteCycle for specStageID stage (1-8); returns 1 when CRAM is updated. */
int scd_special_main_cycle(scd_special_main *m,const scd_special_main_pack *pack,unsigned stage);
/* One VSync step of FadeToWhite (0) or FadeFromWhite (1). step is 0..23. */
void scd_special_main_fade(scd_special_main *m,int from_white,unsigned step);
void scd_special_main_add_score(scd_special_main *m,uint32_t points);
/* Results through DrawResultsBase and PrepFadeFromWhite. */
void scd_special_main_results(scd_special_main *m,const scd_special_main_pack *pack,uint16_t rings,uint32_t timer,uint8_t time_stones);
/* VInt_Results body: score, bonuses and extra player icons. */
void scd_special_main_results_vint(scd_special_main *m,const scd_special_main_pack *pack);
/* Results_MainLoop tally before VSync; returns FM request or 0. */
unsigned scd_special_main_tally(scd_special_main *m);
/* After VSync: returns 1 for ka-ching, 2 to leave (Start or timer). */
unsigned scd_special_main_tally_check(scd_special_main *m,unsigned tapped);
uint32_t scd_special_main_hash(const scd_special_main *m);
#endif
