/* Tidal Tempest gimmicks: R4/HARIR4.C, HARID4.C, SCREW_A.C (Present/Past),
   SCREW_C.C (Futures), OSUMIZU.C, FUNSUI4.C, UKIDAI.C and PLAYSUB4.C bou.
   hitchk is cc_solid, ridechk is cc_ride (RIDECHK.C, r_no1 0 and 1). */

/* ---- HARIR4.C: spikes rising and sinking ------------------------------- */
static void harir4_sub(sprite_status *o){
    if(o->actfree[16]){
        if(--o->actfree[16])return;
        if(o->actflg&128)soundset(183);
    }
    if(o->actfree[18]){
        if(o->actfree[17]<8){o->actfree[17]=o->actfree[18]=0;o->actfree[16]=60;}
        else o->actfree[17]-=8;
    }else if((int8_t)(o->actfree[17]+=8)>=32){o->actfree[17]=32;o->actfree[18]=1;o->actfree[16]=60;}
}
static void harir4_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sproffset=928;o->sprpri=4;
        if(!tt_word(o,29))tt_set_word(o,29,o->xposi.w.h);
        tt_set_word(o,27,o->yposi.w.h);o->sprhsize=18;o->sprvsize=12;
        if(o->userflag.b.h){o->patno=1;o->colino=131;}
    }
    if(o->userflag.b.h!=1){harir4_sub(o);o->yposi.w.h=o->actfree[17]+tt_word(o,27);}
    if(o->patno)cc_solid(i);
    else if(cc_solid(i) && (o->cddat&8) && !plpower_a && !plpower_m && p->r_no0<4 && !scd_word_get(p,26)){
        p->yposi.l-=(int32_t)p->yspeed.w*256;scd_objects_hurt(o->xposi.w.h);
    }
    cc_object_draw(o);
    unsigned ride_actor=(uint16_t)tt_word(o,28);
    if(ride_actor){
        sprite_status *r=&actwk[ride_actor];
        if(!r->actno){remove_slot(i);return;}
        o->xposi.w.h=r->xposi.w.h+(int16_t)o->actfree[14];o->yposi.w.h=r->yposi.w.h+(int16_t)o->actfree[15];
    }
    tt_frameout(i,tt_word(o,29));
}

/* ---- HARID4.C: spike column dropping on the player --------------------- */
static void harid4_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(o->userflag.b.h&128){
        unsigned parent=(uint16_t)tt_word(o,33);
        if(parent<1 || parent>SCD_OBJECT_CAPACITY || actwk[parent].actno!=SCD_OBJ_HARID4){remove_slot(i);return;}
        cc_object_draw(o);return;
    }
    if(!o->r_no0 || (o->actflg&128)){
        /* The original moves actor word 32 even when the tip was never
           allocated (index 0, the player); the port skips that case. */
        unsigned tip=(uint16_t)tt_word(o,32);
        sprite_status *t=tip && tip<=SCD_OBJECT_CAPACITY?&actwk[tip]:0;
        switch(o->r_no0){
        case 0:{
            o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhs=o->sprhsize=16;o->sprvsize=64;o->sproffset=928;
            tt_set_long(o,14,waterposi_m>=o->yposi.w.h?12288:4096);
            int c=tt_child(SCD_OBJ_HARID4,i+1);
            if(c>=0){
                sprite_status *s=&actwk[c+1];
                s->userflag.b.h=-1;s->xposi.w.h=o->xposi.w.h;s->yposi.w.h=o->yposi.w.h+48;
                tt_set_word(s,33,i+1);tt_set_word(o,32,c+1);
                s->colino=176;s->actflg=o->actflg;s->sprpri=o->sprpri;s->sprhs=s->sprhsize=s->sprvsize=16;
                s->sproffset=928;s->patno=1;
            }
            break;
        }
        case 2:{
            int16_t d=p->yposi.w.h-o->yposi.w.h-64;
            if((uint16_t)d>=128)break;
            d=p->xposi.w.h-o->xposi.w.h+16;
            if((uint16_t)d>=32)break;
            o->r_no0+=2;o->yspeed.w=256;tt_set_word(o,27,20);break;
        }
        case 4:{
            int32_t v=tt_free_long(o,0);o->yposi.l+=v;if(t)t->yposi.l+=v;
            tt_set_free_long(o,0,v+8192);
            tt_set_word(o,27,tt_word(o,27)-1);
            if(tt_word(o,27)<0){o->r_no0+=2;tt_set_free_long(o,0,0);tt_set_word(o,27,30);}
            break;
        }
        case 6:
            tt_set_word(o,27,tt_word(o,27)-1);
            if(tt_word(o,27)<0)o->r_no0+=2;
            break;
        case 8:{
            int32_t v=tt_free_long(o,0);o->yposi.l+=v;if(t)t->yposi.l+=v;
            tt_set_free_long(o,0,v+tt_long(o,14));
            short d=emycol_d(o);
            if(d<0){
                o->r_no0+=2;o->yposi.w.h+=d;o->yspeed.w=0;tt_set_free_long(o,4,0x200000);
                if(t && t->actno)remove_slot(tip-1);
            }
            break;
        }
        case 10:{
            int32_t v=tt_free_long(o,0);o->yposi.l+=v;
            tt_set_free_long(o,4,tt_free_long(o,4)-v);
            if(tt_free_long(o,4)<0)o->r_no0+=2;
            break;
        }
        }
        cc_solid(i);
    }
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}

