/* Original robot generator: R3/ET3.C and the complete console routine checked
   by tools/cc_generator_source.py. The PC reconstruction has different tiles,
   collision clearing, and immediate explosion initialization. */
static void cc_generator_patchg(sprite_status *o){
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    o->pattim=3;if(o->patcnt==4)o->patcnt=0;
    o->patno=3+o->patcnt++;o->actflg=(o->actflg&~3)|(o->cddat&3);
}
static void cc_generator_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=34;o->sprvsize=32;
        o->sproffset=current_era<2?(objects_act?874:830):0;
        scd_word_set(o,24,0);scd_word_set(o,26,o->yposi.w.h);
        scd_word_set(o,23,4);scd_word_set(o,27,1);
        o->patno=(good_future?0:2)+(current_era==1);
        if(!good_future && current_era==1){o->colino=250;o->yposi.w.h-=16;}
    }
    switch(o->r_no0){
    case 2:
        if(good_future || current_era!=1)break;
        scd_word_set(o,23,scd_word_get(o,23)+1);
        if(!(scd_word_get(o,23)&7))o->yposi.w.h+=cc_word(o,27);
        if(!(scd_word_get(o,23)&31))scd_word_set(o,27,-cc_word(o,27));
        if(o->colicnt){
            o->colino=o->colicnt=0;scd_word_set(o,23,0);o->patno=7;o->r_no0=4;
            good_future=pending_generator=1;scd_player_points(1500);
            if(cc_solid(i))frip_release(i);
        }else{cc_solid(i);cc_generator_patchg(o);}
        break;
    case 4:{
        static const int8_t events[]={1,0,0,2,-40,-20,3,28,10,4,18,-18,5,-18,-10,6,8,-8,
            8,-18,14,10,-10,10,12,30,-10,15,0,-18,18,20,-10,20,-10,18,22,8,23,
            25,13,-10,26,23,-22,28,-3,-25,30,10,20,32,-10,2,34,30,-8,35,13,-10,40,-10,10,-1};
        unsigned pos=scd_word_get(o,24);int time=events[pos];
        if(time<0){o->r_no0=6;o->actfree[0]=8;break;}
        if(++o->actfree[0]!=(unsigned)time)break;
        scd_word_set(o,24,pos+3);
        int child=scd_objects_spawn(SCD_OBJ_EXPLOSION,o->xposi.w.h+events[pos+1],o->yposi.w.h+events[pos+2],4,0);
        if(child>=0){
            sprite_status *c=&actwk[child+1];c->actflg=0;c->userflag.w=0;c->sprhsize=c->sprvsize=0;c->r_no1=1;
            /* Original FindObjSlot leaves a zeroed actor. Its normal dispatch
               initializes it now only if its slot follows this parent. */
            soundset(158);
        }
        break;
    }
    case 6:
        if(!--o->actfree[0]){o->r_no0=0;o->yposi.w.h=cc_word(o,26);soundset(217);}
        break;
    }
    cc_object_draw(o);
    if(o->r_no0<=2 && !(o->actflg&128) &&
       (uint16_t)((o->xposi.w.h&~127)-((scd_act_view_x()-128)&~127))>640)remove_slot(i);
}
