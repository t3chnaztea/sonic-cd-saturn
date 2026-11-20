#include "special_effects.h"
#include <assert.h>
#include <stdio.h>
static uint32_t seed=29013;
static uint32_t next(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
    unsigned count=0;uint32_t hash=2166136261u;
    for(unsigned n=0;n<65536;n++){
        scd_special_effect_context context={next(),next(),next()};
        for(unsigned kind=0;kind<2;kind++){
            scd_special_effect e={.x=next(),.y=next(),.x_velocity=next(),.y_velocity=next(),.timer=next(),.id=n%13==0?0:kind?13:7,.routine=n%2,.flags=n%8,.animation=kind?4:0,.frame=n%(kind?4:3),.time=next(),.time_copy=kind?4:1,.art=next(),.item_type=next()};
            scd_special_effect drawn;unsigned sound;
            if(kind)scd_special_lost_ring(&e,&context,next(),next(),&drawn,&sound);else scd_special_dust(&e,&context,n&15,&drawn);
            if(drawn.flags&1)assert(!e.id && !e.routine && !e.x && !e.y && !context.d1);
            hash=(hash^e.x^e.y^context.seed)*16777619u;count++;
        }
    }
    printf("Special effects ASan/UBSan: %u states PASS %u\n",count,hash);
}
