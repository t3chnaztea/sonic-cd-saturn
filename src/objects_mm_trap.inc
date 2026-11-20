/* Metallic Madness (R8) traps: R8/TRAP_R81.C, TRAP_R82.C and TRAP_R83.C
   (togedair8 spike/spring blocks and their harir8 spikes, R82's tokusyu
   block, togeita dropping spike plates, futagor8 folding floor, gater8),
   R8/KOMA8.C (the top that carries a spring) and SPRING.C's spring as the
   zone-local child SCD_OBJ_R8_SPRING8 that koma8 and togedair8 spawn
   (retail actno 10, the global spring; it follows its parent through word
   28 and the offsets in actfree[14]/[15]).
   Each act links its own TRAP file: togedair8, harir8 and togeita dispatch
   on objects_act (0 R81, 1 R82, 2 R83).
   Quirks kept:
   - The linked spring never checks that its parent still lives: it keeps
     following that actor slot until its own saved x leaves the screen.
   - R82 dair8_init retries the spawn every update without advancing when
     the actor table is full; R81 frames the block out instead.
   - R82's tokusyu block never leaves r_no0 0: its init runs every update.
   - gater8 frames itself out at once; anar8 is not placed in any act.
   - togeita_move2 adds tbl[subtype] (6 entries) to y: only subtypes 0-5
     are in range; togeita_move3 is a no-op and unreachable.
   - R82 togeita clears word 28 (its link to the spike child) on landing.
   - SPRING.C spring_d (r_no1 5) is never reached by these children. */
extern void speedset2(sprite_status*);
extern void speedset(sprite_status*); /* ACTION.C; objects_mm_remaining.inc ITEM.C itemmove */

