/* Original special-stage priority-one dust and priority-two lost rings. */
#include "special_effects.h"
#include <string.h>
uint32_t scd_special_random(scd_special_effect_context *c){
    uint32_t seed=c->seed?c->seed:0x2a6d365a;
    uint32_t product=seed*41u;
    uint16_t sum=(uint16_t)product+(product>>16);
    c->seed=((uint32_t)sum<<16)|(uint16_t)product;
    return (seed&0xffff0000)|sum;
}
static void draw(scd_special_effect *e,scd_special_effect_context *c,unsigned frames,unsigned delay,scd_special_effect *out){
    /* DrawObject replaces D1's low byte with the animation frame count. */
    c->d1=(c->d1&0xffffff00)|frames;
    if(!(e->flags&2)){
        e->time--;if((int8_t)e->time<0){e->time=delay;e->frame++;if(e->frame>=frames)e->frame=0;}
    }
    if(!(e->flags&4))e->art=0;
    *out=*e;
    if(e->flags&1){memset(e,0,sizeof(*e));c->d1=0;}
}
void scd_special_dust(scd_special_effect *e,scd_special_effect_context *c,unsigned held,scd_special_effect *out){
    memset(out,0,sizeof(*out));if(!e->id)return;
    if(!e->routine){
        e->x=(e->x&65535)|(240u<<16);e->y=(e->y&65535)|(340u<<16);
        e->animation=e->frame=0;e->time=e->time_copy=1;e->timer=6;e->routine=1;
        uint32_t random=scd_special_random(c);c->d1=(c->d1&0xffff0000)|(uint16_t)random;
        e->x=(e->x&65535)|((uint32_t)(uint16_t)((e->x>>16)+(random&31))<<16);
        e->y=(e->y&65535)|((uint32_t)(uint16_t)((e->y>>16)+(random&7))<<16);
        int speed=held&4?3:held&8?-3:0;
        e->x_velocity=(e->x_velocity&65535)|((uint32_t)(uint16_t)speed<<16);
    }
    e->timer--;if(!e->timer)e->flags|=1;
    e->x+=e->x_velocity;e->y=(e->y&65535)|((uint32_t)(uint16_t)((e->y>>16)-1)<<16);
    draw(e,c,3,1,out);
}
void scd_special_lost_ring(scd_special_effect *e,scd_special_effect_context *c,uint32_t sonic_x,uint32_t sonic_y,scd_special_effect *out,unsigned *sound){
    memset(out,0,sizeof(*out));*sound=0;if(!e->id)return;
    if(!e->routine){
        e->item_type=4;e->animation=4;e->frame=0;e->time=e->time_copy=4;
        e->x=(e->x&65535)|(sonic_x&0xffff0000);e->y=(e->y&65535)|(sonic_y&0xffff0000);
        e->routine=1;e->timer=(e->timer&255)|(45u<<8);
        uint32_t random=scd_special_random(c);c->d1=((c->d1&0xffff0000)|(uint16_t)random)&0x3f000;
        unsigned direction=c->ring_direction&1;c->ring_direction^=1;if(direction)c->d1=0u-c->d1;
        e->x_velocity=c->d1;
        e->y_velocity=(e->y_velocity&65535)|((uint32_t)(uint16_t)(-10-(int)(random&15))<<16);
        *sound=0x94;
    }
    /* oTimer is a byte for rings, occupying the high byte of the dust word. */
    unsigned timer=((e->timer>>8)-1)&255;e->timer=(e->timer&255)|(timer<<8);if(!timer)e->flags|=1;
    e->x+=e->x_velocity;e->y+=e->y_velocity;
    if((e->y>>16)>344){e->y=(e->y&65535)|(344u<<16);e->y_velocity=0u-e->y_velocity;}
    else e->y_velocity+=0x20000;
    draw(e,c,4,4,out);
}
void scd_special_item(scd_special_effect *e,scd_special_effect_context *c,scd_special_effect *out,unsigned *sound){
    memset(out,0,sizeof(*out));*sound=0;if(!e->id)return;
    if(!e->routine){
        /* Original UFO headers permit four item types. */
        unsigned spawn_type=e->timer&255;if(spawn_type>3)return;
        e->item_type=e->animation=spawn_type;e->frame=0;e->time=e->time_copy=255;
        e->routine=1;e->timer=(e->timer&255)|(16u<<8);
        e->y_velocity=(e->y_velocity&65535)|0xfff00000u;*sound=0x95;
    }
    unsigned timer=((e->timer>>8)-1)&255;e->timer=(e->timer&255)|(timer<<8);if(!timer)e->flags|=1;
    e->y+=e->y_velocity;e->y_velocity+=0x20000;
    draw(e,c,1,255,out);
}
void scd_special_explosion(scd_special_effect *e,scd_special_effect_context *c,scd_special_effect *out,unsigned *sound){
    memset(out,0,sizeof(*out));*sound=0;if(!e->id)return;
    if(!e->routine){
        e->animation=e->frame=0;e->time=e->time_copy=2;
        e->timer=12;e->routine=1;*sound=0xa3;
    }
    e->timer--;if(!e->timer)e->flags|=1;
    draw(e,c,5,2,out);
}
int scd_special_explosion_slot(const scd_special_effect pool[8]){
    /* Original TST.W checks ID and routine together, including ID-zero
       slots with a nonzero routine. The first zero word wins. */
    for(unsigned i=0;i<8;i++)if(!pool[i].id && !pool[i].routine)return (int)i;
    return -1;
}
