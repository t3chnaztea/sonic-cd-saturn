#ifndef SCD_CDDA_LAW_PREPARATION_H
#define SCD_CDDA_LAW_PREPARATION_H
#include <stdint.h>
/* Source-only profile: original enabled, unpaused FDRCHG(0x20) to zero. */
typedef struct {
    uint16_t master, gain, target, remaining, rate;
    uint8_t active;
} scd_cdda_law;
void scd_cdda_law_reset(scd_cdda_law *s);
int scd_cdda_law_request(scd_cdda_law *s, unsigned rate);
void scd_cdda_law_tick(scd_cdda_law *s);
#endif
