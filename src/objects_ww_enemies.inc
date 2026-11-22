/* Wacky Workbench enemies: R6/BATTA.C, HACHI6.C, SEMI.C, MINOMUSI.C and
   BEEM6.C. Line-for-line ports on the PC scratch layout (objects_qq_common.inc
   accessors take the original indices). The pattern base (patbase) is implied
   by the type and subtype: views use patno. */

/* ---- BATTA.C: grasshopper ---------------------------------------------- */
/* emylr_jump returns emycol_r/l's result: the PC function falls off its end
   with that value still in d0. D3 is passed as unsigned char (sprhs). */
static short batta_lr(sprite_status *o,unsigned char d3){return o->actfree[12]==255?emycol_r(o,d3):emycol_l(o,d3);}
static void batta_patexg(sprite_status *o){
    if(o->patno){o->patno=0;o->sprvsize=19;o->colino=47;}
    else{o->patno=1;o->sprvsize=28;o->colino=48;}
}
static void batta_wall(sprite_status *o){
    o->actfree[8]=o->actfree[9];o->actflg^=1;o->cddat^=1;
    tp_lset(o,0,-tp_l(o,0));qq_ws(o,28,-qq_w(o,28));
    o->actfree[12]=o->actfree[12]==255?1:255;
}
static void batta_fall(sprite_status *o){o->r_no0-=4;o->yposi.w.h-=11;batta_patexg(o);}
static void batta_act(sprite_status *o){
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=9272;o->sprhs=o->sprhsize=16;
        tp_lset(o,4,458752);o->actfree[12]=255;qq_ws(o,28,-16);o->patno=1;batta_patexg(o);
        if(!o->userflag.b.h){tp_lset(o,0,-40960);o->actfree[8]=7;o->actfree[9]=7;}
        else{tp_lset(o,0,-32768);o->actfree[8]=3;o->actfree[9]=3;}
        o->actfree[8]++;
        /* ObjBataPyon_Init falls through to ObjBataPyon_Fall. */
        /* fall through */
    case 2:{
        o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);
        short d1=emycol_d(o);qq_ws(o,33,d1);
        d1=batta_lr(o,(unsigned char)qq_w(o,28));
        if(d1<0){
            if(qq_w(o,33)>=0 || d1<=qq_w(o,33))batta_wall(o);
            else goto floor;
            break;
        }
        if(qq_w(o,33)<0)goto floor;
        tp_lset(o,4,tp_l(o,4)+8192);if(tp_l(o,4)>=458752)tp_lset(o,4,458752);
        break;
    floor:
        o->r_no0+=2;o->yposi.w.h+=qq_w(o,33);qq_ws(o,31,o->userflag.b.h?20:1);
        break;
    }
    case 4:
        if(o->userflag.b.h){
            short d6=7;
            switch(qq_w(o,31)){
            case 11:case 18:d6=-d6;/* fall through */
            case 6:case 15:o->yposi.w.h+=d6;batta_patexg(o);break;
            }
        }
        qq_ws(o,31,qq_w(o,31)-1);
        if(!qq_w(o,31)){
            o->r_no0+=2;o->yposi.w.h-=7;batta_patexg(o);
            tp_lset(o,4,o->userflag.b.h?-327680:-393216);
            if((int8_t)--o->actfree[8]<0)batta_wall(o);
        }
        break;
    case 6:{
        o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);
        short d1=emycol_u(o);qq_ws(o,33,d1);
        d1=batta_lr(o,(unsigned char)qq_w(o,28));
        if(d1<0){
            if(qq_w(o,33)>=0 || d1<=qq_w(o,33))batta_wall(o);
            else{o->yposi.w.h-=qq_w(o,33);tp_lset(o,4,0);batta_fall(o);}
            break;
        }
        if(qq_w(o,33)<0){o->yposi.w.h-=qq_w(o,33);tp_lset(o,4,0);batta_fall(o);break;}
        tp_lset(o,4,tp_l(o,4)+8192);if(tp_l(o,4)>=0)batta_fall(o);
        break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- HACHI6.C: hornet dropping a stinger shot -------------------------- */
