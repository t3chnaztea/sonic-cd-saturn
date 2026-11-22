#include "cdda_law.h"
void scd_cdda_law_reset(scd_cdda_law *s) {
    s->master=896;
    s->gain=(uint16_t)((896u*s->master)/1024u);
    s->target=s->gain;s->remaining=0;s->rate=0;s->active=0;
}
int scd_cdda_law_request(scd_cdda_law *s,unsigned rate) {
    if(rate!=0x20u)return 0;
    s->target=0;s->remaining=s->gain;s->rate=32;s->active=1;
    return 1;
}
void scd_cdda_law_tick(scd_cdda_law *s) {
    if(!s->active)return;
    /* BIOS 28f0/28f4 uses unsigned borrow, not equality. */
    if(s->remaining<s->rate) {
        s->gain=s->target;s->remaining=0;s->rate=0;s->active=0;
    } else {
        s->remaining=(uint16_t)(s->remaining-s->rate);
        s->gain=(uint16_t)(s->target+s->remaining);
    }
}
