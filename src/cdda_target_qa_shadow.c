#include <yaul.h>
#include "cdda_provider/cdda_envelope_shadow.h"
#include "cdda_target_qa_shadow.h"
volatile uint32_t scd_cdda_target_qa_shadow[20];
void scd_cdda_target_snapshot_shadow(void){
    uint32_t seq=scd_cdda_target_qa_shadow[3];
    scd_cdda_target_qa_shadow[3]=seq+1;
    scd_cdda_target_qa_shadow[0]=0x43445131; /* CDQ1 */
    scd_cdda_target_qa_shadow[1]=1;
    scd_cdda_target_qa_shadow[2]=20;
    scd_cdda_target_qa_shadow[4]=(uint32_t)(uintptr_t)scu_ic_ihr_get(SCU_IC_INTERRUPT_SOUND_REQUEST);
    scd_cdda_target_qa_shadow[5]=(uint32_t)scu_ic_mask_get();
    scd_cdda_target_qa_shadow[6]=MEMORY_READ(16,SCSP(0x41e)); /* SCIEB */
    scd_cdda_target_qa_shadow[7]=MEMORY_READ(16,SCSP(0x42c)); /* MCIPD */
    scd_cdda_target_qa_shadow[8]=UINT32_MAX; /* master is write-only; no readback claim */
    scd_cdda_target_qa_shadow[9]=MEMORY_READ(16,SCSP(0x016)); /* PCM0/DSP0 sends */
    scd_cdda_target_qa_shadow[10]=MEMORY_READ(16,SCSP(0x036)); /* PCM1/DSP1 sends */
    scd_cdda_target_qa_shadow[11]=MEMORY_READ(16,SCSP(0x056)); /* PCM2/DSP2 sends */
    scd_cdda_target_qa_shadow[12]=MEMORY_READ(16,SCSP(0x216)); /* direct CDDA0 */
    scd_cdda_target_qa_shadow[13]=MEMORY_READ(16,SCSP(0x236)); /* direct CDDA1 */
    scd_cdda_target_qa_shadow[14]=MEMORY_READ(16,SCSP(0xe7c)); /* target low8 */
    scd_cdda_target_qa_shadow[15]=MEMORY_READ(16,SCSP(0xe7e)); /* target upper16 */
    scd_cdda_target_qa_shadow[16]=MEMORY_READ(16,SCSP(0xec4)); /* next gain*16 */
    scd_cdda_target_qa_shadow[18]=(uint32_t)scd_cdda_envelope_installed_shadow();
    /* Derive from the single raw sample above. Other fields remain sequential. */
    unsigned raw=scd_cdda_target_qa_shadow[16];
    scd_cdda_target_qa_shadow[17]=!scd_cdda_target_qa_shadow[18] || (raw&15u) || raw>784u*16u?UINT32_MAX:raw>>4;
    scd_cdda_target_qa_shadow[19]=cpu_frt_count_get();
    scd_cdda_target_qa_shadow[3]=seq+2;
}
