#ifndef SCD_ZONE_OBJECT_ART_H
#define SCD_ZONE_OBJECT_ART_H
#include <stdint.h>
#include <stddef.h>

/* Gameplay object atlas in VDP1 VRAM: straight after the high Sonic LUT
   (src/sonic_view.inc, 0x1AAA0-0x1AABF), up to the zone art arena. */
#define OBJECT_ATLAS_BASE 0x1AAC0u
#define SCD_ZONE_ART_BASE 0x71000u
#define SCD_ZONE_ART_CAPACITY (0x80000u-SCD_ZONE_ART_BASE)
#define SCD_ZONE_ART_RECORD 48u
#define SCD_ZONE_ART_MAX_FRAMES 512u /* part records count; the lookup indexes first parts only */
/* ZART: per-era records + packed textures. ZAR2: per-era records over one
   packed arena shared by all eras. ZAR3: ZART whose textures use the word-LZ
   codec of tools/zone_art_lz.py (lz=1); composited poses repeat piece rows.
   ZAR4: ZAR2's shared arena packed with the ZAR3 codec (Metallic Madness).
   ZAR5: ZAR2 whose arena exceeds the VDP1 region: each era blob is count,
   era raw bytes, span count, records at era-local offsets, then spans (u16
   arena word, u16 words) in arena order; the loader keeps only those words
   (tools/zone_object_assets.py zar5_layout). */
typedef struct {
    const uint8_t *frames,*packed;
    unsigned count,raw_bytes,packed_bytes;
    unsigned lz;
    /* ZAR5: the era's arena spans and the whole arena's word count. */
    const uint8_t *spans;unsigned span_count,arena_words;
} scd_zone_art;
static inline unsigned scd_zone_art_u16(const uint8_t *p){return (unsigned)p[0]*256+p[1];}
static inline uint32_t scd_zone_art_u32(const uint8_t *p){return (uint32_t)scd_zone_art_u16(p)*65536+scd_zone_art_u16(p+2);}
static inline int scd_zone_art_i16(const uint8_t *p){return (int16_t)scd_zone_art_u16(p);}
static inline unsigned scd_zone_art_bitmap(const uint8_t *f){return scd_zone_art_u32(f+4)&65535u;}
static inline unsigned scd_zone_art_clut(const uint8_t *f){
    unsigned packed=scd_zone_art_u32(f+4),offset=packed>>16;
    return offset?offset:(packed&65535u)+scd_zone_art_u16(f+8)*scd_zone_art_u16(f+10)/2;
}
static inline int scd_zone_art_open(scd_zone_art *out,const uint8_t *data,size_t size,unsigned era){
    *out=(scd_zone_art){0};
    if(size<20 || era>3)return -1;
    unsigned magic=scd_zone_art_u32(data),spans=magic==0x5a415235;
    unsigned shared=magic==0x5a415232 || magic==0x5a415234 || spans,lz=magic==0x5a415233 || magic==0x5a415234;
    if((magic!=0x5a415254 && !shared && !lz) || (shared && size<32))return -1;
    uint32_t at=scd_zone_art_u32(data+4+era*4);
    if(!at)return 0;
    unsigned head=spans?12:shared?4:12;
    if(at<(shared?32u:20u) || at>size || size-at<head)return -1;
    const uint8_t *p=data+at;
    unsigned count=scd_zone_art_u32(p),raw=scd_zone_art_u32(shared && !spans?data+20:p+4),packed=scd_zone_art_u32(shared?data+24:p+8);
    unsigned span_count=spans?scd_zone_art_u32(p+8):0,arena=scd_zone_art_u32(data+20);
    if(!count || count>SCD_ZONE_ART_MAX_FRAMES || !raw || raw>SCD_ZONE_ART_CAPACITY || (raw&31) || !packed || (packed&1))return -1;
    if(spans && (!span_count || (arena&1) || arena/2>65536u))return -1;
    if(size-at-head<count*SCD_ZONE_ART_RECORD || size-at-head-count*SCD_ZONE_ART_RECORD<span_count*4)return -1;
    unsigned packed_at=shared?scd_zone_art_u32(data+28):at+head+count*SCD_ZONE_ART_RECORD;
    if(packed_at<at+head+count*SCD_ZONE_ART_RECORD+span_count*4 || packed_at>size || size-packed_at<packed)return -1;
    const uint8_t *span=p+head+count*SCD_ZONE_ART_RECORD;
    /* Spans ascend through the arena and fill the era's last bytes. */
    for(unsigned i=0,next=0,words=0;i<span_count;i++){
        unsigned from=scd_zone_art_u16(span+i*4),n=scd_zone_art_u16(span+i*4+2);
        if(!n || from<next || from+n>arena/2)return -1;
        next=from+n;words+=n;
        if(words>raw/2)return -1;
        if(i+1==span_count && words*2+32<raw)return -1;
    }
    p+=head;
    for(unsigned i=0;i<count;i++){
        const uint8_t *f=p+i*SCD_ZONE_ART_RECORD;
        unsigned offset=scd_zone_art_bitmap(f),clut=scd_zone_art_clut(f),w=scd_zone_art_u16(f+8),h=scd_zone_art_u16(f+10);
        unsigned bytes=w*h/2;
        if(!w || w>504 || (w&7) || !h || h>255 || (w*h&63) || (offset&31) || (clut&31) || offset>raw || bytes>raw-offset || clut>raw || 32>raw-clut)return -1;
        for(unsigned c=0;c<16;c++)if((scd_zone_art_u16(f+16+c*2)&~0xbfu))return -1;
    }
    *out=(scd_zone_art){p,data+packed_at,count,raw,packed,lz,spans?span:NULL,span_count,arena/2};return 0;
}
/* ZAR3 word LZ (tools/zone_art_lz.py). Back references read words already
   written to the destination (VDP1 VRAM on the Saturn); distance 0 keeps the
   destination's words (a bank packed against the resident one). 0 on success. */
