/* Original NTSC special-stage grounded contacts and active player states. */
#include "special_contacts.h"
#include <string.h>
void scd_special_sound(scd_special_world *w,unsigned sound){
    for(unsigned i=0;i<3;i++)if(!w->sound[i]){w->sound[i]=sound;break;}
}
static void delete_splash(scd_special_world *w){if(w->splash_id)w->splash_flags|=1;}
void scd_special_get_contacts(scd_special_player *p,const scd_special_stage *stage){
    int x=p->x>>16,y=p->y>>16;
    p->stamp_c=scd_special_stamp_type(stage,x,y,0);
    p->orientation=((unsigned)x<4096 && (unsigned)y<4096)?stage->part[1][((y>>5)*128+(x>>5))*2]>>4:0;
    p->stamp_tl=scd_special_stamp_type(stage,x-8,y-8,0);p->stamp_tr=scd_special_stamp_type(stage,x+8,y-8,0);
    p->stamp_br=scd_special_stamp_type(stage,x+8,y+8,0);p->stamp_bl=scd_special_stamp_type(stage,x-8,y+8,0);
}
void scd_special_bumper(scd_special_player *p,scd_special_sprite *s,const scd_special_art *a,scd_special_world *w){
    static const int8_t directions[16][2]={{0,0},{1,1},{-1,1},{0,1},{-1,-1},{1,-1},{-1,0},{-1,1},{1,-1},{1,0},{-1,-1},{1,1},{0,-1},{1,-1},{-1,-1},{-1,-1}};
    unsigned mask=(p->stamp_tl==1)|((p->stamp_tr==1)<<1)|((p->stamp_br==1)<<2)|((p->stamp_bl==1)<<3);
    if(!mask)return;
    uint32_t speed=((uint32_t)p->speed<<8)+0x20000;
    p->x_velocity=directions[mask][0]<0?0u-speed:directions[mask][0]?speed:0;
    p->y_velocity=directions[mask][1]<0?0u-speed:directions[mask][1]?speed:0;
    p->bump_time=16;p->routine=4;p->flags|=0x20;
    scd_special_sound(w,0xb5);scd_special_sprite_set(s,a,0,1);
}
void scd_special_contact(scd_special_player *p,scd_special_sprite *s,const scd_special_art *a,scd_special_world *w){
    scd_special_bumper(p,s,a,w);if(!w->ufo_count)return;
    switch(p->stamp_c){
    case 2:scd_special_player_fan(p);scd_special_sound(w,0xb8);delete_splash(w);break;
    case 3:
        if(!w->stopped){w->splash_id=8;if(w->time_attack)p->top_speed=0x500;}break;
    case 4:
        p->top_speed=0x500;
        if(p->speed>=0x100){for(unsigned i=0;i<8;i++)if(!w->dust[i]){w->dust[i]=0x700;break;}scd_special_sound(w,0xd6);}break;
    case 5:scd_special_player_spring(p);scd_special_sound(w,0x98);delete_splash(w);break;
    case 6:
        if(p->routine!=4 && p->routine!=7){
            p->hurt=46;p->routine=7;scd_special_sprite_set(s,a,13,1);
            unsigned old=w->rings;w->rings>>=1;unsigned lost=old-w->rings;if(lost>7)lost=7;
            for(unsigned i=7-lost;i<7;i++)w->lost_rings[i]=13;
        }break;
    case 7:case 8:{
        static const int8_t directions[8][2]={{0,-1},{-1,0},{0,1},{1,0},{0,-1},{1,0},{0,1},{-1,0}};
        int big=p->stamp_c==7;unsigned direction=(p->orientation&14)>>1;int speed=big?24:16;
        scd_special_sound(w,big?0xce:0xc3);if(big)scd_special_sprite_set(s,a,14,1);
        p->x_velocity=(p->x_velocity&65535)|((uint32_t)(uint16_t)(directions[direction][0]*speed)<<16);
        p->y_velocity=(p->y_velocity&65535)|((uint32_t)(uint16_t)(directions[direction][1]*speed)<<16);
        p->bump_time=big?20:8;p->routine=big?19:4;break;
    }
    default:break;
    }
}
static void jump(scd_special_player *p,scd_special_world *w,unsigned tapped){
    if(scd_special_player_jump(p,tapped,w->inactive)){scd_special_sound(w,0x92);delete_splash(w);}
}
void scd_special_contact_state(scd_special_player *p,scd_special_sprite *s,const scd_special_art *a,scd_special_world *w,unsigned held,unsigned tapped){
    switch(p->routine){
    case 1:scd_special_player_rotate(p,held,w->inactive);jump(p,w,tapped);break;
    case 2:case 3:scd_special_player_air(p,held,w->inactive);break;
    case 4:case 19:{
        int boosted=p->routine==19;
        p->bump_time--;
        if(!p->bump_time){p->routine=1;p->x_velocity=p->y_velocity=0;if(boosted)scd_special_sprite_set(s,a,0,1);}
        else{p->x+=p->x_velocity;p->y+=p->y_velocity;}
        scd_special_player_rotate(p,held,w->inactive);jump(p,w,tapped);break;
    }
    case 5:{ /* Unused sink. */
        uint16_t y=(p->sprite_y>>16)+4;p->sprite_y=(p->sprite_y&65535)|((uint32_t)y<<16);
        if(y>=448)p->routine=6;break;
    }
    case 7:p->hurt--;if(!p->hurt){p->routine=1;scd_special_sprite_set(s,a,0,1);}break;
    case 8:
        if((p->sprite_y>>16)<344){scd_special_player_rotate(p,held,w->inactive);jump(p,w,tapped);}
        else{p->hurt=60;scd_special_sprite_set(s,a,10,1);p->routine=9;w->inactive=1;p->speed=0;}
        break;
    case 9:
        p->hurt--;
        if(!p->hurt){w->time_stone[0]=14;w->time_stone[1]=15;w->time_stone[2]=16;p->routine=10;p->hurt=6;}
        break;
    case 10:case 11:case 12:case 13:case 14:case 15:case 16:{
        static const uint8_t timers[6]={4,5,4,5,4,5};
        p->scroll|=4;p->yaw=(p->yaw&65535)|((((p->yaw>>16)-8)&0x1ff)<<16);
        p->hurt--;if(p->hurt)break;
        unsigned i=p->routine-10;p->routine++;
        if(i<6)p->hurt=timers[i];
        scd_special_sprite_set(s,a,0x24+i,1);break;
    }
    case 18:scd_special_sprite_set(s,a,0x2b,1);break;
    case 0x15:scd_special_sprite_set(s,a,0x2c,1);p->routine=0x16;p->hurt=5;break;
    case 0x16:p->hurt--;if(!p->hurt){scd_special_sprite_set(s,a,10,1);p->routine=0x17;}break;
    default:break;
    }
}
void scd_special_splash_draw(scd_special_world *w,const scd_special_player *p,scd_special_effect *drawn){
    if(drawn)memset(drawn,0,sizeof(*drawn));
    if(!w->splash_id)return;
    if(!w->splash_routine){
        w->splash_animation=0;w->splash_frame=0;w->splash_time=1;w->splash_timer=14;w->splash_routine=1;
        scd_special_sound(w,0xa2);if(!w->time_attack)w->speedup=10;
    }
    if(w->splash_routine==1){
        w->splash_timer--;
        if(!w->splash_timer){
            if(p->stamp_c!=3)w->splash_flags|=1;
            else{w->splash_animation=1;w->splash_frame=0;w->splash_time=0;w->splash_routine=2;}
        }
    }else if(p->stamp_c!=3)w->splash_flags|=1;
    else if(!w->splash_frame)w->speedup=2;
    if(!(w->splash_flags&2)){
        w->splash_time--;
        if((int8_t)w->splash_time<0){w->splash_time=w->splash_animation?0:1;w->splash_frame++;if(w->splash_frame>=(w->splash_animation?3:7))w->splash_frame=0;}
    }
    if(w->stopped)w->splash_flags|=1;
    if(drawn)*drawn=(scd_special_effect){.x=256u<<16,.y=344u<<16,.id=w->splash_id,.routine=w->splash_routine,.flags=w->splash_flags,.animation=w->splash_animation,.frame=w->splash_frame,.time=w->splash_time,.time_copy=w->splash_animation?0:1,.timer=w->splash_timer};
    /* Original RunObject clears a deleted slot after its final DrawObject. */
    if(w->splash_flags&1){w->splash_id=w->splash_routine=w->splash_flags=w->splash_animation=w->splash_frame=w->splash_time=0;w->splash_timer=0;}
}
void scd_special_splash(scd_special_world *w,const scd_special_player *p){scd_special_splash_draw(w,p,0);}
static void timer_tick(scd_special_world *w){
    if(w->stopped || w->inactive)return;
    w->timer--;if((int32_t)w->timer<0){w->timer=0;w->speedup=0;w->stage_over=1;}
    if(w->timer<20 && !w->time_ufo)w->time_ufo=3;
    if(w->timer<15)w->sound[0]=0xdf;
}
void scd_special_timer(scd_special_world *w){
    if(!w->time_attack){
        w->timer_frames--;if(!w->timer_frames){w->timer_frames=20;timer_tick(w);}
        if(w->speedup){w->speedup--;timer_tick(w);}
    }else if(!w->stopped && !w->inactive){
        uint8_t frames=(uint8_t)w->timer+3,seconds=w->timer>>8,minutes=w->timer>>16;
        if(frames>=60){frames-=60;seconds++;if(seconds>=60){seconds-=60;minutes++;if(minutes>=10){w->timer=(9u<<16)|(59u<<8)|59;w->stage_over=1;return;}}}
        w->timer=(w->timer&0xff000000)|((uint32_t)minutes<<16)|((unsigned)seconds<<8)|frames;
    }
}
void scd_special_player_step(scd_special_player *p,scd_special_sprite *s,const scd_special_art *a,scd_special_world *w,const scd_special_stage *stage,unsigned held,unsigned tapped){
    scd_special_player_speed(p,held,w->inactive);p->flags&=~0x24;p->top_speed=0xa00;
    if(!p->routine){
        /* ObjSonic_Init writes high words and falls through to Start1. */
        const uint8_t *start=stage->part[4];
        p->sprite_y=(p->sprite_y&65535)|(344u<<16);scd_special_sprite_set(s,a,9,1);p->routine=0x14;p->speed=0;
        p->x=(p->x&65535)|((uint32_t)((start[0]<<8)|start[1])<<16);p->y=(p->y&65535)|((uint32_t)((start[2]<<8)|start[3])<<16);
        p->yaw=(p->yaw&65535)|((uint32_t)((start[4]<<8)|start[5])<<16);p->z=0x160;
    }else scd_special_contact_state(p,s,a,w,held,tapped);
    int disabled=p->flags&8;
    if(!disabled){
        if(!(p->flags&0xc0) && !w->inactive){scd_special_get_contacts(p,stage);scd_special_contact(p,s,a,w);}
        if(!(p->flags&0x20))scd_special_player_move(p);
    }
    unsigned x=p->x>>16,y=p->y>>16;
    if(!disabled && x<832)x=832;if(x>=3264)x=3264;if(y<832)y=832;if(y>=3264)y=3264;
    p->x=(p->x&65535)|(x<<16);p->y=(p->y&65535)|(y<<16);
    if(p->routine!=7 && p->routine!=19){scd_special_sprite_tilt(s,held);scd_special_sprite_choose(s,p,a,w->inactive);}
}
