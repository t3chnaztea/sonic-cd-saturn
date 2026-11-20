/* Metallic Madness (R8) Act 2-3 transport and doors: R8/SW8.C (floor
   switch), TOBIRA.C (the two-leaf door), PIPE8.C (pipe caps and their
   shutters), SHOOT.C (the pipe route "shooter"), SHUT.C (shut: the boss
   room shutter; kaiten: the rotating floor that swaps the player's layer).
   Line-for-line ports on the PC scratch layout (objects_mm_common.inc).
   Quirks and gaps kept:
   - Subtype 128 (10 Act 2 placements) is shoot_s, the junction the player
     steers: it copies swdata1 (the pad) to swdata, and each press sends the
     player 16 pixels that way; its route counters stay 0, so one step ends
     the ride (native hook: swdata/swdata1 versus player.c's input).
     mspd_set's table is dead: every placed subtype is negative as a char.
     Route shooters never draw and never frame out. The PC's route pointer
     ((unsigned short**)o)[16] (actfree bytes 18-21) is derived from the
     subtype and those bytes stay zero.
   - TOBIRA's master draws its slave (actionsub(&actwk[ano])); the slave's
     own update only checks its master. mm_zone_step keeps the slave's draw.
     A master with userflag 0 opens only when another actor sets its
     actfree[21] (HOTA8's boss room door).
   - SHUT forces userflag 1 in init, so the first shutter always sits 8 to
     the left; its child (userflag 0) sits 8 to the right. They move once
     bossstart bit 7 is set and write block 0 over a 12-block column
     (block_wrt) every 16 pixels, 16 times.
   - KAITEN's ridechk_k lacks a return statement but its value is used
     (UB); the port returns ridechk's result, the value left in d0. The
     rotating floor also sets sproffset bit 15 on actwk[6] and [8..11]
     (the PC's shield and invincibility stars); native objects live there,
     so the port changes only the player: the native shield/star renderers
     must follow the player's layer (native hook). */
