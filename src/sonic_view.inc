#include "zone_object_art.h" /* OBJECT_ATLAS_BASE */
/* Gameplay-only texture arena. The caller has waited for the preceding VDP1
   list; the overlapping clear-only draw never samples these textures. Title
   and special-stage transitions invalidate every slot before gameplay resumes. */
#define SONIC_TEXTURE_BASE 0xB000u
#define SONIC_TEXTURE_STRIDE 2080u
#define SONIC_TEXTURE_SLOTS 8u
/* SonAni_Hurt uses mapping $5D (scddisasm Sonic/Data/Animations.asm).
   Decode once during stage load so a 20-ring loss does not also pay for its
   first pose decode on the same gameplay update. */
#define SONIC_HURT_FRAME 0x5Du
_Static_assert(SONIC_TEXTURE_BASE>=0xAC80,"Sonic overlaps original HUD");
_Static_assert(SONIC_TEXTURE_BASE+SONIC_TEXTURE_STRIDE*SONIC_TEXTURE_SLOTS<=0x10000,"Sonic overlaps diagnostic atlas");
/* Sonic with sproffset bit 15 set (ACTION.C:322 reverse|=32768) is in front
   of high-priority plane cells. Plane cells reach VDP2 priority 5 and RGB
   sprite pixels take sprite register 0 (4), so this LUT gives the pose the
   line-0 palette codes (stage palette = Sonic palette + zone palette) with
   PR=1: sprite register 1 (7), below the later-drawn HUD. */
#define SONIC_HIGH_LUT 0x1AAA0u
_Static_assert(SONIC_HIGH_LUT>=0x10000u+21u*2080u && SONIC_HIGH_LUT+32u<=OBJECT_ATLAS_BASE && SONIC_HIGH_LUT%8u==0,"high Sonic LUT overlaps art");
static __attribute__((unused)) unsigned sonic_view_high_lut(void){
    volatile uint16_t *lut=(volatile uint16_t *)VDP1_VRAM(SONIC_HIGH_LUT);
    lut[0]=0;for(unsigned i=1;i<16;i++)lut[i]=(uint16_t)(0x4000u|i);
    return SONIC_HIGH_LUT/8;
}
static scd_sonic_frames sonic_source;
static int sonic_texture_frames[SONIC_TEXTURE_SLOTS];
static unsigned sonic_texture_next;
static uint16_t sonic_texture_decode[1040] __aligned(16);
static uint16_t sonic_hurt_decode[1040] __aligned(16);
/* Render-side prefetch: the pose a fixed-duration animation shows next is
   decoded here in small steps while the CPU waits for VDP1 to finish the
   frame (sprite_draw), so a cache miss on a busy frame only starts a DMA.
   Slot choice, upload order and pixels are the same as an immediate decode. */
static uint16_t sonic_prefetch_decode[1040] __aligned(16);
static scd_sonic_frames_cursor sonic_prefetch_cursor;
static int sonic_prefetch_frame=-1,sonic_prefetch_done;
/* Last submitted gameplay Sonic: magic, serial, simulation frame, mapping,
   render flags, world X/Y, camera X/Y, slot address, animation/cursor/timer,
   era/act, palette tick, hidden, cache misses and generation. */
/* [16] replay case or UINT32_MAX, [17] path/physics flags for terrain priority. */
volatile uint32_t scd_sonic_view_mailbox[18];
static void sonic_view_reset(void){
    int result=scd_sonic_frames_open(&sonic_source,STAGE_PACK_DATA(PACK_SONIC_FRAMES),stage_pack_bytes[PACK_SONIC_FRAMES]);
    assert(!result);if(result)abort();
    result=scd_sonic_frames_decode(&sonic_source,SONIC_HURT_FRAME,sonic_hurt_decode);
    assert(!result);if(result)abort();
    water_raster_sonic_clut(sonic_hurt_decode+1024);
    for(unsigned i=0;i<SONIC_TEXTURE_SLOTS;i++)sonic_texture_frames[i]=-1;
    sonic_texture_next=0;scd_sonic_view_mailbox[15]++;
    sonic_prefetch_frame=-1;sonic_prefetch_done=0;
}
/* A decoded pose reaches VDP1 VRAM by SCU DMA level 2 (libyaul uses 0 for the
   VDP1 list and 1 for the VBlank queue): the CPU keeps building sprite commands
   while the 2080 bytes move, and sonic_texture_wait() finishes the transfer
   before the next decode into the buffer and before VDP1 is given the list. */
