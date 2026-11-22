#include "sonic_frames.h"
#include <string.h>
static unsigned word(const uint8_t *p){return (unsigned)p[0]<<8|p[1];}
static uint32_t longword(const uint8_t *p){return (uint32_t)word(p)<<16|word(p+2);}
#define HEADER_BYTES (40+4*(SCD_SONIC_FRAME_COUNT+1))
int scd_sonic_frames_open(scd_sonic_frames *out,const uint8_t *data,size_t size){
    if(size<HEADER_BYTES || memcmp(data,"SFR1",4) || longword(data+4)!=SCD_SONIC_FRAME_COUNT)return -1;
    uint32_t previous=HEADER_BYTES;
    for(unsigned i=0;i<=SCD_SONIC_FRAME_COUNT;i++){
        uint32_t offset=longword(data+40+i*4);
        if(offset>size || offset&1 || (i?offset<=previous:offset!=previous))return -1;
        previous=offset;
    }
    if(previous!=size)return -1;
    *out=(scd_sonic_frames){data,size};return 0;
}
int scd_sonic_frames_begin(const scd_sonic_frames *frames,unsigned id,scd_sonic_frames_cursor *cursor){
    if(id>=SCD_SONIC_FRAME_COUNT)return -1;
    uint32_t first=longword(frames->data+40+id*4),last=longword(frames->data+44+id*4);
    if(first<HEADER_BYTES || first>=last || last>frames->size)return -1;
    *cursor=(scd_sonic_frames_cursor){frames,frames->data+first,frames->data+last,0,0,0,0};
    return 0;
}
/* Each run is validated whole before any of it is written, exactly as the
   one-shot decoder did; a long run may then be written over several steps. */
int scd_sonic_frames_step(scd_sonic_frames_cursor *c,uint16_t output[1040],unsigned budget){
    const uint8_t *p=c->p,*end=c->end;unsigned n=c->n,left=c->left;int result=0;
    while(budget){
        if(!left){
            if(p>=end){
                if(n!=1024){result=-1;break;}
                for(unsigned i=0;i<16;i++)output[1024+i]=word(c->frames->data+8+i*2);
                result=1;break;
            }
            if(end-p<2){result=-1;break;}
            unsigned code=word(p);p+=2;unsigned count=code&32767;
            if(!count || count>1024-n || (unsigned)(end-p)<(code&32768?count*2:2)){result=-1;break;}
            left=count;c->literal=!!(code&32768);
            if(!c->literal){c->value=(uint16_t)word(p);p+=2;}
        }
        unsigned run=left<budget?left:budget;
        uint16_t *out=output+n;n+=run;left-=run;budget-=run;
        if(c->literal){for(unsigned i=0;i<run;i++){out[i]=(uint16_t)(p[0]<<8|p[1]);p+=2;}}
        else{const uint16_t value=c->value;for(unsigned i=0;i<run;i++)out[i]=value;}
    }
    c->p=p;c->n=n;c->left=left;
    return result;
}
/* One-shot decode, kept separate from the stepped path: it is the faster loop. */
int scd_sonic_frames_decode(const scd_sonic_frames *frames,unsigned id,uint16_t output[1040]){
    if(id>=SCD_SONIC_FRAME_COUNT)return -1;
    uint32_t first=longword(frames->data+40+id*4),last=longword(frames->data+44+id*4);
    if(first<HEADER_BYTES || first>=last || last>frames->size)return -1;
    const uint8_t *p=frames->data+first,*end=frames->data+last;unsigned n=0;
    while(p<end){
        if(end-p<2)return -1;
        unsigned code=word(p);p+=2;unsigned count=code&32767;
        if(!count || count>1024-n || (unsigned)(end-p)<(code&32768?count*2:2))return -1;
        if(code&32768){for(unsigned i=0;i<count;i++){output[n++]=word(p);p+=2;}}
        else {unsigned value=word(p);p+=2;for(unsigned i=0;i<count;i++)output[n++]=value;}
    }
    if(n!=1024)return -1;
    for(unsigned i=0;i<16;i++)output[1024+i]=word(frames->data+8+i*2);
    return 0;
}