/* ---- SCREW_A.C / SCREW_C.C: switch-driven screw ------------------------ */
static void screw_step(unsigned i){
    static const uint8_t pchg_00[]={1,0,1,2,3,4,255};
    static const uint8_t *const pchg[]={pchg_00};
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17280;
        if(o->userflag.b.h&128)o->actfree[21]=255;
        if(!(o->userflag.b.h&2)){o->sprhsize=16;o->sprvsize=8;}else{o->sprhsize=8;o->sprvsize=16;}
        if(o->userflag.b.h&1){o->actflg|=3;o->cddat|=3;}
    }
    if(!(o->userflag.b.l&128) && !o->actfree[20] && switchflag[o->userflag.b.l]){o->actfree[20]=1;o->actfree[21]=~o->actfree[21];}
    if(!o->actfree[21])o->patno=0;else tt_patchg(o,pchg);
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}
static void screw_f_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->actfree[2]=actwk[(uint16_t)tt_word(o,23)%128].actno;
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17280;
        if(o->userflag.b.h&128)++o->patno;
        if(o->userflag.b.h&2){o->sprhsize=8;o->sprvsize=16;}else{o->sprhsize=16;o->sprvsize=8;}
        if(o->userflag.b.h&1){o->actflg|=3;o->cddat|=3;}
    }
    if(o->actfree[2]==actwk[(uint16_t)tt_word(o,23)%128].actno){
        if(!(o->userflag.b.l&128) && !o->actfree[20] && switchflag[o->userflag.b.l]){o->actfree[20]=255;o->patno^=1;}
        cc_object_draw(o);return;
    }
    remove_slot(i);
}

