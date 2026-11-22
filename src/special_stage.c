/* Original special-stage RunObjects: priority-one effects, Sonic and shadow,
   priority-two item/rings/explosions/UFOs, Draw3DObjects, UFO shadows, then
   UpdateTimer with SpawnTimeUFO. Native adaptations are marked. */
#include "special_stage.h"
#include <string.h>
static uint32_t high(uint32_t value,uint16_t word){return (value&65535)|((uint32_t)word<<16);}
/* SetObjAnim (reset) / ChgObjAnim (keep frame). */
static void animation_set(const scd_special_art *art,unsigned pack,uint8_t *frame,uint8_t *time,uint8_t *time_copy,int reset){
    if(reset)*frame=0;
    *time=*time_copy=art->data[art->animation_offset+pack*4+1];
}
static void record(scd_special_stage_state *st,unsigned kind,unsigned animation,unsigned frame,unsigned palette,int visible,unsigned object,uint32_t x,uint32_t y){
    if(st->draw_count>=SCD_SPECIAL_DRAWS)return;
    st->draws[st->draw_count++]=(scd_special_draw){(int16_t)(x>>16),(int16_t)(y>>16),kind,animation,frame,palette,visible!=0,object};
}
/* DrawObject: animate unless flag 1, draw unless flag 2. */
static void draw_pack(scd_special_stage_state *st,const scd_special_art *art,unsigned animation,uint8_t flags,uint8_t *frame,uint8_t *time,uint8_t *art_flag,uint32_t x,uint32_t y,unsigned palette,unsigned object){
    scd_special_sprite sprite={.animation=animation,.frame=*frame,.time=*time,.art=*art_flag};
    scd_special_player owner={.flags=flags};scd_special_pose pose;
    int visible=!scd_special_sprite_advance(&sprite,&owner,art,&pose);
    *frame=sprite.frame;*time=sprite.time;*art_flag=sprite.art;
    record(st,SCD_SPECIAL_DRAW_UFX,animation,sprite.frame,palette,visible,object,x,y);
}
static void record_effect(scd_special_stage_state *st,unsigned kind,unsigned animation,unsigned palette,const scd_special_effect *e,unsigned object){
    if(e->id)record(st,kind,animation,e->frame,palette,!(e->flags&4),object,e->x,e->y);
}
static void time_stone(scd_special_stage_state *st,unsigned i,scd_special_world *w,scd_special_player *p,const scd_special_art *ufx){
    scd_special_effect *e=st->time_stone+i;
    if(!e->id)return;
    if(!i){
        switch(e->routine){
        case 0:
            e->animation=0;animation_set(ufx,31,&e->frame,&e->time,&e->time_copy,1);
            e->x=high(e->x,257);e->y=high(e->y,112);e->timer=30;e->routine=1;
            /* fall through */
        case 1:e->timer--;if(!e->timer)e->routine=2;break;
        case 2:{
            uint16_t y=(e->y>>16)+4;e->y=high(e->y,y);
            if(y>=336){e->routine=3;st->time_stone[1].flags|=1;st->time_stone[2].flags|=1;e->timer=60;p->routine=18;scd_special_sound(w,0xd9);}
            break;
        }
        default:e->timer--;if(!e->timer)w->got_time_stone=1;break;
        }
    }else{
        if(!e->routine){e->animation=i;animation_set(ufx,31+i,&e->frame,&e->time,&e->time_copy,1);e->routine=1;}
        e->x=high(e->x,st->time_stone[0].x>>16);e->y=high(e->y,(uint16_t)((st->time_stone[0].y>>16)-16*i));
    }
    draw_pack(st,ufx,31+e->animation,e->flags,&e->frame,&e->time,&e->art,e->x,e->y,3,3+i);
    if(e->flags&1)memset(e,0,sizeof(*e));
}
/* ID 0xA runs ObjTitleCardText and ID 0xB ObjTitleCardBar (source slot names
   are swapped). Positions are sprite high words. */