/* ---- SPRING.C spring (linked child) ------------------------------------ */
static const uint8_t spring8_chg0[]={0,0,1,1,2,2,2,2,2,2,1,252};
static const uint8_t *const spring8_chg[]={spring8_chg0};
static void spring8_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(!o->r_no0 || (o->actflg&128))switch(o->r_no0){
    case 0:{
        static const short sjumptbl[2]={-4096,-2560};
        unsigned char d0=(unsigned char)o->userflag.b.h;
        o->r_no0+=2;o->sproffset=1312;o->actflg|=4;o->sprhsize=16;o->sprvsize=8;mm_ws(o,29,o->xposi.w.h);o->sprpri=4;
        if(d0&4){o->r_no0=8;o->sprhsize=8;o->sprvsize=16;}
        else if(d0&8){o->r_no0=20;o->sprhsize=24;o->sprvsize=12;}
        else if(o->actflg&2){o->r_no0=14;o->cddat|=1;}
        if(d0&2)o->sproffset|=8192;
        mm_ws(o,26,sjumptbl[(d0&2)/2]);
        break;
    }
    case 2:
        if(!(o->actflg&128) || !tp_ride_on_chk(o,p))break;
        o->r_no0=4;p->yposi.w.h+=8;p->yspeed.w=mm_w(o,26);p->cddat|=2;p->cddat&=~8;p->mstno.b.h=16;o->cddat&=~8;soundset(152);
        break;
    case 4:case 10:case 16:case 22:tp_patchg(o,spring8_chg);break;
    case 6:o->cddat&=247;o->mstno.b.l=1;o->r_no0-=4;o->patno=0;break;
    case 8:
        if(!(o->actflg&128))break;
        tp_ride_on_chk(o,p);
        if(!(o->cddat&32))break;
        o->r_no0=10;p->xspeed.w=mm_w(o,26);p->xposi.w.h+=8;p->cddat|=1;
        if(!(o->cddat&1)){p->xposi.w.h-=16;p->xspeed.w=-p->xspeed.w;p->cddat&=254;}
        mm_ws(p,33,15);p->mspeed.w=p->xspeed.w;
        if(!(p->cddat&4))p->mstno.b.h=0;
        p->direc.b.h=0;o->cddat&=223;p->cddat&=223;soundset(152);
        break;
    case 12:case 18:case 24:o->mstno.b.l=1;o->r_no0-=4;o->patno=0;break;
    case 14:
        if(!(o->actflg&128) || !tp_hitchk_u(o,p))break;
        o->r_no0=16;p->yposi.w.h-=8;p->yspeed.w=(short)-mm_w(o,26);p->cddat|=2;p->cddat&=247;o->cddat&=247;soundset(152);
        break;
    case 20:{
        if(!(o->actflg&128))break;
        if(!tp_ride_on_chk(o,p) && !(o->cddat&32))break;
        o->r_no0=22;
        short sn,cs;sinset(224,&sn,&cs);
        short d2=(short)-mm_w(o,26);
        int sinl=(int)(uint16_t)sn*d2,cosl=(int)(uint16_t)cs*d2;
        sinl>>=8;cosl>>=8;
        p->yspeed.w=(short)sinl;p->xspeed.w=(short)cosl;p->yposi.w.h+=8;
        if(o->actflg&2){p->yposi.w.h-=16;p->yspeed.w=-p->yspeed.w;}
        p->cddat&=254;p->xposi.w.h-=8;
        if(o->cddat&1){p->xposi.w.h+=16;p->cddat|=1;p->xspeed.w=-p->xspeed.w;}
        p->cddat|=2;p->cddat&=247;p->cddat&=223;o->cddat&=247;o->cddat&=223;soundset(152);
        tp_patchg(o,spring8_chg);
        break;
    }
    }
    tp_draw(o);
    uint16_t d1=(uint16_t)mm_w(o,28);
    if(d1){
        const sprite_status *a=&actwk[d1&127];
        o->xposi.w.h=a->xposi.w.h+(int8_t)o->actfree[14];o->yposi.w.h=a->yposi.w.h+(int8_t)o->actfree[15];
    }
    uint16_t d0=(uint16_t)mm_w(o,29)&0xFF80;
    d0-=(uint16_t)(tp_scra_h()-128)&65408;
    if(d0>640)tp_frameout(o);
}
/* A spring riding on actor o (koma8, togedair8). */
static void mm_spring_child(sprite_status *o,sprite_status *n,unsigned char yofs,unsigned char sub){
    n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;n->actfree[15]=yofs;mm_ws(n,28,(uint16_t)mm_index(o));
    n->userflag.b.h=sub;tp_setactno(n,SCD_OBJ_R8_SPRING8);
}

/* ---- KOMA8.C: the top that carries a spring ---------------------------- */
static void koma8_act(sprite_status *o){
    static const uint8_t komachg0[]={8,0,1,255};
    static const uint8_t *const komachg[]={komachg0};
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhsize=8;o->sprvsize=6;mm_ws(o,29,o->xposi.w.h);o->xspeed.w=256;
        sprite_status *n;
        if(tp_actwkchk2(o,&n)){tp_frameout(o);return;}
        mm_spring_child(o,n,240,(unsigned char)(o->userflag.b.h&15));n->yposi.w.h-=16;
        mm_ws(o,31,80);
        if((int8_t)o->userflag.b.h<0)mm_ws(o,31,64);
    }   /* fall through: koma_init calls koma_move */
    case 2:{
        short c=emycol_d(o);
        if(c<0){o->yposi.w.h+=c;mm_ws(o,27,o->yposi.w.h);o->r_no0+=2;}
        else ++o->yposi.w.h;
        break;
    }
    case 4:{
        short c=o->xspeed.w>=0?emycol_r(o,32):emycol_l(o,232);
        int turn=1;
        if(c>=7){
            short d=o->xposi.w.h-mm_w(o,29);if(d<0)d=-d;
            if(d<mm_w(o,31)){
                c=emycol_d(o);
                if(c>=-7 && c<=7){o->yposi.w.h+=c;turn=0;}
            }
        }
        if(turn)o->xspeed.w=-o->xspeed.w;
        speedset2(o);tp_patchg(o,komachg);tp_draw(o);
        break;
    }
    }
    tp_frameout_s00(o,mm_w(o,29));
}

