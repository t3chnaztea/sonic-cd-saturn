/* Native translations of Special Stage UFO paths, projection and collision. */
#include "special_ufo.h"
#include "special.h"
#include <string.h>
static uint16_t word(const uint8_t *p){return (uint16_t)((p[0]<<8)|p[1]);}
static uint32_t longword(const uint8_t *p){return ((uint32_t)word(p)<<16)|word(p+2);}
static uint32_t high(uint32_t value,uint16_t h){return (value&65535)|((uint32_t)h<<16);}
/* DIVS overflow leaves the dividend's low word, consumed by EXT/ADD.W. */
static uint16_t quotient(int32_t n,int16_t d){
    if(n==INT32_MIN && d==-1)return (uint16_t)n;
    int32_t q=n/d;return q< -32768 || q>32767?(uint16_t)n:(uint16_t)q;
}
int scd_special_ufo_path_open(scd_special_ufo_path *p,const uint8_t *data,size_t size){
    memset(p,0,sizeof(*p));
    if(!data || size<14 || size>65535 || (size-4)%10 || data[0]>3)return -1;
    for(size_t i=2;i<size-2;i+=10)if(!word(data+i) || word(data+i)>=32768)return -1;
    if(word(data+size-2)<32768)return -1;
    p->data=data;p->size=size;return 0;
}
int scd_special_ufo_follow(scd_special_ufo *u,const scd_special_ufo_path *p){
    if(!p->data || p->size<14 || u->path_offset<2 || (u->path_offset-2)%10 || u->path_offset>p->size-2)return -1;
    unsigned offset=u->path_offset;
    if(word(p->data+offset)&32768)offset=2;
    if(offset+10>p->size || !word(p->data+offset) || word(p->data+offset)>=32768)return -1;
    const uint8_t *n=p->data+offset;uint16_t duration=word(n),x=word(n+2),y=word(n+4);
    int32_t dx=(int16_t)(word(n+6)-x),dy=(int16_t)(word(n+8)-y);
    u->x=high(u->x,x);u->y=high(u->y,y);
    u->x_velocity=(uint32_t)(int32_t)(int16_t)quotient(dx*16,(int16_t)duration)<<12;
    u->y_velocity=(uint32_t)(int32_t)(int16_t)quotient(dy*16,(int16_t)duration)<<12;
    u->path_time=duration;u->path_offset=offset+10;return 0;
}
int scd_special_ufo_move(scd_special_ufo *u,const scd_special_ufo_path *p){
    u->x+=u->x_velocity;u->y+=u->y_velocity;
    u->path_time--;return u->path_time?0:scd_special_ufo_follow(u,p);
}
int scd_special_project(uint16_t sx,uint16_t sy,uint16_t x,uint16_t y,uint16_t z_word,unsigned yaw,uint32_t *sprite_x,uint32_t *sprite_y){
    int32_t dx=(int16_t)(sx-x),dy=(int16_t)(sy-y);
    int32_t ys=scd_special_sine(yaw),yc=scd_special_sine(yaw+128);
    int32_t z=64-((dx*ys)>>8)+((dy*yc)>>8);if(!z)z=1;
    if(!(int16_t)z)return -1;
    int32_t nx=(int16_t)((128*yc)>>8)*dx+(int16_t)((128*ys)>>8)*dy;
    int32_t ny=(128*(int16_t)z_word)>>3;
    *sprite_x=high(*sprite_x,(uint16_t)(quotient(nx,(int16_t)z)+256));
    *sprite_y=high(*sprite_y,(uint16_t)(quotient(ny,(int16_t)z)+256));return 0;
}
int scd_special_ufo_project(scd_special_ufo *u,uint16_t sx,uint16_t sy,unsigned yaw){
    return scd_special_project(sx,sy,u->x>>16,u->y>>16,u->z,yaw,&u->sprite_x,&u->sprite_y);
}
void scd_special_on_screen(uint8_t *flags,uint32_t sprite_x,uint32_t sprite_y){
    *flags&=(uint8_t)~4;
    if((sprite_x>>16)>=512 || (int16_t)(sprite_y>>16)<256 || (int16_t)(sprite_y>>16)>=448)*flags|=4;
}
void scd_special_ufo_on_screen(scd_special_ufo *u){scd_special_on_screen(&u->flags,u->sprite_x,u->sprite_y);}
void scd_special_ufo_collision(scd_special_ufo *u,uint16_t sx,uint16_t sy,uint16_t sz,uint8_t sid,uint8_t *collision){
    if(!sid || *collision)return;
    /* Keep signed comparisons of wrapped boundaries, including edge cases. */
    uint16_t x=u->x>>16,y=u->y>>16;
    if((int16_t)(sx-16)>(int16_t)(x+16) || (int16_t)(sx+16)<(int16_t)(x-16))return;
    if((int16_t)(sy-16)>(int16_t)(y+12) || (int16_t)(sy+16)<(int16_t)(y-12))return;
    if(sz<0x210 || sz>=0x270)return;
    *collision=u->id;u->player_collision=sid;
}
uint32_t scd_special_ufo_distance(uint16_t x,uint16_t y,uint16_t sx,uint16_t sy){
    static const uint16_t table[65]={
        0x00ff,0x0100,0x0100,0x0100,0x0100,0x0100,0x0101,0x0101,0x0101,0x0102,
        0x0103,0x0103,0x0104,0x0105,0x0106,0x0106,0x0107,0x0108,0x0109,0x010b,
        0x010c,0x010d,0x010e,0x0110,0x0111,0x0112,0x0114,0x0115,0x0117,0x0119,
        0x011a,0x011c,0x011e,0x0120,0x0121,0x0123,0x0125,0x0127,0x0129,0x012b,
        0x012d,0x0130,0x0132,0x0134,0x0136,0x0138,0x013b,0x013d,0x0140,0x0142,
        0x0144,0x0147,0x0149,0x014c,0x014e,0x0151,0x0154,0x0156,0x0159,0x015c,
        0x015e,0x0161,0x0164,0x0167,0x016a};
    uint16_t dx=x-sx,dy=y-sy;
    if((int16_t)x<(int16_t)sx)dx=(uint16_t)-dx;
    /* Preserve GetAngle's original negative-Y absolute-value bug. */
    if((int16_t)dy<0 && (int16_t)sy>=0)dy=(uint16_t)-dy;
    unsigned inner=dy>=dx;uint16_t major=inner?dy:dx,minor=inner?dx:dy;
    uint32_t n=(uint32_t)(int32_t)(int16_t)minor<<6;
    uint32_t q=major?n/major:0;if(q>65535)q=n;
    unsigned angle=q&255;if(angle>=64)angle=63;
    uint16_t distance=inner?sy-y:sx-x;if((int16_t)distance<0)distance=(uint16_t)-distance;
    return (uint32_t)table[angle]*distance>>8;
}
unsigned scd_special_ufo_animation(uint32_t d){
    if(d>=0x500)return 9;
    unsigned i=d>>4;return i<2?i:i<4?2:i<8?3:i<16?4:i<32?5:i<48?6:i<64?7:8;
}

