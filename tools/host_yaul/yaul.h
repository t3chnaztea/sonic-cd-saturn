/* Host stand-in for the parts of <yaul.h> that src/water_raster.c uses, so
   host tests link the real water raster code (tools/test-sonic-view.sh).
   VDP2 registers and colour RAM are host arrays; SCU timer 0 is recorded. */
#ifndef SCD_HOST_YAUL_H
#define SCD_HOST_YAUL_H
#include <stdint.h>
#include <string.h>
#define CRAOFA 0x00E4u
#define CRAOFB 0x00E6u
#define EXTEN 0x0002u
#define TVSTAT 0x0004u
#define VCNT 0x000Au
static uint16_t host_vdp2_regs[0x100];
static uint16_t host_vdp2_cram[0x800];
static void (*host_scu_timer0_handler)(void);
static uint16_t host_scu_timer0_value;
static int host_scu_timer_enabled;
#define VDP2(r) (r)
#define MEMORY_WRITE(bits,address,value) (host_vdp2_regs[((address)/2)&0xff]=(uint16_t)(value))
#define MEMORY_READ(bits,address) (host_vdp2_regs[((address)/2)&0xff])
#define VDP2_CRAM_ADDR(offset) ((uintptr_t)(host_vdp2_cram+(offset)/2))
static inline void scu_timer_t0_value_set(uint16_t value){host_scu_timer0_value=value;}
static inline void scu_timer_t0_set(void (*handler)(void)){host_scu_timer0_handler=handler;}
static inline void scu_timer_t0_clear(void){host_scu_timer0_handler=0;}
static inline void scu_timer_enable(void){host_scu_timer_enabled=1;}
/* SCU DMA level 2 as src/sonic_view.inc uses it: a direct transfer that lands
   only when the level is waited on, so host tests prove the code waits before
   VDP1 (or the next decode) would use the destination. */
typedef enum {SCU_DMA_MODE_DIRECT=0} scu_dma_mode_t;
typedef enum {SCU_DMA_SPACE_BUS_B=0} scu_dma_space_t;
typedef enum {SCU_DMA_STRIDE_2_BYTES=1} scu_dma_stride_t;
typedef enum {SCU_DMA_UPDATE_NONE=0} scu_dma_update_t;
typedef enum {SCU_DMA_START_FACTOR_ENABLE=7} scu_dma_start_factor_t;
typedef struct {scu_dma_mode_t mode;struct {struct {uintptr_t len,dst,src;} direct;} xfer;
    scu_dma_space_t space;scu_dma_stride_t stride;scu_dma_update_t update;} scu_dma_level_cfg_t;
typedef struct {uintptr_t len,dst,src;} scu_dma_handle_t;
static scu_dma_handle_t host_scu_dma_pending[3];static int host_scu_dma_busy[3];
static inline void scu_dma_config_buffer(scu_dma_handle_t *h,const scu_dma_level_cfg_t *c){h->len=c->xfer.direct.len;h->dst=c->xfer.direct.dst;h->src=c->xfer.direct.src;}
static inline void scu_dma_config_set(int level,scu_dma_start_factor_t f,const scu_dma_handle_t *h,void *cb){(void)f;(void)cb;host_scu_dma_pending[level]=*h;}
static inline void scu_dma_level_fast_start(int level){host_scu_dma_busy[level]=1;}
static inline void scu_dma_level_wait(int level){
    if(!host_scu_dma_busy[level])return;
    memcpy((void *)host_scu_dma_pending[level].dst,(const void *)host_scu_dma_pending[level].src,host_scu_dma_pending[level].len);
    host_scu_dma_busy[level]=0;
}
#endif
