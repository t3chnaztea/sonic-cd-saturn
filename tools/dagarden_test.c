/* Host run of src/dagarden.c with a retail D.A. Garden pad script (tools/dagarden_retail.py).
   Prints one JSON record per V-INT in the retail record's field names; CRC fields are zlib
   CRC32 of the big-endian bytes, so tools/test_dagarden.py compares them directly. Objects
   are printed in the retail 64-byte layout with oMap as an offset into the tables part. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dagarden.h"
static uint32_t crc32(const uint8_t *p,size_t n){
    static uint32_t table[256];
    if(!table[1])for(unsigned i=0;i<256;i++){uint32_t c=i;for(unsigned k=0;k<8;k++)c=c&1?0xedb88320u^(c>>1):c>>1;table[i]=c;}
    uint32_t c=0xffffffffu;while(n--)c=table[(c^*p++)&255]^(c>>8);return ~c;
}
static uint32_t words(const uint16_t *w,size_t n){
    uint8_t *b=malloc(n*2);for(size_t i=0;i<n;i++){b[i*2]=w[i]>>8;b[i*2+1]=w[i];}
    uint32_t c=crc32(b,n*2);free(b);return c;
}
static void put16(uint8_t *p,unsigned v){p[0]=v>>8;p[1]=v;}
static void put32(uint8_t *p,uint32_t v){put16(p,v>>16);put16(p+2,v);}
static void hex(const uint8_t *p,size_t n){for(size_t i=0;i<n;i++)printf("%02x",p[i]);}
enum {VINTS=20000};
/* VDP state right after each V-INT routine (the retail record's first frame of that vintCounter). */
static char vdp_after[512];
static void after_vint(const scd_dagarden *t){
    uint8_t sat[0x280];memcpy(sat,t->vram+0xEC00,sizeof(sat));
    snprintf(vdp_after,sizeof(vdp_after),"\"cram\":\"%08x\",\"vsram\":\"%04x%04x\",\"hscroll\":\"%04x0000\",\"plane_a\":\"%08x\",\"plane_b\":\"%08x\",\"sat\":\"%08x\",\"buffer1\":\"%08x\",\"buffer2\":\"%08x\"",
        words(t->cram,64),t->vsram[0],t->vsram[1],t->hscroll_a,crc32(t->vram+0xC000,0x1000),crc32(t->vram+0xE000,0x1000),crc32(sat,sizeof(sat)),crc32(t->vram,SCD_DG_IMAGE),crc32(t->vram+SCD_DG_IMAGE,SCD_DG_IMAGE));
}
static unsigned pads[VINTS];
int main(int argc,char **argv){
    if(argc!=3){fprintf(stderr,"usage: dagarden_test dagarden.bin route.pad\n");return 2;}
    FILE *f=fopen(argv[1],"rb");if(!f){perror(argv[1]);return 2;}
    fseek(f,0,SEEK_END);long size=ftell(f);fseek(f,0,SEEK_SET);
    uint8_t *data=malloc(size);if(fread(data,1,size,f)!=(size_t)size)return 2;fclose(f);
    f=fopen(argv[2],"r");if(!f){perror(argv[2]);return 2;}
    unsigned v,pad,last=0,value=0;
    while(fscanf(f,"%u %u",&v,&pad)==2){if(v>=VINTS)return 2;for(unsigned i=last;i<v;i++)pads[i]=value;last=v;value=pad;}
    for(unsigned i=last;i<VINTS;i++)pads[i]=value;
    fclose(f);
    scd_dagarden_pack pack;scd_dagarden *t=calloc(1,sizeof(*t));
    if(scd_dagarden_open(&pack,data,size) || scd_dagarden_start(t,&pack) || (t->after_vint=after_vint,after_vint(t),0)){fprintf(stderr,"D.A. Garden pack rejected\n");return 1;}
    int done=0;
    for(;;){
        uint8_t sel[8],timers[12],objects[16*64],planet[0x22],map[112],sat[0x280];
        put16(sel,t->sel_routine);put16(sel+2,t->sel_id);put16(sel+4,t->sel_title);put16(sel+6,t->sel_dir);
        for(unsigned i=0;i<6;i++)put16(timers+i*2,t->spawn_timers[i]);
        memset(objects,0,sizeof(objects));
        for(unsigned i=0;i<16;i++){
            const scd_dagarden_object *o=t->objects+i;uint8_t *p=objects+i*64;
            put16(p,o->id);put16(p+2,o->routine);put32(p+4,o->x);put32(p+8,o->y);put32(p+12,o->xvel);put32(p+16,o->yvel);
            put16(p+0x1A,o->xoff);put16(p+0x1C,o->yoff);put16(p+0x1E,o->float_angle);put16(p+0x22,o->anim_time);put16(p+0x24,o->anim_frame);
            put16(p+0x26,o->tile);put32(p+0x28,o->map);p[0x2C]=o->flags;p[0x2D]=o->spawn_id;put16(p+0x2E,o->dest_x);put16(p+0x30,o->dest_y);
            put16(p+0x32,o->float_speed);put16(p+0x34,o->float_amp);p[0x36]=o->timer;p[0x37]=o->timer2;
        }
        memset(planet,0,sizeof(planet));planet[3]=t->planet_routine;put16(planet+0x10,t->planet_angle);
        put16(planet+0x14,t->planet_x);put16(planet+0x18,t->planet_y);put16(planet+0x1C,t->planet_z);
        for(unsigned r=0;r<7;r++)for(unsigned c=0;c<8;c++)put16(map+r*16+c*2,t->stamp_map[r][c]);
        uint8_t tr[176*8];for(unsigned i=0;i<176*4;i++)put16(tr+i*2,t->trace[i]);
        memcpy(sat,t->vram+0xEC00,sizeof(sat));
        printf("{\"v\":%u,\"routine\":%u,\"timer\":%u,\"buf_count\":%u,\"cycle\":[%u,%u],\"volcano\":[%u,%u],\"spr_cycle\":[%u,%u],\"sel_flags\":%u,\"sel\":\"",
            t->vint,(uint16_t)t->routine,t->timer,(uint16_t)t->buf_count,t->cycle_timer,t->cycle_index,t->volcano_timer,t->volcano_index,t->sprite_cycle_timer,t->sprite_cycle_index,t->sel_flags);
        hex(sel,8);printf("\",\"spawn_timers\":\"");hex(timers,12);
        printf("\",\"spawn\":[%u,%u],\"buttons\":%u,\"seed\":\"%08x\",\"zone\":%u,\"no_cycle\":%u,\"ctrl\":[%u,%u],\"ga_flags\":%u,\"ga_cmd\":[0,%u,%u]",
            t->spawn_flags,t->spawn_id,t->button_flags,t->seed,t->zone,t->no_cycle,t->hold,t->tap,(unsigned)t->main_flags<<8|t->sub_flags,t->cmd_track,t->cmd_zone);
        printf(",\"objects\":\"");hex(objects,sizeof(objects));
        printf("\",\"palette\":\"%08x\",\"fade\":\"%08x\",\"sprites_buf\":\"%08x\",\"planet_image\":\"%08x\",\"image\":\"%08x\",\"trace\":\"%08x\",\"stamp_map\":\"%08x\"",
            words(t->palette,64),words(t->fade,64),crc32(t->sprites,640),crc32(t->planet_image,SCD_DG_IMAGE),crc32(t->rendered,SCD_DG_IMAGE),crc32(tr,sizeof(tr)),crc32(map,sizeof(map)));
        printf(",\"planet\":\"");hex(planet,sizeof(planet));
        printf("\",\"sub\":[0,%d,%d,\"%08x\",%u]",t->scale_dir,t->angle_dir,(uint32_t)t->angle_speed,t->planet_flags);
        printf(",\"vdp\":{%s},\"object_tiles\":\"%08x\"",vdp_after,crc32(t->vram+0xB000,0x1000));
        printf(",\"lag_frames\":%u,\"art_bytes\":%u,\"art_id\":%u,\"step\":%u,\"music\":%u,\"done\":%d,\"pad\":%u}\n",scd_dagarden_lag_frames(t),t->art_bytes,t->art_last,t->step,t->music,done,t->vint<VINTS?pads[t->vint]:0);
        if(done || t->vint>=VINTS-1)break;
        done=scd_dagarden_vint(t,pads[t->vint]);
    }
    free(t);free(data);
    return done?0:1;
}
