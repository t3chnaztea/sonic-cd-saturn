/* Compile the production streaming include against guarded host VRAM. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sonic_frames.h"
#include <yaul.h> /* tools/host_yaul: SCU DMA level 2 stand-in used by sonic_view.inc */
#define __aligned(n) __attribute__((aligned(n)))
static uint8_t vram[0x10000] __aligned(16),previous[0x10000],pack[0x34000];
static uint32_t stage_pack_bytes[1];
#define PACK_SONIC_FRAMES 0
#define STAGE_PACK_DATA(id) (pack)
#define VDP1_VRAM(address) (vram+(address))
#include "../src/sonic_view.inc"
static uint16_t expected[198][4096];
static void check(unsigned frame,unsigned address){
    assert(address>=SONIC_TEXTURE_BASE && address+2080<=sizeof(vram));
    assert(!((address-SONIC_TEXTURE_BASE)%SONIC_TEXTURE_STRIDE));
    assert(!memcmp(vram,previous,address));
    assert(!memcmp(vram+address+2080,previous+address+2080,sizeof(vram)-address-2080));
    const uint16_t *pixels=(const uint16_t *)(vram+address),*clut=pixels+1024;
    for(unsigned i=0;i<4096;i++)assert(clut[(pixels[i/4]>>((3-(i&3))*4))&15]==expected[frame][i]);
}
int main(void){
    FILE *f=fopen("assets/generated/sonic-frames.bin","rb");assert(f);
    stage_pack_bytes[0]=fread(pack,1,sizeof(pack),f);assert(feof(f));fclose(f);
    f=fopen("build/sonic-animation/expected-frames.bin","rb");assert(f);
    for(unsigned n=0;n<198;n++)for(unsigned i=0;i<4096;i++){
        int high=fgetc(f),low=fgetc(f);assert(high>=0 && low>=0);expected[n][i]=(high<<8)|low;
    }
    assert(fgetc(f)==EOF);fclose(f);
    memset(vram,0xA5,sizeof(vram));sonic_view_reset();
    unsigned samples=0;
    for(unsigned epoch=0;epoch<3;epoch++){
        /* Title/special overwrite every slot. Reset must force fresh uploads,
           including the previously cached pose, and preserve adjacent arenas. */
        if(epoch){memset(vram+SONIC_TEXTURE_BASE,0xCC,SONIC_TEXTURE_SLOTS*SONIC_TEXTURE_STRIDE);sonic_view_reset();}
        for(unsigned n=0;n<396;n++){
            unsigned frame=n<198?n:395-n;
            /* The upload is an SCU DMA (host: lands at the level wait): before
               sonic_texture_wait() VRAM is untouched; after it, exactly the slot changed. */
            memcpy(previous,vram,sizeof(vram));unsigned at=sonic_view_texture(frame);
            assert(!memcmp(vram,previous,sizeof(vram)));sonic_texture_wait();check(frame,at);samples++;
            memcpy(previous,vram,sizeof(vram));unsigned misses=scd_sonic_view_mailbox[14];
            assert(sonic_view_texture(frame)==at && misses==scd_sonic_view_mailbox[14]);
            assert(!memcmp(previous,vram,sizeof(vram)));
        }
    }
    assert(scd_sonic_view_mailbox[15]==3);
    /* Render-side prefetch: partly and fully stepped decodes (7-word steps)
       upload the same pixels and slots as an immediate decode. */
    memset(vram+SONIC_TEXTURE_BASE,0xCC,SONIC_TEXTURE_SLOTS*SONIC_TEXTURE_STRIDE);sonic_view_reset();
    unsigned prefetched=0;
    for(unsigned n=0;n<198;n++){
        sonic_view_prefetch(n);
        for(unsigned step=0;step<(n%3?1000:n%7);step++)sonic_view_prefetch_step(7);
        memcpy(previous,vram,sizeof(vram));unsigned misses=scd_sonic_view_mailbox[14];
        unsigned at=sonic_view_texture(n);sonic_texture_wait();check(n,at);
        assert(scd_sonic_view_mailbox[14]==misses+1 && at==SONIC_TEXTURE_BASE+(n%SONIC_TEXTURE_SLOTS)*SONIC_TEXTURE_STRIDE);
        sonic_view_prefetch(n);assert(sonic_prefetch_frame<0);prefetched++;
    }
    /* All eight slots survive a hot eight-pose loop without another decode. */
    for(unsigned n=0;n<8;n++)sonic_view_texture(n);
    unsigned misses=scd_sonic_view_mailbox[14];
    for(unsigned n=0;n<800;n++)sonic_view_texture(n%8);
    assert(scd_sonic_view_mailbox[14]==misses);
    /* Bounded hostile/truncated pack handling, with guard words around output. */
    scd_sonic_frames valid=sonic_source,bad;
    for(unsigned n=0;n<stage_pack_bytes[0];n++)assert(scd_sonic_frames_open(&bad,pack,n)==-1);
    struct {uint16_t before,pixels[1040],after;} guarded={.before=0x1357,.after=0x2468};
    assert(scd_sonic_frames_decode(&valid,198,guarded.pixels)==-1);
    unsigned first=(unsigned)pack[40]<<24|(unsigned)pack[41]<<16|(unsigned)pack[42]<<8|pack[43];
    uint8_t saved[2]={pack[first],pack[first+1]};
    for(unsigned code=0;code<=0xFFFF;code+=0x7FFF){
        pack[first]=code>>8;pack[first+1]=code;
        assert(scd_sonic_frames_decode(&valid,0,guarded.pixels)==-1);
        assert(guarded.before==0x1357 && guarded.after==0x2468);
    }
    pack[first]=saved[0];pack[first+1]=saved[1];
    printf("Sonic texture streaming: %u exact 4096-pixel uploads, %u prefetched, cache hits, all 198 poses, three arena generations and adjacent VRAM guards pass\n",samples,prefetched);
}
