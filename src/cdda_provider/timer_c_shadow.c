#include <yaul.h>
#include "timer_c_shadow.h"
#include "cdda_envelope_shadow.h"
#include "../cdda_law.h"
static scd_cdda_law law;
static scu_ic_ihr_t previous_handler;
static scu_ic_mask_t previous_mask;
volatile scd_cdda_timer_status_shadow scd_cdda_timer_qa_shadow;

static void timer_c_irq(void){
    unsigned pending=MEMORY_READ(16,SCSP(0x42c));
    uint16_t now=cpu_frt_count_get();
    if(!(pending&0x100u)){
        scd_cdda_timer_qa_shadow.unexpected_irq++;
        MEMORY_WRITE(16,SCSP(0x42a),0); /* only this source owns MCIEB */
        scu_ic_mask_chg(SCU_IC_MASK_ALL,SCU_IC_MASK_SOUND_REQUEST);
        return;
    }
    /* Rearm before the next prescaled sample; target latency must prove this.
     * It is not an automatic147-count timer. Clear only our pending bit. */
    MEMORY_WRITE(16,SCSP(0x41c),0x026d);
    MEMORY_WRITE(16,SCSP(0x42e),0x0100);
    unsigned tick=scd_cdda_timer_qa_shadow.ticks;
    scd_cdda_timer_qa_shadow.timestamps[tick&127u]=now;
    scd_cdda_timer_qa_shadow.ticks=tick+1;
    if(scd_cdda_timer_qa_shadow.applying){
        unsigned before=law.gain;
        scd_cdda_law_tick(&law);
        if(law.gain!=before && !scd_cdda_envelope_target_shadow(law.gain))
            scd_cdda_timer_qa_shadow.request_rejected++;
    }
}

int scd_cdda_timer_start_shadow(scu_ic_ihr_t expected_idle){
    if(scd_cdda_timer_qa_shadow.running || !expected_idle ||
       scu_ic_ihr_get(SCU_IC_INTERRUPT_SOUND_REQUEST)!=expected_idle ||
       !(scu_ic_mask_get()&SCU_IC_MASK_SOUND_REQUEST) ||
       (MEMORY_READ(16,SCSP(0x41e))&0x100u))return 0;
    uint8_t mask=cpu_intc_mask_get();cpu_intc_mask_set(15);
    previous_handler=expected_idle;previous_mask=scu_ic_mask_get();
    scd_cdda_law_reset(&law);
    scd_cdda_timer_qa_shadow=(scd_cdda_timer_status_shadow){0};
    scu_ic_ihr_set(SCU_IC_INTERRUPT_SOUND_REQUEST,timer_c_irq);
    MEMORY_WRITE(16,SCSP(0x42a),0); /* audited startup ownership, not readback */
    MEMORY_WRITE(16,SCSP(0x42e),0x0100);
    MEMORY_WRITE(16,SCSP(0x41c),0x026d);
    MEMORY_WRITE(16,SCSP(0x42a),0x0100);
    scd_cdda_timer_qa_shadow.running=1;
    scu_ic_mask_chg(SCU_IC_MASK_ALL&~SCU_IC_MASK_SOUND_REQUEST,SCU_IC_MASK_NONE);
    cpu_intc_mask_set(mask);return 1;
}
int scd_cdda_timer_stop_shadow(void){
    if(!scd_cdda_timer_qa_shadow.running ||
       scu_ic_ihr_get(SCU_IC_INTERRUPT_SOUND_REQUEST)!=timer_c_irq)return 0;
    uint8_t mask=cpu_intc_mask_get();cpu_intc_mask_set(15);
    scu_ic_mask_chg(SCU_IC_MASK_ALL,SCU_IC_MASK_SOUND_REQUEST);
    MEMORY_WRITE(16,SCSP(0x42a),0);
    MEMORY_WRITE(16,SCSP(0x42e),0x0100);
    scu_ic_ihr_set(SCU_IC_INTERRUPT_SOUND_REQUEST,previous_handler);
    scd_cdda_timer_qa_shadow.running=0;scd_cdda_timer_qa_shadow.applying=0;
    scu_ic_mask_chg(SCU_IC_MASK_ALL&~SCU_IC_MASK_SOUND_REQUEST,
                   previous_mask&SCU_IC_MASK_SOUND_REQUEST);
    cpu_intc_mask_set(mask);return 1;
}
int scd_cdda_timer_apply_shadow(void){
    if(!scd_cdda_timer_qa_shadow.running ||
       scd_cdda_timer_qa_shadow.unexpected_irq ||
       !scd_cdda_envelope_installed_shadow())return 0;
    scd_cdda_timer_qa_shadow.applying=1;return 1;
}
int scd_cdda_request_shadow(unsigned rate){
    uint8_t mask=cpu_intc_mask_get();cpu_intc_mask_set(15);
    int valid=scd_cdda_timer_qa_shadow.running &&
        scd_cdda_timer_qa_shadow.applying &&
        !scd_cdda_timer_qa_shadow.unexpected_irq &&
        scd_cdda_envelope_installed_shadow() && scd_cdda_law_request(&law,rate);
    if(valid){
        scd_cdda_timer_qa_shadow.request_tick=scd_cdda_timer_qa_shadow.ticks;
        scd_cdda_timer_qa_shadow.request_frt=cpu_frt_count_get();
    }else scd_cdda_timer_qa_shadow.request_rejected++;
    cpu_intc_mask_set(mask);return valid;
}
int scd_cdda_reset_shadow(void){
    if(!scd_cdda_envelope_installed_shadow())return 0;
    uint8_t mask=cpu_intc_mask_get();cpu_intc_mask_set(15);
    scd_cdda_law_reset(&law);
    int valid=scd_cdda_envelope_reset_shadow();
    scd_cdda_timer_qa_shadow.reset_tick=scd_cdda_timer_qa_shadow.ticks;
    cpu_intc_mask_set(mask);return valid;
}
