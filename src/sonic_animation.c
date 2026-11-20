/* Level/_Objects/Sonic/Main.asm ObjSonic_Animate, normal-size and miniature
   (miniSonic, R8 shrink beam) branches.
   Use explicit 8/16-bit arithmetic for the original 68000 wrap semantics. */
#include "sonic_animation.h"
#include "sonic-animation.inc"

static void flip(scd_sonic_animation *s,uint8_t flags){
    s->sprite_flags=(s->sprite_flags&252)|(flags&1);
}
static int script(scd_sonic_animation *s,unsigned id){
    unsigned index=1u+s->cursor;
    if(index>=sonic_animation_sizes[id])return -1;
    const uint8_t *data=sonic_animations[id];uint8_t value=data[index];
    if(value<253){s->mapping=value;s->cursor++;return 0;}
    if(value==255){s->cursor=1;s->mapping=data[1];return 0;}
    if(index+1>=sonic_animation_sizes[id])return -1;
    if(value==253){s->animation=data[index+1];return 0;}
    /* Loop back is byte-sized subtraction, then fetch and advance. */
    uint8_t cursor=(uint8_t)(s->cursor-data[index+1]);
    if(1u+cursor>=sonic_animation_sizes[id])return -1;
    s->mapping=data[1u+cursor];s->cursor=(uint8_t)(cursor+1);return 0;
}
/* ObjSonic_GetMiniAnim .MiniAnims (Main.asm:2961; PLAYER.C little_patchg). */
static const uint8_t mini_anims[60]={33,24,35,35,39,31,38,40,32,9,10,11,12,36,14,15,40,17,18,19,
    20,21,22,23,24,25,37,37,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,48,44,45,46,47,0,0,
    0,0,0,0,0,0,57,0,0,0};
static int animate(scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control,int mini)
{
    scd_sonic_animation s=*state;unsigned id=s.animation;int rolled=0;
    if(id>=60)return -1;
    if(s.animation!=s.previous){s.previous=s.animation;s.cursor=s.timer=0;}
    if(mini)id=mini_anims[id];
    uint8_t command=sonic_animations[id][0],offset=0;
    if(command<128)flip(&s,flags);
    if((int8_t)--s.timer>=0){*state=s;return 0;}
    if(command<128)s.timer=command;
    else if(command==255 && mini){
        /* .MiniSonicRun: steep angles curl Sonic up (the caller sets the
           rolling flag and the 10/5 radii) and run the mini roll. */
        uint8_t direction=(uint8_t)(((flags&1)?angle:(uint8_t)~angle)+16);
        flip(&s,flags);
        if((uint8_t)(direction+48)>=96){rolled=1;command=254;}
        else{
            uint16_t speed=ground_speed<0?(uint16_t)-(uint16_t)ground_speed:(uint16_t)ground_speed;
            id=speed>=1536?34:33;
            int16_t duration=(int16_t)(2048-speed);
            s.timer=duration<0?0:(uint16_t)duration>>8;
        }
    }
    else if(command==255){
        uint8_t direction=(flags&1)?angle:(uint8_t)~angle;
        direction+=(control&2)?8:16;
        s.sprite_flags=(s.sprite_flags&252)|((flags&1)^((direction&128)?3:0));
        if(flags&32)command=253;
        else{
            uint16_t speed=ground_speed<0?(uint16_t)-(uint16_t)ground_speed:(uint16_t)ground_speed;
            if(control&2){id=53;offset=((direction>>4)<<1)&14;}
            else{
                offset=(direction>>4)&6;
                if(speed>=2560)id=49;
                else if(speed>=1536)id=1;
                else{id=0;offset+=offset/2;}
            }
            offset*=2;
            int16_t duration=(int16_t)(2048-speed);
            s.timer=duration<0?0:(uint16_t)duration>>8;
        }
    }
    if(command==254){
        uint16_t speed=ground_speed<0?(uint16_t)-(uint16_t)ground_speed:(uint16_t)ground_speed;
        if(mini)id=35;
        else if(control&2)id=((uint8_t)(angle+16)&192)?54:3;
        else id=speed>=1536?3:2;
        int16_t duration=(int16_t)(1024-speed);
        s.timer=duration<0?0:(uint16_t)duration>>8;flip(&s,flags);
    }else if(command==253){
        int16_t negative=ground_speed>=0?(int16_t)-(uint16_t)ground_speed:ground_speed;
        int16_t duration=(int16_t)(negative+2048);
        s.timer=duration<0?0:(uint16_t)duration>>6;id=mini?39:4;flip(&s,flags);
    }else if(command>=128 && command!=255){
        /* Frozen scripts are controlled externally, e.g. the spinning disc. */
        if(1u+s.cursor>=sonic_animation_sizes[id])return -1;
        s.mapping=sonic_animations[id][1u+s.cursor];s.timer=0;*state=s;return 0;
    }
    if(script(&s,id))return -1;
    s.mapping+=offset;*state=s;return rolled;
}
int scd_sonic_animate(scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control){
    return animate(state,ground_speed,angle,flags,control,0);
}
int scd_sonic_animate_mini(scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control){
    return animate(state,ground_speed,angle,flags,control,1);
}
/* The mapping the next timer expiry selects if the animation, speed, angle,
   flags and control stay as given; -1 when it cannot be predicted (invalid
   state or a pending animation change). Rendering uses it only to decode
   that pose early; it never changes the actor. */
int scd_sonic_animation_next(const scd_sonic_animation *state,int16_t ground_speed,
    uint8_t angle,uint8_t flags,uint8_t control,int mini){
    scd_sonic_animation s=*state;
    if(s.animation>=60 || s.animation!=s.previous)return -1;
    s.timer=0;
    if(animate(&s,ground_speed,angle,flags,control,mini) || s.animation!=state->animation)return -1;
    return s.mapping;
}
