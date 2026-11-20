/* Bounded stage dispatch under ASan/UBSan: random controls, seeded hits,
   timer/UFO boundaries, packs and reset rejection. */
#include "special_stage.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t random_state=30035;
static uint32_t next(void){random_state=random_state*1664525u+1013904223u;return random_state;}
static uint8_t *read_file(const char *name,size_t *size){
    FILE *f=fopen(name,"rb");assert(f);fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);
    uint8_t *data=malloc(*size);assert(data && fread(data,1,*size,f)==*size);fclose(f);return data;
}
int main(void){
    size_t sizes[4];const char *names[4]={"assets/generated/special-sonic.bin","assets/generated/special-ufo-art.bin","assets/generated/special-effects.bin","assets/generated/special-ufo-paths.bin"};
    uint8_t *data[4];scd_special_art art[3];
    for(unsigned i=0;i<4;i++)data[i]=read_file(names[i],sizes+i);
    for(unsigned i=0;i<3;i++)assert(!scd_special_art_open(art+i,data[i],sizes[i]));
    static scd_special_stage_state st;scd_special_world w;uint32_t hash=2166136261u;unsigned updates=0;
    for(size_t n=0;n<sizes[3];n+=97)assert(scd_special_stage_reset(&st,&w,data[3],n,0)==-1);
    assert(scd_special_stage_reset(&st,&w,data[3],sizes[3],8)==-1);
    for(unsigned stage_id=1;stage_id<=8;stage_id++){
        char name[20];snprintf(name,sizeof(name),"cd/SP%u.BIN",stage_id);size_t size;uint8_t *map=read_file(name,&size);
        scd_special_stage stage;assert(!scd_special_open(&stage,map,size));
        for(unsigned run=0;run<6;run++){
            w=(scd_special_world){.timer=run==1?19:run==2?0:100,.timer_frames=1+next()%20,.rings=next()%1200,.time_attack=run==3,.stopped=run==4};
            assert(!scd_special_stage_reset(&st,&w,data[3],sizes[3],stage_id-1));
            if(run==5)w.ufo_count=next()%3;
            scd_special_player p={.x=(832+next()%2432)<<16,.y=(832+next()%2432)<<16,.yaw=next()&0x1ffffff,.sprite_y=344u<<16,.z=352,.top_speed=0xa00,.routine=1};
            scd_special_sprite s={.tilt=5};scd_special_sprite_set(&s,art,10,1);
            for(unsigned tick=0;tick<700;tick++){
                if(next()%23==0){
                    unsigned i=next()%7;const scd_special_ufo *u=&st.ufos[i].u;
                    if(u->id){p.x=u->x;p.y=u->y;p.routine=2;p.flags=0x80;p.sprite_y=288u<<16;p.z=0x240;p.sprite_velocity=0;}
                }
                if(next()%97==0){p.routine=next()%24;p.hurt=next();}
                scd_special_pose pose;int visible;memset(w.sound,0,3);
                unsigned held=next()&0x7f,tapped=next()&0x70,yaw=p.yaw>>16;
                assert(!scd_special_stage_update(&st,&w,&p,&s,art,art+1,art+2,&stage,held,tapped,yaw,&pose,&visible));
                assert(st.draw_count<=SCD_SPECIAL_DRAWS);
                for(unsigned d=0;d<st.draw_count;d++){
                    const scd_special_draw *e=st.draws+d;const scd_special_art *pack=e->kind==SCD_SPECIAL_DRAW_SFX?art+2:art+1;
                    if(e->kind==SCD_SPECIAL_DRAW_SONIC)continue;
                    assert(e->animation<pack->animations && e->palette<4 && e->object<44);
                    const uint8_t *a=pack->data+pack->animation_offset+e->animation*4;assert(e->frame<a[0]);
                }
                uint32_t words[SCD_SPECIAL_STAGE_WORDS];unsigned count=scd_special_stage_words(&st,words);assert(count<=SCD_SPECIAL_STAGE_WORDS);
                hash=(hash^scd_special_stage_hash(&st)^scd_special_effects_hash(&st.effects))*16777619u;updates++;
                if(w.got_time_stone || (p.routine>=5 && p.routine!=7 && p.routine<19 && next()%50==0))p.routine=1,w.inactive=0;
            }
        }
        free(map);
    }
    scd_special_stage_state empty={0};scd_special_player p={0};scd_special_sprite s={0};scd_special_pose pose;int visible=1;
    scd_special_stage stage={0};
    assert(scd_special_stage_update(&empty,&w,&p,&s,art,art+1,art+2,&stage,0,0,0,&pose,&visible)==-1 && !visible);
    for(unsigned i=0;i<4;i++)free(data[i]);
    printf("Special stage ASan/UBSan: %u updates PASS %u\n",updates,hash);
}
