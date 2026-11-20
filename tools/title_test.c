/* Host run of src/title.c with a retail title pad script (tools/title_retail.py).
   Prints one JSON record per V-INT in the retail record's field names; CRC fields are
   zlib CRC32 of the big-endian bytes, so tools/check_title.py compares them directly. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "title.h"
static uint32_t crc32(const uint8_t *p,size_t n){
    static uint32_t table[256];
    if(!table[1])for(unsigned i=0;i<256;i++){uint32_t c=i;for(unsigned k=0;k<8;k++)c=c&1?0xedb88320u^(c>>1):c>>1;table[i]=c;}
    uint32_t c=0xffffffffu;while(n--)c=table[(c^*p++)&255]^(c>>8);return ~c;
}
static uint32_t words(const uint16_t *w,size_t n){
    uint8_t *b=malloc(n*2);for(size_t i=0;i<n;i++){b[i*2]=w[i]>>8;b[i*2+1]=w[i];}
    uint32_t c=crc32(b,n*2);free(b);return c;
}
static unsigned pads[4000];
int main(int argc,char **argv){
    if(argc!=3){fprintf(stderr,"usage: title_test title.bin route.pad\n");return 2;}
    FILE *f=fopen(argv[1],"rb");if(!f){perror(argv[1]);return 2;}
    fseek(f,0,SEEK_END);long size=ftell(f);fseek(f,0,SEEK_SET);
    uint8_t *data=malloc(size);if(fread(data,1,size,f)!=(size_t)size)return 2;fclose(f);
    f=fopen(argv[2],"r");if(!f){perror(argv[2]);return 2;}
    unsigned v,pad,last=0,value=0;
    while(fscanf(f,"%u %u",&v,&pad)==2){if(v>=4000)return 2;for(unsigned i=last;i<v;i++)pads[i]=value;last=v;value=pad;}
    for(unsigned i=last;i<4000;i++)pads[i]=value;
    fclose(f);
    scd_title_pack pack;scd_title *t=calloc(1,sizeof(*t));
    if(scd_title_open(&pack,data,size) || scd_title_start(t,&pack)){fprintf(stderr,"title pack rejected\n");return 1;}
    int done=0;
    for(;;){
        printf("{\"v\":%u,\"routine\":%u,\"mode\":%u,\"timer\":%u,\"exit\":%u,\"menu_sel\":%u,\"menu_options\":\"",t->vint,t->routine,t->mode,t->timer,t->exit_flag,t->menu_sel);
        for(unsigned i=0;i<8;i++)printf("%02x",t->menu_options[i]);
        printf("\",\"cycle\":[%u,%u],\"ctrl\":[%u,%u],\"enable_display\":%u,\"display\":%u,\"gfx\":[%d,%d,%d,%d,%d]",t->cycle_frame,t->cycle_delay,t->hold,t->tap,t->enable_display,t->display,
            t->cam_x,t->cam_y,t->cam_z,t->pitch,t->yaw);
        printf(",\"cram\":\"%08x\",\"palette\":\"%08x\",\"fade\":\"%08x\",\"hscroll_buf\":\"%08x\",\"hscroll\":\"%08x\"",words(t->cram,64),words(t->palette,64),words(t->fade,64),words(t->hscroll_buffer,448),words(t->hscroll,448));
        printf(",\"sprites_buf\":\"%08x\",\"sat\":\"%08x\",\"clouds_image\":\"%08x\"",crc32(t->sprites,640),crc32(t->sat,640),crc32(t->clouds_image,SCD_TITLE_IMAGE));
        printf(",\"plane_a\":\"%08x\",\"plane_b\":\"%08x\",\"tiles\":\"%08x\",\"cloud_tiles\":\"%08x\"",crc32(t->vram+0xC000,0x1000),crc32(t->vram+0xE000,0x1000),crc32(t->vram,0xC000),crc32(t->vram+0x20,0x6000));
        printf(",\"objects\":[");
        for(unsigned i=0;i<SCD_TITLE_OBJECTS;i++){const scd_title_object *o=t->objects+i;printf("%s[%u,%u,%u,%u,%d,%d]",i?",":"",o->active,o->flags,o->tile,o->frame,o->x,o->y);}
        printf("],\"lag_frames\":%u,\"done\":%d,\"exit_code\":%u,\"pad\":%u}\n",scd_title_lag_frames(t),done,t->exit_code,t->vint<4000?pads[t->vint]:0);
        if(done || t->vint>=3999)break;
        done=scd_title_vint(t,pads[t->vint]);
    }
    free(t);free(data);
    return done?0:1;
}
