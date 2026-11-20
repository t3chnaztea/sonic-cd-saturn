/* R3/KAMA.C: normal/damaged mantis and its two delayed, deflectable blades. */
static void kama_patchg(sprite_status *o,int blade){
    static const uint8_t walk[]={7,0,1,2,3,255},wait[]={7,5,6,255},attack[]={7,0,4,255},
        pose[]={7,7,4,255},idle[]={7,0,255},spin[]={3,0,1,2,3,4,5,255},fast[]={0,0,1,2,3,4,5,255};
    static const uint8_t *const parent[]={walk,wait,attack,pose,idle},*const child[]={spin,fast};
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=blade?child[o->mstno.b.h]:parent[o->mstno.b.h];
    o->pattim=script[0];unsigned pat=script[o->patcnt+1];
    if(pat==255){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
static void kama_move_xy(sprite_status *o){o->xposi.l+=(int32_t)o->xspeed.w*256;o->yposi.l+=(int32_t)o->yspeed.w*256;}
static void kama_spawn_blades(unsigned i){
    sprite_status *o=&actwk[i+1];if(o->userflag.b.h<0)return;
    for(unsigned n=0;n<2;n++){
        int dx=n?9:17,dy=n?6:4;
        int child=scd_objects_spawn(SCD_OBJ_KAMA_BLADE,o->xposi.w.h+((o->actflg&1)?dx:-dx),o->yposi.w.h-dy,(uint8_t)o->userflag.b.h,0);
        if(child<0)continue;
        sprite_status *b=&actwk[child+1];scd_word_set(b,26,i+1);scd_word_set(b,24,n?20:64);
        b->actfree[4]=o->actflg;stats.projectiles++;
    }
}
static void kama_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(cc_enemy_suicide(i))return;
    if(!o->r_no0){
        o->actfree[4]=(uint8_t)o->userflag.b.h;o->patno=o->userflag.b.h<0?2:1;
        o->actflg=4;o->sprpri=3;o->sprhsize=16;o->sprvsize=20;o->sproffset=9202;
        o->yspeed.w=256;o->colino=6;o->r_no0=2;
    }
    switch(o->r_no0){
    case 2:kama_move_xy(o);if(emycol_d(o)<0)o->r_no0=4;break;
    case 4:
        if(o->actflg&128){
            o->actflg&=~1;o->cddat&=~1;
            int16_t dx=o->xposi.w.h-actwk[0].xposi.w.h;
            if((uint16_t)o->xposi.w.h<(uint16_t)actwk[0].xposi.w.h){dx=(int16_t)-dx;o->actflg|=1;o->cddat|=1;}
            int16_t dy=o->yposi.w.h-actwk[0].yposi.w.h;
            if((uint16_t)o->yposi.w.h<(uint16_t)actwk[0].yposi.w.h)dy=(int16_t)-dy;
            if((uint16_t)dy<32 && (uint16_t)dx<96){o->mstno.b.h=2;kama_spawn_blades(i);scd_word_set(o,24,120);o->r_no0=6;goto attack;}
        }
        o->mstno.b.h=1;break;
    case 6:
    attack:
        scd_word_set(o,24,scd_word_get(o,24)-1);
        if(scd_word_get(o,24))break;
        o->mstno.b.h=3;scd_word_set(o,24,60);o->r_no0=8;
        /* Original state changes call the next routine in this same update. */
        __attribute__((fallthrough));
    case 8:
        scd_word_set(o,24,scd_word_get(o,24)-1);
        if(scd_word_get(o,24))break;
        o->r_no0=10;
        __attribute__((fallthrough));
    case 10:{
        o->xspeed.w=o->userflag.b.h<0?128:256;if(!(o->cddat&1))o->xspeed.w=-o->xspeed.w;
        o->mstno.b.h=0;kama_move_xy(o);
        if(dircol_l2(o)>=0 && dircol_r2(o)>=0){
            int d=emycol_d(o);if(d>=-7 && d<7){o->yposi.w.h+=d;break;}
        }
        scd_word_set(o,24,72);o->mstno.w=3;o->r_no0=12;
    }
        __attribute__((fallthrough));
    case 12:
        scd_word_set(o,24,scd_word_get(o,24)-1);
        if(!scd_word_get(o,24)){o->actflg^=1;o->cddat^=1;o->r_no0-=2;}break;
    }
    kama_patchg(o,0);cc_object_draw(o);
}
static void kama_blade_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->actflg=4;o->sprpri=1;o->sprhs=o->sprvsize=4;o->sproffset=9202;
        scd_word_set(o,27,o->xposi.w.h);o->xspeed.w=768;
        if(!(o->actfree[4]&1)){o->actflg|=1;o->cddat|=1;o->xspeed.w=-768;}
        o->r_no0=2;cc_object_draw(o);return;
    }
    if(o->r_no0==2){
        scd_word_set(o,24,scd_word_get(o,24)-1);
        if(!scd_word_get(o,24)){o->r_no0=4;o->colino=135;scd_word_set(o,28,60);}
        unsigned parent=scd_word_get(o,26);
        if(parent>SCD_OBJECT_CAPACITY || actwk[parent].actno!=SCD_OBJ_KAMA){remove_slot(i);return;}
    }else{
        kama_move_xy(o);o->yspeed.w+=(int16_t)scd_word_get(o,23);
        if(!o->patno && (o->actflg&128))soundset(185);
        sprite_status *p=actwk;
        int16_t dx=p->xposi.w.h-o->xposi.w.h+28,dy=p->yposi.w.h-o->yposi.w.h+28;
        if((plpower_m || (p->cddat&4)) && dx>=0 && dx<56 && dy>=0 && dy<56){
            o->colino=0;o->mstno.b.h=1;o->xspeed.w+=p->xspeed.w;o->yspeed.w=-2048;scd_word_set(o,23,64);
        }
        scd_word_set(o,28,scd_word_get(o,28)-1);
        if(!scd_word_get(o,28)){scd_word_set(o,28,1);o->colino=0;}
    }
    kama_patchg(o,1);cc_object_draw(o);
}
