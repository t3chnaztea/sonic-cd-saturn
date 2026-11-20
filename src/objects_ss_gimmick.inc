/* Stardust Speedway gimmicks: R7/SLIGHT7.C (search lights), CHGWALL7.C (the
   wall that is solid on the upper layer), TEKKYU7.C (the swinging iron ball)
   and TEKKYU7J.C (the ball launcher and its jumping balls). Line-for-line
   ports on the PC scratch layout (objects_ss_common.inc). */

/* The PC's time_flag for the loaded era: 1 Present, 0 Past, 2 either Future. */
static unsigned ss_time_flag(void){return current_era==0?1:current_era==1?0:2;}

/* ---- SLIGHT7.C --------------------------------------------------------- */
static void slight7_pchgsub(sprite_status *o,const signed char *a){
    if(!o->actfree[16]){
        a+=o->actfree[18]<<2;
        o->patno=(unsigned char)*a++;o->actfree[16]=(unsigned char)*a++;
        unsigned char b1=(unsigned char)*a++;
        o->xposi.w.h=ss_w(o,29)+(short)*a++;
        o->actflg&=254;o->cddat&=254;
        if(b1){o->actflg|=1;o->cddat|=1;}
    }
    if(--o->actfree[16])return;
    if(++o->actfree[18]>=o->actfree[19])o->actfree[18]=0;
}
static void slight7_move(sprite_status *o){
    static const signed char t0[44]={0,10,0,0,3,20,0,0,2,20,0,68,1,20,0,12,3,10,0,0,2,30,1,-4,1,20,0,12,3,20,0,0,1,10,1,64,3,20,0,0,2,20,1,-16};
    static const signed char t1[32]={0,30,0,0,1,30,0,48,2,30,0,92,1,30,0,48,0,30,0,0,1,30,1,-48,2,30,1,-92,1,30,1,-48};
    static const signed char t2[16]={0,30,0,0,1,30,0,48,2,30,0,92,1,30,0,48};
    static const signed char t3[16]={0,30,0,0,1,30,1,-48,2,30,1,-92,1,30,1,-48};
    o->yposi.w.h=(short)scd_act_view_y()+112;
    switch(o->userflag.b.h){
    case 0:o->actfree[19]=11;slight7_pchgsub(o,t0);break;
    case 1:o->actfree[19]=8;slight7_pchgsub(o,t1);break;
    case 2:o->actfree[19]=4;slight7_pchgsub(o,t2);break;
    case 3:o->actfree[19]=4;slight7_pchgsub(o,t3);break;
    case 4:case 5:case 6:o->patno=o->userflag.b.h<4?0:o->userflag.b.h-4;break;
    default:
        o->patno=o->userflag.b.h<6?0:o->userflag.b.h-6;
        o->actflg|=1;o->cddat|=1;
        break;
    }
    /* Retail R71A-R72D slight7_move ($20F66A in R71A) masks levelFrames with 3,
       and with 1 without userflag bit 2; the PC SLIGHT7.C:173 masks with 6 and
       2, so its lights flicker at half the retail rate. */
    unsigned char b0=gametimer.w&3;
    if(o->userflag.b.l&4){if(o->actfree[6]==b0)tp_draw(o);}
    else if(o->actfree[6]==(b0&1))tp_draw(o);
}
static void slight7_act(sprite_status *o){
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprhsize=127;o->sprvsize=127;ss_ws(o,29,o->xposi.w.h);
        o->actfree[6]=o->userflag.b.l&3; /* retail slight7_init $20F616: & 3 (PC: & 6) */o->sprpri=1;o->sproffset=42159;
        if(o->userflag.b.l&8){
            o->sprpri=3;o->sproffset=9391;
            if(ss_time_flag()!=1)o->sproffset+=8192;
        }
    }
    slight7_move(o);
    tp_frameout_s00(o,ss_w(o,29));
}