/* ---- TRAP_R8x.C harir8: spikes (placed, or riding a togedair8) --------- */
/* The spike-top contact: a player standing on it (cddat bit 3) is hurt. */
static void harir8_stand_hurt(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(!tp_hitchk(o,p) || !(o->cddat&8))return;
    if(plpower_a || plpower_m || p->r_no0>=4 || scd_word_get(p,26))return;
    p->yposi.l-=(int)p->yspeed.w<<8;
    scd_objects_hurt(o->xposi.w.h);
}
static int mm_near_y(const sprite_status *o){short c=actwk[0].yposi.w.h-o->yposi.w.h;if(c<0)c=-c;return c<32;}
/* R81/R83 harir8_move. */
static void harir8_move13(sprite_status *o){
    if(!o->patno){if(mm_near_y(o))harir8_stand_hurt(o);return;}
    if(!(o->actflg&128) || !mm_near_y(o))return;
    tp_hitchk(o,&actwk[0]);
}
/* R82 harir8_ridechk / harir8_move. */
static void harir8_ridechk82(sprite_status *o){
    if(!o->patno){o->colino=0;harir8_stand_hurt(o);return;}
    if(o->actflg&128)tp_hitchk(o,&actwk[0]);
}
static void harir8_move82(sprite_status *o){
    int8_t t=(int8_t)-(int8_t)o->userflag.b.h;
    if(t<3){harir8_ridechk82(o);return;}
    if(t<5){
        o->sproffset=32768;o->colino=131;
        if(!prio_flag){harir8_ridechk82(o);return;}
    }else{
        o->sprpri=3;o->colino=131;
        if(prio_flag){harir8_ridechk82(o);return;}
    }
    o->colino=0;tp_ride_on_clr(o,&actwk[0]);
}
static void harir8_act(sprite_status *o){
    unsigned act=objects_act;
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;
        if(act==1){o->sproffset=0;o->sprpri=1;}else o->sprpri=act==0?4:3;
        mm_ws(o,29,o->xposi.w.h);mm_ws(o,27,o->yposi.w.h);o->sprhsize=16;o->sprvsize=8;
        if(act==1?!(o->userflag.b.h&1):(int8_t)o->userflag.b.h!=-1){o->patno=1;o->colino=131;o->sprhsize=18;}
    }
    if(act==1)harir8_move82(o);else harir8_move13(o);
    tp_draw(o);
    uint16_t m=(uint16_t)mm_w(o,28);
    if(m){
        const sprite_status *a=&actwk[m&127];
        if(!a->actno){tp_frameout(o);return;}
        o->xposi.w.h=a->xposi.w.h+(int8_t)o->actfree[14];o->yposi.w.h=a->yposi.w.h+(int8_t)o->actfree[15];
    }
    tp_frameout_s00(o,mm_w(o,29));
}

/* ---- TRAP_R82.C tokusyu_block (togedair8 subtype -8) ------------------- */
static void tokusyu_act(sprite_status *o){
    o->actflg|=4;o->sprpri=3;o->sprhsize=24;o->sprvsize=16;
    if(!prio_flag)tp_ride_on_clr(o,&actwk[0]);else tp_ride_on_chk(o,&actwk[0]);
    tp_draw(o);tp_frameout_s(o);
}

