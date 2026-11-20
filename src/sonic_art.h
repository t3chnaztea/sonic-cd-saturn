#ifndef SCD_SONIC_ART_H
#define SCD_SONIC_ART_H
#include <stddef.h>
#include <stdint.h>
#define SCD_SONIC_FRAME_COUNT 198
typedef struct {const uint8_t *part[4];uint32_t size[4];} scd_sonic_art;
int scd_sonic_art_open(scd_sonic_art *out,const uint8_t *data,size_t size);
/* Decode one original DPLC/mapping pose to a 64x64 packed 4bpp texture, four
   pixels per host word, high nibble first. Global flips belong to the sprite
   command, not this texture. Returns -1 for malformed input. */
int scd_sonic_art_decode(const scd_sonic_art *art,unsigned frame,uint16_t pixels[1024]);
uint16_t scd_sonic_art_color(const scd_sonic_art *art,unsigned index);
#endif
