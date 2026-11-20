/* Prove that loading-time textures remain valid until their first reveal and
   that every warmed key actually occurs in the source program's sprite table. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "title.h"
#include "title_scale.h"
#include "title-parts.inc"

typedef struct {
    unsigned tile,width,height,bytes;
    scd_title_scaled_shape shape;
    uint8_t texture[768];
} warmed;
static warmed pieces[38];
static unsigned count;
static unsigned be16(const uint8_t *p){return (unsigned)p[0]<<8|p[1];}
static void prepare(const scd_title *t,unsigned part,unsigned frame,unsigned base,int x){
    const uint8_t *map=t->pack->data+t->pack->offset[part];
    unsigned offset=be16(map+frame*2),n=map[offset];
    assert(offset+1+n*5<=t->pack->length[part]);
    for(unsigned i=0;i<n;i++){
        const uint8_t *entry=map+offset+1+i*5;
        assert(count<38);warmed *p=pieces+count++;
        p->tile=(be16(entry+2)+base)&0x1fff;p->width=((entry[1]>>2)&3)+1;p->height=(entry[1]&3)+1;
        p->shape=scd_title_shape(x+(int8_t)entry[4],p->width);
        p->bytes=scd_title_expand(p->texture,t->vram,p->tile,p->width,p->height,p->shape);
    }
}
int main(int argc,char **argv){
    assert(argc==2);FILE *file=fopen(argv[1],"rb");assert(file);
    assert(!fseek(file,0,SEEK_END));long size=ftell(file);assert(size>0);rewind(file);
    uint8_t *data=malloc((size_t)size);assert(data);
    assert(fread(data,1,(size_t)size,file)==(size_t)size);fclose(file);
    scd_title_pack pack;scd_title *t=calloc(1,sizeof(*t));assert(t);
    assert(!scd_title_open(&pack,data,(size_t)size) && !scd_title_start(t,&pack));
    prepare(t,TITLE_PART_MAP_BANNER,0,0xF000/32,127);
    prepare(t,TITLE_PART_MAP_SONIC,4,0x6D00/32,91);
    prepare(t,TITLE_PART_MAP_SONIC,9,0x6D00/32,140);
    assert(count==38);
    uint8_t current[768];unsigned comparisons=0;
    for(unsigned v=1;v<=82;v++){
        assert(!scd_title_vint(t,0) && t->vint==v);
        for(unsigned i=0;i<count;i++){
            const warmed *p=pieces+i;
            assert(scd_title_expand(current,t->vram,p->tile,p->width,p->height,p->shape)==p->bytes);
            assert(!memcmp(current,p->texture,p->bytes));comparisons++;
        }
    }
    for(unsigned i=0;i<count;i++){
        const warmed *p=pieces+i;unsigned found=0,index=0;
        for(unsigned n=0;n<64;n++){
            const uint8_t *s=t->sat+index*8;
            unsigned width=((s[2]>>2)&3)+1,height=(s[2]&3)+1;
            scd_title_scaled_shape shape=scd_title_shape((int)(be16(s+6)&511)-128,width);
            if((be16(s+4)&0x1fff)==p->tile && width==p->width && height==p->height && shape.phase==p->shape.phase)found++;
            index=s[3]&127;if(!index)break;assert(index<64);
        }
        assert(found);
    }
    free(t);free(data);
    printf("Title prewarm: %u exact texture comparisons; all 38 keys present at the reveal\n",comparisons);
}
