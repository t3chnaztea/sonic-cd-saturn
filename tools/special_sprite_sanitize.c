#include "special_sprite.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv){
    assert(argc<=2);
    FILE *f=fopen(argc==2?argv[1]:"assets/generated/special-sonic.bin","rb");assert(f);fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);
    uint8_t *data=malloc(size);assert(data && fread(data,1,size,f)==(size_t)size);fclose(f);
    scd_special_art art;assert(!scd_special_art_open(&art,data,size));
    for(long n=0;n<size;n++)assert(scd_special_art_open(&(scd_special_art){0},data,n)==-1);
    uint32_t hash=2166136261u;unsigned cases=0;
    for(unsigned animation=0;animation<art.animations;animation++)for(unsigned flags=0;flags<8;flags+=2){
        scd_special_sprite s={.tilt=5};scd_special_player player={.flags=flags};scd_special_pose pose;
        scd_special_sprite_set(&s,&art,animation,1);
        for(unsigned tick=0;tick<128;tick++){
            int result=scd_special_sprite_advance(&s,&player,&art,&pose);assert((result<0)==((flags&4)!=0));
            if(!result)for(unsigned i=0;i<pose.width*pose.height/2;i++)hash=(hash^pose.pixels[i])*16777619u;
            cases++;
        }
    }
    for(unsigned offset=0;offset<art.texture_offset;offset++){
        uint8_t original=data[offset];data[offset]^=0xff;
        scd_special_art test;
        if(!scd_special_art_open(&test,data,size))for(unsigned animation=0;animation<art.animations;animation++){
            scd_special_sprite s={0};scd_special_player player={0};scd_special_pose pose;
            scd_special_sprite_set(&s,&test,animation,1);int result=scd_special_sprite_advance(&s,&player,&test,&pose);
            assert(!result);for(unsigned i=0;i<pose.width*pose.height/2;i++)hash=(hash^pose.pixels[i])*16777619u;
        }
        data[offset]=original;
    }
    free(data);printf("Special Sonic ASan/UBSan: %u animation states, all truncated lengths and metadata-byte mutations PASS %u\n",cases,hash);
}
