#include "special_effects_runtime.h"
void scd_special_effects_before(scd_special_effect_pool *f,scd_special_world *w,const scd_special_player *p){
    scd_special_splash_draw(w,p,f->drawn);
    for(unsigned i=0;i<8;i++){
        f->dust[i].id=w->dust[i]>>8;f->dust[i].routine=w->dust[i];
        scd_special_dust(f->dust+i,&f->context,f->previous_held,f->drawn+1+i);
        w->dust[i]=((unsigned)f->dust[i].id<<8)|f->dust[i].routine;
    }
}
void scd_special_effects_after(scd_special_effect_pool *f,scd_special_world *w,const scd_special_player *p,unsigned held){
    /* New ring slots only originate at grounded hazard contact. CheckBumper
       leaves this high word in D1. Sonic and its shadow retain that high word;
       the shadow's zero Y distance and DrawObject leave low word 1. Carry D1
       between rings, including RunObject clearing it on deletion. Outside a
       new hazard spawn its initial value cannot affect any ring's motion. */
    f->context.d1=((((uint32_t)p->speed<<8)+0x20000)&0xffff0000)|1;
    for(unsigned i=0;i<7;i++){
        f->rings[i].id=w->lost_rings[i];unsigned sound;
        scd_special_lost_ring(f->rings+i,&f->context,256u<<16,p->sprite_y,f->drawn+9+i,&sound);
        w->lost_rings[i]=f->rings[i].id;if(sound)scd_special_sound(w,sound);
    }
    f->previous_held=held;
}
static uint32_t word_hash(uint32_t h,uint32_t value){for(int shift=24;shift>=0;shift-=8)h=(h^((value>>shift)&255))*16777619u;return h;}
static uint32_t actor_hash(uint32_t h,const scd_special_effect *e){
    const uint32_t values[]={e->x,e->y,e->x_velocity,e->y_velocity,e->timer,e->id,e->routine,e->flags,e->animation,e->frame,e->time,e->time_copy,e->art,e->item_type};
    for(unsigned i=0;i<14;i++)h=word_hash(h,values[i]);return h;
}
uint32_t scd_special_effects_hash(const scd_special_effect_pool *f){
    uint32_t h=word_hash(2166136261u,f->context.seed);h=word_hash(h,f->context.ring_direction);h=word_hash(h,f->previous_held);
    for(unsigned i=0;i<8;i++)h=actor_hash(h,f->dust+i);
    for(unsigned i=0;i<7;i++)h=actor_hash(h,f->rings+i);
    for(unsigned i=0;i<16;i++)h=actor_hash(h,f->drawn+i);
    return h;
}
