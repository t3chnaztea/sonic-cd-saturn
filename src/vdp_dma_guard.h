/* VDP DMA queue guard. Yaul's vdp_dma_enqueue fills an SCU indirect table of
   DMA_QUEUE_REQUESTS_MAX_COUNT (16) transfers. Before
   tools/patches/libyaul-dma-queue-table.patch, the table held only 10 (it was
   sized with sizeof(dma_queue_t)). An 11th transfer in one frame overwrote the
   DMA callback list, and the next VBlank took a CPU address error (TT1 A route,
   seq 276). tools/test_yaul_dma_queue.py checks that the linked library carries
   the fix.

   Every game enqueue goes through scd_vdp_dma_enqueue (main.c includes this
   header after yaul.h, so the macro below covers main.c and its .inc views).
   A full queue never overflows. The copy goes straight to VRAM/CRAM and is
   counted, so QA sees it. scd_vdp_dma_stats: [0] highest queue count
   seen after a game enqueue, [1] direct copies because the queue was full. */
#ifndef SCD_VDP_DMA_GUARD_H
#define SCD_VDP_DMA_GUARD_H
#include <yaul.h>
#include <string.h>

/* Yaul itself enqueues on the same queue (vdp2_scrn_back_color_set, line colour
   screen, dbgio), bypassing this guard: game requests stop 2 slots short of 16. */
#define SCD_VDP_DMA_QUEUE 16u
#define SCD_VDP_DMA_RESERVED 2u
#define SCD_VDP_DMA_CAPACITY (SCD_VDP_DMA_QUEUE-SCD_VDP_DMA_RESERVED)
extern volatile uint32_t scd_vdp_dma_stats[2];

static inline void scd_vdp_dma_enqueue(void *dst,const void *src,size_t len){
    uint32_t queued=vdp_dma_count_get();
    if(queued>=SCD_VDP_DMA_CAPACITY){memcpy(dst,src,len);scd_vdp_dma_stats[1]++;return;}
    vdp_dma_enqueue(dst,src,len);
    if(queued+1>scd_vdp_dma_stats[0])scd_vdp_dma_stats[0]=queued+1;
}
#define vdp_dma_enqueue scd_vdp_dma_enqueue
#endif
