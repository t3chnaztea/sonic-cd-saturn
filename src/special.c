/* Original Special Stage/Sub.asm projection and non-repeating 32x32 stamp
   sampling. This code is native SH-2 C; emulators are used only by QA. */
#include "special.h"
#include <string.h>
#include "special-sine.inc"
static unsigned word(const uint8_t *p){return (p[0]<<8)|p[1];}
static uint32_t longword(const uint8_t *p){return ((uint32_t)word(p)<<16)|word(p+2);}
int scd_special_open(scd_special_stage *s,const uint8_t *data,size_t size){
    memset(s,0,sizeof(*s));if(!data || size<72 || memcmp(data,"SSP1",4))return -1;
    unsigned stage=longword(data+4),count=longword(data+8),length=longword(data+12);
    if(stage<1 || stage>8 || count!=7 || length>size || length<72)return -1;
    unsigned end=72;
    for(unsigned i=0;i<7;i++){
        unsigned offset=longword(data+16+8*i),n=longword(data+20+8*i);
        if((offset&3) || offset<end || offset>length || n>length-offset)return -1;
        s->part[i]=data+offset;s->size[i]=n;end=offset+n;
    }
    if(end!=length || s->size[0]<512 || s->size[0]>0x1c000 || (s->size[0]&511) || s->size[1]!=32768 || s->size[2]>512 || !s->size[2] || s->size[3]!=64 || s->size[4]!=6)return -1;
    for(unsigned i=0;i<16384;i++){
        unsigned raw=word(s->part[1]+i*2),index=(raw&2047)>>2;
        if(raw!=65535 && (index>=s->size[0]/512 || index>=s->size[2]))return -1;
    }
    for(unsigned part=5;part<7;part++){
        unsigned stride=part==5?10:8;
        if(!s->size[part] || s->size[part]%stride)return -1;
        for(unsigned row=0;row<s->size[part];row+=stride){
            unsigned offset=word(s->part[part]+row);
            if((offset&1) || offset>=32768)return -1;
            for(unsigned frame=2;frame<stride;frame+=2){
                unsigned raw=word(s->part[part]+row+frame),index=(raw&2044)>>2;
                if(raw!=65535 && (index>=s->size[0]/512 || index>=s->size[2]))return -1;
            }
        }
    }
    s->stage=stage;return 0;
}
int scd_special_sine(unsigned angle){
    unsigned i=angle&127;if(angle&128)i^=127;
    return angle&256?-special_sines[i]:special_sines[i];
}
/* m68k MULS consumes signed low words, even when the previous operation
   left a long result. DIVS truncates toward zero; preserve word wrapping. */
static int32_t muls(int32_t a,int32_t b){return (int32_t)(int16_t)a*(int16_t)b;}
static int divide(int32_t value,int32_t divisor,int16_t *result){
    int16_t d=(int16_t)divisor;if(!d)return -1;
    /* DIVS overflow leaves the destination unchanged on the original 68000.
       The following ADD.W reads its low word, including at high jump heights. */
    if(value==INT32_MIN && d==-1){*result=(int16_t)value;return 0;}
    int32_t q=value/d;*result=(q< -32768 || q>32767)?(int16_t)value:(int16_t)q;return 0;
}
int scd_special_trace(scd_special_line lines[96],scd_special_camera c){
    int ps=scd_special_sine(c.pitch),pc=scd_special_sine(c.pitch+128);
    int ys=scd_special_sine(c.yaw),yc=scd_special_sine(c.yaw+128);
    int16_t pcys=muls(pc,ys)>>5,pcyc=muls(pc,yc)>>5;
    int32_t psys=muls(muls(128,ps),ys)>>5,psyc=muls(muls(128,ps),yc)>>5;
    int32_t pcfov=muls(128,pc);
    int16_t centerx=muls(muls(ps,ys)>>5,64)>>8,centery=muls(muls(ps,yc)>>5,64)>>8;
    for(unsigned row=0;row<3;row++)lines[row]=(scd_special_line){0,65528,0,0};
    for(unsigned row=3;row<96;row++){
        int line=-(int)row;int32_t z=(muls(line,ps)+pcfov)>>5;if(!z)z=1;
        int16_t points[4];
        for(unsigned endpoint=0;endpoint<2;endpoint++){
            int x=endpoint?127:-128;
            int32_t nx=((muls(x,yc)*8-muls(pcys,line)+psys)>>8);
            int32_t ny=((muls(x,ys)*8+muls(pcyc,line)-psyc)>>8);
            int16_t qx,qy;if(divide(muls(nx,c.z),z,&qx) || divide(muls(ny,c.z),z,&qy))return -1;
            points[endpoint*2]=(uint16_t)qx+(uint16_t)c.x*8-centerx;
            points[endpoint*2+1]=(uint16_t)qy+(uint16_t)c.y*8+centery;
        }
        lines[row]=(scd_special_line){(uint16_t)points[0],(uint16_t)points[1],(int16_t)(points[2]-points[0]),(int16_t)(points[3]-points[1])};
    }
    return 0;
}
static unsigned stamp(const scd_special_stage *s,int x,int y){
    return word(s->part[1]+((unsigned)(y>>5)*128+(unsigned)(x>>5))*2);
}
int scd_special_stamp_type(const scd_special_stage *s,int x,int y,unsigned *orientation){
    if((unsigned)x>=4096 || (unsigned)y>=4096)return -1;
    unsigned raw=stamp(s,x,y);if(raw==65535)return -1;
    if(orientation)*orientation=raw>>13;
    return s->part[2][(raw&2047)>>2];
}
static unsigned stamp_pixel(const scd_special_stage *s,unsigned raw,unsigned px,unsigned py){
    unsigned index=(raw&2044)>>2;
    if(!index || raw==65535)return 0;
    unsigned flags=raw>>13;
    if(flags&4)px^=31;
    if(flags&2){px^=31;py^=31;}
    if(flags&1){unsigned old=px;px=py^31;py=old;}
    unsigned offset=index*512+((px>>3)*4+(py>>3))*32+(py&7)*4+((px&7)>>1);
    unsigned pair=s->part[0][offset];return (pair>>((px&1)?0:4))&15;
}
unsigned scd_special_pixel(const scd_special_stage *s,int x,int y){
    if((unsigned)x>=4096 || (unsigned)y>=4096)return 0;
    return stamp_pixel(s,stamp(s,x,y),x&31,y&31);
}