static void title_card(scd_special_stage_state *st,unsigned i,scd_special_world *w,scd_special_player *p,const scd_special_art *ufx){
    scd_special_effect *e=st->title+i;
    if(!e->id)return;
    uint16_t v;
    if(!i){
        switch(e->routine){
        case 0:
            e->x=high(e->x,456);e->y=high(e->y,240);e->animation=0;animation_set(ufx,35,&e->frame,&e->time,&e->time_copy,1);e->routine=1;
            /* fall through */
        case 1:v=(e->x>>16)-32;e->x=high(e->x,v);if(v<=312){e->x=high(e->x,312);e->timer=80;e->routine=2;}break;
        case 2:e->timer--;if(!e->timer)e->routine=3;break;
        default:v=(e->x>>16)+32;e->x=high(e->x,v);if(v>464)e->flags|=1;break;
        }
        draw_pack(st,ufx,35+e->animation,e->flags,&e->frame,&e->time,&e->art,e->x,e->y,0,44);
    }else{
        switch(e->routine){
        case 0:
            e->x=high(e->x,244);e->y=high(e->y,32);e->animation=0;animation_set(ufx,34,&e->frame,&e->time,&e->time_copy,1);e->routine=1;
            /* fall through */
        case 1:v=(e->y>>16)+32;e->y=high(e->y,v);if(v>=240){e->y=high(e->y,240);e->timer=80;e->routine=2;}break;
        case 2:e->timer--;if(!e->timer)e->routine=3;if(e->timer==50)p->routine=0x15;break;
        case 3:v=(e->y>>16)-32;e->y=high(e->y,v);if((int16_t)v<0){e->timer=3;e->flags|=4;e->routine=4;p->routine=1;}break;
        default:e->timer--;if(!e->timer){e->flags|=1;w->inactive=0;}break;
        }
        draw_pack(st,ufx,34+e->animation,e->flags,&e->frame,&e->time,&e->art,e->x,e->y,0,45);
    }
    if(e->flags&1)memset(e,0,sizeof(*e));
}
static unsigned ufo_base(const scd_special_ufo_actor *a){return a->u.id==3 || !a->u.item?0:10;}
static void ufo_animation(scd_special_ufo_actor *a,const scd_special_art *ufx,unsigned animation,int reset){
    a->animation=animation;animation_set(ufx,ufo_base(a)+animation,&a->frame,&a->time,&a->time_copy,reset);
}
static void ufo_explode(scd_special_stage_state *st,scd_special_ufo_actor *a){
    scd_special_ufo *u=&a->u;
    uint16_t x=(u->sprite_x>>16)-4;if(!a->explode_dir)x+=8;
    u->sprite_x=high(u->sprite_x,x);u->sprite_y=high(u->sprite_y,(uint16_t)((u->sprite_y>>16)+1));
    u->flags&=(uint8_t)~4;
    a->timer--;if(!a->timer)u->flags|=1;
    if(a->timer&1)return;
    int slot=scd_special_explosion_slot(st->explosions);
    if(slot<0)return;
    scd_special_effect *e=st->explosions+slot;e->id=12;
    /* Source subtracts the X offset from Y as well; D1's copy is unused. */
    unsigned r=scd_special_random(&st->effects.context)&31;
    e->x=high(e->x,(uint16_t)((u->sprite_x>>16)-16+r));e->y=high(e->y,(uint16_t)((u->sprite_y>>16)-r));
}
static void ufo(scd_special_stage_state *st,unsigned i,scd_special_world *w,scd_special_player *p,const scd_special_art *ufx,unsigned yaw){
    scd_special_ufo_actor *a=st->ufos+i;scd_special_ufo *u=&a->u;
    if(!u->id)return;
    int time=u->id==3;scd_special_ufo_path path;
    scd_special_ufo_path_get(&st->paths,time?48:st->stage*6+i,&path);
    switch(a->routine){
    case 0:
        scd_special_ufo_follow(u,&path);
        u->z=p->z-0x140;
        if(!time){a->ufo_animation=0;ufo_animation(a,ufx,0,1);}
        a->draw_delay=2;a->routine=1;
        if(time)scd_special_sound(w,0xbc);
        /* fall through */
    case 1:{
        scd_special_ufo_move(u,&path);
        /* ObjUFO_Draw: Z-buffer level by distance, then distance animation. */
        uint32_t distance=scd_special_ufo_distance(u->x>>16,u->y>>16,p->x>>16,p->y>>16);
        unsigned level=(distance>=0x1000?0xfff:distance)>>6,animation=scd_special_ufo_animation(distance);
        if(st->zcount[level]<7)st->zbuffer[level][st->zcount[level]++]=30+i;else st->zbuffer[level][6]=30+i;
        if(animation!=a->ufo_animation){a->ufo_animation=animation;ufo_animation(a,ufx,animation,0);}
        scd_special_ufo_project(u,p->x>>16,p->y>>16,yaw);
        scd_special_ufo_collision(u,p->x>>16,p->y>>16,p->z,1,&st->sonic_collision);
        if(!u->player_collision || (time && w->stopped))break;
        if(!time){if(w->ufo_count<2)w->stopped=1;w->ufo_count--;}
        a->routine=2;st->shadows[i].flags|=1;a->timer=60;
        a->explode_dir=scd_special_random(&st->effects.context)&1;
        ufo_animation(a,ufx,0,1);
        if(time)w->timer+=30;
        st->item.id=4;st->item.x=high(st->item.x,u->sprite_x>>16);st->item.y=high(st->item.y,u->sprite_y>>16);
        st->item.timer=(st->item.timer&0xff00)|(time?3:u->item);
        if(time)break;
        if(u->item==1){p->shoes=200;w->ring_bonus=20;}
        else{uint16_t bonus=w->ring_bonus,rings=w->rings+bonus;w->ring_bonus=bonus*2;w->rings=rings>999?999:rings;}
        break;
    }
    default:ufo_explode(st,a);break;
    }
    u->z=p->z-0x140;
    if(a->draw_delay){a->draw_delay--;u->flags|=4;}
    if(u->flags&1)memset(a,0,sizeof(*a));
}
static void shadow(scd_special_stage_state *st,unsigned i,const scd_special_player *p,const scd_special_art *ufx,unsigned yaw){
    scd_special_shadow *h=st->shadows+i;
    if(!h->id)return;
    if(!h->routine){h->shadow_animation=h->animation=0;animation_set(ufx,20,&h->frame,&h->time,&h->time_copy,1);h->routine=1;}
    scd_special_ufo *parent=&st->ufos[i].u;
    h->x=high(h->x,parent->x>>16);h->y=high(h->y,parent->y>>16);
    parent->flags|=4;if(!(h->flags&4))parent->flags&=(uint8_t)~4;
    h->z=p->z;
    /* Its Z-buffer entry follows Draw3DObjects and is never drawn. */
    unsigned animation=scd_special_ufo_animation(scd_special_ufo_distance(h->x>>16,h->y>>16,p->x>>16,p->y>>16));
    if(animation!=h->shadow_animation){h->shadow_animation=h->animation=animation;animation_set(ufx,20+animation,&h->frame,&h->time,&h->time_copy,0);}
    scd_special_project(p->x>>16,p->y>>16,h->x>>16,h->y>>16,h->z,yaw,&h->sprite_x,&h->sprite_y);
    scd_special_on_screen(&h->flags,h->sprite_x,h->sprite_y);
    draw_pack(st,ufx,20+h->animation,h->flags,&h->frame,&h->time,&h->art,h->sprite_x,h->sprite_y,3,37+i);
    if(h->flags&1)memset(h,0,sizeof(*h));
}
int scd_special_stage_reset(scd_special_stage_state *st,scd_special_world *w,const void *paths,size_t size,unsigned stage){
    memset(st,0,sizeof(*st));
    if(stage>=8 || scd_special_ufo_paths_open(&st->paths,paths,size))return -1;
    st->stage=stage;
    for(unsigned i=0;i<6;i++){
        scd_special_ufo_path path;scd_special_ufo_path_get(&st->paths,stage*6+i,&path);
        st->ufos[i].u.id=2;st->ufos[i].u.item=path.data[0];st->ufos[i].u.unknown=path.data[1];st->ufos[i].u.path_offset=2;
        st->shadows[i].id=5;
    }
    st->sonic_shadow.id=6;w->ufo_count=6;w->ring_bonus=20;w->time_ufo=0;
    return 0;
}
void scd_special_stage_start(scd_special_stage_state *st,scd_special_world *w,scd_special_player *p,scd_special_sprite *s){
    memset(p,0,sizeof(*p));memset(s,0,sizeof(*s));
    st->title[0].id=0xa;st->title[1].id=0xb;w->inactive=1;
}
int scd_special_stage_update(scd_special_stage_state *st,scd_special_world *w,scd_special_player *p,scd_special_sprite *s,const scd_special_art *sonic_art,const scd_special_art *ufx,const scd_special_art *sfx,const scd_special_stage *stage,unsigned held,unsigned tapped,unsigned yaw,scd_special_pose *pose,int *visible){
    *visible=0;
    if(!sonic_art->data || !ufx->data || ufx->animations<36 || !sfx->data || sfx->animations<8 || !st->paths.data)return -1;
    scd_special_effect_pool *f=&st->effects;
    memset(st->zcount,0,sizeof(st->zcount));st->draw_count=0;
    /* Priority one: splash, unspawned title card, time stone, sparkles, dust. */
    scd_special_splash_draw(w,p,f->drawn);
    record_effect(st,SCD_SPECIAL_DRAW_SFX,f->drawn[0].animation,0,f->drawn,2);
    for(unsigned i=0;i<2;i++)title_card(st,i,w,p,ufx);
    for(unsigned i=0;i<3;i++){st->time_stone[i].id=w->time_stone[i];time_stone(st,i,w,p,ufx);w->time_stone[i]=st->time_stone[i].id;}
    for(unsigned i=0;i<8;i++){
        f->dust[i].id=w->dust[i]>>8;f->dust[i].routine=w->dust[i];
        scd_special_dust(f->dust+i,&f->context,f->previous_held,f->drawn+1+i);
        w->dust[i]=((unsigned)f->dust[i].id<<8)|f->dust[i].routine;
        record_effect(st,SCD_SPECIAL_DRAW_SFX,2,0,f->drawn+1+i,6+i);
    }
    /* Sonic. CheckWin follows CheckJump in routines 1/4; only the wrapper's
       bumper can replace its routine 8, so applying it afterwards (unless
       this update bumped) yields the original state. */
    unsigned entry=p->routine;
    scd_special_player_step(p,s,sonic_art,w,stage,held,tapped);
    if((entry==1 || entry==4) && !w->ufo_count){
        if(!(p->flags&0x20))p->routine=8;
        if(st->ufos[6].u.id)st->ufos[6].u.flags|=1;
        if(st->shadows[6].id)st->shadows[6].flags|=1;
    }
    /* Sonic writes spawn IDs into already-run priority-one slots. */
    for(unsigned i=0;i<8;i++){f->dust[i].id=w->dust[i]>>8;f->dust[i].routine=w->dust[i];}
    for(unsigned i=0;i<3;i++)st->time_stone[i].id=w->time_stone[i];
    *visible=!scd_special_sprite_advance(s,p,sonic_art,pose);
    record(st,SCD_SPECIAL_DRAW_SONIC,s->animation,s->frame,0,*visible,0,256u<<16,p->sprite_y);
    st->sonic_collision=0;
    scd_special_shadow *h=&st->sonic_shadow;
    if(h->id){
        if(!h->routine){h->shadow_animation=h->animation=5;animation_set(ufx,25,&h->frame,&h->time,&h->time_copy,1);h->routine=1;}
        h->x=high(h->x,p->x>>16);h->y=high(h->y,p->y>>16);h->z=p->z;
        scd_special_project(p->x>>16,p->y>>16,h->x>>16,h->y>>16,h->z,yaw,&h->sprite_x,&h->sprite_y);
        draw_pack(st,ufx,20+h->animation,h->flags,&h->frame,&h->time,&h->art,h->sprite_x,h->sprite_y,3,1);
    }
    /* Priority two. CheckBumper and the Sonic shadow leave this D1 value;
       item deletion can clear it before a new ring reads its high word. */
    f->context.d1=((((uint32_t)p->speed<<8)+0x20000)&0xffff0000)|1;
    unsigned sound;scd_special_effect drawn;
    scd_special_item(&st->item,&f->context,&drawn,&sound);if(sound)scd_special_sound(w,sound);
    record_effect(st,SCD_SPECIAL_DRAW_SFX,3+drawn.animation,0,&drawn,14);
    for(unsigned i=0;i<7;i++){
        f->rings[i].id=w->lost_rings[i];
        scd_special_lost_ring(f->rings+i,&f->context,256u<<16,p->sprite_y,f->drawn+9+i,&sound);
        w->lost_rings[i]=f->rings[i].id;if(sound)scd_special_sound(w,sound);
        record_effect(st,SCD_SPECIAL_DRAW_SFX,7,3,f->drawn+9+i,15+i);
    }
    for(unsigned i=0;i<8;i++){
        scd_special_explosion(st->explosions+i,&f->context,&drawn,&sound);if(sound)scd_special_sound(w,sound);
        record_effect(st,SCD_SPECIAL_DRAW_UFX,30,0,&drawn,22+i);
    }
    for(unsigned i=0;i<7;i++)ufo(st,i,w,p,ufx,yaw);
    for(unsigned level=0;level<64;level++)for(unsigned k=0;k<st->zcount[level];k++){
        unsigned object=st->zbuffer[level][k];scd_special_ufo_actor *a=st->ufos+(object-30);
        /* Native adaptation: a slot cleared after queuing (CheckWin's time
           UFO) has no mappings; the original draws from address zero. */
        if(!a->u.id)continue;
        draw_pack(st,ufx,ufo_base(a)+a->animation,a->u.flags,&a->frame,&a->time,&a->art,a->u.sprite_x,a->u.sprite_y,a->u.id==3?0:3,object);
    }
    for(unsigned i=0;i<7;i++)shadow(st,i,p,ufx,yaw);
    f->previous_held=held;
    w->time_ufo=st->ufos[6].u.id;
    scd_special_timer(w);
    if(w->time_ufo==3 && !st->ufos[6].u.id){
        scd_special_ufo_path path;scd_special_ufo_path_get(&st->paths,48,&path);
        scd_special_ufo *u=&st->ufos[6].u;u->id=3;u->item=path.data[0];u->unknown=path.data[1];u->path_offset=2;
        st->shadows[6].id=5;
    }
    w->time_ufo=st->ufos[6].u.id;
    if(w->time_attack || (w->mode&1)){
        unsigned alive=0;for(unsigned i=0;i<6;i++)alive|=st->ufos[i].u.id;
        if(!alive)w->stage_over=1;
    }
    return 0;
}
typedef struct {uint32_t *out,hash;unsigned count;} word_sink;
static void emit(word_sink *k,uint32_t value){
    if(k->out)k->out[k->count]=value;
    k->count++;
    for(int shift=24;shift>=0;shift-=8)k->hash=(k->hash^((value>>shift)&255))*16777619u;
}
static void emit_effect(word_sink *k,const scd_special_effect *e){
    const uint32_t v[]={e->x,e->y,e->x_velocity,e->y_velocity,e->timer,e->id,e->routine,e->flags,e->animation,e->frame,e->time,e->time_copy,e->art,e->item_type};
    for(unsigned i=0;i<14;i++)emit(k,v[i]);
}
static void emit_shadow(word_sink *k,const scd_special_shadow *h){
    const uint32_t v[]={h->x,h->y,h->sprite_x,h->sprite_y,h->z,h->id,h->routine,h->flags,h->animation,h->shadow_animation,h->frame,h->time,h->time_copy,h->art};
    for(unsigned i=0;i<14;i++)emit(k,v[i]);
}
static void emit_state(word_sink *k,const scd_special_stage_state *st){
    emit_effect(k,&st->item);
    for(unsigned i=0;i<8;i++)emit_effect(k,st->explosions+i);
    for(unsigned i=0;i<3;i++)emit_effect(k,st->time_stone+i);
    for(unsigned i=0;i<7;i++){
        const scd_special_ufo_actor *a=st->ufos+i;const scd_special_ufo *u=&a->u;
        const uint32_t v[]={u->x,u->y,u->x_velocity,u->y_velocity,u->sprite_x,u->sprite_y,u->path_offset,u->path_time,u->z,u->id,u->flags,u->player_collision,u->item,u->unknown,a->timer,a->routine,a->animation,a->ufo_animation,a->explode_dir,a->draw_delay,a->frame,a->time,a->time_copy,a->art};
        for(unsigned n=0;n<24;n++)emit(k,v[n]);
    }
    for(unsigned i=0;i<7;i++)emit_shadow(k,st->shadows+i);
    emit_shadow(k,&st->sonic_shadow);
    for(unsigned i=0;i<2;i++)emit_effect(k,st->title+i);
    emit(k,st->sonic_collision);emit(k,st->draw_count);
    for(unsigned i=0;i<st->draw_count;i++){
        const scd_special_draw *d=st->draws+i;
        const uint32_t v[]={(uint16_t)d->x,(uint16_t)d->y,d->kind,d->animation,d->frame,d->palette,d->visible,d->object};
        for(unsigned n=0;n<8;n++)emit(k,v[n]);
    }
}
unsigned scd_special_stage_words(const scd_special_stage_state *st,uint32_t *words){
    word_sink k={words,2166136261u,0};emit_state(&k,st);return k.count;
}
uint32_t scd_special_stage_hash(const scd_special_stage_state *st){
    word_sink k={0,2166136261u,0};emit_state(&k,st);return k.hash;
}