static inline int scd_zone_art_lz_unpack(const uint8_t *r,unsigned bytes,volatile uint16_t *to,unsigned words){
    const uint8_t *end=r+bytes;unsigned at=0;
    while(end-r>=2){
        unsigned code=(unsigned)r[0]<<8|r[1];r+=2;
        if(code&0x8000){
            if(end-r<2)return -1;
            unsigned n=code&0x7fff,d=(unsigned)r[0]<<8|r[1];r+=2;
            if(!n || d>at || n>words-at)return -1;
            if(!d){at+=n;continue;}
            for(;n;n--,at++)to[at]=to[at-d];
        }else if(code&0x4000){
            unsigned n=code&0x3fff;
            if(!n || n>words-at || (unsigned)(end-r)<n*2)return -1;
            for(;n;n--,at++,r+=2)to[at]=(uint16_t)(r[0]<<8|r[1]);
        }else{
            if(!code || code>words-at || end-r<2)return -1;
            uint16_t v=(uint16_t)(r[0]<<8|r[1]);r+=2;
            for(;code;code--)to[at++]=v;
        }
    }
    return r==end && at==words?0:-1;
}
static inline unsigned scd_zone_art_kind(unsigned type,unsigned subtype){
    unsigned kind=type==68 && (subtype&128)?168:type;
    if(type==80 || type==83 || type==84)kind=subtype&128?type+100:type;
    if(type==78 || type==79)kind=(int8_t)subtype>0?type+200:subtype&128?type+100:type;
    if(type==89)kind=subtype&127?189:89;
    /* SIKAKE33: kaitenban 293, stopper 193, light 93. */
    if(type==93)kind=subtype&128?293:subtype?193:93;
    return kind;
}
static inline const uint8_t *scd_zone_art_find_kind(const scd_zone_art *art,unsigned kind,unsigned frame){
    for(unsigned i=0;i<art->count;i++){
        const uint8_t *f=art->frames+i*SCD_ZONE_ART_RECORD;
        if(scd_zone_art_u16(f)==kind && scd_zone_art_u16(f+2)==frame)return f;
    }
    return NULL;
}
/* ZAR3 (Tidal Tempest) keys a subtype's own pattern table as type|subtype<<8
   and falls back to the plain type when the subtype shares its table. */
static inline const uint8_t *scd_zone_art_find(const scd_zone_art *art,unsigned type,unsigned subtype,unsigned frame){
    if(art->lz){
        const uint8_t *f=scd_zone_art_find_kind(art,(type&255)|(subtype&255)<<8,frame);
        return f?f:scd_zone_art_find_kind(art,type,frame);
    }
    unsigned kind=scd_zone_art_kind(type,subtype);
    for(unsigned i=0;i<art->count;i++){
        const uint8_t *f=art->frames+i*SCD_ZONE_ART_RECORD;
        if(scd_zone_art_u16(f)==kind && scd_zone_art_u16(f+2)==frame)return f;
    }
    return NULL;
}
#endif
