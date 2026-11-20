/* Collision Chaos Act 1 Amy/Mecha Sonic scene, R3/MECASNC.C.  The placed
   emie3 actor creates Mecha Sonic; hearts and exhaust reuse their parents'
   mapping tables.  hari3x props break when Mecha Sonic reaches them. */
static void mecasnc_face(sprite_status *o,const sprite_status *p){
    o->cddat&=~1;o->actflg&=~1;
    if(o->xposi.l>=p->xposi.l){o->cddat|=1;o->actflg|=1;}
}
static void mecasnc_anim(slot *s,sprite_status *o,unsigned animation,const uint8_t *const *scripts){
    if(s->anim!=s->prev_anim){s->prev_anim=s->anim;s->anim_frame=s->anim_time=0;}
    if((int8_t)--s->anim_time>=0)return;
    const uint8_t *script=scripts[animation];
    for(;;){
        unsigned at=s->anim_frame,value=script[at];
        if(value!=255){s->frame=o->patno=value&31;s->anim_time=script[at+1];if(s->anim_time<2)s->anim_time++;s->anim_frame+=2;return;}
        s->anim_frame=0;
    }
}
static void emie_anim(slot *s,sprite_status *o){
    static const uint8_t a0[]={3,39,4,9,5,39,4,9,255};
    static const uint8_t a1[]={0,3,1,2,2,3,1,2,255};
    static const uint8_t a2[]={11,13,12,13,255};
    static const uint8_t a3[]={6,19,7,9,255};
    static const uint8_t *const scripts[]={a0,a1,a2,a3};
    mecasnc_anim(s,o,s->anim,scripts);
}
static int mecasnc_parent(unsigned actor,unsigned type){
    return actor && actor<=SCD_OBJECT_CAPACITY && pool[actor-1].type==type;
}
static void mecasnc_finish(unsigned i){emie3_ended=1;emie_palette_active=0;remove_slot(i);}
static void heart3_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(!o->r_no0){o->r_no0=2;o->actflg|=4;o->sprpri=3;o->yspeed.w=-96;s->frame=o->patno=8;}
    if(!o->actfree[18]){short sn,cs;sinset(o->actfree[16]*3,&sn,&cs);o->xspeed.w=sn/4;}
    o->xposi.l+=(int32_t)o->xspeed.w*256;o->yposi.l+=(int32_t)o->yspeed.w*256;
    if(++o->actfree[16]==20)s->frame=o->patno=9;
    if(o->actfree[16]==110){s->frame=o->patno=10;o->xspeed.w=o->yspeed.w=0;o->actfree[18]=255;}
    if(o->actfree[16]==120){remove_slot(i);return;}
    cc_object_draw(o);
}
static void emie_heart(unsigned i){
    sprite_status *o=&actwk[i+1];unsigned sum=o->actfree[17]+8;o->actfree[17]=(uint8_t)sum;
    if(sum<=255)return;
    int x=o->xposi.w.h+((o->cddat&1)?-14:12),child=spawn_from(SCD_OBJ_EMIE3,x,o->yposi.w.h-12,128,0,0);
    if(child>=0){pool[child].parent=i+1;stats.amy_hearts++;}
}
static void emie3_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(s->subtype){heart3_step(i);return;}
    if(emie3_ended){remove_slot(i);return;}
    if(!o->r_no0){
        emie_palette_active=1;o->actflg|=4;o->sprpri=1;mecasnc_face(o,p);s->anim=0;
        if(p->xposi.w.h>=o->xposi.w.h)o->r_no0=2;
        emie_anim(s,o);cc_object_draw(o);
        if(p->xposi.w.h>=1216)mecasnc_finish(i);
        return;
    }
    if(o->r_no0==2){
        if(mecasnc_parent(s->parent,SCD_OBJ_MECASNC3) && actwk[s->parent].actfree[19]){
            o->r_no0=4;soundset(125);emie_anim(s,o);emie_heart(i);cc_object_draw(o);return;
        }
        mecasnc_face(o,p);
        if((o->cddat&1) && o->xposi.w.h<128){s->anim=0;o->xspeed.w=0;emie_anim(s,o);emie_heart(i);cc_object_draw(o);return;}
        if(o->xposi.w.h<960){
            int speed=o->xspeed.w+((o->cddat&1)?-32:32);
            if(speed>512)speed=512;if(speed<-512)speed=-512;o->xspeed.w=speed;
            o->xposi.l+=(int32_t)o->xspeed.w*256;s->anim=1;
            if(o->xposi.w.h<960){emie_anim(s,o);emie_heart(i);cc_object_draw(o);return;}
        }
        s->anim=0;
        if(!mecasnc_parent(s->parent,SCD_OBJ_MECASNC3)){
            int child=spawn_from(SCD_OBJ_MECASNC3,1280,1000,0,0,0);
            if(child>=0){s->parent=child+1;pool[child].parent=i+1;}
        }
        emie_anim(s,o);emie_heart(i);
    }else{
        if(!mecasnc_parent(s->parent,SCD_OBJ_MECASNC3)){remove_slot(i);return;}
        sprite_status *m=&actwk[s->parent];int dx=(m->cddat&1)?-8:8;
        mecasnc_face(o,m);o->xposi.w.h=m->xposi.w.h+dx;o->yposi.w.h=m->yposi.w.h+4;s->anim=2;emie_anim(s,o);
    }
    cc_object_draw(o);if(p->xposi.w.h>=1216)mecasnc_finish(i);
}
static void mecasnc_fire_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(!mecasnc_parent(s->parent,SCD_OBJ_MECASNC3)){remove_slot(i);return;}
    sprite_status *m=&actwk[s->parent];
    if(!o->r_no0){o->r_no0=2;o->actflg|=4;o->sprpri=3;s->frame=o->patno=12;}
    o->xposi.w.h=m->xposi.w.h+(m->cddat&1?16:-16);o->yposi.w.h=m->yposi.w.h;
    static const uint8_t poses[]={12,15,13,15};
    if(!o->pattim){o->pattim=1;s->frame=o->patno=poses[o->patcnt++&3];}else o->pattim--;
    cc_object_draw(o);
}
static void mecasnc3_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(s->subtype){mecasnc_fire_step(i);return;}
    if(!o->r_no0){o->r_no0=2;o->actflg|=4;o->sprpri=2;o->sprvsize=32;s->frame=o->patno=14;o->actfree[16]=60;}
    if(o->r_no0==2){if(o->actfree[16])o->actfree[16]--;else{o->cddat|=1;o->actflg|=1;scd_word_set(o,33,-16);o->r_no0=4;if(o->actflg&128)soundset(202);cc_object_draw(o);return;}}
    else if(o->r_no0==4){
        o->xposi.l+=(int32_t)o->xspeed.w*256;int speed=o->xspeed.w+(int16_t)scd_word_get(o,33);if(speed<-768)speed=-768;o->xspeed.w=speed;
        int target=mecasnc_parent(s->parent,SCD_OBJ_EMIE3)?actwk[s->parent].xposi.w.h+32:992;
        if(target>=o->xposi.w.h){o->xspeed.w=0;scd_word_set(o,33,0);o->actfree[19]=255;s->anim=2;scd_word_set(o,27,o->yposi.w.h);o->r_no0=6;
            int child=spawn_from(SCD_OBJ_MECASNC3,0,0,1,0,0);if(child>=0)pool[child].parent=i+1;}
    }else if(o->r_no0==6){
        mecasnc_face(o,p);short sn,cs;sinset(o->actfree[16],&sn,&cs);o->yposi.l=(int32_t)(int16_t)scd_word_get(o,27)*65536+(int32_t)sn*1024;o->actfree[16]+=4;
        if((int8_t)o->actfree[16]<0){o->r_no0=8;o->yspeed.w=-704;scd_word_set(o,33,11);o->actfree[17]=64;o->actfree[6]=80;}
    }else if(o->r_no0==8){
        mecasnc_face(o,p);
        if(o->actfree[17]){o->xposi.l+=(int32_t)o->xspeed.w*256;o->yposi.l+=(int32_t)o->yspeed.w*256;o->yspeed.w+=(int16_t)scd_word_get(o,33);if(--o->actfree[17])goto mecasnc_draw;o->yspeed.w=0;scd_word_set(o,33,0);scd_word_set(o,27,o->yposi.w.h);}
        {short sn,cs;sinset(o->actfree[16],&sn,&cs);o->yposi.l=(int32_t)(int16_t)scd_word_get(o,27)*65536+(int32_t)sn*1024;o->actfree[16]+=4;}
        if(--o->actfree[6]==0){o->cddat&=~1;o->actflg&=~1;o->xspeed.w=0;scd_word_set(o,33,96);o->r_no0=10;}
    }else{
        o->xposi.l+=(int32_t)o->xspeed.w*256;int speed=o->xspeed.w+(int16_t)scd_word_get(o,33);if(speed>1024)speed=1024;o->xspeed.w=speed;
        if(o->xposi.w.h>=1320){mecasnc_finish(i);return;}
    }
