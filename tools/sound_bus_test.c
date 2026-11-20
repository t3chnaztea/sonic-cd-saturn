#include "sound_bus.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    uint8_t source[33];for(unsigned i=0;i<33;i++)source[i]=(uint8_t)(i*37+11);
    for(unsigned offset=0;offset<8;offset++)for(unsigned length=0;length<=33;length++){
        uint16_t ram[24];for(unsigned i=0;i<24;i++)ram[i]=0xa55a;
        scd_sound_copy(ram,offset,source,length);
        uint32_t hash=2166136261u;
        for(unsigned i=0;i<48;i++){
            unsigned actual=(ram[i/2]>>(i&1?0:8))&255;
            unsigned expected=i>=offset && i<offset+length?source[i-offset]:(i&1?0x5a:0xa5);
            assert(actual==expected);hash=(hash^expected)*16777619u;
            assert(scd_sound_hash(ram,i+1)==hash);
        }
    }
    puts("SCSP word-bus copy/hash: 272 alignment/length cases passed");
}
