/* R3/POCKET.C, with the Sega CD capture tail-return verified in
   tools/cc_pocket_source.py. Negative subtype is the pocket; zero is its lid. */
static int pocket_allocate(unsigned type,sprite_status *parent,unsigned sub){
    int child=scd_objects_spawn(type,0,0,sub,0);
    if(child>=0){
        sprite_status *o=&actwk[child+1];
        o->actflg=0;o->xposi.w.h=parent->xposi.w.h;o->yposi.w.h=parent->yposi.w.h;
    }
    return child;
}
/* Original HUD/points actor's negative-subtype branch. Only the dynamic
   point popup belongs here; the native HUD uses its existing renderer. */
static void cc_points_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->sproffset=1734;
        o->patno=o->userflag.b.h&127;o->actfree[0]=24;
    }
    if(!--o->actfree[0]){remove_slot(i);return;}
    o->yposi.w.h-=2;cc_object_draw(o);
}
static void pocket_child_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->r_no0==4){remove_slot(i);return;}
    if(!o->r_no0){o->r_no0=2;o->actflg|=4;o->sprpri=0;o->sprhsize=24;o->sprvsize=8;o->sproffset=17327;}
    unsigned parent=scd_word_get(o,25);
    if(!parent || parent>SCD_OBJECT_CAPACITY || actwk[parent].actno!=SCD_OBJ_POCKET){remove_slot(i);return;}
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim<0){
        o->pattim=3;if(o->patcnt==2)o->patcnt=0;
        o->patno=o->patcnt++;o->actflg=(o->actflg&~3)|(o->cddat&3);
    }
    cc_object_draw(o);
}
static void pocket_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(o->userflag.b.h>=0){pocket_child_step(i);return;}
    if(!o->r_no0){
        if(current_era>=2 && good_future){remove_slot(i);return;}
        o->r_no0=2;o->actflg|=4;o->sprpri=0;o->sproffset=943;scd_word_set(o,26,7);
    }
    if(o->r_no0==2){
        if(!editmode.w){
            if(p->yspeed.w>=0 && p->r_no0!=4 && p->r_no0!=6 &&
               (uint16_t)(p->yposi.w.h-o->yposi.w.h+24)<16 &&
               (uint16_t)(p->xposi.w.h-o->xposi.w.h+24)<48){
                o->actfree[20]=255;p->actfree[2]|=1;p->cddat|=4;
                p->sprvsize=14;p->sprhs=7;p->mstno.b.h=2;p->xspeed.w=0;p->yspeed.w=-2048;
                p->xposi.w.h=o->xposi.w.h;p->yposi.w.h=o->yposi.w.h-16;
            }
            if(o->actfree[20]){o->r_no0=4;scd_word_set(o,23,8);o->patno=1;soundset(215);}
        }
    }else{
        unsigned timer=(uint16_t)(scd_word_get(o,23)-1);scd_word_set(o,23,timer);
        if((int16_t)timer<0)switch(o->r_no0){
        case 4:{
            o->r_no0=6;o->patno=2;scd_word_set(o,23,6);
            int child=pocket_allocate(SCD_OBJ_POCKET,o,0);
            /* Original allocation failure removes the pocket without clearing
               Sonic's control bit. Do not silently change the original path. */
            if(child<0){remove_slot(i);return;}
            scd_word_set(o,24,child+1);scd_word_set(&actwk[child+1],25,i+1);p->actfree[2]|=64;
            break;
        }
        case 6:o->r_no0=8;scd_word_set(o,23,2);o->patno=3;break;
        case 8:o->r_no0=10;scd_word_set(o,23,30);o->patno=0;break;
        case 10:case 12:
            o->r_no0+=2;scd_word_set(o,23,30);
            if(scd_word_get(o,26)){
                scd_word_set(o,26,scd_word_get(o,26)-1);scd_player_points(100);
                pocket_allocate(SCD_OBJ_CC_POINTS,o,128);
            }
            break;
        case 14:o->r_no0=16;scd_word_set(o,23,4);o->patno=3;break;
        case 16:o->r_no0=18;scd_word_set(o,23,6);o->patno=2;break;
        case 18:{
            soundset(159);o->r_no0=20;o->patno=0;scd_word_set(o,23,120);
            unsigned child=scd_word_get(o,24);
            if(child && child<=SCD_OBJECT_CAPACITY)actwk[child].r_no0=4;
            if(o->actfree[20]){o->actfree[20]=0;p->actfree[2]&=~65;}
            break;
        }
        case 20:o->r_no0=2;o->actfree[20]=0;break;
        }
    }
    cc_object_draw(o);
    if(!(o->actflg&128) && (uint16_t)((o->xposi.w.h&~127)-((scd_act_view_x()-128)&~127))>640)remove_slot(i);
}