/* The shot is a child of the same type with userflag.b.h -1 (tama). */
static void hachi6_turn(sprite_status *o){
    qq_ls(o,12,-qq_l(o,12));qq_ws(o,26,-qq_w(o,26));o->actflg^=1;o->cddat^=1;
}
static void hachi6_move(sprite_status *o){o->r_no0+=2;qq_ws(o,23,o->userflag.b.h?1024:512);}
static void hachi6_tama(sprite_status *o){
    static const uint8_t t0[]={1,2,3,255};static const uint8_t *const pchg[]={t0};
    switch(o->r_no0){
    case 0:o->r_no0+=2;qq_ws(o,23,3);/* fall through */
    case 2:if(qq_ws(o,23,qq_w(o,23)-1)>0)break;o->r_no0+=2;o->patno=1;qq_ws(o,23,10);break;
    case 4:o->xposi.l+=qq_l(o,12);o->yposi.l+=qq_l(o,13);if(qq_ws(o,23,qq_w(o,23)-1)>0)break;o->r_no0+=2;break;
    case 6:
        if(!(o->actflg&128)){tp_frameout(o);return;}
        o->xposi.l+=qq_l(o,12);o->yposi.l+=qq_l(o,13);tp_patchg(o,pchg);break;
    }
    tp_draw(o);tp_frameout_s(o);
}
static void hachi6_act(sprite_status *o){
    static const uint8_t p00[]={1,0,1,255},p01[]={1,2,3,255};
    static const uint8_t *const pchg[]={p00,p01};
    if((int8_t)o->userflag.b.h<0){hachi6_tama(o);return;}
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=24;o->sprvsize=12;o->sproffset=42071;o->colino=49;
        qq_ws(o,26,-8);qq_ls(o,12,o->userflag.b.h?-32768:-65536);
        hachi6_move(o);break;
    case 2:hachi6_move(o);break;
    case 4:{
        o->xposi.l+=qq_l(o,12);
        if(!o->userflag.b.h){
            if(qq_w(o,27))qq_ws(o,27,qq_w(o,27)-1);
            else{
                /* act_check */
                sprite_status *p=&actwk[0];short d0=p->yposi.w.h-o->yposi.w.h;
                if(d0>=-96 && d0<=96){
                    char d1=(short)(p->xposi.w.h-o->xposi.w.h)>=0?-1:0;
                    d0=p->xposi.w.h-o->xposi.w.h;
                    if(d0>=-120 && d0<=120){
                        char d2=o->actflg&1?-1:0;
                        if(d2^d1)hachi6_turn(o);
                        o->r_no0=12;break;
                    }
                }
            }
        }
        if(!qq_ws(o,23,qq_w(o,23)-1))o->r_no0=6;
        break;
    }
    case 6:o->r_no0+=2;qq_ws(o,23,30);break;
    case 8:if(qq_ws(o,23,qq_w(o,23)-1)>=0)break;o->r_no0+=2;qq_ws(o,23,30);hachi6_turn(o);break;
    case 10:if(qq_ws(o,23,qq_w(o,23)-1)>=0)break;o->r_no0=2;break;
    case 12:o->r_no0+=2;qq_ws(o,23,30);/* fall through: act_shot calls act_shot1 */
    case 14:
        if(qq_ws(o,23,qq_w(o,23)-1)>=0)break;
        o->r_no0+=2;qq_ws(o,23,30);o->mstno.b.h=1;o->colino=50;o->sprvsize=16;o->sprhs=o->sprhsize=16;
        o->xposi.w.h+=qq_w(o,26);o->yposi.w.h+=4;break;
    case 16:{
        if(qq_ws(o,23,qq_w(o,23)-1)>=0)break;
        o->r_no0+=2;qq_ws(o,23,30);
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        a->userflag.b.h=-1;tp_setactno(a,o->actno);a->actflg=o->actflg;a->sproffset=o->sproffset;
        a->sprpri=1;a->sprvsize=16;a->sprhs=a->sprhsize=16;a->colino=179;
        a->yposi.w.h=o->yposi.w.h+23;qq_ls(a,13,0x20000);a->xposi.w.h=o->xposi.w.h;
        if(o->actflg&1){a->xposi.w.h+=7;qq_ls(a,12,0x20000);}
        else{a->xposi.w.h-=7;qq_ls(a,12,-0x20000);}
        if(o->actflg&128)soundset(160);
        break;
    }
    case 18:
        if(qq_ws(o,23,qq_w(o,23)-1)>=0)break;
        o->r_no0=2;qq_ws(o,27,60);o->mstno.b.h=0;o->colino=49;o->sprvsize=12;o->sprhs=o->sprhsize=24;o->yposi.w.h-=4;break;
    }
    tp_patchg(o,pchg);tp_draw(o);tp_frameout_s(o);
}

