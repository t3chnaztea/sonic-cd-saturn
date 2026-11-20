/* Level/_Objects/Powerup/Main.asm and Object Animate.asm. */
#include <string.h>
#include "powerup_visual.h"
#include "powerup-animation.inc"

static int animate(scd_powerup_visual *s){
    if(s->animation>=9)return -1;
    if(s->animation!=s->previous){s->previous=s->animation;s->cursor=0;s->timer=0;}
    s->timer--;
    if(!(s->timer&128))return 0;
    const uint8_t *script=powerup_animations[s->animation];
    if(1u+s->cursor>=powerup_animation_sizes[s->animation])return -1;
    s->timer=script[0];
    uint8_t frame=script[1+s->cursor];
    if(frame==255){s->cursor=0;frame=script[1];}
    if(frame&128)return -1; /* These nine original scripts use only FF. */
    s->mapping=frame&31;
    uint8_t flip=(uint8_t)((frame<<3)|(frame>>5));
    s->sprite_flags=(s->sprite_flags&252)|((flip^s->flags)&3);
    s->cursor++;
    return 0;
}
int scd_powerup_visual_step(scd_powerup_visual *s,scd_powerup_context *c){
    if(!s->active)return 0;
    if(s->animation>=9)return -1;
    if(!s->routine){
        s->routine=2;s->sprite_flags=4;s->priority=1;s->width=16;s->tile=0x544;
        if(s->animation)s->routine=s->animation<5?4:6;
        return 0;
    }
    if(s->routine==2){
        if(!c->shield){memset(s,0,sizeof(*s));return 0;}
        if(c->travel || c->invincible)return 0;
        s->x=c->x;s->y=c->y;s->flags=c->flags;
    }else if(s->routine==4 || s->routine==6){
        if(s->routine==4 && c->travel)return 0;
        if(!(s->routine==4?c->invincible:c->travel)){memset(s,0,sizeof(*s));return 0;}
        /* The source subtracts byte offsets in a 256-byte/64-position ring.
           Each actor owns its six-update phase, frozen while suppressed. */
        unsigned n=(s->animation-1u)&3;
        uint8_t offset=(uint8_t)(c->record_index-(n*24+4)-s->phase);
        s->phase=(uint8_t)(s->phase+4);if(s->phase>=24)s->phase=0;
        s->x=c->history[offset/4][0];s->y=c->history[offset/4][1];s->flags=c->flags;
    }else return -1;
    if(c->zone==6){s->tile|=0x8000;if(c->layer)s->tile&=0x7fff;}
    if(animate(s))return -1;
    uint8_t kind=c->powerup&15;
    if(kind>=8)return 0;
    if(kind!=s->routine)c->powerup=s->routine|128;
    return 1;
}
