#include "special_ufo.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static uint32_t seed=30;
static uint32_t next(void){seed=seed*1664525+1013904223;return seed;}
int main(void){
    uint8_t data[24]={0,0,0,3,8,0,8,0,9,0,9,0,0,1,9,0,9,0,8,0,8,0,255,255};
    scd_special_ufo_path path;assert(!scd_special_ufo_path_open(&path,data,sizeof(data)));
    for(unsigned n=0;n<sizeof(data);n++){
        scd_special_ufo_path invalid;assert(scd_special_ufo_path_open(&invalid,data,n)==-1);assert(!invalid.data && !invalid.size);
    }
    scd_special_ufo_path invalid;assert(scd_special_ufo_path_open(&invalid,NULL,24)==-1);
    for(unsigned offset=0;offset<sizeof(data);offset++)for(unsigned value=0;value<256;value++){
        uint8_t changed[24];memcpy(changed,data,24);changed[offset]=value;
        scd_special_ufo_path mutated;if(!scd_special_ufo_path_open(&mutated,changed,24)){
            scd_special_ufo u={.path_offset=2};assert(!scd_special_ufo_follow(&u,&mutated));
            u.path_offset=12;assert(!scd_special_ufo_follow(&u,&mutated));u.path_offset=22;assert(!scd_special_ufo_follow(&u,&mutated));
        }
    }
    uint32_t hash=0;
    for(unsigned n=0;n<65536;n++){
        scd_special_ufo u={.id=2,.x=next(),.y=next(),.sprite_x=next(),.sprite_y=next(),.z=next(),.flags=next(),.path_offset=2};
        uint16_t sx=next(),sy=next(),z=next();uint8_t collision=0;
        (void)scd_special_ufo_project(&u,sx,sy,n);scd_special_ufo_on_screen(&u);scd_special_ufo_collision(&u,sx,sy,z,n&1,&collision);
        hash+=scd_special_ufo_distance(u.x>>16,u.y>>16,sx,sy)+u.sprite_x+u.sprite_y+collision;
        assert(scd_special_ufo_animation(next())<=9);
        u.path_offset=n;
        int result=scd_special_ufo_follow(&u,&path);assert(result==((n==2 || n==12 || n==22)?0:-1));
        u.path_offset=2;assert(!scd_special_ufo_follow(&u,&path));for(unsigned i=0;i<10;i++)assert(!scd_special_ufo_move(&u,&path));
    }
    FILE *f=fopen("assets/generated/special-ufo-paths.bin","rb");assert(f);fseek(f,0,SEEK_END);long length=ftell(f);rewind(f);
    uint8_t *pack=malloc(length);assert(pack && fread(pack,1,length,f)==(size_t)length);fclose(f);
    scd_special_ufo_paths paths;assert(!scd_special_ufo_paths_open(&paths,pack,length));
    for(long n=0;n<length;n++)assert(scd_special_ufo_paths_open(&paths,pack,n)==-1);
    for(long n=0;n<length;n++){
        pack[n]^=255;
        if(!scd_special_ufo_paths_open(&paths,pack,length))for(unsigned i=0;i<49;i++){
            scd_special_ufo_path p;assert(!scd_special_ufo_path_get(&paths,i,&p));scd_special_ufo u={.path_offset=2};assert(!scd_special_ufo_follow(&u,&p));
        }
        pack[n]^=255;
    }
    free(pack);
    printf("UFO sanitizers PASS: 65536 states, checksum %u\n",hash);return 0;
}