/* ---- SEMI.C: cicada dropping bombs -------------------------------------- */
/* Bombs are children of the same type with userflag.b.l -1. */
static int semi_check(sprite_status *o){
    sprite_status *p=&actwk[0];short d0=p->yposi.w.h-o->yposi.w.h;
    if(d0<-96 || d0>96)return 0;
    qq_ws(o,28,p->xposi.w.h-o->xposi.w.h);
    d0=p->xposi.w.h-o->xposi.w.h;
    return d0>=-120 && d0<=120;
}
static void semi_bomb(sprite_status *o){
    static const uint8_t b0[]={1,0,1,255};static const uint8_t *const pchg[]={b0};
    switch(o->r_no0){
    case 0:o->r_no0+=2;o->colino=183;o->sprvsize=6;o->sprhs=o->sprhsize=6;o->sproffset=33992;tp_lset(o,4,32768);
        /* fall through */
    case 2:{
        o->yposi.l+=tp_l(o,4);tp_lset(o,4,tp_l(o,4)+16384);
        short d1=emycol_d(o);
        if(d1<0){o->r_no0+=2;o->yposi.w.h+=d1;qq_ws(o,27,120);}
        break;
    }
    case 4:if(qq_ws(o,27,qq_w(o,27)-1)<0){o->r_no0+=2;qq_ws(o,27,120);}break;
    case 6:if(qq_ws(o,27,qq_w(o,27)-1)<0)o->r_no0+=2;tp_patchg(o,pchg);break;
    case 8:{
        int visible=o->actflg&128;
        qq_explode(o);o->r_no0=0;o->r_no1=1;
        if(visible)soundset(158);
        return;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}
static void semi_act(sprite_status *o){
    static const uint8_t p0[]={3,1,2,3,2,255};static const uint8_t *const pchg[]={p0};
    if((int8_t)o->userflag.b.l<0){semi_bomb(o);return;}
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprvsize=16;o->sprhs=o->sprhsize=19;o->sproffset=42152;o->colino=54;
        o->actfree[8]=o->userflag.b.l;
        /* fall through */
    case 2:if(qq_ws(o,27,qq_w(o,27)-1)>0)break;o->r_no0+=2;break;
    case 4:if(semi_check(o))o->r_no0+=2;break;
    case 6:{
        o->r_no0+=2;
        int d0=65536,d1=-32768;short d2=96;
        if(o->userflag.b.h){d0=49152;d1=24576;d2=42;}
        if(qq_w(o,28)>=0)d0=-d0;
        tp_lset(o,0,d0);tp_lset(o,4,d1);qq_ws(o,27,d2);
    }   /* fall through */
    case 8:
        if(qq_ws(o,27,qq_w(o,27)-1)<=0)o->r_no0+=2;
        o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);tp_patchg(o,pchg);break;
    case 10:{
        o->r_no0+=2;qq_ws(o,27,0);
        int d0=o->userflag.b.h?49152:65536;
        if(qq_w(o,28)>=0)d0=-d0;
        tp_lset(o,0,d0);
    }   /* fall through */
    case 12:
        if(!o->userflag.b.h){
            qq_ws(o,27,qq_w(o,27)&63);
            sprite_status *a;
            if(!qq_w(o,27) && semi_check(o) && !tp_actwkchk(&a)){
                a->xposi.l=o->xposi.l;a->yposi.l=o->yposi.l;a->yposi.w.h+=10;a->userflag.b.l=-1;
                a->actflg=o->actflg;a->sprpri=o->sprpri+1;tp_setactno(a,o->actno);
            }
            qq_ws(o,27,qq_w(o,27)+1);
        }
        o->xposi.l+=tp_l(o,0);tp_patchg(o,pchg);break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- MINOMUSI.C: bagworm on a thread ------------------------------------ */
/* Children of the same type: the thread (ito, userflag.b.l -1) and the spike
   burst (hari, userflag.b.l 1), both linked to the body by ((short*)o)[30]. */
static void minomusi_body(sprite_status *o){
    static const uint8_t p0[]={0,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,10,11,11,10,11,11,11,11,11,11,11,11,11,11,11,11,11,11,10,255},p1[]={9,9,10,255};
    static const uint8_t *const pchg[]={p0,p1};
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprvsize=16;o->sprhs=o->sprhsize=16;o->sproffset=9352;o->colino=52;
        o->yposi.w.h+=8;qq_ws(o,28,o->yposi.w.h);qq_ws(o,29,o->yposi.w.h+95);
        sprite_status *a;
        if(tp_actwkchk2(o,&a)){tp_frameout(o);return;}
        a->userflag.b.l=-1;a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h;a->actflg=o->actflg;a->sprpri=o->sprpri+1;
        a->sproffset=o->sproffset;a->sprvsize=32;a->sprhs=a->sprhsize=1;qq_ws(a,30,qq_index(o));tp_setactno(a,o->actno);
        /* ObjMinomusi_Init falls through SetWait and WaitPlayer. */
        /* fall through */
    }
    case 2:o->r_no0+=2;o->patno=9;qq_ws(o,23,121);/* fall through */
    case 4:
        if(qq_ws(o,23,qq_w(o,23)-1))break;
        /* ObjMinomusi_WaitPlayer reloads the timer before its sight check. */
        qq_ws(o,23,121);
        {
            /* act_check */
            sprite_status *p=&actwk[0];short d0=p->yposi.w.h-o->yposi.w.h-40;int seen=0;
            if(d0>=0 && d0<=120){d0=p->xposi.w.h-o->xposi.w.h+168;seen=d0>=0 && d0<336;}
            o->r_no0+=seen?2:-2;
        }
        break;
    case 6:o->r_no0+=2;qq_ls(o,13,524288);/* fall through */
    case 8:{
        o->yposi.l+=qq_l(o,13);short d0=qq_w(o,29)-o->yposi.w.h;
        if(d0<=0){o->yposi.w.h+=d0;o->r_no0=14;}
        break;
    }
    case 10:o->r_no0+=2;qq_ls(o,13,o->userflag.b.h?0x20000:458752);/* fall through */
    case 12:{
        o->yposi.l-=qq_l(o,13);short d0=qq_w(o,28)-o->yposi.w.h;
        if(d0>=0){o->yposi.w.h+=d0;o->r_no0=2;}
        break;
    }
    case 14:o->r_no0+=2;qq_ws(o,23,o->userflag.b.h?61:230);o->mstno.w=o->userflag.b.h?511:255;break;
    case 16:{
        if(!qq_ws(o,23,qq_w(o,23)-1))o->r_no0=10;
        tp_patchg(o,pchg);
        sprite_status *a;
        if(o->userflag.b.h || o->patcnt!=15 || tp_actwkchk2(o,&a))break;
        a->userflag.b.l=1;a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h+4;a->actflg=o->actflg;a->sprpri=o->sprpri;
        a->sproffset=o->sproffset;a->sprvsize=o->sprvsize;a->sprhs=o->sprhs;a->sprhsize=o->sprhsize;qq_ws(a,30,qq_index(o));
        a->colino=181;tp_setactno(a,o->actno);
        if(o->actflg&128)soundset(183);
        break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}
static void minomusi_act(sprite_status *o){
    if(!o->userflag.b.l){minomusi_body(o);return;}
    sprite_status *m=&actwk[(uint16_t)qq_w(o,30)];
    if((int8_t)o->userflag.b.l<0){
        /* ito: the thread follows the body's drop. */
        if(m->actno!=SCD_OBJ_R6_MINOMUSI){tp_frameout(o);return;}
        short d0=(short)(m->yposi.w.h-qq_w(m,28)-24)>>3;
        if(d0<0)d0=0;
        o->patno=d0;o->yposi.w.h=(d0<<2)+qq_w(m,28)+16;
        tp_draw(o);return;
    }
    /* hari: the spike burst lasts until the body's pattern counter wraps. */
    if(m->patcnt==1)tp_frameout(o);else tp_draw(o);
}

/* ---- BEEM6.C: the electric beam cycle ----------------------------------- */
/* Subtype 0 is a still emitter sprite. Subtype 1 (one per act, created by
   beem6_actsch if the layout has none) follows the player and runs the beam
   cycle: palette flashes in lpcolorwk and st6clrchg (1-3, the beam direction
   PLAYER6.C sibi2 tests against the player's block). The object palette
   writes land in ww_colorwk/ww_colorwk2 (Mega Drive words, set flags) for the
   stage palette to apply (scd_objects_ww_palette). */
static const short ww_clrtblA[]={0,0,3808,3808,0,0,238,238,0,0,3598,3598,0,0,-1},ww_clrtblA2[]={2656,2656,2720,2720,2656,2656,2720,2720,-1};
static const short ww_clrtblB[]={0,0,3808,3808,0,0,238,238,0,0,3598,3598,0,0,-1},ww_clrtblB2[]={2118,2118,2122,2122,2118,2118,2122,2122,-1};
static const short ww_clrtblD[]={0,0,3808,3808,0,0,238,238,0,0,3598,3598,0,0,-1},ww_clrtblD2[]={580,580,584,584,580,580,584,584,-1};
static uint16_t ww_colorwk[2][64];static uint64_t ww_colorset[2];
static void ww_pal(unsigned which,unsigned n,short col){ww_colorwk[which][n]=(uint16_t)col&0xFFF;ww_colorset[which]|=1ull<<n;}
static void beem6_clrset0(unsigned which){
    unsigned a3=32;short d0=1574,d2=1606;unsigned tf=qq_time_flag();
    if(tf){a3=61;d0=546;d2=1664;if(tf!=1){d0=1026;d2=582;if(good_future)return;}}
    ww_pal(which,50,d0);ww_pal(which,51,d0);ww_pal(which,52,d0);ww_pal(which,a3,d2);
}
static void beem6_clrset1(sprite_status *o,unsigned d0){
    static const char clrsel[3]={0,2,4};unsigned tf=qq_time_flag();
    const short *a1=tf?(tf!=1?ww_clrtblD:ww_clrtblA):ww_clrtblB;
    ww_pal(0,(unsigned)(clrsel[d0]>>1)+50,a1[o->actfree[20]]);
    if(a1[++o->actfree[20]]==-1)o->actfree[20]=0;
    unsigned n=32;a1=ww_clrtblB2;
    if(tf){n=61;a1=tf!=1?ww_clrtblD2:ww_clrtblA2;}
    ww_pal(0,n,a1[o->actfree[21]]);
    if(a1[++o->actfree[21]]==-1)o->actfree[21]=0;
}
static void beem6_posiset(sprite_status *o){o->xposi.w.h=actwk[0].xposi.w.h;o->yposi.w.h=actwk[0].yposi.w.h;}
static void beem6_move(sprite_status *o){
    beem6_posiset(o);
    if(qq_w(o,26)){
        /* maeclrset: the warning blink before the beam. */
        static const char clrsel[3]={0,2,4};
        ww_pal(0,(unsigned)(clrsel[(signed char)o->actfree[18]]>>1)+50,o->actfree[4]&2?0:128);
        o->actfree[4]=(o->actfree[4]+1)&3;
        if(qq_ws(o,26,qq_w(o,26)-1))return;
        beem6_clrset0(0);
    }
    st6clrchg=o->actfree[18]+1;beem6_clrset1(o,o->actfree[18]);
    if(qq_ws(o,31,qq_w(o,31)-1))return;
    o->r_no0-=2;st6clrchg=0;
    if(++o->actfree[18]<3)return;
    o->actfree[18]=0;qq_ws(o,33,0);
}
static void beem6_act(sprite_status *o){
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sproffset=25432;o->sprvsize=o->sprhsize=16;o->patno=o->userflag.b.h;
        /* beem6_actsch: one beam controller per act. */
        int found=0;
        for(unsigned k=0;k<SCD_OBJECT_CAPACITY && !found;k++)found=pool[k].type==SCD_OBJ_R6_BEEM6 && actwk[k+1].userflag.b.h;
        sprite_status *a;
        if(!found && !tp_actwkchk(&a)){a->userflag.b.h=1;a->xposi.w.h=actwk[0].xposi.w.h;a->yposi.w.h=actwk[0].yposi.w.h;tp_setactno(a,SCD_OBJ_R6_BEEM6);}
        beem6_clrset0(1);
    }  /* fall through */
    case 2:{
        if(!o->userflag.b.h)break;
        beem6_posiset(o);
        if(qq_w(o,31)){
            /* cntdwn */
            if(qq_ws(o,31,qq_w(o,31)-1))break;
            o->r_no0+=2;qq_ws(o,31,120);qq_ws(o,26,90);o->actfree[4]=0;
            if(o->actflg&128)soundset(178);
            beem6_move(o);break;
        }
        beem6_clrset0(0);
        unsigned tf=qq_time_flag();
        if(tf==2 && good_future)break;
        /* ObjElectricBeams_Main gates Act 1 by cameraY, not the zone id. */
        if(objects_act==0 && scra_v_posit.w.h>=1024)break;
        qq_ws(o,31,tf?(tf-1?240:480):360);
        break;
    }
    case 4:beem6_move(o);break;
    }
    tp_draw(o);tp_frameout_s(o);
}
/* The beam palette words (Mega Drive 0BGR) BEEM6 wrote since the stage reset:
   out[0..63] lpcolorwk, out[64..127] lpcolorwk2 (the fade target); returns
   the set masks. */
uint64_t scd_objects_ww_palette(uint16_t *out,uint64_t *fade_set){
    for(unsigned w=0;w<2;w++)for(unsigned n=0;n<64;n++)if(ww_colorset[w]>>n&1)out[w*64+n]=ww_colorwk[w][n];
    if(fade_set)*fade_set=ww_colorset[1];
    return ww_colorset[0];
}