extern short time_stop;
extern unsigned char switchflag[32];
extern unsigned char bossstart,shut_flag;
extern void block_wrt(unsigned short,unsigned short,unsigned short);
extern ushort_union swdata1;
static const unsigned short mm_shooterposi_d[11]={20,896,1744,896,1920,640,1920,640,896,1144,896};
static const unsigned short mm_shooterposi_e[11]={20,1120,896,640,896,640,1920,896,1920,896,1720};
static const unsigned short mm_shooterposi_f[5]={8,1152,720,1152,888};
static const unsigned short mm_shooterposi_10[5]={8,1152,864,1152,696};
static const unsigned short mm_shooterposi_11[13]={24,1152,928,1152,1152,1280,1152,1536,896,1664,896,1664,696};
static const unsigned short mm_shooterposi_12[13]={24,1664,720,1664,896,1536,896,1280,1152,1152,1152,1152,904};
static const unsigned short mm_shooterposi_13[15]={28,1184,896,1280,896,1536,1152,1664,1152,1664,1664,1920,1664,1920,1464};
static const unsigned short mm_shooterposi_14[15]={28,1920,1488,1920,1664,1664,1664,1664,1152,1536,1152,1280,896,1160,896};
static const unsigned short mm_shooterposi_15[7]={12,3712,208,3712,384,4216,384};
static const unsigned short mm_shooterposi_16[7]={12,4192,384,3712,384,3712,184};
static const unsigned short mm_shooterposi_17[5]={8,4224,208,4224,376};
static const unsigned short mm_shooterposi_18[5]={8,4224,352,4224,184};
static const unsigned short mm_shooterposi_19[9]={16,4224,416,4224,896,3968,896,3968,696};
static const unsigned short mm_shooterposi_1a[9]={16,3968,720,3968,896,4224,896,4224,392};
static const unsigned short mm_shooterposi_1b[11]={20,4256,384,4480,384,4480,1152,4992,1152,4992,952};
static const unsigned short mm_shooterposi_1c[11]={20,4992,976,4992,1152,4480,1152,4480,384,4232,384};
static const unsigned short mm_shooterposi_1d[9]={16,6272,720,6272,1152,6528,1152,6528,952};
static const unsigned short mm_shooterposi_1e[9]={16,6528,976,6528,1152,6272,1152,6272,696};
static const unsigned short mm_shooterposi_25[11]={20,896,1488,896,1664,640,1664,640,896,1144,896};
static const unsigned short mm_shooterposi_26[11]={20,1120,896,640,896,640,1664,896,1664,896,1464};
static const unsigned short mm_shooterposi_27[13]={24,1152,864,1152,640,1280,640,1536,384,1664,384,1664,184};
static const unsigned short mm_shooterposi_28[13]={24,1664,208,1664,384,1536,384,1280,640,1152,640,1152,888};
static const unsigned short mm_shooterposi_29[21]={40,1152,928,1152,1152,1280,1152,1536,896,1664,896,1664,640,1536,640,1280,384,1152,384,1152,184};
static const unsigned short mm_shooterposi_2a[21]={40,1152,208,1152,384,1280,384,1536,640,1664,640,1664,896,1536,896,1280,1152,1152,1152,1152,904};
static const unsigned short mm_shooterposi_2b[35]={68,2176,720,2176,896,2560,896,3072,384,3328,384,3584,640,3712,640,3712,896,3328,896,2816,384,2432,384,2432,640,2560,640,2816,896,3072,896,3584,384,4216,384};
static const unsigned short mm_shooterposi_2c[35]={68,4192,384,3584,384,3072,896,2816,896,2560,640,2432,640,2432,384,2816,384,3328,896,3712,896,3712,640,3584,640,3328,384,3072,384,2560,896,2176,896,2176,696};
static const unsigned short mm_shooterposi_2d[9]={16,4224,416,4224,1664,3968,1664,3968,1464};
static const unsigned short mm_shooterposi_2e[9]={16,3968,1488,3968,1664,4224,1664,4224,392};
static const unsigned short mm_shooterposi_2f[11]={20,4256,384,4480,384,4480,1152,4736,1152,4736,952};
static const unsigned short mm_shooterposi_30[11]={20,4736,976,4736,1152,4480,1152,4480,384,4232,384};
static const unsigned short mm_shooterposi_35[5]={8,1152,928,1152,1144};
static const unsigned short mm_shooterposi_36[5]={8,1152,1120,1152,904};
static const unsigned short mm_shooterposi_37[11]={20,1152,1184,1152,1408,896,1408,896,1152,1144,1152};
static const unsigned short mm_shooterposi_38[11]={20,1120,1152,896,1152,896,1408,1152,1408,1152,1160};
static const unsigned short mm_shooterposi_39[11]={20,1184,1152,1280,1152,1536,896,1664,896,1664,696};
static const unsigned short mm_shooterposi_3a[11]={20,1664,720,1664,896,1536,896,1280,1152,1160,1152};
static const unsigned short mm_shooterposi_3b[33]={64,2176,720,2176,896,2560,896,2816,640,3072,896,3328,640,3584,896,3712,896,3712,640,3584,640,3328,896,3072,640,2816,896,2560,640,2432,640,2432,440};
static const unsigned short mm_shooterposi_3c[33]={64,2432,464,2432,640,2560,640,2816,896,3072,640,3328,896,3584,640,3712,640,3712,896,3584,896,3328,640,3072,896,2816,640,2560,896,2176,896,2176,696};
static const unsigned short *const mm_shooterpositbl[61]={mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_d,mm_shooterposi_e,mm_shooterposi_f,mm_shooterposi_10,mm_shooterposi_11,mm_shooterposi_12,mm_shooterposi_13,mm_shooterposi_14,mm_shooterposi_15,mm_shooterposi_16,mm_shooterposi_17,mm_shooterposi_18,mm_shooterposi_19,mm_shooterposi_1a,mm_shooterposi_1b,mm_shooterposi_1c,mm_shooterposi_1d,mm_shooterposi_1e,mm_shooterposi_25,mm_shooterposi_25,mm_shooterposi_25,mm_shooterposi_25,mm_shooterposi_25,mm_shooterposi_25,mm_shooterposi_25,mm_shooterposi_26,mm_shooterposi_27,mm_shooterposi_28,mm_shooterposi_29,mm_shooterposi_2a,mm_shooterposi_2b,mm_shooterposi_2c,mm_shooterposi_2d,mm_shooterposi_2e,mm_shooterposi_2f,mm_shooterposi_30,mm_shooterposi_35,mm_shooterposi_35,mm_shooterposi_35,mm_shooterposi_35,mm_shooterposi_35,mm_shooterposi_36,mm_shooterposi_37,mm_shooterposi_38,mm_shooterposi_39,mm_shooterposi_3a,mm_shooterposi_3b,mm_shooterposi_3c};

