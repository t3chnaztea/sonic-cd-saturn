#include "special_effects.h"
#include <assert.h>
#include <stdio.h>
static uint32_t seed=300412;
static uint32_t next(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
    uint32_t hash=0;
    for(unsigned n=0;n<65536;n++)for(unsigned kind=0;kind<2;kind++){
        scd_special_effect e={.id=n%17?(kind?12:4):0,.routine=n%2,.x=next(),.y=next(),.x_velocity=next(),.y_velocity=next(),.timer=(next()&0xff00)|(n%4),.flags=n%8,.animation=kind?0:n%4,.frame=kind?n%5:0,.time=next(),.time_copy=kind?2:255,.art=next(),.item_type=next()};
        scd_special_effect out;scd_special_effect_context c={next(),next(),next()};unsigned sound;
        if(kind)scd_special_explosion(&e,&c,&out,&sound);else scd_special_item(&e,&c,&out,&sound);
        if(out.flags&1)assert(!e.id && !e.routine && !e.y && !c.d1);
        hash+=e.y+e.y_velocity+sound+out.timer;
    }
    printf("Reward sanitizers PASS: 131072 states, checksum %u\n",hash);return 0;
}
