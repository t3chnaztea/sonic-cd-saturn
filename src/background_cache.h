#ifndef SCD_BACKGROUND_CACHE_H
#define SCD_BACKGROUND_CACHE_H
#include "stage.h"

/* Each physical row holds the 64 world tiles starting at its cached sx.
   Reuse their overlap only when the world row matches (ring wrap invalidates
   it). Fixed rows always have sx == 0; their source wraps at 512 pixels. */
#define SCD_BACKGROUND_PERIODIC_ROWS 128
/* periodic[row] is the tile width W over which world tile wx repeats tile
   wx&63 (W>=64; capped at 255). Ring slot s holds tile wx with wx&63 == s, so
   for starts old and sx with both 64-tile windows inside [0,W) every slot
   already holds the right PND: a raster band whose scroll wraps at 512
   pixels, or a row read through both raster paths, needs no refill. */
static inline void scd_background_periodic_rows(const stage_t *stage,uint8_t *periodic){
    for(int row=0;row<SCD_BACKGROUND_PERIODIC_ROWS;row++){
        int w=64;
        while(w<254){
            uint16_t a[2],b[2];
            stage_tile_pair(stage,1,(w-64)*8,row*8,a);stage_tile_pair(stage,1,w*8,row*8,b);
            if(a[0]!=b[0]||a[1]!=b[1]){if(a[0]==b[0])w++;break;}
            w+=2;
        }
        periodic[row]=(uint8_t)w;
    }
}
/* Aligned big-endian loads: one bus read each on the SH-2. */
static inline uint32_t scd_background_be16(const uint8_t *p){
    uint16_t v=*(const uint16_t *)(const void *)p;
#if __BYTE_ORDER__==__ORDER_LITTLE_ENDIAN__
    v=__builtin_bswap16(v);
#endif
    return v;
}
static inline uint32_t scd_background_be32(const uint8_t *p){
    uint32_t v=*(const uint32_t *)(const void *)p;
#if __BYTE_ORDER__==__ORDER_LITTLE_ENDIAN__
    v=__builtin_bswap32(v);
#endif
    return v;
}
/* Tiles [wx,end) of BG row y into ring row out: the PNDs stage_tile gives.
   A Quartz Quadrant layout switch (enkeichg: about 1,900 changed cells)
   refills all 30 visible rows in one frame, and the per-tile stage_tile path
   made that frame miss its VBlank (QQ1A x 3652/8965, QQ2A x 3617, QQ2C x
   3606/7164/7179). Here each pair of tiles costs one 16-bit block load and
   one 32-bit table load; the flip/palette/priority bits (tile>>11) come from
   scd_background_pnd_high; the layout byte is read once per 256-pixel chunk,
   whose 32 tiles never straddle the 64-tile ring. Out of line so the loop
   keeps its values in registers. */
static const uint32_t scd_background_pnd_high[32]={
#define SCD_PND_HIGH(t) (((uint32_t)((t)&16)<<25|(uint32_t)((t)&2)<<30|(uint32_t)((t)&1)<<30|(uint32_t)((t)>>2&3)<<16)+4096u) /* stage_saturn_pnd_inline((t)<<11,4096) */
#define SCD_PND_HIGH4(t) SCD_PND_HIGH(t),SCD_PND_HIGH(t+1),SCD_PND_HIGH(t+2),SCD_PND_HIGH(t+3)
    SCD_PND_HIGH4(0),SCD_PND_HIGH4(4),SCD_PND_HIGH4(8),SCD_PND_HIGH4(12),
    SCD_PND_HIGH4(16),SCD_PND_HIGH4(20),SCD_PND_HIGH4(24),SCD_PND_HIGH4(28)
#undef SCD_PND_HIGH4
#undef SCD_PND_HIGH
};
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((optimize("O2")))
#endif
static __attribute__((noinline)) void scd_background_fill_row(const stage_t *stage,uint32_t *out,int y,int wx,int end,int fixed){
    const uint32_t *high=scd_background_pnd_high;
    const uint8_t *layout=stage->part[4]+(y>>8)*64;
    const uint8_t *table=stage->part[1];
    unsigned ty=((unsigned)y>>3&1)*4; /* a vertical flip XORs it */
    unsigned chunks=stage->size[2]/512,blocks=stage->size[1]/8,tiles=stage->size[0]/32;
    unsigned block_row=((unsigned)y>>4&15)*32;
    const uint32_t empty=high[0]; /* stage_saturn_pnd_inline(0,4096) */
    while(wx<end){
        int stop=(wx|31)+1;if(stop>end)stop=end;
        unsigned chunk=layout[(fixed?wx&63:wx)>>5]&127; /* fixed rows: x=(wx*8)&511 */
        if(!chunk||chunk>chunks){for(;wx<stop;wx++)out[wx&63]=empty;continue;}
        if(wx&1){out[wx&63]=stage_saturn_pnd_inline(stage_tile(stage,1,fixed?(wx*8)&511:wx*8,y),4096);wx++;}
        const uint8_t *cell=stage->part[2]+(chunk-1)*512+block_row+(wx&30);
        uint32_t *o=out+(wx&63);
        for(int n=(stop-wx)>>1;n>0;n--,cell+=2,o+=2){
            unsigned block=scd_background_be16(cell),index=block&1023;
            uint32_t a=empty,b=empty;
            if(index<blocks){
                uint32_t pair=scd_background_be32(table+(((index*8)|ty)^(block>>10&4)))^((block&0x1800u)*0x10001u);
                unsigned t0=pair>>16&2047u,t1=pair&2047u;
                if(t0<tiles)a=high[pair>>27]+t0;
                if(t1<tiles)b=high[pair>>11&31]+t1;
                if(block&0x800){uint32_t t=a;a=b;b=t;}
            }
            o[0]=a;o[1]=b;
        }
        wx+=((stop-wx)>>1)*2;
        if(wx<stop){out[wx&63]=stage_saturn_pnd_inline(stage_tile(stage,1,fixed?(wx*8)&511:wx*8,y),4096);wx++;}
    }
}
/* The full QQ mapwrtb redraw may divide independent rows between both SH-2s.
   Keep the eligibility test and fill operation explicit: callers that run a
   fill asynchronously must publish their cache keys only after it completes. */