/* ---- SW8.C: floor switch ------------------------------------------------ */
static void sw8_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=16;o->sprvsize=8;mm_ws(o,32,(int8_t)o->userflag.b.h);return;}
    o->actfree[20]=o->actfree[21];
    short a=mm_w(o,32);
    if(tp_hitchk(o,p) && p->yposi.w.h<=o->yposi.w.h){o->actfree[21]=255;switchflag[a]|=192;}
    else{o->actfree[21]=0;switchflag[a]&=127;}
    if(!o->actfree[20] && o->actfree[21]==255){
        if(o->actflg&128)soundset(191);
        switchflag[a]^=32;p->yposi.w.h+=8;o->yposi.w.h+=4;++o->patno;o->sprvsize-=4;
    }
    /* SW8.C:67 has 12; retail lifts Sonic 8 on release (R81A $20D8C6,
       R82A $20F498, R83C $20F260 subq #8; retail MM2A row 2320: 709 to 701). */
    if(o->actfree[20]==255 && !o->actfree[21]){p->yposi.w.h-=8;o->yposi.w.h-=4;--o->patno;o->sprvsize+=4;}
    tp_draw(o);tp_frameout_s(o);
}

/* ---- TOBIRA.C: the door (master and slave leaf) ------------------------ */
static void tobira_ini_com(const sprite_status *m,sprite_status *a){
    a->actflg|=4;a->sprpri=3;a->sproffset=1150;a->sprhsize=8;a->sprvsize=16;
    a->yposi.w.h=mm_w(m,25);mm_ws(a,26,mm_w(m,25));mm_ws(a,27,mm_w(m,25));
}
static int tobira_area(const sprite_status *o,short d4,short d5){
    short d0=actwk[0].xposi.w.h-o->xposi.w.h-d4;
    if((unsigned short)d5<=(unsigned short)d0)return 0;
    d0=actwk[0].yposi.w.h-mm_w(o,25)+48;
    return (unsigned short)d0<96;
}
static void tobira_act(sprite_status *o){
    static const uint8_t pchg00[]={2,0,1,255};
    static const uint8_t *const pchg[]={pchg00};
    sprite_status *p=&actwk[0];
    short m=mm_w(o,23);
    if(m){if(actwk[m&127].actno!=SCD_OBJ_R8_TOBIRA)tp_frameout(o);return;}
    if(!o->r_no0){
        o->r_no0+=2;mm_ws(o,25,o->yposi.w.h-16);
        sprite_status *a;
        if(tp_actwkchk2(o,&a)){tp_frameout(o);return;}
        a->xposi.w.h=o->xposi.w.h;mm_ws(a,23,(uint16_t)mm_index(o));mm_ws(o,24,(uint16_t)mm_index(a));tp_setactno(a,o->actno);
        tobira_ini_com(o,a);a->yposi.w.h-=16;mm_ws(a,26,mm_w(a,26)-16);mm_ws(a,27,mm_w(a,27)-49);
        tobira_ini_com(o,o);o->yposi.w.h+=16;mm_ws(o,26,mm_w(o,26)+16);mm_ws(o,27,mm_w(o,27)+49);
        return;
    }
    sprite_status *s=&actwk[(uint16_t)mm_w(o,24)&127];
    tp_hitchk(s,p);tp_hitchk(o,p);
    switch(o->r_no0){
    case 2:
        if(o->actfree[21])o->actfree[21]=0;
        else if(!o->userflag.b.h || !tobira_area(o,o->userflag.b.h!=1?-72:8,64))break;
        o->r_no0+=2;break;
    case 4:
        o->yposi.w.h+=2;s->yposi.w.h-=2;
        if(mm_w(o,27)<=o->yposi.w.h){o->r_no0+=2;o->yposi.w.h=mm_w(o,27);s->yposi.w.h=mm_w(s,27);}
        break;
    case 6:
        if(o->userflag.b.h && !tobira_area(o,o->userflag.b.h!=1?-72:-40,112))o->r_no0+=2;
        break;
    case 8:
        o->yposi.w.h-=2;s->yposi.w.h+=2;
        if(mm_w(o,26)>=o->yposi.w.h){o->r_no0=2;o->yposi.w.h=mm_w(o,26);s->yposi.w.h=mm_w(s,26);}
        break;
    }
    tp_patchg(o,pchg);s->patno=o->patno;mm_draw_other(s);tp_draw(o);tp_frameout_s(o);
}

