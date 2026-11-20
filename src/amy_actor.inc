/* PPZ Amy Rose/Main.asm. Included by objects.c for bounded actor allocation.
 * actfree: flags (source Var3E), hops (3F), pause carry (3A), heart carry (3B).
 * Heart actfree: age (3A), stopped (3C). Routine numbers retain source values. */
static void amy_facing(slot *s,sprite_status *o){
    unsigned flip=(uint16_t)o->xposi.w.h>=(uint16_t)actwk[0].xposi.w.h;
    o->cddat=(o->cddat&~1)|flip;o->actflg=(o->actflg&~1)|flip;s->flags=o->actflg&3;
}
static void amy_animate(slot *s,sprite_status *o,unsigned animation){
    o->mstno.b.h=animation;
    if(o->mstno.b.l!=animation){o->mstno.b.l=animation;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=amy_animations[animation];
    if(script[o->patcnt]==255)o->patcnt=0;
    unsigned frame=script[o->patcnt];s->frame=o->patno=frame&31;
    o->actflg=(o->actflg&~3)|(((frame>>5)^o->cddat)&3);s->flags=o->actflg&3;
    o->pattim=script[o->patcnt+1];o->patcnt+=2;
}
static int amy_in_bounds(const slot *s,const sprite_status *o){
    return o->xspeed.w<0?(uint16_t)(s->home_x-304)<(uint16_t)o->xposi.w.h:
        (uint16_t)(s->home_x+144)>=(uint16_t)o->xposi.w.h;
}
static void amy_jump(void){
    sprite_status *p=&actwk[0];short sn,cs;
    p->actfree[2]=0;control_actor=0;
    sinset((uint8_t)(p->direc.b.h-64),&sn,&cs);
    p->xspeed.w+=(cs*1664)>>8;p->yspeed.w+=(sn*1664)>>8;
    p->cddat=(p->cddat|2)&~32;p->actfree[18]=1;p->actfree[14]=0;
    p->sprvsize=19;p->sprhs=9;
    if(!(p->cddat&4)){p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;p->cddat|=4;p->mstno.b.h=2;}
    else p->cddat|=16;
}
static void amy_grab(slot *s,sprite_status *o){
    sprite_status *p=&actwk[0];
    if(!amy_in_bounds(s,o) || scd_player_get().elapsed>=590*60 || debugflag.w)return;
    int dx=(p->cddat&1)?o->xposi.w.h-p->xposi.w.h:p->xposi.w.h-o->xposi.w.h;
    int dy=p->yposi.w.h-o->yposi.w.h;
    if(dx<12 || dx>=24 || dy< -8 || dy>=8)return;
    /* A native actor already owning Sonic cannot be stolen. Death/damage
       ownership is also excluded, preventing a stale lock in those modes. */
    if((p->cddat&6) || (uint8_t)scd_word_get(p,26) || magnitude(p->xspeed.w)>=1664 || plpower_b || travel_protection || plpower_m || p->r_no0!=2 || control_actor || p->actfree[2]&1){s->state=6;return;}
    p->cddat&=~4;o->actfree[0]|=0x81;o->xspeed.w=o->yspeed.w=0;
    s->frame=o->patno=7;s->state=4;amy_idle_cursor=amy_idle_timer=0;amy_idle_pose=1;
    soundset(183);stats.amy_grabs++;
    /* Hold applies control next update, after Sonic's normal update. */
}
static void amy_main(slot *s,sprite_status *o){
    sprite_status *p=&actwk[0];amy_facing(s,o);
    if(o->actfree[0]&64)goto wall;
    if(o->actfree[0]&4){
        if(magnitude(p->xposi.w.h-o->xposi.w.h)<32)goto near;
        o->actfree[0]&=~4;
    }else if(!p->xspeed.w && magnitude(p->xposi.w.h-o->xposi.w.h)<10)goto near;
    int velocity=(int16_t)(o->xspeed.w+((o->cddat&1)?-16:16));
    if(magnitude(velocity)>=512)velocity=velocity<0?-512:512;
    o->xspeed.w=velocity;if(!amy_in_bounds(s,o))goto wall;
    int floor=emycol_d(o);if(floor>=7 || floor< -7)goto wall;
    o->yposi.w.h+=floor;o->xposi.l+=o->xspeed.w*256;
    amy_grab(s,o);amy_animate(s,o,2);return;
near:
    o->actfree[0]|=4;o->xspeed.w=0;goto align;
wall:
    o->xspeed.w=0;
    if(!(o->actfree[0]&128))goto align;
    if(!(o->actfree[0]&64)){
        if(o->actfree[1]>=3){
            unsigned carry=o->actfree[2]+4;o->actfree[2]=carry;
            if(carry>255)o->actfree[1]=0;
            amy_animate(s,o,4);return;
        }
        o->yspeed.w=-768;o->actfree[0]|=64;
    }
    o->yposi.l+=o->yspeed.w*256;o->yspeed.w+=64;
    s->frame=o->patno=o->yspeed.w<0?6:4;
    if(emycol_d(o)<0){o->yspeed.w=0;o->actfree[0]&=~64;o->actfree[1]++;}
    return;
align:
    o->yposi.w.h+=emycol_d(o);amy_animate(s,o,1);
}
static void amy_hold(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(p->r_no0!=2 || debugflag.w || (control_actor && control_actor!=i+1) || (p->actfree[2]&0xC0)){
        if(control_actor==i+1)scd_objects_release_control();
        o->actfree[0]&=~1;s->state=6;return;
    }
    control_actor=i+1;p->actfree[2]|=1;p->mstno.b.h=5;
    /* Source tests Amy's velocity, which a successful grab has cleared. */
    if(o->xspeed.w){
        p->xposi.l+=p->xspeed.w*256;p->yposi.w.h+=emycol_d(p);
        int v=p->xspeed.w;p->xspeed.w=v<0?(v+64<0?v+64:0):(v-64>0?v-64:0);
    }
    amy_facing(s,o);o->xposi.w.h=p->xposi.w.h+((p->cddat&1)?12:-12);o->yposi.w.h=p->yposi.w.h;
    if(swdata.b.l&SCD_JUMP){amy_jump();o->actfree[0]&=~1;s->state=6;return;}
    if(scd_player_get().elapsed>=590*60){amy_jump();o->actfree[0]&=~1;s->state=2;return;}
    amy_animate(s,o,3);
}
static void amy_wait(slot *s,sprite_status *o){
    o->xposi.l+=o->xspeed.w*256;o->yposi.l+=o->yspeed.w*256;o->yspeed.w+=64;
    if(o->yspeed.w>=0)s->frame=o->patno=7;
    if(emycol_d(o)<0){
        o->xspeed.w=o->yspeed.w=0;unsigned carry=o->actfree[2]+16;o->actfree[2]=carry;
        if(carry>255)s->state=2;
    }
}
static void amy_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];s->sink=0;
    if(ta_flag){amy_palette_active=0;if(control_actor==i+1)scd_objects_release_control();return;}
    switch(s->state){
    case 0:{
        s->home_x=o->xposi.w.h;amy_palette_active=1;
        unsigned aligned=0;
        /* Original loops until aligned. Bound malformed/floorless fixtures
           to one stage height; real placement resolves in a few probes. */
        for(unsigned n=0;n<128;n++){
            int floor=emycol_d(o);if(!floor){aligned=1;break;}
            o->yposi.w.h+=floor;if(o->yposi.w.h<0 || o->yposi.w.h>=2048)break;
        }
        if(!aligned){if(s->origin< SCD_PLACEMENT_CAPACITY)deferred_reload[s->origin]=1;remove_slot(i);return;}
        amy_facing(s,o);
        if(magnitude(actwk[0].xposi.w.h-o->xposi.w.h)<112)s->state=2;
        amy_animate(s,o,5);break;
    }
    case 2:amy_main(s,o);break;
    case 4:amy_hold(i);break;
    case 6:
        s->frame=o->patno=6;o->xspeed.w=(o->cddat&1)?128:-128;
        if(magnitude(o->xposi.w.h-s->home_x)>=128)o->xspeed.w=0;
        o->yspeed.w=-768;s->state=8;amy_wait(s,o);break;
    case 8:amy_wait(s,o);break;
    }
    o->r_no0=s->state;s->sink=1;
    unsigned carry=o->actfree[3]+((o->actfree[0]&1)?16:6);o->actfree[3]=carry;
    if(carry>255){
        int offset=(o->cddat&1)?-10:8;if(o->actfree[0]&1)offset=-offset;
        if(scd_objects_spawn(SCD_OBJ_AMY_HEART,o->xposi.w.h+offset,o->yposi.w.h-12,0,0)>=0)stats.amy_hearts++;
    }
}
static void amy_heart_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(!s->state){s->state=2;s->frame=o->patno=8;o->yspeed.w=-96;}
    if(!o->actfree[1]){short sn,cs;sinset((uint8_t)(o->actfree[0]*3),&sn,&cs);o->xspeed.w=sn>>2;}
    o->xposi.l+=o->xspeed.w*256;o->yposi.l+=o->yspeed.w*256;
    unsigned age=++o->actfree[0];
    if(age==20)s->frame=o->patno=9;
    if(age==110){s->frame=o->patno=10;o->xspeed.w=o->yspeed.w=0;o->actfree[1]=1;}
    if(age==120 || magnitude(o->xposi.w.h-actwk[0].xposi.w.h)>640){remove_slot(i);return;}
    s->sink=1;o->r_no0=2;
}