/* ---- CHGWALL7.C -------------------------------------------------------- */
static void chgwall7_act(sprite_status *o){
    if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprhs=o->sprhsize=32;o->sprvsize=17;}
    o->patno=0;
    if(prio_flag){if(tp_hitchk(o,&actwk[0]))o->actfree[0]=1;}
    else if(o->actfree[0]){o->actfree[0]=0;tp_ride_on_clr(o,&actwk[0]);}
    tp_draw(o);
    tp_frameout_s(o);
}

/* ---- TEKKYU7.C: the ball sliding between two points ---------------------- */
static void tekkyu7_move(sprite_status *o){
    o->xposi.l+=tp_l(o,8);o->yposi.l+=tp_l(o,12);
    if(!ss_ws(o,26,ss_w(o,26)-1)){
        o->r_no0+=2;ss_ws(o,26,ss_w(o,25));
        tp_lset(o,8,-tp_l(o,8));tp_lset(o,12,-tp_l(o,12));
    }
}
static void tekkyu7_act(sprite_status *o){
    static const short tbl0[24]={1024,0,24,12,0,1024,16,8,512,0,48,24,0,512,32,16,256,0,96,48,0,256,64,32};
    static const short tbl1[3]={60,40,20};
    switch(o->r_no0/2){
    case 0:{
        unsigned tf=ss_time_flag(),k=tf*8+o->userflag.b.h*4;
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->colino=181;o->sprhs=16;o->sprhsize=16;o->sprvsize=16;o->sproffset=902;
        ss_ws(o,23,o->xposi.w.h);ss_ws(o,25,tbl1[tf]);
        tp_lset(o,8,tbl0[k]<<8);tp_lset(o,12,tbl0[k+1]<<8);ss_ws(o,24,tbl0[k+2]);ss_ws(o,26,tbl0[k+3]);
        tekkyu7_move(o);
        break;
    }
    case 1:tekkyu7_move(o);break;
    default:
        if(!ss_ws(o,26,ss_w(o,26)-1)){o->r_no0-=2;ss_ws(o,26,ss_w(o,24));}
        break;
    }
    tp_draw(o);
    tp_frameout_s00(o,ss_w(o,23));
}

/* ---- TEKKYU7J.C: the launcher (userflag.b.l 0) and its balls (-1) ------- */
static void tekkyu7j_ball(sprite_status *o){
    switch(o->r_no0/2){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->colino=181;o->sprhs=16;o->sprhsize=16;o->sprvsize=16;o->sproffset=902;
        ss_ws(o,25,32);ss_ls(o,13,32768);o->actfree[21]=0;
        if(!(o->userflag.b.h&1)){o->actfree[21]=255;ss_ls(o,13,-ss_l(o,13));}
        o->actfree[0]=0;
        short d0=o->xposi.w.h;
        if(o->userflag.b.h<2){o->actfree[0]=1;d0=o->yposi.w.h;}
        ss_ws(o,24,d0);
    }
    /* fall through: tekkyu7_init ends in tekkyu7_move */
    case 1:
        if(o->actfree[0])o->yposi.l+=ss_l(o,13);else o->xposi.l+=ss_l(o,13);
        if(!ss_ws(o,25,ss_w(o,25)-1)){o->r_no0+=2;ss_ws(o,25,30);}
        break;
    case 2:
        if(!ss_ws(o,25,ss_w(o,25)-1)){
            o->r_no0+=2;ss_ls(o,13,393216);ss_ls(o,14,-16384);
            if(!(o->userflag.b.h&1)){ss_ls(o,13,-ss_l(o,13));ss_ls(o,14,-ss_l(o,14));}
        }
        break;
    default:{
        ss_ls(o,13,ss_l(o,13)+ss_l(o,14));
        short d0;
        if(o->actfree[0]){o->yposi.l+=ss_l(o,13);d0=o->yposi.w.h;}
        else{o->xposi.l+=ss_l(o,13);d0=o->xposi.w.h;}
        unsigned char b0=d0<ss_w(o,24)?255:0;
        if(o->actfree[21]!=b0){tp_frameout(o);return;}
        break;
    }
    }
    tp_draw(o);
}
static void tekkyu7j_act(sprite_status *o){
    if(o->userflag.b.l){tekkyu7j_ball(o);return;}
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sproffset=910;o->patno=o->userflag.b.h;ss_ws(o,23,150);
        o->sprhs=16;o->sprhsize=16;o->sprvsize=16;
    }
    if(!ss_ws(o,23,ss_w(o,23)-1)){
        ss_ws(o,23,150);
        sprite_status *n;
        if(!tp_actwkchk(&n)){
            tp_setactno(n,o->actno);n->userflag.b.h=o->userflag.b.h;n->userflag.b.l=255;
            n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;
        }
    }
    tp_draw(o);
    tp_frameout_s(o);
}