/* ---- PIPE8.C: pipe caps and the shutter between them ------------------- */
static void pipe8_init_sub(const sprite_status *m,sprite_status *a){
    a->r_no0=6;a->actflg|=4;a->sprpri=3;a->sproffset=828;a->sprhs=a->sprhsize=8;a->sprvsize=4;a->yposi.w.h=m->yposi.w.h;
}
static int pipe8_check1(const sprite_status *o,const sprite_status *a,short d0,short d1,short d2,short d3){
    short d4=a->yposi.w.h-o->yposi.w.h-d2;
    if((unsigned short)d3<=(unsigned short)d4)return 0;
    d4=a->xposi.w.h-o->xposi.w.h-d0;
    return (unsigned short)d1>(unsigned short)d4;
}
static int pipe8_check2(const sprite_status *o,const sprite_status *a,short d0,short d1,short d2,short d3){
    return a->yspeed.w<0 && pipe8_check1(o,a,d0,d1,d2,d3);
}
static void pipe8_shatter(sprite_status *o){
    static const uint8_t p00[]={0,1,3,5,255},p01[]={0,4,3,2,1,255};
    static const uint8_t *const pchg[]={p00,p01};
    sprite_status *p=&actwk[0];
    if(actwk[(uint16_t)mm_w(o,33)&127].actno!=SCD_OBJ_R8_PIPE8){tp_frameout(o);return;}
    unsigned char *sw=&switchflag[(int8_t)o->userflag.b.h];
    switch(o->r_no0){
    case 0:o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sproffset=828;o->sprhs=o->sprhsize=16;o->sprvsize=4;break;
    case 2:o->r_no0+=2;o->patno=1;*sw&=191;break;
    case 4:
        tp_ridechk(o,p);
        if((int8_t)*sw<0){o->r_no0+=2;mm_ws(o,23,5);}
        else if(pipe8_check2(o,p,-8,16,-3,123)){o->r_no0+=6;o->patno=5;}
        break;
    case 6:
        if(mm_ws(o,23,mm_w(o,23)-1)<0){o->r_no0+=2;o->patno=5;}
        else tp_patchg(o,pchg);
        break;
    case 8:if(!pipe8_check1(o,p,-256,512,-160,320))o->r_no0-=6;break;
    case 10:if(pipe8_check2(o,p,-8,16,-120,116)){o->r_no0+=2;o->mstno.b.h=1;mm_ws(o,23,7);}break;
    case 12:
        if(mm_ws(o,23,mm_w(o,23)-1)<0){o->r_no0-=10;o->mstno.b.h=0;o->patno=1;}
        else tp_patchg(o,pchg);
        break;
    }
    tp_draw(o);
}
static void pipe8_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if((int8_t)o->userflag.b.l<0){pipe8_shatter(o);return;}
    if((int8_t)o->userflag.b.h<0 && actwk[(uint16_t)mm_w(o,33)&127].actno!=SCD_OBJ_R8_PIPE8){tp_frameout(o);return;}
    switch(o->r_no0){
    case 0:mm_ws(o,23,o->xposi.w.h);pipe8_init_sub(o,o);o->r_no0=2;o->patno=5;
        /* fall through: act0wait1 */
    case 2:{
        short d0=p->xposi.w.h-o->xposi.w.h+320;
        if((unsigned short)d0>=640)break;
        o->r_no0+=2;o->patno=0;break;
    }
    case 4:{
        sprite_status *a;
        if(tp_actwkchk(&a)){tp_frameout(o);return;}
        mm_ws(a,33,(uint16_t)mm_index(o));a->userflag.b.h=-1;tp_setactno(a,o->actno);a->xposi.w.h=o->xposi.w.h+48;a->actflg^=1;a->cddat^=1;
        pipe8_init_sub(o,o);pipe8_init_sub(o,a);
        if(tp_actwkchk(&a)){tp_frameout(o);return;}
        a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=-1;tp_setactno(a,o->actno);
        a->xposi.w.h=o->xposi.w.h+24;a->yposi.w.h=o->yposi.w.h;mm_ws(a,33,(uint16_t)mm_index(o));
    }   /* fall through: act0move */
    case 6:tp_ridechk(o,p);break;
    }
    tp_draw(o);
    if((int8_t)o->userflag.b.h>=0)tp_frameout_s00(o,mm_w(o,23));
}

