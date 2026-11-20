#include <stdio.h>
#include <string.h>
#include "title_scale.h"
static uint8_t vram[65536];
static int floor256(int n){return n>=0?n/256:-((-n+255)/256);}
int main(void){
    unsigned cases=0;uint8_t texture[48*32/2+8];uint32_t random=42;
    for(unsigned i=0;i<sizeof(vram);i++){random=random*1664525u+1013904223u;vram[i]=random>>24;}
    for(int origin=-128;origin<384;origin++)for(unsigned w=1;w<=4;w++)for(unsigned h=1;h<=4;h++)for(unsigned flip=0;flip<4;flip++){
        scd_title_scaled_shape shape=scd_title_shape(origin,w);
        unsigned tile=0x7fbu|(flip<<11);
        memset(texture,0xa5,sizeof(texture));unsigned bytes=scd_title_expand(texture,vram,tile,w,h,shape);
        assert(bytes<=48*32/2 && shape.stride%8==0);
        assert(floor256((shape.left-1)*205)<origin);
        assert(floor256((shape.left+(int)shape.width)*205)>=origin+(int)w*8);
        for(unsigned y=0;y<h*8;y++)for(unsigned x=0;x<shape.stride;x++){
            unsigned expected=0;
            if(x<shape.width){
                int sx=floor256((shape.left+(int)x)*205)-origin;unsigned sy=y;
                assert(sx>=0 && sx<(int)w*8);
                if(flip&1)sx=w*8-1-sx;if(flip&2)sy=h*8-1-y;
                unsigned address=(((tile&0x7ff)+(unsigned)sx/8*h+sy/8)&0x7ff)*32+(sy%8)*4+(unsigned)sx%8/2;
                expected=(vram[address]>>((sx&1)?0:4))&15;
            }
            unsigned actual=(texture[(y*shape.stride+x)/2]>>(x&1?0:4))&15;
            assert(actual==expected);
        }
        for(unsigned i=bytes;i<sizeof(texture);i++)assert(texture[i]==0xa5);
        cases++;
    }
    printf("Title scale: %u origins/sizes/flips passed, including padding and tile wrap\n",cases);
}