mecasnc_draw:
    if(o->r_no0>=4){
        static const uint8_t a0[]={0,0,1,0,255},a1[]={6,1,7,1,8,1,9,1,255},a2[]={14,1,255};
        static const uint8_t *const scripts[]={a0,a1,a2};mecasnc_anim(s,o,s->anim,scripts);
    }
    cc_object_draw(o);if(p->xposi.w.h>=1216)mecasnc_finish(i);
}
static void hari3x_speed(sprite_status *o){
    static const int16_t speed[8]={512,-512,-256,-1024,-256,-512,512,-1024};
    unsigned part=o->actfree[18]*2;o->xspeed.w=speed[part];o->yspeed.w=speed[part+1];scd_word_set(o,33,96);o->actfree[16]=120;
}
static void hari3x_break(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];unsigned base=s->subtype?4:0;if(s->subtype!=0 && s->subtype!=2)base=9;
    s->frame=o->patno=4+base;
    for(unsigned part=3;part;part--){int child=spawn_from(SCD_OBJ_HARI3X,o->xposi.w.h,o->yposi.w.h,0,0,0);if(child>=0){sprite_status *d=&actwk[child+1];d->actfree[18]=part;d->patno=part+base;pool[child].frame=d->patno;d->r_no0=4;d->colino=0;d->sprpri=3;d->sprhsize=18;d->sprvsize=32;hari3x_speed(d);}}
    o->r_no0=4;o->colino=0;hari3x_speed(o);soundset(163);
}
static void hari3x_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        if(emie3_ended){remove_slot(i);return;}o->r_no0=2;o->actflg|=4;o->sprpri=3;o->sprhsize=18;o->sprvsize=8;
        if(s->subtype!=1){o->sprvsize=32;if(s->subtype){s->frame=o->patno=s->subtype==2?9:14;o->colino=134;o->sprhsize=12;}}
    }
    if(o->r_no0==4){o->xposi.l+=(int32_t)o->xspeed.w*256;o->yposi.l+=(int32_t)o->yspeed.w*256;o->yspeed.w+=(int16_t)scd_word_get(o,33);if(!--o->actfree[16]){remove_slot(i);return;}cc_object_draw(o);return;}
    if(s->subtype==1){
        if(cc_ride(i) && !plpower_a && !plpower_m && actwk[0].r_no0<4 && !scd_word_get(&actwk[0],26)){actwk[0].yposi.l-=(int32_t)actwk[0].yspeed.w*256;scd_objects_hurt(o->xposi.w.h);}
    }else{
        cc_ride(i);
        for(unsigned n=0;n<SCD_OBJECT_CAPACITY;n++)if(pool[n].type==SCD_OBJ_MECASNC3 && !pool[n].subtype){
            sprite_status *m=&actwk[n+1];int w=o->sprhsize+16,h=o->sprvsize+16;
            if(m->xposi.w.h-o->xposi.w.h+w>=0 && m->xposi.w.h-o->xposi.w.h+w<w*2 && m->yposi.w.h-o->yposi.w.h+h>=0 && m->yposi.w.h-o->yposi.w.h+h<h*2){hari3x_break(i);cc_ride_end(i);}break;
        }
    }
    cc_object_draw(o);
}
