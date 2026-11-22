/* R3/TOGEBL3A/B/D.C: rotating chain, with 3/2/4/4 balls by era.
   Children allocate strictly after their parent and consume its fixed-point
   scratch positions in the same actor update. Original console init moves
   immediately; the reconstructed PC initializer waits one update. */
static void togeball_position(sprite_status *o,unsigned word,int32_t value){
    scd_word_set(o,word,(uint32_t)value);scd_word_set(o,word+1,(uint32_t)value>>16);
}
static void togeball_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->userflag.b.h<0){
        if(!o->r_no0){o->r_no0=2;o->actflg|=4;o->sprpri=1;o->sproffset=957;o->colino=139;}
        o->xposi.w.h=scd_word_get(o,24);o->yposi.w.h=scd_word_get(o,26);
        unsigned parent=scd_word_get(o,33);
        if(!parent || parent>SCD_OBJECT_CAPACITY || actwk[parent].actno!=SCD_OBJ_TOGEBALL){remove_slot(i);return;}
        cc_object_draw(o);return;
    }
    unsigned count=current_era==0?3:current_era==1?2:4;
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->sprpri=1;o->sprhsize=o->sprvsize=8;o->sproffset=957;
        scd_word_set(o,24,o->userflag.b.h?-256:256);
        for(unsigned n=0;n<count;n++){
            int child=spawn_from(SCD_OBJ_TOGEBALL,0,0,255,0,i+1);
            if(child<0){remove_slot(i);return;}
            sprite_status *c=&actwk[child+1];
            /* Original actwkchk2 returns a zeroed actor, not a placement. */
            c->actflg=0;c->sprhsize=c->sprvsize=8;
            scd_word_set(c,33,i+1);scd_word_set(o,25+n,child+1);
        }
    }
    unsigned angle=(uint16_t)(scd_word_get(o,23)+scd_word_get(o,24));scd_word_set(o,23,angle);
    short sn,cs;sinset(angle>>8,&sn,&cs);
    for(unsigned n=0;n<count;n++){
        sprite_status *c=&actwk[scd_word_get(o,25+n)];
        togeball_position(c,23,o->xposi.l+(int32_t)cs*(4096*(n+1)));
        togeball_position(c,25,o->yposi.l+(int32_t)sn*(4096*(n+1)));
    }
    cc_object_draw(o);
    /* frameout_s uses camera-aligned 128-pixel blocks, after DrawObject.
       Placement loading and travel reset remain owned by the shared stream. */
    if(!(o->actflg&128) && (uint16_t)((o->xposi.w.h&~127)-((scd_act_view_x()-128)&~127))>640)remove_slot(i);
}
