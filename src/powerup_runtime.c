#include <assert.h>
#include <string.h>
#include "powerup_runtime.h"
void scd_powerup_runtime_reset(scd_powerup_runtime *s,uint32_t resets){
    memset(s,0,sizeof(*s));s->resets=resets;
}
static void spawn(scd_powerup_runtime *s,unsigned first,unsigned count){
    for(unsigned n=first;n<first+count;n++){
        /* Original monitor/Sonic creation writes only ID and animation. */
        s->actors[n].active=3;s->actors[n].animation=n;
    }
}
void scd_powerup_runtime_step(scd_powerup_runtime *s,scd_player_effect_sample p,
    unsigned post_shield,unsigned post_invincible,unsigned travel){
    s->submitted=0;
    if(!p.valid)return;
    if(s->resets!=p.resets)scd_powerup_runtime_reset(s,p.resets);
    scd_powerup_context *c=&s->context;
    if(p.record){
        c->history[c->record_index/4][0]=p.record_x;
        c->history[c->record_index/4][1]=p.record_y;c->record_index+=4;
    }
    c->x=p.x;c->y=p.y;c->flags=p.flags;c->shield=p.shield;
    c->invincible=p.invincible;c->travel=!!travel;c->powerup&=127;
    if(p.shield && !s->actors[0].active)spawn(s,0,1);
    if(p.invincible && !s->actors[1].active)spawn(s,1,4);
    if(travel && !s->actors[5].active)spawn(s,5,4);
    for(unsigned n=0;n<9;n++)if(s->actors[n].active){
        int result=scd_powerup_visual_step(&s->actors[n],c);assert(result>=0);
        if(result>0)s->submitted|=1u<<n;
    }
    /* A monitor later in the object pass can create, but cannot initialize or
       animate, a reserved effect slot that has already had its turn. */
    if(post_shield && !p.shield)spawn(s,0,1);
    if(post_invincible && !p.invincible)spawn(s,1,4);
    s->updates++;
}
int scd_powerup_screen(const scd_powerup_visual *s,int cx,int cy,int *x,int *y){
    *x=(int16_t)(s->x-cx);
    int wy=s->y;
    if((uint16_t)cy<0x100){if((uint16_t)wy>=0x800)wy=(int16_t)(wy-0x800);}
    else if((uint16_t)cy>=0x700 && (uint16_t)wy<0x100)wy=(int16_t)(wy+0x800);
    *y=(int16_t)(wy-cy);
    return (int16_t)(*x+s->width)>=0 && (int16_t)(*x-s->width)<320 && *y>=0 && *y<224;
}
