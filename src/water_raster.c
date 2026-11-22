/* Saturn water line for Tidal Tempest. See water_raster.h. */
#include <yaul.h>
#include "water_raster.h"

volatile uint32_t scd_water_mailbox[8];
static int enabled;
static unsigned pending_line=224;
/* Handler state: written in VBLANK by water_raster_latch, read once by the
   timer 0 handler during the displayed frame. */
static volatile uint16_t armed;
#define BANK1_CRAOFA 0x0011u /* NBG0 and NBG1 colour RAM offset 1 (x256) */
#define BANK1_CRAOFB 0x0010u /* sprite colour RAM offset 1 */

static void bank1_now(void){
    MEMORY_WRITE(16,VDP2(CRAOFA),BANK1_CRAOFA);
    MEMORY_WRITE(16,VDP2(CRAOFB),BANK1_CRAOFB);
}
/* Reading EXTEN with EXLTEN 0 latches the H/V counters (VDP2 manual; Beetle
   vdp2.c RegsRead); TVSTAT bit 2 is HBLANK. */
static unsigned raster_line(void){(void)MEMORY_READ(16,VDP2(EXTEN));return MEMORY_READ(16,VDP2(VCNT))&0x3ffu;}
#define TVSTAT_HBLANK 0x0004u
/* The timer fires one line early (water_raster_latch); wait here for the
   HBLANK that ends the line above the water and switch inside it. The switch
   row then no longer depends on how long the CPU took to take the interrupt
   (bus stalls, masked sections), which moved it by part of a line with CPU
   load. A handler entered past that HBLANK switches at once. */
static void water_line_handler(void){
    unsigned line=armed;
    if(!line)return;
    unsigned above=line-1,now;
    for(;;){
        now=raster_line();
        if(now>above || now>=224)break;
        if(now==above && (MEMORY_READ(16,VDP2(TVSTAT))&TVSTAT_HBLANK))break;
    }
    bank1_now();
    armed=0;
    scd_water_mailbox[5]=now;
    scd_water_mailbox[4]++;
}
int water_raster_active(void){return enabled;}
void water_raster_enable(int on){
    armed=0;pending_line=224;
    if(on && !enabled){
        scu_timer_t0_value_set(224);scu_timer_t0_set(water_line_handler);scu_timer_enable();
    } else if(!on && enabled){
        scu_timer_t0_clear();
    }
    enabled=on;
    scd_water_mailbox[7]=(uint32_t)on;scd_water_mailbox[0]=0x57415452;
}
void water_raster_palette(const uint16_t water[64]){
    if(!enabled)return;
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_ADDR(0);
    for(unsigned i=0;i<256;i++)cram[256+i]=cram[i];
    for(unsigned i=0;i<64;i++){cram[256+i]=water[i];cram[384+i]=water[i];}
}
void water_raster_commit(unsigned line){
    if(!enabled){return;}
    pending_line=line>224?224:line;
}
void water_raster_latch(void){
    if(!enabled){armed=0;return;}
    unsigned line=pending_line;
    scd_water_mailbox[2]=line;
    /* Direct register writes here, after the VBLANK register commit, last for
       the frame now starting; the next commit restores the shadow (bank 0).
       A frame that is not latched (menus, loading) therefore shows bank 0. */
    if(!line){armed=0;bank1_now();scd_water_mailbox[6]++;}
    else if(line<224){
        /* SCU timer 0 counts HBLANK-IN from VBLANK-OUT and interrupts on the
           compare value: the handler runs in the HBLANK before screen line
           `line` (measured by tools/test_water_emulator.py). */
        /* Compare c interrupts in the HBLANK ending screen line c-1 (above);
           c = line-1 leaves the handler a whole line to wait in. */
        unsigned compare=line>=2?line-1:line;
        scu_timer_t0_value_set((uint16_t)compare);scd_water_mailbox[3]=compare;armed=(uint16_t)line;
    } else armed=0;
    pending_line=224;
    scd_water_mailbox[1]++;
}
void water_raster_sonic_clut(uint16_t clut[16]){
    if(!enabled)return;
    for(unsigned i=1;i<16;i++)clut[i]=(uint16_t)i;
}