/* ---- BRANKO7.C: the swinging platform and its chain links -------------- */
static const short branko7_initbl[32]={-16384,2,256,-256,-16384,2,256,-256,-16384,-2,-256,256,-24576,3,384,-384,
    -32768,-2,-256,256,-32768,2,256,-256,-32768,-1,-256,0,-32768,1,256,0};
static void branko7_ridechk(sprite_status *o){
    o->sprvsize=8;
    if(!tp_hitchk(o,&actwk[0])){
        o->sprvsize=12;
        if(!tp_hitchk(o,&actwk[0])){o->sprvsize=8;return;}
    }
    o->sprvsize=8;
    if(o->yposi.w.h>=actwk[0].yposi.w.h)
        actwk[0].yposi.w.h=o->yposi.w.h-(short)(char)o->sprvsize-(short)(char)actwk[0].sprvsize+2;
}
static void branko7_posiset(sprite_status *o){
    short spd;
    if(!o->actfree[19]){
        spd=(short)(ss_w(o,26)+ss_w(o,33));ss_ws(o,26,spd);ss_ws(o,31,ss_w(o,31)+spd);
        if(spd==ss_w(o,28))o->actfree[19]=1;
    }else{
        spd=(short)(ss_w(o,26)-ss_w(o,33));ss_ws(o,26,spd);ss_ws(o,31,ss_w(o,31)+spd);
        if(spd==ss_w(o,30))o->actfree[19]=0;
    }
    int_union s,c;s.l=c.l=0;
    sinset(o->actfree[63-46],&s.w.l,&c.w.l);
    short u=(short)(signed char)o->actfree[64-46];u=(short)(u<<4);
    s.l*=u;c.l*=u;s.l>>=4;s.w.l>>=4;c.l>>=4;c.w.l>>=4;
    o->yposi.w.h=(short)(c.w.l+ss_w(o,27));o->xposi.w.h=(short)(s.w.l+ss_w(o,29));
}
static void branko7_move(sprite_status *o){
    int lx=o->xposi.l,ly=o->yposi.l;
    branko7_posiset(o);
    if(o->actfree[5]==o->actfree[18]){
        o->xspeed.w=(short)(o->xposi.l-lx>>8);o->yspeed.w=(short)(o->yposi.l-ly>>8);
        branko7_ridechk(o);
    }
}
static void branko7_act(sprite_status *o){
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=870;o->sprhsize=32;o->sprvsize=8;
        if(!o->actfree[18]){
            ss_ws(o,29,o->xposi.w.h);ss_ws(o,27,o->yposi.w.h);
            int f=o->userflag.b.h&15;o->actfree[5]=(uint8_t)f;
            for(int c=f-1;c>=0;--c,--f){
                sprite_status *n;
                if(!tp_actwkchk(&n)){
                    tp_setactno(n,SCD_OBJ_R7_BRANKO7);ss_ws(n,29,ss_w(o,29));ss_ws(n,27,ss_w(o,27));
                    n->userflag.b.h=o->userflag.b.h;n->actfree[5]=o->actfree[5];n->actfree[18]=(uint8_t)f;n->patno=2;
                    if(o->actfree[5]==(uint8_t)f){n->patno=1;n->colino=169;}
                }
            }
        }
        const short *t=&branko7_initbl[((o->userflag.b.h&240)>>1)/2];
        ss_ws(o,31,t[0]);ss_ws(o,33,t[1]);ss_ws(o,28,t[2]);ss_ws(o,30,t[3]);
    }
    branko7_move(o);
    tp_draw(o);
    tp_frameout_s00(o,ss_w(o,29));
}