static inline int scd_background_fill_row_fast_eligible(const stage_t *stage,int row,int first,int end,int fixed){
    int y=stage->wrap_y?(row*8)&2047:row*8;
    return (fixed || (first>=0 && end<=2048)) && y>=0 && y<2048 &&
        !((uintptr_t)stage->part[1]&3) && !((uintptr_t)stage->part[2]&1);
}
static inline void scd_background_fill_row_fast(const stage_t *stage,uint32_t *out,int row,int first,int end,int fixed){
    int y=stage->wrap_y?(row*8)&2047:row*8;
    scd_background_fill_row(stage,out,y,first,end,fixed);
}
static inline unsigned scd_background_cache_row_periodic(const stage_t *stage,
    uint32_t *map, int *world_rows, int *starts, int row, int sx, int fixed, const uint8_t *periodic)
{
    unsigned slot=(unsigned)row&63;
    int first=sx,end=sx+64,old=starts[slot];
    if(world_rows[slot]==row){
        if(sx==old)return 0;
        if(periodic && row>=0 && row<SCD_BACKGROUND_PERIODIC_ROWS && !fixed &&
           sx>=0 && old>=0 && sx+64<=periodic[row] && old+64<=periodic[row]){starts[slot]=sx;return 0;}
        if(sx>old && sx<old+64)first=old+64;
        else if(sx<old && sx+64>old)end=old;
    }
    int wx=first;
    if(scd_background_fill_row_fast_eligible(stage,row,first,end,fixed)){
        scd_background_fill_row_fast(stage,map+slot*64,row,first,end,fixed);
        world_rows[slot]=row;starts[slot]=sx;
        return (unsigned)(end-first);
    }
    if(wx<end&&(wx&1)){
        map[slot*64+((unsigned)wx&63)]=stage_saturn_pnd_inline(
            stage_tile(stage,1,fixed?(wx*8)&511:wx*8,row*8),4096);wx++;
    }
    for(;wx+1<end;wx+=2){
        uint16_t tiles[2];int x=fixed?(wx*8)&511:wx*8;
        stage_tile_pair(stage,1,x,row*8,tiles);
        map[slot*64+((unsigned)wx&63)]=stage_saturn_pnd_inline(tiles[0],4096);
        map[slot*64+((unsigned)(wx+1)&63)]=stage_saturn_pnd_inline(tiles[1],4096);
    }
    if(wx<end)map[slot*64+((unsigned)wx&63)]=stage_saturn_pnd_inline(
        stage_tile(stage,1,fixed?(wx*8)&511:wx*8,row*8),4096);
    world_rows[slot]=row;starts[slot]=sx;
    return (unsigned)(end-first);
}
static inline unsigned scd_background_cache_row(const stage_t *stage,
    uint32_t *map, int *world_rows, int *starts, int row, int sx, int fixed)
{
    return scd_background_cache_row_periodic(stage,map,world_rows,starts,row,sx,fixed,0);
}
#endif
