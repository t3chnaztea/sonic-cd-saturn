#include "sonic_art.h"
#include <string.h>
static unsigned word(const uint8_t *p){return (unsigned)p[0]<<8|p[1];}
static uint32_t longword(const uint8_t *p){return (uint32_t)word(p)<<16|word(p+2);}
int scd_sonic_art_open(scd_sonic_art *out,const uint8_t *data,size_t size){
    if(size<40 || memcmp(data,"SON1",4) || longword(data+4)!=4)return -1;
    scd_sonic_art s;
    for(unsigned i=0;i<4;i++){
        uint32_t offset=longword(data+8+i*8),length=longword(data+12+i*8);
        if(offset<40 || offset>size || length>size-offset)return -1;
        s.part[i]=data+offset;s.size[i]=length;
    }
    if(s.size[1]<SCD_SONIC_FRAME_COUNT*2 || s.size[2]<SCD_SONIC_FRAME_COUNT*2 || s.size[3]!=32)return -1;
    *out=s;return 0;
}
int scd_sonic_art_decode(const scd_sonic_art *art,unsigned frame,uint16_t pixels[1024]){
    if(frame>=SCD_SONIC_FRAME_COUNT)return -1;
    unsigned mo=word(art->part[1]+frame*2),dp=word(art->part[2]+frame*2);
    if(mo<SCD_SONIC_FRAME_COUNT*2 || mo>=art->size[1] || dp<SCD_SONIC_FRAME_COUNT*2 || dp+2>art->size[2])return -1;
    const uint8_t *mapping=art->part[1]+mo,*dplc=art->part[2]+dp;
    unsigned pieces=mapping[0],loads=word(dplc),tiles=0;
    if(mo+1+pieces*5>art->size[1] || dp+2+loads*2>art->size[2])return -1;
    const uint8_t *tile[64];
    for(unsigned i=0;i<loads;i++){
        unsigned w=word(dplc+2+i*2),count=(w>>12)+1,first=w&4095;
        if(tiles+count>64 || (first+count)*32>art->size[0])return -1;
        for(unsigned j=0;j<count;j++)tile[tiles++]=art->part[0]+(first+j)*32;
    }
    /* Validate all pieces before touching the output texture. */
    for(unsigned i=0;i<pieces;i++){
        const uint8_t *p=mapping+1+i*5;unsigned w=word(p+2);
        unsigned width=((p[1]>>2)&3)+1,height=(p[1]&3)+1;
        int x=(int8_t)p[4],y=(int8_t)p[0];
        if((w&2047)+width*height>tiles || x< -32 || y< -32 || x+(int)width*8>32 || y+(int)height*8>32)return -1;
    }
    memset(pixels,0,2048);
    for(unsigned i=0;i<pieces;i++){
        const uint8_t *p=mapping+1+i*5;unsigned w=word(p+2);
        unsigned width=(((p[1]>>2)&3)+1)*8,height=((p[1]&3)+1)*8;
        int x=32+(int8_t)p[4],y=32+(int8_t)p[0];
        for(unsigned py=0;py<height;py++)for(unsigned px=0;px<width;px++){
            unsigned sx=w&2048?width-1-px:px,sy=w&4096?height-1-py:py;
            const uint8_t *source=tile[(w&2047)+(sx/8)*(height/8)+sy/8];
            unsigned b=source[(sy&7)*4+(sx&7)/2],color=sx&1?b&15:b>>4;
            unsigned dx=(unsigned)x+px,dy=(unsigned)y+py,shift=(3-(dx&3))*4,index=dy*16+dx/4;
            /* Mega Drive earlier sprite pieces win if mappings overlap. */
            if(color && !(pixels[index]&(15u<<shift)))pixels[index]|=(uint16_t)(color<<shift);
        }
    }
    return 0;
}
uint16_t scd_sonic_art_color(const scd_sonic_art *art,unsigned index){
    if(!index || index>=16)return 0;
    unsigned c=word(art->part[3]+index*2);
    return (uint16_t)(0x8000|(((c>>1)&7)*31/7)|((((c>>5)&7)*31/7)<<5)|((((c>>9)&7)*31/7)<<10));
}