/* ---- SHOOT.C: the pipe route ------------------------------------------- */
static void shooter_spdset(sprite_status *o){
    sprite_status *p=&actwk[0];
    short m0,m1;m0=m1=p->mspeed.w;
    short cx=mm_w(o,29)-p->xposi.w.h;if(cx<0){cx=-cx;m0=-m0;}
    short cy=mm_w(o,30)-p->yposi.w.h;if(cy<0){cy=-cy;m1=-m1;}
    int lx,ly;
    if(cx<=cy){
        cy=mm_w(o,30)-p->yposi.w.h;ly=(int)((uint32_t)(int32_t)cy<<16);ly/=m1;
        cx=mm_w(o,29)-p->xposi.w.h;lx=(int)((uint32_t)(int32_t)cx<<16);if(lx)lx/=ly;
        p->xspeed.w=(short)lx;p->yspeed.w=m1;if(ly<0)ly=-ly;
        o->actfree[4]=(uint8_t)(ly>>8);o->actfree[5]=(uint8_t)ly;return;
    }
    cx=mm_w(o,29)-p->xposi.w.h;lx=(int)((uint32_t)(int32_t)cx<<16);lx/=m0;
    cy=mm_w(o,30)-p->yposi.w.h;ly=(int)((uint32_t)(int32_t)cy<<16);if(ly)ly/=lx;
    p->yspeed.w=(short)ly;p->xspeed.w=m0;if(lx<0)lx=-lx;
    o->actfree[4]=(uint8_t)(lx>>8);o->actfree[5]=(uint8_t)lx;
}
static void shooter_capture(sprite_status *o);
static void shooter_move3(sprite_status *o,const unsigned short *route);
/* SHOOT.C shoot_s: the junction the player steers (subtype 128). */
static void shoot_s_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(p->r_no0>=6)return;
    swdata.w=swdata1.w;
    switch(o->r_no0){
    case 0:o->actflg|=4;mm_ws(o,31,4);mm_ws(o,29,o->xposi.w.h);mm_ws(o,30,o->yposi.w.h);o->r_no0+=2;break;
    case 2:shooter_capture(o);break;
    case 4:
        if(swdata.b.l&1)mm_ws(o,30,mm_w(o,30)-16);
        else if(swdata.b.l&2)mm_ws(o,30,mm_w(o,30)+16);
        else if(swdata.b.l&4)mm_ws(o,29,mm_w(o,29)-16);
        else if(swdata.b.l&8)mm_ws(o,29,mm_w(o,29)+16);
        else break;
        o->r_no0+=2;p->mspeed.w=4096;shooter_spdset(o);break;
    case 6:shooter_move3(o,0);break;
    }
    tp_frameout_s(o);
}
static void shooter_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    /* The flagwork clearing ahead of this needs time_flag bit 7 (time travel
       in progress), which never reaches native actors. */
    if(p->mstno.b.h==43 || p->r_no0>=6)return;
    if((unsigned char)o->userflag.b.h==128){shoot_s_act(o);return;}
    const unsigned short *route=mm_shooterpositbl[(unsigned char)o->userflag.b.h&127];
    switch(o->r_no0){
    case 0:
        o->actflg=4;o->sprpri=1;o->sprhsize=16;o->r_no0+=2;
        o->actfree[16]=(uint8_t)(route[0]>>8);o->actfree[17]=(uint8_t)route[0];
        mm_ws(o,29,route[1]);mm_ws(o,30,route[2]);
        /* fall through: shooterinit calls shootermove */
    case 2:shooter_capture(o);break;
    case 4:shooter_spdset(o);o->r_no0+=2;soundset(145);break;
    case 6:shooter_move3(o,route);break;
    }
    /* Retail shooter (R82A $20825A, R82B $2084EA, R82C $2085B0, R82D $208482):
       cmpib #4,r_no0; bcc rts; jmp frameout_s. SHOOT.C lost that tail, so an
       idle shooter never freed its slot (retail MM2D frees slot 33 at row 2816). */
    if(o->r_no0<4)tp_frameout_s(o);
}
/* SHOOT.C shootermove: take the player in. */
static void shooter_capture(sprite_status *o){
    sprite_status *p=&actwk[0];
    {
        short c=p->xposi.w.h-o->xposi.w.h+16;
        if(c>=32 || c<0)return;
        c=p->yposi.w.h-o->yposi.w.h+16;
        if(c>=32 || c<0 || p->actfree[2])return;
        if(p->r_no0==4){p->r_no0-=2;scd_word_set(p,26,120);}
        o->r_no0+=2;p->actfree[2]=129;p->sproffset&=32767;p->mstno.b.h=2;
        p->mspeed.w=4096;
        if((int8_t)o->userflag.b.h>=0 && (o->userflag.b.h&15)<4){
            static const short mspdtbl[4]={4096,3072,3072,2048};
            short s=mspdtbl[o->userflag.b.h&15];if(s>p->mspeed.w)p->mspeed.w=s;
        }
        p->xspeed.w=p->yspeed.w=0;o->cddat&=223;p->cddat&=223;p->cddat|=2;
        p->xposi.w.h=o->xposi.w.h;p->yposi.w.h=o->yposi.w.h;o->actfree[8]=0;soundset(145);
    }
}
/* SHOOT.C shootermove3: ride one leg; route is the table after its length
   (shoot_s never sets its counters, so it ends after one leg). */
