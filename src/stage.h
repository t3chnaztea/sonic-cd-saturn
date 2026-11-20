#ifndef STAGE_H
#define STAGE_H
#include <stddef.h>
#include <stdint.h>
typedef struct {
    const uint8_t *part[6];
    uint32_t size[6];
    uint16_t start_x, start_y;
    /* Tidal Tempest Acts 2/3: the map repeats every 2048 lines (FCOL.C scramapad
       (y>>8)&7), so tile lookups wrap Y instead of reading past the bottom. */
    uint8_t wrap_y;
} stage_t;
int stage_open(stage_t *stage, const uint8_t *data, size_t size);
uint16_t stage_tile(const stage_t *stage, int background, int x, int y);
void stage_tile_pair(const stage_t *stage, int background, int x, int y, uint16_t out[2]);
static inline __attribute__((always_inline)) uint32_t stage_saturn_pnd_inline(uint16_t tile,uint32_t character_base){
    return (((uint32_t)tile&0x8000)<<14)|(((uint32_t)tile&0x1000)<<19)|(((uint32_t)tile&0x0800)<<19)|
        (((uint32_t)tile>>13&3)<<16)|(character_base+(tile&2047));
}
uint32_t stage_saturn_pnd(uint16_t tile, uint32_t character_base);
#endif