/* ---- TRAP_R8x.C togedair8: the block (spring or spikes on top) --------- */
static void dair8_move(sprite_status *o){
    if(!(o->actflg&128) || !mm_near_y(o))return;
    tp_hitchk(o,&actwk[0]);
}
static void togedair8_act(sprite_status *o){
    unsigned act=objects_act;
    if(act==1 && (int8_t)o->userflag.b.h==-8){tokusyu_act(o);return;}
    if((int8_t)o->userflag.b.h<0){harir8_act(o);return;}
    if(!o->r_no0){
        if(!act)o->r_no0+=2;
        o->actflg|=4;o->sprpri=3;mm_ws(o,29,o->xposi.w.h);mm_ws(o,27,o->yposi.w.h);o->sprhsize=o->sprvsize=16;
        sprite_status *n;
        if(tp_actwkchk(&n)){
            if(!act){tp_frameout(o);return;}
        }else{
            if(act)o->r_no0+=2;
            if(o->userflag.b.h!=1)mm_spring_child(o,n,232,(unsigned char)o->userflag.b.h);
            else{
                n->userflag.b.h=-1;tp_setactno(n,SCD_OBJ_R8_TOGEDAIR8);n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;
                n->actfree[15]=232;mm_ws(n,28,(uint16_t)mm_index(o));
            }
        }
    }
    dair8_move(o);
    tp_draw(o);tp_frameout_s00(o,mm_w(o,29));
}

/* ---- TRAP_R81.C futagor8: the folding floor ---------------------------- */
static void futagor8_act(sprite_status *o){
    static const uint8_t tbl[48]={0,120,8,56,1,4,8,40,2,4,8,24,3,32,8,8,4,4,24,8,5,4,40,8,6,120,56,8,5,4,40,8,4,4,24,8,
        3,32,8,8,2,4,24,8,1,4,40,8};
    if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprpri=3;mm_ws(o,29,o->xposi.w.h);mm_ws(o,27,o->yposi.w.h);}
    if(!o->actfree[16]){
        unsigned pp=(unsigned char)(o->actfree[18]*4);
        o->patno=tbl[pp];o->actfree[16]=tbl[pp+1];o->sprhsize=tbl[pp+2];o->sprvsize=tbl[pp+3];
    }else if(!--o->actfree[16]){if(++o->actfree[18]>=12)o->actfree[18]=0;}
    o->yspeed.w=o->patno?0:256;
    tp_ride_on_chk(o,&actwk[0]);tp_draw(o);tp_frameout_s00(o,mm_w(o,29));
}

