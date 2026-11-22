#ifndef SCD_FOREGROUND_CACHE_H
#define SCD_FOREGROUND_CACHE_H
#include "stage.h"

/* Update the exposed edges of the 42x30 tile viewport. The old renderer
   scanned all 1260 cells to discover these edges. Preserve its writes and
   all offscreen ring-map cells, including after teleports and reversals. */
static inline unsigned scd_foreground_cache(const stage_t *stage,uint32_t *map,
    int tx,int ty,int old_x,int old_y)
{
    if(tx==old_x && ty==old_y)return 0;
    unsigned written=0;
    for(int wy=ty;wy<ty+30;wy++){
        int first=tx,end=tx+42;
        if(wy>=old_y && wy<old_y+30){
            if(tx==old_x)continue;
            if(tx>old_x && tx<old_x+42)first=old_x+42;
            else if(tx<old_x && tx+42>old_x)end=old_x;
        }
        /* Decode 16-pixel blocks once per tile pair, as the BG cache does:
           fast diagonal travel exposes whole rows every frame. */
        uint32_t *line=map+((unsigned)wy&63)*64;int wx=first;
        if(wx<end&&(wx&1)){line[(unsigned)wx&63]=stage_saturn_pnd_inline(stage_tile(stage,0,wx*8,wy*8),0);wx++;}
        for(;wx+1<end;wx+=2){
            uint16_t tiles[2];stage_tile_pair(stage,0,wx*8,wy*8,tiles);
            line[(unsigned)wx&63]=stage_saturn_pnd_inline(tiles[0],0);
            line[(unsigned)(wx+1)&63]=stage_saturn_pnd_inline(tiles[1],0);
        }
        if(wx<end)line[(unsigned)wx&63]=stage_saturn_pnd_inline(stage_tile(stage,0,wx*8,wy*8),0);
        if(end>first)written+=(unsigned)(end-first);
    }
    return written;
}
#endif
