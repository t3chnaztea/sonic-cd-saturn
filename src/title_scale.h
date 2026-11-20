#ifndef SCD_TITLE_SCALE_H
#define SCD_TITLE_SCALE_H
#include <assert.h>
#include <stdint.h>
/* VDP2's nearest representable horizontal source step to 256/320. */
#define SCD_TITLE_X_STEP 205
typedef struct {int left;unsigned width,stride,phase;} scd_title_scaled_shape;
static inline int scd_title_scaled_edge(int x){int n=x*256;return n>=0?(n+204)/205:n/205;}
static inline scd_title_scaled_shape scd_title_shape(int x,unsigned tile_width){
    int left=scd_title_scaled_edge(x),right=scd_title_scaled_edge(x+(int)tile_width*8);
    return (scd_title_scaled_shape){left,(unsigned)(right-left),((unsigned)(right-left)+7)&~7u,(unsigned)(left*205-x*256)};
}
/* Convert column-major MD tiles into padded row-major Saturn 4bpp texture data.
   Flip the visible content, never the transparent eight-dot alignment padding. */
static inline unsigned scd_title_expand(uint8_t *texture,const uint8_t *vram,unsigned tile,unsigned width,unsigned height,scd_title_scaled_shape shape){
    assert(width>=1 && width<=4 && height>=1 && height<=4 && shape.stride<=48 && shape.phase<205);
    uint8_t sample[48],row[33];row[32]=0;
    for(unsigned x=0;x<shape.stride;x++){
        unsigned sx=(x*205+shape.phase)>>8;
        sample[x]=x<shape.width?(uint8_t)(tile&0x800?width*8-1-sx:sx):32;
    }
    for(unsigned y=0;y<height*8;y++){
        unsigned sy=tile&0x1000?height*8-1-y:y;
        for(unsigned c=0;c<width;c++){
            unsigned index=((tile&0x7FF)+c*height+(sy>>3))&0x7FF;
            const uint8_t *src=vram+index*32+(sy&7)*4;
            for(unsigned n=0;n<4;n++){row[c*8+n*2]=src[n]>>4;row[c*8+n*2+1]=src[n]&15;}
        }
        for(unsigned x=0;x<shape.stride;x+=2)texture[(y*shape.stride+x)/2]=(uint8_t)((row[sample[x]]<<4)|row[sample[x+1]]);
    }
    return shape.stride*height*4;
}
#endif
