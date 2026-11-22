#include "stage.h"
#include <string.h>
static uint16_t be16(const uint8_t *p) { return ((uint16_t)p[0] << 8) | p[1]; }
static uint32_t be32(const uint8_t *p) { return ((uint32_t)be16(p) << 16) | be16(p+2); }
int stage_open(stage_t *s, const uint8_t *data, size_t size) {
    if (size < 56 || memcmp(data, "PPZ1", 4)) return -1;
    for (unsigned i=0;i<6;i++) {
        uint32_t offset=be32(data+4+i*8), length=be32(data+8+i*8);
        if (offset<56 || offset>size || length>size-offset) return -1;
        s->part[i]=data+offset; s->size[i]=length;
    }
    if (s->size[3]!=512 || s->size[4]!=512 || s->size[5]!=128 ||
        s->size[0]%32 || s->size[1]%8 || s->size[2]%512) return -1;
    s->start_x=be16(data+52); s->start_y=be16(data+54);
    s->wrap_y=0;
    return 0;
}
uint16_t stage_tile(const stage_t *s, int background, int x, int y) {
    if (s->wrap_y) y&=2047;
    if (x<0 || y<0 || x>=16384 || y>=2048) return 0;
    unsigned chunk=s->part[background?4:3][(y>>8)*64+(x>>8)] & 127;
    if (!chunk || chunk*512>s->size[2]) return 0;
    unsigned address=(chunk-1)*512 + ((y>>4)&15)*32 + ((x>>4)&15)*2;
    uint16_t block=be16(s->part[2]+address);
    unsigned index=block&1023;
    if (index*8+8>s->size[1]) return 0;
    unsigned tx=(x>>3)&1, ty=(y>>3)&1;
    if (block&0x800) tx^=1;
    if (block&0x1000) ty^=1;
    uint16_t tile=be16(s->part[1]+index*8+ty*4+tx*2);
    tile ^= block & 0x1800;
    if ((uint32_t)(tile&2047)*32+32>s->size[0]) return 0;
    return tile;
}
void stage_tile_pair(const stage_t *s, int background, int x, int y, uint16_t out[2]) {
    out[0]=out[1]=0;
    if (s->wrap_y) y&=2047;
    if (x<0 || y<0 || x+8>=16384 || y>=2048 || (x&15)) return;
    unsigned chunk=s->part[background?4:3][(y>>8)*64+(x>>8)]&127;
    if (!chunk || chunk*512>s->size[2]) return;
    unsigned address=(chunk-1)*512+((y>>4)&15)*32+((x>>4)&15)*2;
    uint16_t block=be16(s->part[2]+address);
    unsigned index=block&1023;
    if (index*8+8>s->size[1]) return;
    unsigned ty=(y>>3)&1;
    if (block&0x1000) ty^=1;
    for(unsigned n=0;n<2;n++) {
        unsigned tx=n;
        if (block&0x800) tx^=1;
        uint16_t tile=be16(s->part[1]+index*8+ty*4+tx*2);
        tile^=block&0x1800;
        if ((uint32_t)(tile&2047)*32+32<=s->size[0]) out[n]=tile;
    }
}
uint32_t stage_saturn_pnd(uint16_t tile, uint32_t character_base) {
    return stage_saturn_pnd_inline(tile,character_base);
}