static void shooter_move3(sprite_status *o,const unsigned short *route){
    sprite_status *p=&actwk[0];
    {
        if((int8_t)--o->actfree[4]<0){
            p->xposi.w.h=mm_w(o,29);p->yposi.w.h=mm_w(o,30);
            unsigned char mc=(unsigned char)(o->actfree[16]+4);
            if(mc>=o->actfree[17]){p->yposi.w.h&=2047;o->r_no0=0;p->actfree[2]=0;return;}
            o->actfree[16]=mc;
            mm_ws(o,29,route[1+mc/2]);mm_ws(o,30,route[1+mc/2+1]);
            shooter_spdset(o);return;
        }
        p->xposi.l+=(int)p->xspeed.w<<8;p->yposi.l+=(int)p->yspeed.w<<8;
    }
}

/* ---- SHUT.C shut: the boss room shutter -------------------------------- */
static void shut_act(sprite_status *o){
    switch(o->r_no0){
    case 0:{
        mm_ws(o,23,o->xposi.w.h);o->userflag.b.h=1;o->actflg|=1;
        o->xposi.w.h-=8;
        o->r_no0+=2;o->actflg|=4;o->sprpri=2;o->sproffset=32768;
        sprite_status *n;
        if(tp_actwkchk(&n)){tp_frameout_s0(o);return;}
        mm_ws(n,23,mm_w(o,23));n->xposi.w.h=mm_w(o,23);n->yposi.w.h=o->yposi.w.h;n->xposi.w.h+=8;
        n->r_no0+=2;n->actflg|=4;n->sprpri=2;n->sproffset=32768;tp_setactno(n,SCD_OBJ_R8_SHUT);
        break;
    }
    case 2:
        if((int8_t)bossstart>=0)break;
        shut_flag=0;o->r_no0+=2;break;
    case 4:{
        unsigned short bx=(unsigned short)(o->xposi.w.h-8);
        if(!(bx&15)){
            if(++o->actfree[2]>=17){tp_frameout_s0(o);return;}
            unsigned short by=(unsigned short)(o->yposi.w.h-96);
            for(unsigned i=0;i<12;i++,by+=16)block_wrt(0,bx,by);
        }
        o->xposi.w.h+=2;
        if(o->userflag.b.h)o->xposi.w.h-=4;
        break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- SHUT.C kaiten: the rotating floor --------------------------------- */
/* ACTSET.C actwkchk2 as a probe: the next free actor after o, unclaimed. */
static sprite_status *mm_free_after(sprite_status *o){
    for(unsigned i=tp_slot(o)+1;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type)return &actwk[i+1];
    return 0;
}
static void kaiten_act(sprite_status *o){
    static const uint8_t kaitenchg0[]={2,0,1,255};
    static const uint8_t *const kaitenchg[]={kaitenchg0};
    sprite_status *p=&actwk[0];
    int dy=o->yposi.w.h-p->yposi.w.h;
    if(dy>22 && dy<=156){if(prio_flag)p->sproffset&=32767;else p->sproffset|=32768;}
    switch(o->r_no0){
    case 0:{
        static const unsigned char tbl[3]={64,149,234};
        sprite_status *old=o;
        for(int i=0;i<4;i++){old=mm_free_after(old);if(!old)break;}
        if(!old)break;
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhsize=40;o->sprvsize=8;
        sprite_status *n;
        tp_actwkchk2(o,&n);
        n->actflg|=4;n->sprpri=1;n->sprhsize=40;n->sprvsize=8;n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h-176;
        n->userflag.b.h=1;n->r_no0+=2;tp_setactno(n,SCD_OBJ_R8_KAITEN);
        for(int i=0;i<3;i++){
            tp_actwkchk2(o,&n);
            n->actflg|=4;n->sprpri=1;n->sprhsize=8;n->sprvsize=80;n->actfree[3]=tbl[2-i];n->patno=2;n->r_no0=8;
            mm_ws(n,23,o->xposi.w.h);n->yposi.w.h=o->yposi.w.h-88;tp_setactno(n,SCD_OBJ_R8_KAITEN);
            short sn,cs;sinset(n->actfree[3],&sn,&cs);
            n->xposi.w.h=mm_w(n,23)+(short)((cs<<5)>>8);
        }
        break;
    }
    case 2:{
        if(o->userflag.b.h){if(p->mstno.b.h>=51)tp_patchg(o,kaitenchg);break;}
        if(!tp_ridechk(o,p)){o->actfree[2]=0;break;}
        /* Retail kaiten_move0 (R83D $20AB8C): subw; addqw #8; bcs; cmpiw #16;
           bcc. The carry, not a sign test, rejects a player 1-8 px right of
           the centre (SHUT.C:212-214 reads it as cal_xposi < 0), so Sonic
           is taken only at x in (centre-8, centre] (retail MM3D: 2447 rides
           on, 2440 at 2786 is taken). */
        unsigned d=(uint16_t)(o->xposi.w.h-p->xposi.w.h)+8u;
        if(d>0xffffu || d>=16){o->actfree[2]=0;break;}
        if(o->actfree[2]&1)break;
        o->actfree[2]|=1;p->actfree[2]|=1;p->xposi.w.h=o->xposi.w.h;p->xspeed.w=p->mspeed.w=0;
        p->mstno.b.h=prio_flag?52:51;o->r_no0+=2;
        break;
    }
    case 4:
        tp_patchg(o,kaitenchg);
        if(p->mstno.b.h!=5){tp_ridechk(o,p);break;}
        o->r_no0+=2;
        /* fall through: kaiten_move2 */
    case 6:
        p->actfree[2]&=254;tp_ridechk(o,p);prio_flag^=1;p->actflg^=1;p->cddat^=1;
        p->sproffset|=32768;if(prio_flag)p->sproffset&=32767;
        o->r_no0=2;break;
    case 8:
        if(p->mstno.b.h<51)break;
        o->r_no0+=2;o->actfree[4]=o->actfree[3]+128;break;
    case 10:{
        if(p->mstno.b.h<51){o->r_no0-=2;o->actfree[3]=o->actfree[4];}
        else{
            unsigned char d=4;
            if(!(p->cddat&1)){if(prio_flag)d=(unsigned char)-d;}
            else if(!prio_flag)d=(unsigned char)-d;
            o->actfree[3]+=d;
        }
        short sn,cs;sinset(o->actfree[3],&sn,&cs);
        o->xposi.w.h=mm_w(o,23)+(short)((cs*24)>>8);
        o->sprpri=(int8_t)o->actfree[3]>=0?4:1;
        break;
    }
    }
    if(!o->r_no0){tp_frameout_s0(o);return;}
    tp_draw(o);
    if(o->r_no0<8)tp_frameout_s(o);else tp_frameout_s00(o,mm_w(o,23));
}
