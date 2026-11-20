#ifndef SCD_CDDA_TIMER_C_SHADOW_H
#define SCD_CDDA_TIMER_C_SHADOW_H
#include <yaul.h>
typedef struct {
    uint32_t running,ticks,unexpected_irq,request_rejected,applying;
    uint32_t request_tick,request_frt,reset_tick;
    uint16_t timestamps[128];
} scd_cdda_timer_status_shadow;
extern volatile scd_cdda_timer_status_shadow scd_cdda_timer_qa_shadow;
/* Diagnostic only at first. Precondition: source audit proves MCIEB has no
 * owner; its register is write-only, so a read cannot prove that precondition.
 * Sound request must be masked and its handler must equal expected_idle. */
int scd_cdda_timer_start_shadow(scu_ic_ihr_t expected_idle);
int scd_cdda_timer_stop_shadow(void);
/* Enable only after actual timer diagnostic acceptance. Does not reset phase. */
int scd_cdda_timer_apply_shadow(void);
int scd_cdda_request_shadow(unsigned rate);
int scd_cdda_reset_shadow(void);
#endif
