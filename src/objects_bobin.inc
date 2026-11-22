/* Collision Chaos round bumper, R3/BOBIN.C bobininit/bobinmove.
   Actor scratch words use the original PC offsets through scd_word_*; the
   16.16 motion value occupies scratch bytes 0..3 (words 23 and 24).
   Included after slot/pool and release_rider are defined. */
static void bobin_patchg(sprite_status *o){
    static const uint8_t idle[]={15,0,255},hit[]={4,1,2,1,2,253,0},flip[]={1,1,2,1,253,0};
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=o->mstno.b.h?(o->actno==SCD_OBJ_FRIP?flip:hit):idle;
    o->pattim=script[0];unsigned pat=script[o->patcnt+1];
    if(pat==253){o->mstno.b.h=script[o->patcnt+2];return;}
    if(pat==255){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
static void bobin_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    /* The player's touch (cc_touch_arbitrate, in pcol after his movement)
       precedes the object's first dispatch and its motion. An uninitialized
       actor has colino=0 and cannot bounce Sonic. */
    if(!o->r_no0){
        unsigned sub=(uint8_t)o->userflag.b.h;
        o->r_no0=2;o->sproffset=1230;
        if(o->xposi.w.h==10624 && o->yposi.w.h==1024)o->sproffset|=32768;
        o->actflg|=4;o->sprhs=o->sprhsize=o->sprvsize=16;o->sprpri=1;o->colino=215;
        scd_word_set(o,27,o->xposi.w.h);scd_word_set(o,28,5);
        unsigned range=((sub&2)?64:0)+((sub&1)?32:0);
        scd_word_set(o,26,range);scd_word_set(o,25,range/2);
        if(range){scd_word_set(o,23,0);scd_word_set(o,24,(sub&64)?1:65535);}
    }
    int32_t speed=(int32_t)((uint32_t)scd_word_get(o,24)*65536+scd_word_get(o,23));
    if(speed){
        if((uint8_t)o->userflag.b.h&128)o->xposi.l+=speed;else o->yposi.l+=speed;
        unsigned remaining=(uint16_t)(scd_word_get(o,25)-1);
        if(!remaining){
            remaining=scd_word_get(o,26);speed=-speed;
            scd_word_set(o,23,(uint32_t)speed);scd_word_set(o,24,(uint32_t)speed>>16);
        }
        scd_word_set(o,25,remaining);
    }
    if(o->colicnt){
        unsigned awards=scd_word_get(o,28);
        if(awards){scd_word_set(o,28,awards-1);scd_player_points(100);}
        if(o->actflg&128)soundset(127); /* original PCM request, bank added separately */
        o->colicnt=0;
        unsigned angle=atan_sonic(o->xposi.w.h-p->xposi.w.h,o->yposi.w.h-p->yposi.w.h);
        short sn,cs;sinset(angle,&sn,&cs);
        p->xspeed.w=((int)cs*-1792)>>8;p->yspeed.w=((int)sn*-1792)>>8;
        p->cddat=(p->cddat|2)&~(16|32);p->actfree[18]=0;o->mstno.b.h=1;
    }
    bobin_patchg(o);
}

/* BOBIN.C's flipped left endpoint indexes byte 64. The retail Sega CD programs
   R31A-D store 18 immediately after frip_posi and 0 after frip_posi_r. Keep
   those verified bytes explicitly instead of reproducing C out-of-bounds reads. */
static const int8_t frip_posi[65]={
    14,13,12,11,11,10,10,9,9,8,8,7,7,6,6,5,5,4,4,3,3,2,2,1,1,0,0,-1,-1,-2,-2,-3,
    -3,-4,-4,-5,-5,-6,-6,-7,-7,-8,-8,-9,-9,-10,-10,-11,-11,-11,-12,-12,-12,-12,-12,-12,
    -11,-11,-10,-10,-9,-8,-6,-4,18};
static const int8_t frip_posi_r[65]={
    18,19,20,20,20,20,20,20,20,19,19,19,19,19,19,19,18,18,18,18,18,18,17,17,
    17,17,17,17,16,16,16,16,16,16,16,15,15,15,15,15,14,14,14,14,14,14,13,13,
    13,13,13,13,12,12,12,12,11,11,10,10,9,8,6,4,0};
static void frip_release(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!(o->cddat&8) || !(p->cddat&8) || p->actfree[19]!=i+1)return;
    if(p->actfree[0])soundset(171);
    p->actfree[14]=0;p->cddat=(p->cddat|2)&~8;o->cddat&=~8;
    if(!(p->actfree[2]&64) && p->mstno.b.h!=23)p->actfree[2]&=~1;
    p->actfree[19]=0;if(p->mstno.b.h==43)p->cddat&=~2;
}
static void frip_stand(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(p->r_no0==4){p->r_no0=2;scd_word_set(p,26,120);}
    o->r_no1=0;p->actfree[18]=0;
    unsigned standing=o->cddat&8;o->cddat|=8;
    if(!standing){
        if(p->mstno.b.h==43){o->cddat&=~8;frip_release(i);return;}
        p->cddat&=~16;
        if(p->cddat&4){
            p->cddat&=~4;p->sprvsize=chibi_flag?10:19;p->sprhs=chibi_flag?5:9;
            p->yposi.w.h-=chibi_flag?2:5;p->mstno.b.h=0;
        }
    }
    standing=p->cddat&8;p->cddat|=8;
    if(standing){
        if(p->actfree[19]==i+1)return;
        if(p->actfree[19]<=SCD_OBJECT_CAPACITY)actwk[p->actfree[19]].cddat&=~8;
    }
    p->actfree[19]=i+1;p->direc.w=0;p->yspeed.w=0;
    /* SolidObject's StandOnObject keeps ground speed only for an up spring
       (routine 2). Native idle springs keep r_no0 0, so use the subtype. */
    /* Side (subtype 4, routine 8) and diagonal (8) springs set it in every
       zone (retail CC1B lands on a side spring with ground speed = X speed). */
    if(!(pool[i].type==SCD_OBJ_SPRING && !(pool[i].subtype&12) && o->r_no0<=2))p->mspeed.w=p->xspeed.w;
    p->cddat&=~2;
}
static void frip_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!o->r_no0){
        o->r_no0=2;o->sproffset=1181;o->actflg|=4;o->sprpri=1;o->sprhsize=32;o->sprvsize=16;
    }
    if(!o->mstno.b.h){
        int index=p->xposi.w.h-o->xposi.w.h+o->sprhsize;
        if(p->mstno.b.h==43 || index<0 || index>=o->sprhsize*2)frip_release(i);
        else{
            if(o->cddat&1)index=64-index;
            int surface=o->yposi.w.h+(p->yspeed.w<0?frip_posi_r[index]:frip_posi[index]);
            int radius=p->yspeed.w<0?-(int)p->sprvsize:p->sprvsize;
            int overlap=radius+p->yposi.w.h-surface+8;
            if(overlap<0 || overlap>=16)frip_release(i);
            else{
                p->yposi.w.h=surface-radius;
                if(p->yspeed.w>=0)frip_stand(i);
                else{p->yspeed.w=0;p->mspeed.w=p->xspeed.w;}
            }
        }
    }
    bobin_patchg(o);
}