/* ---- OSUMIZU.C: water current and its moving streams ------------------- */
static void osumizu_step(unsigned i){
    static const uint8_t chg0[]={9,0,1,2,3,255};
    static const uint8_t *const chg[]={chg0};
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(o->userflag.b.h&128){
        if((uint16_t)(p->yposi.w.h-o->yposi.w.h+12)<24 && (uint16_t)(p->xposi.w.h-o->xposi.w.h+20)<40)
            p->mspeed.w=(int16_t)(tt_long(o,12)>>8);
        o->xposi.l+=tt_long(o,12);tt_patchg(o,chg);cc_object_draw(o);tt_frameout(i,o->xposi.w.h);return;
    }
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhsize=8;o->sprvsize=16;o->sproffset=17176;
        if(o->userflag.b.h){o->actflg|=1;o->cddat|=1;tt_set_long(o,12,196608);tt_set_word(o,26,-32);}
        else{tt_set_long(o,12,-196608);tt_set_word(o,26,32);}
        tt_set_word(o,26,tt_word(o,26)+o->xposi.w.h);
    }
    tt_set_word(o,23,tt_word(o,23)-1);
    if(tt_word(o,23)<0){
        tt_set_word(o,23,30);
        int c=tt_child(pool[i].type,0);
        if(c>=0){
            sprite_status *s=&actwk[c+1];
            s->userflag.b.h=-1;s->xposi.w.h=tt_word(o,26);s->yposi.w.h=o->yposi.w.h+4;tt_set_long(s,12,tt_long(o,12));
            s->actflg=o->actflg;s->sprpri=o->sprpri+1;s->sprhsize=32;s->sprvsize=6;s->sproffset=792;s->cddat=o->cddat;
        }
    }
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}

/* ---- FUNSUI4.C: fountain platform and its spray ------------------------ */
static const uint8_t funsui4_pchg0[]={0,0,1,2,3,4,255},funsui4_pchg1[]={0,5,6,7,8,255};
static const uint8_t *const funsui4_pchg[]={funsui4_pchg0,funsui4_pchg1};
static void funsui4_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if((uint8_t)o->userflag.b.h==255){
        if(!o->r_no0){
            o->r_no0+=2;o->actflg|=4;o->sproffset=25344;o->sprpri=3;o->sprhsize=o->sprvsize=16;o->mstno.b.h=1;
        }
        if(o->actfree[17]+2>255){o->actfree[17]+=2;remove_slot(i);return;}
        o->actfree[17]+=2;
        o->xposi.l+=(int32_t)o->xspeed.w*256;o->yposi.l+=(int32_t)o->yspeed.w*256;o->yspeed.w+=8;
        tt_patchg(o,funsui4_pchg);cc_object_draw(o);tt_frameout(i,o->xposi.w.h);return;
    }
    /* tbl[2] (sibuki_move) is unreachable: nothing sets a fountain's routine to 4. */
    if(!o->r_no0){
        /* The PC palette writes (lpcolorwk 55-57) belong to the zone palette. */
        o->r_no0+=2;o->actflg|=4;o->sproffset=25344;o->sprpri=1;o->sprhsize=32;o->sprvsize=60;
    }
    /* sibuki_set */
    if(o->actfree[17]+16<256)o->actfree[17]+=16;
    else{
        o->actfree[17]+=16;
        int c=tt_child(pool[i].type,0);
        if(c>=0){
            static const int16_t tbl[16]={-40,-72,-32,-128,8,-72,32,-128,40,-72,64,-128,-8,-72,-64,-128};
            sprite_status *s=&actwk[c+1];unsigned d=o->actfree[16]&3;
            s->userflag.b.h=-1;s->patno=5;s->actfree[16]=d;
            s->xposi.w.h=o->xposi.w.h+tbl[d*4];s->yposi.w.h=o->yposi.w.h+tbl[d*4+1];
            s->xspeed.w=tbl[d*4+2];s->yspeed.w=tbl[d*4+3];
            ++o->actfree[16];
        }
    }
    tt_patchg(o,funsui4_pchg);
    o->yposi.w.h=waterposi-48;
    cc_ride(i);
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}

