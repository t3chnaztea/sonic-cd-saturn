/* Metallic Madness (R8) story actors: R8/FRIEND8.C (Flicky and the sheep)
   and ET8.C (robot generator). R8 has no projector (no MOVIE8), so
   friend_suicide keeps the animals away in the Present and Past unless
   projector_flag is already set; they live in the Good Future.
   Quirks kept:
   - Both set_sproffset/m_init index their 11-entry sproffset tables with
     ((stageno.w + 1) << 2) + time_flag. stageno.w holds the round byte
     too, so the PC reads far past the table (UB); Act 3 overflows even
     with the round byte clear. The port (and the fixture's copy of the
     original) use stageno.b.l, i.e. (act + 1) * 4 + time_flag, and 0 past
     the table. sproffset only selects art.
   - ET8's hit clears colino but not colicnt, and its explosion cursor is a
     table index in word 24 (no pointer). */

/* ---- FRIEND8.C: Flicky (hato, orbiting) and the sheep (hopping) --------- */
static void friend8_sproffset(sprite_status *o){
    static const unsigned short tbl[11]={1943,986,986,0,1943,986,986,0,0,0,986};
    unsigned n=(objects_act+1)*4+qq_time_flag();
    o->sproffset=n<11?tbl[n]:0;
}
static void friend8_act(sprite_status *o){
    static const uint8_t p00[]={3,0,1,255},p01[]={0,0,0,2,0,0,2,1,1,2,2,1,1,2,2,0,0,2,0,0,2,1,1,2,2,1,1,2,2,255};
    static const uint8_t *const pchg0[]={p00,p01};
    if(qq_friend_suicide(o))return;
    if(o->userflag.b.h&127){
        /* sheep */
        if(!o->r_no0){
            o->r_no0+=2;o->actflg|=4;o->sprvsize=7;o->sprhs=8;o->sprpri=4;o->sprhsize=8;friend8_sproffset(o);
            mm_ls(o,12,65536);mm_ls(o,13,-0x40000);return;
        }
        o->xposi.l+=mm_l(o,12);o->yposi.l+=mm_l(o,13);
        o->patno=mm_ls(o,13,(int)((uint32_t)mm_l(o,13)+8192))<0?0:1;
        short d=emycol_d(o);
        if(d<0){o->yposi.w.h+=d;mm_ls(o,13,-0x40000);mm_ls(o,12,(int)(0u-(uint32_t)mm_l(o,12)));o->actflg^=1;o->cddat^=1;}
        tp_draw(o);tp_frameout_s(o);return;
    }
    /* hato (Flicky) */
    if(!o->r_no0){
        o->r_no0+=2;o->actflg=4;o->sprvsize=8;o->sprhs=8;o->sprpri=4;o->sprhsize=8;
        mm_ws(o,23,o->xposi.w.h);mm_ws(o,24,o->yposi.w.h);o->actflg^=1;o->cddat^=1;friend8_sproffset(o);
        o->actfree[4]=1;o->actfree[5]=1;return;
    }
    short sn,cs;sinset(o->actfree[4],&sn,&cs);
    o->xposi.w.h=(short)((cs>>1)+mm_w(o,23));o->yposi.w.h=(short)((sn>>1)+mm_w(o,24));
    int8_t d0=(int8_t)((int8_t)o->actfree[4]+(int8_t)o->actfree[5]),d1=(int8_t)(d0+126);
    if(d1>=0){d0=(int8_t)o->actfree[4];o->actfree[5]=(uint8_t)-o->actfree[5];o->actflg^=1;o->cddat^=1;}
    o->actfree[4]=(uint8_t)d0;
    tp_patchg(o,pchg0);tp_draw(o);tp_frameout_s00(o,mm_w(o,23));
}

/* ---- ET8.C: robot generator ---------------------------------------------- */
static void et8_act(sprite_status *o){
    static const uint8_t pchg0[]={3,3,4,5,6,255};
    static const uint8_t *const pchg[]={pchg0};
    static const int8_t tbl0[64]={1,0,0,2,-40,-20,3,28,10,4,18,-18,5,-18,-10,6,8,-8,8,-18,14,10,-10,10,
        12,30,-10,15,0,-18,18,20,-10,20,-10,18,22,8,23,25,13,-10,26,23,-22,28,-3,-25,30,10,20,32,-10,2,34,30,-8,35,13,-10,40,-10,10,-1};
    static const unsigned short sproffsets[11]={1087,1033,0,0,1108,1024,0,0,0,0,0};
    sprite_status *p=&actwk[0];unsigned tf=qq_time_flag();
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=34;o->sprvsize=32;
        unsigned n=(objects_act+1)*4+tf;o->sproffset=n<11?sproffsets[n]:0;
        mm_ws(o,24,0);mm_ws(o,26,o->yposi.w.h);mm_ws(o,23,4);mm_ws(o,27,1);
        o->patno=(good_future?0:2)+(tf==0);
        if(!good_future && tf==0){o->colino=226;o->yposi.w.h-=16;}
    }   /* fall through: case 0 runs m_wait */
    case 2:
        if(good_future || tf!=0)break;
        mm_ws(o,23,mm_w(o,23)+1);
        if(!(mm_w(o,23)&7))o->yposi.w.h+=mm_w(o,27);
        if(!(mm_w(o,23)&31))mm_ws(o,27,-mm_w(o,27));
        if(o->colicnt){
            o->colino=0;mm_ws(o,23,0);o->patno=7;o->r_no0+=2;
            good_future=pending_generator=1;tp_scoreup(150);
            if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        }else{tp_hitchk(o,p);tp_patchg(o,pchg);}
        break;
    case 4:{
        short a6=mm_w(o,24);int8_t d0=tbl0[a6++];
        if(d0<0){o->r_no0+=2;o->actfree[0]=8;break;}
        if((int8_t)++o->actfree[0]!=d0)break;
        short d5=tbl0[a6++],d6=tbl0[a6++];mm_ws(o,24,a6);
        tt_blast(o->xposi.w.h+d5,o->yposi.w.h+d6);
        break;
    }
    case 6:
        if(--o->actfree[0])break;
        o->r_no0-=6;o->yposi.w.h=mm_w(o,26);soundset(217);
        break;
    }
    tp_draw(o);
    if(o->r_no0<=2)tp_frameout_s(o);
}
