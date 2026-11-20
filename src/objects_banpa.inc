/* R3/BANPA.C: rectangular bumper, contact response before its one-pixel move. */
static void banpa_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!o->r_no0){
        scd_word_set(o,33,o->xposi.w.h);o->r_no0=2;o->actflg=4;
        o->sprhsize=32;o->sprvsize=16;o->sprpri=1;o->colino=231;o->sproffset=0x435e;
        unsigned range=o->userflag.b.h<0?192:160;
        scd_word_set(o,26,range);scd_word_set(o,25,range/2);
        scd_word_set(o,23,0);scd_word_set(o,24,(o->userflag.b.h&64)?1:65535);
        /* The console initializer falls directly into movement. */
    }
    if(o->colicnt){
        if(o->actflg&128)soundset(181);o->colicnt=0;
        if((uint16_t)(p->yposi.w.h-o->yposi.w.h+8)<16)p->xspeed.w=0;
        else{
            if((uint16_t)(p->xposi.w.h-o->xposi.w.h+24)<48)p->yspeed.w=p->yposi.w.h>=o->yposi.w.h?1792:-1792;
            else{
                p->xspeed.w=p->xposi.w.h>=o->xposi.w.h?1267:-1267;
                p->yspeed.w=p->yposi.w.h>=o->yposi.w.h?1267:-1267;
            }
            p->cddat=(p->cddat|2)&207;
        }
    }
    int32_t speed=(int32_t)((uint32_t)scd_word_get(o,23)|((uint32_t)scd_word_get(o,24)<<16));
    if(o->userflag.b.h<0)o->xposi.l+=speed;else o->yposi.l+=speed;
    unsigned timer=(uint16_t)(scd_word_get(o,25)-1);
    if(!timer){timer=scd_word_get(o,26);speed=-speed;scd_word_set(o,23,speed);scd_word_set(o,24,(uint32_t)speed>>16);}
    scd_word_set(o,25,timer);cc_object_draw(o);
}