/* ---- UKIDAI.C: float carried by the rising water ----------------------- */
static void ukidai_move1(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    o->yposi.w.h=waterposi;
    int16_t d4=(int16_t)((int8_t)p->xspeed.b.h+p->xposi.w.h-o->xposi.w.h);
    if(o->xposi.w.h){
        int32_t a6=2;int16_t d6=1,d5=o->sprhs;
        if(d4<0){a6=1;d6=-d6;d5=-d5;d4=-d4;}
        tt_set_free_long(o,0,a6);tt_set_word(o,25,d6);tt_set_word(o,26,d5);tt_set_word(o,27,d4);
        tt_set_word(o,28,o->yposi.w.h+7);
        for(;;){
            a6=tt_free_long(o,0);
            int16_t d3=o->xposi.w.h+tt_word(o,26);
            if(a6!=2)d3^=15;
            int16_t d2=tt_word(o,28);
            short d1=a6==1?emycol_l3(o,d3,d2):emycol_r3(o,d3,d2);
            if(d1<0)break;
            if(tt_word(o,27)<2){tt_set_word(o,27,tt_word(o,27)-1);break;}
            tt_set_word(o,27,tt_word(o,27)-1);
            o->xposi.w.h+=tt_word(o,25);
        }
    }
    if(cc_ride(i))p->xposi.w.h=o->xposi.w.h;
}
static void ukidai_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhs=o->sprhsize=16;o->sprvsize=8;o->sproffset=848;
        tt_set_word(o,29,o->xposi.w.h);
        /* UKIDAI.C a_init: plain frameout keeps ACTSET's loaded bit (gone for the act). */
        if(watermoveposi!=1920 && watermoveposi!=1504){if(pool[i].origin!=65535)consumed[pool[i].origin]=1;remove_slot(i);return;}
        /* fall through */
    case 2:
        o->yposi.w.h=waterposi;
        if(watermoveposi==waterposi_m){
            if(waterposi_m==1920){
                o->r_no0=4;o->yposi.w.h=waterposi;
                if(cc_ride(i)){o->r_no0+=2;o->xposi.w.h=p->xposi.w.h;watermoveposi=1504;}
                break;
            }
            if(waterposi_m==1504){
                o->r_no0=8;o->yspeed.w=-(int16_t)(uint16_t)((waterspeed<<8)|water_flag);ukidai_move1(i);break;
            }
            remove_slot(i);return;
        }
        break;
    case 4:
        o->yposi.w.h=waterposi;
        if(cc_ride(i)){o->r_no0+=2;o->xposi.w.h=p->xposi.w.h;watermoveposi=1504;}
        break;
    case 6:
        o->r_no0+=2;o->yspeed.w=-(int16_t)(uint16_t)((waterspeed<<8)|water_flag);
        /* fall through */
    case 8:ukidai_move1(i);break;
    }
    cc_object_draw(o);tt_frameout(i,tt_word(o,29));
}

/* ---- PLAYSUB4.C bou: pole the player hangs on --------------------------- */
static void bou_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    switch(o->r_no0){
    case 0:o->actflg|=4;o->sproffset=17144;o->r_no0+=2;
        /* fall through */
    case 2:{
        if(editmode.b.h)break;
        int16_t d=o->xposi.w.h-p->xposi.w.h+4;
        if(d<0 || d>=8)break;
        d=o->yposi.w.h-p->yposi.w.h+24;
        if(d<0 || d>=48)break;
        p->actfree[2]|=1;p->xposi.w.h=o->xposi.w.h;
        int16_t d1=0,d0=24;if(p->xspeed.w<0){d1=1;d0=-d0;}
        p->cddat=(p->cddat&254)|d1;o->actflg|=d1;p->xposi.w.h+=d0;p->mstno.b.h=17;
        tt_set_word(o,23,o->userflag.b.h?60:180);o->r_no0+=2;break;
    }
    case 4:
        tt_set_word(o,23,tt_word(o,23)-1);
        if(tt_word(o,23) && !(swdata1.b.l&112)){
            if(swdata1.b.h&1){if(o->yposi.w.h-24>=--p->yposi.w.h)p->yposi.w.h=o->yposi.w.h-24;}
            else if(swdata1.b.h&2){if(o->yposi.w.h+24<++p->yposi.w.h)p->yposi.w.h=o->yposi.w.h+24;}
            break;
        }
        p->actfree[2]&=254;o->patno=1;o->r_no0+=2;break;
    }
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}
