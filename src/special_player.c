/* Translation of Special Stage/Objects/Sonic/Main.asm, USA motion routines.
   These primitives do not yet dispatch UFOs, stage completion or stamp contact. */
#include "special_player.h"
#include "special.h"
void scd_special_player_speed(scd_special_player *p,unsigned held,int inactive){
    if(inactive)return;
    if((held&15)==2){
        p->speed-=0x40;if((int16_t)p->speed<0x200)p->speed=0x200;
    }else{
        unsigned cap=p->top_speed;
        if(p->shoes){p->shoes--;cap=0xe00;}else if(p->routine==7)cap=0x200;
        p->speed+=0x20;if(p->speed>cap)p->speed=cap;
    }
}
void scd_special_player_rotate(scd_special_player *p,unsigned held,int inactive){
    if(inactive)return;
    if(held&8){p->yaw=(p->yaw-0x60000u)&0x1ffffff;p->scroll|=8;}
    if(held&4){p->yaw=(p->yaw+0x60000u)&0x1ffffff;p->scroll|=4;}
}
void scd_special_player_move(scd_special_player *p){
    unsigned angle=((p->yaw>>16)+0x180)&511;
    p->x=(p->x+(uint32_t)(scd_special_sine(angle+128)*(int16_t)p->speed))&0xfffffff;
    p->y=(p->y+(uint32_t)(scd_special_sine(angle)*(int16_t)p->speed))&0xfffffff;
}
int scd_special_player_jump(scd_special_player *p,unsigned tapped,int inactive){
    if(inactive || !(tapped&0x70))return 0;
    p->routine=2;p->sprite_velocity=(uint32_t)-0x80000;
    p->jump_timer=20;p->flags|=0x80;p->bump_time=0;return 1;
}
void scd_special_player_air(scd_special_player *p,unsigned held,int inactive){
    int floating=p->routine==3;
    p->sprite_y+=p->sprite_velocity;p->sprite_velocity+=floating?0x2000:0xa000;
    if(!floating && p->jump_timer){
        p->sprite_velocity+=0xa000;p->jump_timer--;
        if(held&0x70)p->sprite_velocity-=0xa000;
    }
    if((p->sprite_y>>16)>=344){
        p->routine=1;p->sprite_y=344u<<16;p->sprite_velocity=0;
        p->flags&=~(floating?0x40:0x80);
    }
    scd_special_player_rotate(p,held,inactive);
    p->z=352+4*(344-(p->sprite_y>>16));
}
void scd_special_player_spring(scd_special_player *p){
    p->routine=2;p->sprite_velocity=(uint32_t)-0x100000;p->flags|=0x80;
}
void scd_special_player_fan(scd_special_player *p){
    p->routine=3;p->sprite_velocity=(uint32_t)-0x40000;p->flags|=0x40;
}
