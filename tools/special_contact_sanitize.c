/* Exercise bounded contact sampling, wraparound timers and pool boundaries. */
#include "special_contacts.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned random_state=28013;
static uint32_t next(void){random_state=random_state*1664525u+1013904223u;return random_state;}
static uint8_t *read_file(const char *name,size_t *size){
    FILE *f=fopen(name,"rb");assert(f);fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);
    uint8_t *data=malloc(*size);assert(data && fread(data,1,*size,f)==*size);fclose(f);return data;
}
int main(void){
    size_t size;uint8_t *art_data=read_file("assets/generated/special-sonic.bin",&size);scd_special_art art;assert(!scd_special_art_open(&art,art_data,size));
    unsigned cases=0;uint32_t hash=2166136261u;
    const uint16_t edges[]={0,7,8,31,32,831,832,3264,4087,4095,4096,65535};
    for(unsigned stage_id=1;stage_id<=8;stage_id++){
        char name[20];snprintf(name,sizeof(name),"cd/SP%u.BIN",stage_id);uint8_t *data=read_file(name,&size);scd_special_stage stage;assert(!scd_special_open(&stage,data,size));
        for(unsigned x=0;x<12;x++)for(unsigned y=0;y<12;y++){
            scd_special_player p={.x=(uint32_t)edges[x]<<16,.y=(uint32_t)edges[y]<<16};scd_special_get_contacts(&p,&stage);cases++;
        }
        for(unsigned n=0;n<8192;n++){
            scd_special_player p={.x=next(),.y=next(),.yaw=next(),.sprite_y=next(),.sprite_velocity=next(),.z=next(),.speed=next(),.top_speed=next(),.shoes=next(),.jump_timer=next(),.bump_time=next(),.routine=1+n%19,.flags=next(),.hurt=next(),.stamp_c=n%10,.stamp_tl=n&1,.stamp_tr=(n>>1)&1,.stamp_br=(n>>2)&1,.stamp_bl=(n>>3)&1,.orientation=n%16,.x_velocity=next(),.y_velocity=next()};
            scd_special_sprite s={.tilt=n%10};scd_special_sprite_set(&s,&art,n%45,1);
            scd_special_world w={.timer=next(),.rings=next(),.timer_frames=next(),.speedup=next(),.ufo_count=n%7,.time_attack=n%2,.stopped=n%11==0,.inactive=n%13==0,.splash_id=n%2?8:0,.splash_timer=next(),.splash_routine=n%3,.splash_flags=n%8,.splash_animation=n%2,.splash_frame=n%3,.splash_time=next()};
            for(unsigned i=0;i<8;i++)w.dust[i]=next()&1?0x700:0;for(unsigned i=0;i<3;i++)w.sound[i]=next()&1?0x92:0;
            scd_special_contact(&p,&s,&art,&w);scd_special_splash(&w,&p);scd_special_timer(&w);
            scd_special_player_step(&p,&s,&art,&w,&stage,n&127,(n>>3)&112);
            assert((p.x>>16)<=3264 && (p.y>>16)>=832 && (p.y>>16)<=3264);
            scd_special_pose pose;int drawn=scd_special_sprite_advance(&s,&p,&art,&pose);
            if(!drawn){assert(pose.width<=64 && pose.height<=64);hash=(hash^pose.pixels[pose.width*pose.height/2-1])*16777619u;}
            hash=(hash^p.x^p.y^w.timer)*16777619u;cases++;
        }
        free(data);
    }
    free(art_data);printf("Special contacts ASan/UBSan: %u states and map boundaries PASS %u\n",cases,hash);
}