void scd_special_render(const scd_special_stage *s,const scd_special_line lines[96],uint8_t *pixels,unsigned stride){
    for(unsigned y=0;y<96;y++){
        uint32_t x=(uint32_t)lines[y].x<<8,v=(uint32_t)lines[y].y<<8;
        for(unsigned n=0;n<256;n++){
            x&=0xffffff;v&=0xffffff;
            pixels[y*stride+n]=scd_special_pixel(s,x>>11,v>>11);
            x+=lines[y].dx;v+=lines[y].dy;
        }
    }
}
static unsigned cache_key(unsigned raw){return ((raw>>13)<<9)|((raw&2044)>>2);}
static unsigned cache_stamp(const scd_special_stage *s,uint8_t *cache,unsigned raw,unsigned used,size_t capacity){
    if(raw==65535 || !(raw&2044))return used;
    uint16_t *lookup=(uint16_t *)(cache+0x8000);unsigned key=cache_key(raw);
    if(lookup[key])return used;
    if(used>capacity || capacity-used<1024)return 0;
    lookup[key]=used/1024;
    for(unsigned y=0;y<32;y++)for(unsigned x=0;x<32;x++)cache[used+y*32+x]=stamp_pixel(s,raw,x,y);
    return used+1024;
}
size_t scd_special_cache(const scd_special_stage *s,void *buffer,size_t capacity){
    if(!buffer || ((uintptr_t)buffer&3) || capacity<0xa400)return 0;
    uint8_t *cache=buffer;uint16_t *map=buffer;uint16_t *lookup=(uint16_t *)(cache+0x8000);
    memset(lookup,0,8192+1024);unsigned used=0xa400;
    for(unsigned cell=0;cell<16384;cell++){
        unsigned raw=word(s->part[1]+cell*2);
        used=cache_stamp(s,cache,raw,used,capacity);if(!used)return 0;
        map[cell]=(raw==65535 || !(raw&2044))?0x28:lookup[cache_key(raw)];
    }
    /* Animation can introduce stamps absent from the initial map. Prepare
       their original orientations now, while both rendering CPUs are idle. */
    for(unsigned part=5;part<7;part++){
        unsigned stride=part==5?10:8;
        for(unsigned row=0;row<s->size[part];row+=stride)for(unsigned frame=2;frame<stride;frame+=2){
            used=cache_stamp(s,cache,word(s->part[part]+row+frame),used,capacity);if(!used)return 0;
        }
    }
    return used;
}
unsigned scd_special_animate(const scd_special_stage *s,scd_special_animation *a,uint8_t *raw_map,const void *cache,uint16_t *map){
    const uint16_t *lookup=(const uint16_t *)((const uint8_t *)cache+0x8000);unsigned writes=0;
    a->fan+=2;if(a->fan>=6)a->fan=0;
    a->delay++;if(!(a->delay&1))a->hazard=(a->hazard+2)&7;
    for(unsigned part=5;part<7;part++){
        if(part==5 && (a->delay&1))continue;
        unsigned stride=part==5?10:8,frame=part==5?a->hazard:a->fan;
        for(unsigned row=0;row<s->size[part];row+=stride){
            const uint8_t *p=s->part[part]+row;unsigned offset=word(p),raw=word(p+2+frame);
            raw_map[offset]=raw>>8;raw_map[offset+1]=raw;
            map[offset/2]=(raw==65535 || !(raw&2044))?0x28:lookup[cache_key(raw)];writes++;
        }
    }
    return writes;
}

#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC push_options
#pragma GCC optimize ("O3")
#endif
/* Number of samples before a signed 5.11 step leaves this 32-pixel
   stamp. Check the end of a run first to avoid division on constant axes. */
