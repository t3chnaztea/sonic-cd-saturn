#ifndef SCD_SOUND_BUS_H
#define SCD_SOUND_BUS_H
#include <stdint.h>
#include <stddef.h>
/* The SCSP main interface is word-wide (ST-077, 3.1). These helpers never
   issue byte transactions to sound RAM, including unaligned PCM boundaries. */
static inline void scd_sound_copy(volatile uint16_t *ram,size_t offset,const uint8_t *src,size_t bytes){
    if((offset&1) && bytes){
        uint16_t old=ram[offset/2];ram[offset/2]=(uint16_t)((old&0xff00)|*src++);
        offset++;bytes--;
    }
    while(bytes>=2){ram[offset/2]=(uint16_t)((uint16_t)src[0]<<8|src[1]);src+=2;offset+=2;bytes-=2;}
    if(bytes){uint16_t old=ram[offset/2];ram[offset/2]=(uint16_t)((uint16_t)*src<<8|(old&255));}
}
static inline uint32_t scd_sound_hash(const volatile uint16_t *ram,size_t bytes){
    uint32_t hash=2166136261u;
    for(size_t i=0;i<bytes;i+=2){uint16_t word=ram[i/2];hash=(hash^(word>>8))*16777619u;if(i+1<bytes)hash=(hash^(word&255))*16777619u;}
    return hash;
}
#endif
