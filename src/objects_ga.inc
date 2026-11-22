/* R3/GA3.C. The signed subtype selects normal/damaged moth or its harmless
   falling sparkle. Keep original scratch offsets without host pointer aliasing. */
static int32_t ga_long(const sprite_status *o,unsigned index){
    return (int32_t)((uint32_t)scd_word_get(o,index*2)|((uint32_t)scd_word_get(o,index*2+1)<<16));
}
static void ga_set_long(sprite_status *o,unsigned index,int32_t value){
    scd_word_set(o,index*2,value);scd_word_set(o,index*2+1,(uint32_t)value>>16);
}
static void ga_patchg(sprite_status *o){
    static const uint8_t appear0[]={29,0,1,1},appear1[]={49,2,2},fly[]={4,3,4,5,4,255},sparkle[]={5,4,5,6,7,255};
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=o->userflag.b.h>0?sparkle:o->mstno.b.h==0?appear0:o->mstno.b.h==1?appear1:fly;
    o->pattim=script[0];unsigned pat=script[o->patcnt+1];
    if(pat==255){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
static void ga_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->userflag.b.h>0){
        if(!o->r_no0){
            o->r_no0=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=o->sprvsize=6;
            o->sproffset=42926;scd_word_set(o,23,180);
        }
        unsigned timer=(uint16_t)(scd_word_get(o,23)-1);scd_word_set(o,23,timer);
        if(o->r_no0==4 || !timer){remove_slot(i);return;}
        o->yposi.l+=65536;ga_patchg(o);return;
    }
    if(cc_enemy_suicide(i))return;
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->patno=0;o->sprpri=1;o->sprhsize=16;o->sprvsize=8;o->sproffset=42017;
        scd_word_set(o,23,61);if(o->userflag.b.h>=0)o->actfree[21]=255;
    }
    unsigned timer=(uint16_t)(scd_word_get(o,23)-1);scd_word_set(o,23,timer);
    switch(o->r_no0){
    case 2:if(!timer){o->r_no0=4;scd_word_set(o,23,61);}return;
    case 4:if(!timer){o->colino=37;o->r_no0=6;++o->mstno.b.h;scd_word_set(o,23,51);}break;
    case 6:
        if(!timer){
            o->colino=38;o->r_no0=8;++o->mstno.b.h;
            ga_set_long(o,13,32768);scd_word_set(o,23,o->userflag.b.h<0?48:32);
            int32_t vx=o->userflag.b.h<0?-16384:-32768;
            if(o->xposi.w.h-actwk[0].xposi.w.h<0){vx=-vx;o->actflg|=1;o->cddat|=1;}
            ga_set_long(o,12,vx);
        }
        break;
    case 8:
        o->xposi.l+=ga_long(o,12);o->yposi.l+=ga_long(o,13);
        if(!timer){
            scd_word_set(o,23,o->userflag.b.h<0?97:65);ga_set_long(o,13,-ga_long(o,13));
            if(o->actfree[21]){
                int child=scd_objects_spawn(SCD_OBJ_GA,o->xposi.w.h,o->yposi.w.h,1,0);
                if(child>=0){
                    actwk[child+1].xposi.l=o->xposi.l;actwk[child+1].yposi.l=o->yposi.l;
                    stats.projectiles++;
                }
            }
        }
        break;
    }
    ga_patchg(o);
}
