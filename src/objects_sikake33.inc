/* Collision Chaos Act 3 id 54, R3/SIKAKE33.C: userflag.b.h < 0 runs the
   kaitenban (R3/ROLLPLAT.C), 0 a light (R3/LIGHT.C), otherwise the stopper
   (R3/STOPPER.C). Scratch words keep their original offsets; link words hold
   actor indices (pool slot + 1), as the original holds actwk indices. The
   children's actno check compares the port type the parent copies to them.
   frameout_s is the native placement stream; ACTION.C actionsub is
   cc_object_draw. tools/test-cc-sikake33.sh checks this file against the
   compiled original. */
static const uint8_t sikake_kaiten_00[]={3,1,2,3,0,255},sikake_kaiten_01[]={3,3,2,1,0,255};
static const uint8_t *const sikake_kaiten_scripts[2]={sikake_kaiten_00,sikake_kaiten_01};
static const uint8_t sikake_stop_00[]={9,0,1,2,252},sikake_stop_01[]={9,2,1,0,252};
static const uint8_t *const sikake_stop_scripts[2]={sikake_stop_00,sikake_stop_01};
/* PLAYSUB.C patchg for scripts whose first byte is nonzero and whose only
   codes are 255 (loop) and 252 (advance r_no0). */
static void sikake_patchg(sprite_status *o,const uint8_t *const *scripts){
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=scripts[(uint8_t)o->mstno.b.h];
    o->pattim=script[0];
    unsigned pat=script[o->patcnt+1];
    if(pat==252){o->r_no0+=2;return;}
    if(pat==255){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
/* actwkchk returns a cleared actor; the original sets only these fields. */
static int sikake_child(unsigned parent,int x,int y,unsigned sub){
    int c=spawn_from(SCD_OBJ_SIKAKE33,x,y,sub,0,0);
    if(c<0)return c;
    sprite_status *o=&actwk[c+1];
    o->actflg=0;o->cddat=0;o->sprhsize=o->sprvsize=0;
    scd_word_set(o,29,parent);
    return c;
}
static sprite_status *sikake_actor(unsigned index){
    return index<=SCD_OBJECT_CAPACITY?&actwk[index]:NULL;
}
static void kaitenban_check(unsigned i){
    static const int16_t tbl[3]={1176,1200,1224};
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if((uint16_t)(o->yposi.w.h-p->yposi.w.h+16)>=32 || (uint16_t)(o->xposi.w.h-p->xposi.w.h+16)>=32){o->actfree[20]=0;return;}
    if(o->actfree[20])return;
    o->actfree[20]=255;
    o->mstno.w=p->yspeed.w>=0?255:511;
    int16_t previous=cc_word(o,23);scd_word_set(o,23,128);
    if(previous)return;
    int16_t state=cc_word(o,25);
    if(state!=4){
        state+=2;scd_word_set(o,25,(uint16_t)state);
        scd_word_set(o,28,scd_word_get(o,27));scd_word_set(o,27,scd_word_get(o,26));
        int c=sikake_child(i+1,896,tbl[state/2],0);
        if(c>=0)scd_word_set(o,26,c+1);
        if(state==4){sprite_status *s=sikake_actor(scd_word_get(o,24));if(s)s->r_no0=4;}
        return;
    }
    scd_word_set(o,25,(uint16_t)-2);
    static const uint8_t words[4]={26,27,28,24};
    for(unsigned k=0;k<4;k++){sprite_status *s=sikake_actor(scd_word_get(o,words[k]));if(s)s->r_no0=k<3?4:6;}
}
static void kaitenban_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->sprpri=3;o->sprhsize=o->sprvsize=16;
        scd_word_set(o,25,(uint16_t)-2);
        if((int8_t)o->userflag.b.h==-1){scd_word_set(o,23,128);o->actfree[20]=o->actfree[21]=255;}
        int c=sikake_child(i+1,896,1272,1);
        if(c>=0)scd_word_set(o,24,c+1);
    }
    kaitenban_check(i);
    if(cc_word(o,23)){scd_word_set(o,23,scd_word_get(o,23)-1);sikake_patchg(o,sikake_kaiten_scripts);}
    cc_object_draw(o);
}
static int sikake_orphan(unsigned i){
    sprite_status *parent=sikake_actor(scd_word_get(&actwk[i+1],29));
    if(parent && parent->actno==SCD_OBJ_SIKAKE33)return 0;
    remove_slot(i);return 1;
}
static void light_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){o->r_no0=2;o->actflg|=4;o->sprpri=3;o->sprhsize=o->sprvsize=8;}
    else if(o->r_no0==4){remove_slot(i);return;} /* act_die */
    if(sikake_orphan(i))return;
    cc_object_draw(o);
}
static void stopper_move(unsigned i){
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(o->patno!=2 || !cc_ride(i))return;
    p->cddat=(p->cddat&~(8|16|32))|2;
    p->xspeed.w=0;p->yspeed.w=-1024;
}
static void stopper_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(o->r_no0){
    case 0:o->r_no0=2;o->actflg|=4;o->sprpri=3;o->sprhsize=16;o->sprvsize=8;
        __attribute__((fallthrough));
    case 2:case 10:stopper_move(i);break;
    case 4:o->mstno.w=255;o->r_no0+=4;sikake_patchg(o,sikake_stop_scripts);break;
    case 6:o->mstno.w=511;o->r_no0+=2;sikake_patchg(o,sikake_stop_scripts);break;
    case 8:sikake_patchg(o,sikake_stop_scripts);break;
    }
    if(sikake_orphan(i))return;
    cc_object_draw(o);
}
static void sikake33_step(unsigned i){
    int8_t sub=(int8_t)actwk[i+1].userflag.b.h;
    if(sub<0)kaitenban_step(i);else if(!sub)light_step(i);else stopper_step(i);
}
