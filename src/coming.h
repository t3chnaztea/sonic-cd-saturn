#ifndef SCD_COMING_H
#define SCD_COMING_H
#include <stdint.h>
/* Exact COME__.MMD78dd6500 model. Native pad uses original MD byte. */
typedef struct {
    int32_t scroll,shown_scroll;
    uint32_t frames,exit_reason;
    uint16_t timer,palette[64];
    uint8_t previous_hold,hold,tap,initial_wait,fade_step;
} fe_coming_state;
void fe_coming_begin(fe_coming_state *s,const uint16_t palette[64],unsigned prior_hold);
/* Publishes pre-decrement scroll. First initial VSync does not test exit.
   Later freshA/B/C/Start -> reasonmaskF0; timer0 -> reason100. Reason latches. */
int fe_coming_vint(fe_coming_state *s,unsigned hold);
int fe_coming_fade(fe_coming_state *s);
int fe_coming_pack_valid(const uint8_t *data,unsigned bytes);
/*15uint32 words; phase1load/2initialVSync/3screen/4fade/5finished/6failed.
   result0none/1missing/2invalid/3input/4timeout. scroll holds signed bits. */
typedef struct {uint32_t phase,frames,scroll,timer,held,tap,load_ok,result,fade_out,pack_bytes,tiles,music_started,exit_reason,fade_requested,previous_hold;} fe_coming_status;
extern volatile fe_coming_status fe_coming_qa;
void fe_coming(unsigned prior_hold);
#endif
