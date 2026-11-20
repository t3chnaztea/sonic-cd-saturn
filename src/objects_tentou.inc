/* R3/TENTOU.C: terrain-following hover enemy and its falling, timed bombs. */
static int32_t tentou_long(const sprite_status *o,unsigned byte){
    unsigned word=23+byte/2;
    return (int32_t)((uint32_t)scd_word_get(o,word)|((uint32_t)scd_word_get(o,word+1)<<16));
}
static void tentou_set_long(sprite_status *o,unsigned byte,int32_t value){
    unsigned word=23+byte/2;scd_word_set(o,word,value);scd_word_set(o,word+1,(uint32_t)value>>16);
}
static void tentou_patchg(sprite_status *o){
    static const uint8_t fly[]={3,0,1,2,255},bomb[]={1,0,1,255};
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=o->userflag.b.h>0?bomb:fly;
    o->pattim=script[0];unsigned pat=script[o->patcnt+1];
    if(pat==255){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
static void tentou_hover(sprite_status *o){
    unsigned timer=(uint16_t)(scd_word_get(o,29)+1);scd_word_set(o,29,timer);
    o->yposi.l+=tentou_long(o,4);
    if(!(timer&15))tentou_set_long(o,4,-tentou_long(o,4));
}
static void tentou_bomb_die(sprite_status *o){
    /* Original tentou1 still calls DrawObject with the bomb mapping in this
       update. Switch the native view to the shared explosion on the next one. */
    o->actno=SCD_OBJ_EXPLOSION;o->r_no0=0;o->r_no1=1;
    if(o->actflg&128)soundset(158);
}
static void cc_bomb_explosion_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->r_no0==4){remove_slot(i);return;}
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->sprpri=1;o->sproffset=34432;
        if(o->userflag.b.l)o->sproffset&=32767;
        o->colino=o->patcnt=o->pattim=0;o->mstno.w=o->userflag.b.h?256:0;
    }
    /* PLAYSUB.C/TBL1.C: the terminal update keeps the last visible pose;
       baku_die removes the non-enemy explosion on the following update. */
    static const uint8_t normal[]={3,0,5,6,3,4,252},alternate[]={3,0,1,2,3,4,252};
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim<0){
        const uint8_t *script=o->mstno.b.h?alternate:normal;
        o->pattim=script[0];unsigned pat=script[o->patcnt+1];
        if(pat==252)o->r_no0+=2;
        else{o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;}
    }
    pool[i].frame=o->patno;pool[i].flags=o->actflg&3;
}
static void tentou_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->actno==SCD_OBJ_EXPLOSION){
        pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=3;
        pool[i].state=pool[i].frame=pool[i].cooldown=0;cc_bomb_explosion_step(i);return;
    }
    if(o->userflag.b.h>0){
        if(!o->r_no0){
            o->r_no0=2;o->actflg|=4;o->sprpri=2;o->colino=139;
            o->sprhs=o->sprhsize=o->sprvsize=6;o->sproffset=1173;
        }
        switch(o->r_no0){
        case 2:{
            if(o->colicnt){tentou_bomb_die(o);return;}
            o->yposi.l+=65536;int d=emycol_d(o);
            if(d<0){o->yposi.w.h+=d;scd_word_set(o,23,120);o->r_no0=4;}
            return;
        }
        case 4:case 6:{
            if(o->colicnt){tentou_bomb_die(o);return;}
            unsigned state=o->r_no0,timer=(uint16_t)(scd_word_get(o,23)-1);scd_word_set(o,23,timer);
            if(!timer){o->r_no0+=2;if(state==4)scd_word_set(o,23,120);}
            if(state==6)tentou_patchg(o);return;
        }
        case 8:tentou_bomb_die(o);return;
        }
        return;
    }
    if(cc_enemy_suicide(i))return;
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=132;o->sprpri=1;o->colino=6;
        o->sprhsize=o->sprvsize=14;o->sproffset=42090;
        if(o->userflag.w>=0)o->actfree[21]=255;
    }
    switch(o->r_no0){
    case 2:{
        o->yposi.l+=65536;int16_t d=(int16_t)(emycol_d(o)-8);
        if(d<=0){
            /* Preserve the original SUB correction here (LR uses ADD). */
            o->yposi.w.h-=d;tentou_set_long(o,8,o->yposi.l);tentou_set_long(o,4,12288);
            scd_word_set(o,29,8);o->r_no0+=2;if(tentou_long(o,0))o->r_no0+=2;
        }
        break;
    }
    case 4:{
        tentou_hover(o);
        /* Sega CD R32A $20C270: subi.w #-80 / subi.w #160 / bcc, so the window
           is -80 <= d < 80 (the PC build's |d| <= 80 also takes d = 80). */
        int16_t dy=o->yposi.w.h-actwk[0].yposi.w.h;
        if((uint16_t)(dy+80)>=160)break;
        int16_t dx=o->xposi.w.h-actwk[0].xposi.w.h;
        if((uint16_t)(dx+80)>=160)break;
        o->r_no0+=2;tentou_set_long(o,0,-49152);
        if(dx>=0){o->actflg^=1;o->cddat^=1;tentou_set_long(o,0,49152);}break;
    }
    case 6:{
        o->xposi.l+=tentou_long(o,0);o->yposi.l=tentou_long(o,8);
        int d=tentou_long(o,0)>=0?emycol_r(o,o->sprhs):emycol_l(o,o->sprhs);
        if(d<0){o->r_no0+=2;break;}
        d=emycol_d(o);
        if(d>=16){o->r_no0+=4;tentou_hover(o);tentou_set_long(o,8,o->yposi.l);break;}
        o->yposi.w.h+=d-8;tentou_set_long(o,8,o->yposi.l);tentou_hover(o);
        if(o->actfree[21]){
            unsigned timer=scd_word_get(o,29)&127;scd_word_set(o,29,timer);
            if(!timer){
                int child=scd_objects_spawn(SCD_OBJ_TENTOU,o->xposi.w.h,o->yposi.w.h+16,1,0);
                if(child>=0){
                    actwk[child+1].xposi.l=o->xposi.l;actwk[child+1].yposi.l=o->yposi.l;
                    actwk[child+1].yposi.w.h+=16;stats.projectiles++;
                }
            }
        }
        break;
    }
    case 8:o->yposi.l-=32768;break;
    case 10:{
        o->xposi.l+=tentou_long(o,0);
        int16_t x=o->xposi.w.h-o->sprhsize;if(tentou_long(o,0)>0)x+=o->sprhsize*2;
        if(emycol_d2(o,x)>=16)o->r_no0-=8;break;
    }
    }
    tentou_patchg(o);
}
