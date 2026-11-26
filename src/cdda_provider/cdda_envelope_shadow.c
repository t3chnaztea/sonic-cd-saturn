#include <yaul.h>
#include "ponesound.h"
#include "cdda_envelope_shadow.h"
#include "envelope_words.h"
extern sysComPara *m68k_com;
static unsigned installed;
static unsigned previous_target=784;
enum { TABLE_BEGIN=0xc400,TABLE_END=0xd866,SFX_BEGIN=0xe000 };
_Static_assert(0x408+DRV_SYS_END+sizeof(sysComPara)<=TABLE_BEGIN,"DSP tables overlap driver communication");
_Static_assert(TABLE_END<=SFX_BEGIN,"DSP tables overlap PCM samples");
/* CDDA output mix: measured against isolated retail FM effects. Scale only
 * the decoded stereo samples in TEMP14/15, before the existing fade multiply.
 * The original program's gain law, target/current witness and RAM operations
 * remain unchanged. COEF5 is 3276/4096 (0.7998, -1.94 dB). */
enum { MIX_BEGIN=56,MIX_STEPS=3,MIX_COEF=0x6660 };
static const uint16_t mix_program[MIX_STEPS][4]={
    {0x0e00,0x2c80,0x0002,0x0a00}, /* TEMP14 * COEF5 -> accumulator */
    {0x0f8e,0x2c80,0x0002,0x0a00}, /* save left; TEMP15 * COEF5 */
    {0x008f,0xac80,0x0002,0x0600}  /* save right; zero accumulator */
};
static uint16_t program_word(unsigned step,unsigned word){
    if(step<MIX_BEGIN)return scd_env_program[step][word];
    if(step<MIX_BEGIN+MIX_STEPS)return mix_program[step-MIX_BEGIN][word];
    return scd_env_program[step-MIX_STEPS][word];
}
static void write_target(unsigned gain){
    /* MEMS24 register format is low8 at+0, upper16 at+2. target=gain<<12.
     * Its low8 stays0, so one16-bit bus write updates the whole target. */
    MEMORY_WRITE(16,SCSP(0xe7e),(uint16_t)(gain<<4));
    previous_target=gain;
}
int scd_cdda_envelope_installed_shadow(void){return installed!=0;}
int scd_cdda_envelope_target_shadow(unsigned gain){
    if(!installed || gain>previous_target ||
       (gain!=previous_target && gain!=(previous_target>32?previous_target-32:0)))return 0;
    write_target(gain);
    return 1;
}
int scd_cdda_envelope_reset_shadow(void){
    if(!installed)return 0;
    write_target(784);return 1;
}
int scd_cdda_envelope_current_shadow(void){
    if(!installed)return -1;
    unsigned raw=MEMORY_READ(16,SCSP(0xec4));
    if((raw&15u) || raw>784u*16u)return -1;
    return (int)(raw>>4);
}
int scd_cdda_envelope_install_shadow(void){
    if(installed || m68k_com->start!=0x7777)return 0;
    for(unsigned i=0;i<0x400;i+=2)
        if(MEMORY_READ(16,SCSP(0x800+i))!=0)return 0;
    /* Audited startup ownership: no DSP program, PCM/CD playback or VBlank.
     * Direct CDDA is replaced, never mixed twice. Global master is untouched. */
    m68k_com->cdda_left_channel_vol_pan=0x1f;
    m68k_com->cdda_right_channel_vol_pan=0x0f;
    MEMORY_WRITE(16,SCSP(0x216),0x001f);
    MEMORY_WRITE(16,SCSP(0x236),0x000f);
    for(unsigned slot=0;slot<3;slot++)
        MEMORY_WRITE(16,SCSP(slot*32+0x16),MEMORY_READ(16,SCSP(slot*32+0x16))&0xff00u);
    MEMORY_WRITE(16,SCSP(0x402),0); /* owned DSP RBP0/RBL0; table addressing */
    for(unsigned i=0;i<sizeof(scd_env_data)/sizeof(scd_env_data[0]);i++)
        MEMORY_WRITE(16,SCSP_RAM(TABLE_BEGIN+i*2),scd_env_data[i]);
    for(unsigned i=0;i<128;i++){
        MEMORY_WRITE(16,SCSP(0xc00+i*4),0);
        MEMORY_WRITE(16,SCSP(0xc02+i*4),0x3100); /* TEMP gain784<<12 */
    }
    for(unsigned i=0;i<32;i++){
        MEMORY_WRITE(16,SCSP(0xe00+i*4),0);
        MEMORY_WRITE(16,SCSP(0xe02+i*4),0);
    }
    MEMORY_WRITE(16,SCSP(0xe02),0x8000); /* MEMS0=-2^23 */
    MEMORY_WRITE(16,SCSP(0xe06),0x0010); /* MEMS1=4096 */
    MEMORY_WRITE(16,SCSP(0xe7e),0x3100); /* MEMS31 target784<<12 */
    for(unsigned i=0;i<sizeof(scd_env_coef)/sizeof(scd_env_coef[0]);i++)
        MEMORY_WRITE(16,SCSP(0x700+i*2),scd_env_coef[i]);
    MEMORY_WRITE(16,SCSP(0x70a),MIX_COEF);
    for(unsigned i=0;i<sizeof(scd_env_madrs)/sizeof(scd_env_madrs[0]);i++)
        MEMORY_WRITE(16,SCSP(0x780+i*2),scd_env_madrs[i]);
    for(unsigned step=0;step<128;step++)for(unsigned word=0;word<4;word++)
        MEMORY_WRITE(16,SCSP(0x800+step*8+word*2),program_word(step,word));
    for(unsigned i=0;i<sizeof(scd_env_data)/sizeof(scd_env_data[0]);i++)
        if(MEMORY_READ(16,SCSP_RAM(TABLE_BEGIN+i*2))!=scd_env_data[i])return 0;
    for(unsigned step=0;step<128;step++)for(unsigned word=0;word<4;word++)
        if(MEMORY_READ(16,SCSP(0x800+step*8+word*2))!=program_word(step,word))return 0;
    for(unsigned i=0;i<sizeof(scd_env_coef)/sizeof(scd_env_coef[0]);i++)
        if(MEMORY_READ(16,SCSP(0x700+i*2))!=scd_env_coef[i])return 0;
    if(MEMORY_READ(16,SCSP(0x70a))!=MIX_COEF)return 0;
    for(unsigned i=0;i<sizeof(scd_env_madrs)/sizeof(scd_env_madrs[0]);i++)
        if(MEMORY_READ(16,SCSP(0x780+i*2))!=scd_env_madrs[i])return 0;
    MEMORY_WRITE(16,SCSP(0x016),(MEMORY_READ(16,SCSP(0x016))&0xff00u)|0x00ffu);
    MEMORY_WRITE(16,SCSP(0x036),(MEMORY_READ(16,SCSP(0x036))&0xff00u)|0x00efu);
    /* EFREG2 is a read-only QA witness; its effect send remains zero. */
    installed=1;
    previous_target=784;
    return 1;
}