int scd_special_ufo_paths_open(scd_special_ufo_paths *paths,const void *data,size_t size){
    memset(paths,0,sizeof(*paths));const uint8_t *p=data;
    if(!p || size<408 || memcmp(p,"UFP1",4) || longword(p+8)!=49 || longword(p+12)!=16)return -1;
    uint32_t length=longword(p+4);if(length>size || length<408)return -1;
    uint32_t end=408;
    for(unsigned i=0;i<49;i++){
        uint32_t offset=longword(p+16+i*8),n=longword(p+20+i*8);scd_special_ufo_path path;
        if(offset!=end || offset>length || n>length-offset || scd_special_ufo_path_open(&path,p+offset,n))return -1;
        end=offset+n;
    }
    if(end!=length)return -1;
    *paths=(scd_special_ufo_paths){p,length};return 0;
}
int scd_special_ufo_path_get(const scd_special_ufo_paths *paths,unsigned index,scd_special_ufo_path *path){
    memset(path,0,sizeof(*path));if(!paths->data || index>=49)return -1;
    unsigned offset=longword(paths->data+16+index*8),n=longword(paths->data+20+index*8);
    if(offset>paths->size || n>paths->size-offset)return -1;
    *path=(scd_special_ufo_path){paths->data+offset,n};return 0;
}