static int sonic_texture_dma_busy;
static void sonic_texture_wait(void){if(sonic_texture_dma_busy){scu_dma_level_wait(2);sonic_texture_dma_busy=0;}}
static void sonic_texture_upload(unsigned address,const uint16_t *source){
    const scu_dma_level_cfg_t cfg={.mode=SCU_DMA_MODE_DIRECT,.xfer.direct.len=sizeof(sonic_texture_decode),
        .xfer.direct.dst=(uintptr_t)VDP1_VRAM(address),.xfer.direct.src=(uintptr_t)source,
        .space=SCU_DMA_SPACE_BUS_B,.stride=SCU_DMA_STRIDE_2_BYTES,.update=SCU_DMA_UPDATE_NONE};
    static scu_dma_handle_t handle;
    scu_dma_config_buffer(&handle,&cfg);
    scu_dma_config_set(2,SCU_DMA_START_FACTOR_ENABLE,&handle,NULL);
    scu_dma_level_fast_start(2);sonic_texture_dma_busy=1;
}
static int sonic_texture_cached(unsigned frame){
    for(unsigned i=0;i<SONIC_TEXTURE_SLOTS;i++)if(sonic_texture_frames[i]==(int)frame)return 1;
    return 0;
}
/* One bounded step of the pending prefetch; returns nonzero while work remains. */
static int sonic_view_prefetch_step(unsigned budget){
    if(sonic_prefetch_frame<0 || sonic_prefetch_done)return 0;
    sonic_texture_wait(); /* The previous upload may still read this buffer. */
    int result=scd_sonic_frames_step(&sonic_prefetch_cursor,sonic_prefetch_decode,budget);
    assert(result>=0);if(result<0)abort();
    sonic_prefetch_done=result;
    return !result;
}
static __attribute__((unused)) void sonic_view_prefetch(unsigned frame){
    if(frame==SONIC_HURT_FRAME || (int)frame==sonic_prefetch_frame || sonic_texture_cached(frame))return;
    int result=scd_sonic_frames_begin(&sonic_source,frame,&sonic_prefetch_cursor);
    assert(!result);if(result){sonic_prefetch_frame=-1;return;}
    sonic_prefetch_frame=(int)frame;sonic_prefetch_done=0;
}
static unsigned sonic_view_texture(unsigned frame){
    for(unsigned i=0;i<SONIC_TEXTURE_SLOTS;i++)if(sonic_texture_frames[i]==(int)frame)return SONIC_TEXTURE_BASE+i*SONIC_TEXTURE_STRIDE;
    sonic_texture_wait();
    const uint16_t *source=sonic_texture_decode;
    if((int)frame==sonic_prefetch_frame){
        while(sonic_view_prefetch_step(1024)){}
        /* Tidal Tempest: line-0 palette codes so the water line switches Sonic too. */
        water_raster_sonic_clut(sonic_prefetch_decode+1024);
        source=sonic_prefetch_decode;sonic_prefetch_frame=-1;sonic_prefetch_done=0;
    }
    else if(frame==SONIC_HURT_FRAME)memcpy(sonic_texture_decode,sonic_hurt_decode,sizeof(sonic_texture_decode));
    else{
        int result=scd_sonic_frames_decode(&sonic_source,frame,sonic_texture_decode);
        assert(!result);if(result)abort();
        /* Tidal Tempest: line-0 palette codes so the water line switches Sonic too. */
        water_raster_sonic_clut(sonic_texture_decode+1024);
    }
    unsigned slot=sonic_texture_next;sonic_texture_next=(slot+1)%SONIC_TEXTURE_SLOTS;
    unsigned address=SONIC_TEXTURE_BASE+slot*SONIC_TEXTURE_STRIDE;
    sonic_texture_upload(address,source);
    sonic_texture_frames[slot]=frame;scd_sonic_view_mailbox[14]++;
    return address;
}
