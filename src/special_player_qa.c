/* Bounded cross-target probe; host oracle executes the original 68000 for
   these same motion states. No reference machine code is linked here. */
#include "special_player.h"
static uint32_t record(uint32_t h,const scd_special_player *p){
    const uint32_t words[]={p->x,p->y,p->yaw,p->sprite_y,p->sprite_velocity,p->z,p->speed,p->top_speed,p->shoes,p->jump_timer,p->bump_time,p->routine,p->flags,p->scroll};
    for(unsigned i=0;i<sizeof(words)/sizeof(words[0]);i++)for(int shift=24;shift>=0;shift-=8)h=(h^((words[i]>>shift)&255))*16777619u;
    return h;
}
uint32_t scd_special_player_probe(unsigned *count){
    uint32_t h=2166136261u;*count=0;
    for(unsigned yaw=0;yaw<512;yaw++){
        scd_special_player p={.x=0x340fedc,.y=0xcbf0123,.yaw=(yaw<<16)|0x9876,.speed=yaw&1?0xa00:0xfa00};
        scd_special_player_move(&p);h=record(h,&p);(*count)++;
    }
    for(unsigned arc=0;arc<6;arc++){
        scd_special_player p={.x=1344u<<16,.y=1312u<<16,.yaw=128u<<16,.sprite_y=344u<<16,.z=352,.speed=0xa00,.top_speed=0xa00,.routine=1,.jump_timer=arc==4?20:0};
        if(arc<2)scd_special_player_jump(&p,0x10,0);else if(arc<5)scd_special_player_spring(&p);else scd_special_player_fan(&p);
        h=record(h,&p);(*count)++;
        unsigned tick=0;
        while(p.routine!=1){
            if(++tick>200)return 0;
            scd_special_player_air(&p,arc==1 || arc==3?0x10:0,0);h=record(h,&p);(*count)++;
        }
    }
    return h;
}
#ifdef SCD_SPECIAL_PLAYER_QA_MAIN
#include <stdio.h>
int main(void){unsigned count;uint32_t hash=scd_special_player_probe(&count);printf("%u %u\n",hash,count);return !hash;}
#endif