static inline unsigned stamp_run(uint32_t coordinate,int delta,unsigned reciprocal,unsigned count,unsigned mask){
    if(!delta)return count;
    unsigned step=delta<0?-delta:delta;
    unsigned distance=delta<0?(coordinate&mask):mask-(coordinate&mask);
    if(step*(count-1)<=distance)return count;
    /* floor((2^32-1)/step) gives either the exact quotient or one less
       for a numerator below 2^32. One multiply/subtract repairs it exactly. */
    unsigned quotient=((uint64_t)distance*reciprocal)>>32;
    if(distance-quotient*step>=step)quotient++;
    return quotient+1;
}
/* floor((2^32-1)/|step|) of both steps, two words per row (0 for a zero step). */
void scd_special_reciprocals(const scd_special_line *lines,unsigned rows,uint32_t *reciprocals){
    for(unsigned row=0;row<rows;row++){
        int dx=lines[row].dx,dy=lines[row].dy;
        reciprocals[row*2]=dx?UINT32_MAX/(unsigned)(dx<0?-dx:dx):0;
        reciprocals[row*2+1]=dy?UINT32_MAX/(unsigned)(dy<0?-dy:dy):0;
    }
}
/* Samples first..first+count-1 of each row; pixels holds sample first of the
   first row. Every sample depends only on its own coordinate, so a span
   writes the same bytes as the full row does there. reciprocals holds
   scd_special_reciprocals of these rows, or NULL to compute them here. */
void scd_special_render_span(const void *buffer,const uint16_t *map,const scd_special_line *lines,const uint32_t *reciprocals,uint8_t *pixels,unsigned stride,unsigned rows,unsigned first,unsigned count){
    const uint8_t *cache=buffer;
    for(unsigned row=0;row<rows;row++){
        int dx=lines[row].dx,dy=lines[row].dy;unsigned n=0;
        uint32_t x=((uint32_t)lines[row].x<<8)+(uint32_t)dx*first,y=((uint32_t)lines[row].y<<8)+(uint32_t)dy*first;
        /* A step of 0x3000 or more leaves a stamp within six samples; the
           run setup then costs more than sampling each pixel directly
           (stamp 0x28 of the cache is transparent, as outside the world). */
        if((unsigned)(dx<0?-dx:dx)>=0x3000 || (unsigned)(dy<0?-dy:dy)>=0x3000){
            for(;n<count;n++){
                unsigned texture=((x|y)&0x800000)?0x28:map[((y>>9)&0x3f80)|((x>>16)&127)];
                pixels[n]=cache[texture*1024+(((y>>11)&31)<<5)+((x>>11)&31)];
                x+=dx;y+=dy;
            }
            pixels+=stride;continue;
        }
        uint32_t du=(uint32_t)dx*32,dv=(uint32_t)dy*1024;
        unsigned rx,ry;
        if(reciprocals){rx=reciprocals[row*2];ry=reciprocals[row*2+1];}
        else{rx=dx?UINT32_MAX/(unsigned)(dx<0?-dx:dx):0;ry=dy?UINT32_MAX/(unsigned)(dy<0?-dy:dy):0;}
        while(n<count){
            /* Outside the non-repeating world, no stamp lookup is needed
               until this coordinate crosses a 4096-pixel world boundary. */
            if((x|y)&0x800000){
                unsigned run=(x&0x800000)?stamp_run(x,dx,rx,count-n,0x7fffff):stamp_run(y,dy,ry,count-n,0x7fffff);
                memset(pixels+n,0,run);x+=dx*run;y+=dy*run;n+=run;continue;
            }
            unsigned run=stamp_run(x,dx,rx,count-n,65535);run=stamp_run(y,dy,ry,run,65535);
            unsigned texture=map[((y>>9)&0x3f80)|((x>>16)&127)];
            if(texture==0x28){
                memset(pixels+n,0,run);x+=dx*run;y+=dy*run;n+=run;
            }else{
                const uint8_t *stamp_pixels=cache+texture*1024;
                /* Only local stamp bits are needed inside this bounded run.
                   Put both fields above bit 16 so SH-2 extracts them with
                   one instruction; full 24-bit world stepping stays outside. */
                unsigned end=n+run;uint32_t u=x<<5,v=y<<10;
                x+=dx*run;y+=dy*run;
                do{
                    pixels[n++]=stamp_pixels[((v>>16)&992)|((u>>16)&31)];
                    u+=du;v+=dv;
                }while(n<end);
            }
        }
        pixels+=stride;
    }
}
void scd_special_render_rows(const void *buffer,const uint16_t *map,const scd_special_line *lines,uint8_t *pixels,unsigned stride,unsigned rows){
    scd_special_render_span(buffer,map,lines,NULL,pixels,stride,rows,0,256);
}
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC pop_options
#endif

void scd_special_render_cached(const void *cache,const scd_special_line lines[96],uint8_t *pixels,unsigned stride){
    scd_special_render_cached_map(cache,cache,lines,pixels,stride);
}

void scd_special_render_cached_map(const void *cache,const uint16_t *map,const scd_special_line lines[96],uint8_t *pixels,unsigned stride){
    scd_special_render_rows(cache,map,lines,pixels,stride,96);
}