/* ---- TRAP_R82.C / TRAP_R83.C togeita: dropping spike plates ------------ */
static void tr8_fout(sprite_status *o){tp_frameout_s0(o);}
static const uint8_t togeita_data0[12]={1,204,28,8,4,188,12,8,5,220,44,8};
static const uint8_t togeita_data1[12]={3,0,24,8,3,224,24,8,3,32,24,8};
static const uint8_t togeita_data2[12]={2,52,28,8,5,36,44,8,4,68,12,8};
static void togeita_dataset(const sprite_status *o,sprite_status *n,const uint8_t *d){
    unsigned pp=(unsigned char)(o->actfree[18]*4);
    n->patno=d[pp];n->sprhsize=d[pp+2];n->sprvsize=d[pp+3];mm_ws(n,29,mm_w(o,29));n->yposi.w.h=o->yposi.w.h;
    n->xposi.w.h=mm_w(o,29)+(int8_t)d[pp+1];n->userflag.b.h=o->userflag.b.h;
}
static int togeita_plchk(const sprite_status *o,short cal_x){
    short c=actwk[0].xposi.w.h-mm_w(o,29)+cal_x;
    return c>=0 && c<cal_x*2;
}
static void togeita_itaset(sprite_status *o){
    short c=actwk[0].yposi.w.h-o->yposi.w.h;
    if(c<0){c=-c;if(c>=128)return;}
    if(!togeita_plchk(o,160))return;
    short n=mm_ws(o,26,mm_w(o,26)+1);
    if(n!=300 && n!=600 && n!=840 && n!=1080)return;
    if(o->actfree[17]<5){
        sprite_status *a;
        if(tp_actwkchk(&a))return;
        a->xposi.w.h=mm_w(o,29);a->yposi.w.h=mm_w(o,27)-(short)((int8_t)o->actfree[17]*16);
        a->userflag.b.h=o->actfree[17];tp_setactno(a,SCD_OBJ_R8_TOGEITA);
        ++o->actfree[17];
    }
}
static void togeitax_act(sprite_status *o){
    static const uint8_t colitbl[6]={0,156,156,0,155,157};
    o->actflg|=4;o->patno=6;
    const sprite_status *r=&actwk[(uint16_t)mm_w(o,28)&127];
    if(r->actno!=SCD_OBJ_R8_TOGEITA){tp_frameout(o);return;}
    o->yspeed.w=r->yspeed.w;o->yposi.w.h=r->yposi.w.h+12;o->colino=colitbl[o->actfree[18]];
    tp_draw(o);
}
static void togeita_act(sprite_status *o){
    static const uint8_t ita82[56]={0,1,2,1,0,2,0,0,1,2,1,2,1,2,1,2,0,2,1,2,0,1,2,1,1,2,1,2,2,1,2,2,1,2,1,1,0,1,2,0,1,2,2,1,0,1,2,1,1,0,2,1,0,1,2,2};
    static const uint8_t ita83[56]={0,1,0,2,0,0,0,0,1,2,1,2,1,2,1,2,0,2,1,2,0,1,2,1,1,2,1,2,2,1,2,2,1,2,1,1,0,1,2,0,1,2,2,1,0,1,2,1,1,0,2,1,0,1,2,2};
    static const short drop[6]={8,32,56,80,104,128};
    int r82=objects_act==1;
    if((int8_t)o->userflag.b.h<0){togeitax_act(o);return;}
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;
        o->actfree[18]=(r82?ita82:ita83)[(int8_t)o->userflag.b.h];
        sprite_status *n;
        if(!o->actfree[19]){
            unsigned pp=(unsigned char)(o->actfree[18]*4);
            o->patno=togeita_data0[pp];o->sprhsize=togeita_data0[pp+2];o->sprvsize=togeita_data0[pp+3];
            mm_ws(o,29,o->xposi.w.h);mm_ws(o,27,o->yposi.w.h);o->xposi.w.h+=(int8_t)togeita_data0[pp+1];o->actfree[17]=1;
            if(tp_actwkchk(&n)){tr8_fout(o);return;}
            n->actfree[19]=1;togeita_dataset(o,n,togeita_data1);tp_setactno(n,SCD_OBJ_R8_TOGEITA);
            if(tp_actwkchk(&n)){tr8_fout(o);return;}
            n->actfree[19]=2;togeita_dataset(o,n,togeita_data2);tp_setactno(n,SCD_OBJ_R8_TOGEITA);
        }
        if(o->patno==3 || tp_actwkchk(&n))break;
        n->userflag.b.h=-1;tp_setactno(n,SCD_OBJ_R8_TOGEITA);n->xposi.w.h=o->xposi.w.h;n->actfree[18]=o->patno;
        mm_ws(n,28,(uint16_t)mm_index(o));mm_ws(o,28,(uint16_t)mm_index(n));
        break;
    }
    case 2:{
        short c=actwk[0].yposi.w.h-o->yposi.w.h;
        if(c<0 || c>=256)break;
        if(togeita_plchk(o,o->userflag.b.h?80:48))o->r_no0+=2;
        break;
    }
    case 4:{
        if(!o->userflag.b.h && !o->actfree[19])togeita_itaset(o);
        if(o->actfree[21])break;
        int stack=o->yposi.l;
        o->yposi.w.h+=drop[(uint8_t)o->userflag.b.h];
        short c=emycol_d(o);
        o->yposi.l=stack;
        if(c>=0){o->yposi.l+=32768;o->yspeed.w=128;}
        else{o->yspeed.w=0;if(r82)mm_ws(o,28,0);o->actfree[21]=255;}
        break;
    }
    }
    if(o->patno!=3 && (o->actflg&128) && mm_near_y(o))tp_ride_on_chk(o,&actwk[0]);
    tp_draw(o);tp_frameout_s00(o,mm_w(o,29));
}
