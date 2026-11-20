/* Metallic Madness (R8) Act 2 badniks: R8/DANGO8.C (the pill bug).
   DANGO8 is DANGO7.C (objects_ss_enemies.inc); sproffset is 9263 in every
   era. The decomp's unsigned bounce speed (DANGO8.C:466) is not what retail
   runs: the roll speed after a hit sign-extends as in R7 (a_roll1 below). */
extern short atan_sonic(short,short);
/* ---- DANGO8.C ---------------------------------------------------------- */
static const unsigned char mm_dg_e00[]={9,0,1,255},mm_dg_e01[]={0,0,252},mm_dg_e02[]={3,4,4,5,252},mm_dg_e03[]={4,2,3,2,3,2,3,252},mm_dg_e04[]={4,2,3,255},mm_dg_e05[]={4,5,4,4,252};
static const unsigned char mm_dg_b00[]={29,0,1,255},mm_dg_b01[]={59,0,252},mm_dg_b02[]={9,4,4,5,252},mm_dg_b03[]={9,2,3,2,3,2,3,2,3,2,3,2,3,252},mm_dg_b04[]={9,2,3,255},mm_dg_b05[]={9,5,4,4,252};
static const unsigned char *const mm_dg_pchg_e[6]={mm_dg_e00,mm_dg_e01,mm_dg_e02,mm_dg_e03,mm_dg_e04,mm_dg_e05};
static const unsigned char *const mm_dg_pchg_b[6]={mm_dg_b00,mm_dg_b01,mm_dg_b02,mm_dg_b03,mm_dg_b04,mm_dg_b05};
static void mm_dg_patchg(sprite_status *o){tp_patchg(o,tp_l(o,4)==0?mm_dg_pchg_e:mm_dg_pchg_b);}
static void mm_dg_speedset(int nw,int old,sprite_status *o){
    if(o->userflag.b.h)nw=old;
    if(!(o->actflg&1))nw=-nw;
    tp_lset(o,0,nw);
}
static short mm_dg_move(sprite_status *o){
    short t1,t2;
    o->xposi.l+=tp_l(o,0);
    if((long)tp_l(o,0)>=0)t1=emycol_r(o,o->sprhs);
    else t1=emycol_l(o,-(char)o->sprhs);
    if(t1>=0){
        t1=emycol_d(o);t2=(short)(t1+7);
        if((unsigned short)t2<14){o->yposi.w.h+=t1;return -1;}
    }
    o->xposi.l-=tp_l(o,0);
    return 0;
}
static void dango8_act(sprite_status *o){
    if(mm_enemy_suicide(o))return;
    switch(o->r_no0/2){
    case 0:
        o->r_no0+=2;o->actflg=4;o->sprpri=3;o->sprhs=14;o->sprhsize=14;o->sprvsize=9;o->colino=44;
        o->sproffset=9263;
        tp_lset(o,4,o->userflag.b.h?1:0);
        break;
    case 1:{
        o->yposi.l+=65536;
        short d1=emycol_d(o);
        if(d1<0){o->yposi.w.h+=d1;o->r_no0+=2;}
        break;
    }
    case 2:o->r_no0+=2;mm_dg_speedset(24576,4096,o);break;
    case 3:{
        if(!mm_dg_move(o)){tp_lset(o,0,-tp_l(o,0));o->actflg^=1;o->cddat^=1;break;}
        short d0=actwk[0].xposi.w.h-o->xposi.w.h,d1=d0>=0?255:0;
        if((unsigned short)(d0+128)<256){
            d0=(short)(actwk[0].yposi.w.h-o->yposi.w.h+128);
            if((unsigned short)d0<256){
                d0=o->actflg&1?255:0;
                if(!(d0^d1))o->r_no0+=2;
            }
        }
        mm_dg_patchg(o);
        break;
    }
    case 4:o->r_no0+=2;++o->mstno.b.h;break;
    case 5:case 7:case 13:mm_dg_patchg(o);break;
    case 6:o->r_no0+=2;++o->mstno.b.h;o->yposi.w.h-=6;o->sprvsize=16;break;
    case 8:o->r_no0+=2;++o->mstno.b.h;o->yposi.w.h+=3;o->sprvsize=13;o->colino=237;tp_lset(o,0,0);break;
    case 10:o->r_no0+=2;++o->mstno.b.h;mm_dg_speedset(0x40000,65536,o);break;
    case 9:case 11:
        if(!o->colicnt){
            if(mm_dg_move(o))mm_dg_patchg(o);
            else o->r_no0+=2;
        }else{
            short w1=o->xposi.w.h-actwk[0].xposi.w.h,w2=o->yposi.w.h-actwk[0].yposi.w.h,w0=atan_sonic(w1,w2),s,c;
            sinset((unsigned char)(w0&255),&s,&c);
            int l1=c*-1792;l1>>=8;actwk[0].xspeed.w=(unsigned short)(long)l1;
            int l0=s*-1792;l0>>=8;actwk[0].yspeed.w=(unsigned short)(long)l0;
            actwk[0].cddat|=2;actwk[0].cddat&=239;actwk[0].cddat&=223;actwk[0].actfree[18]=0;
            o->colicnt=0;
            /* DANGO8.C:466 reads "lD1 &= 65535", but retail sign-extends the
               word as R7 does: retail MM2B row 3463 sets Sonic's xspeed -175
               and the pill bug then rolls +44800 (175 << 8) per update. */
            l1=-(short)l1;
            l1<<=8;tp_lset(o,0,l1);o->mstno.b.h=4;o->r_no0=22;
        }
        break;
    case 12:o->r_no0+=2;++o->mstno.b.h;o->yposi.w.h-=3;o->sprvsize=16;o->colino=44;break;
    default:o->r_no0=4;o->mstno.b.h=0;o->yposi.w.h+=6;o->sprvsize=9;break;
    }
    tp_draw(o);
    tp_frameout_s(o);
}

/* ---- LEGMECA8.C: the walking two-legged platform ----------------------- */
/* The master (subtype 0) is one leg and drives everything: its words 25..33
   hold its own number, the seven chain links and the second leg (subtype
   1, like the links, which only check their master). actfree[0] is the
   master's walk phase, actfree[1] the steps left (12), word 24 the swing
   angle (its high byte, actfree[3], feeds sinset). Each leg's r_no0 is its
   own state: 0 standing (centre: ridechk; radius: a ride starts a step),
   2 the centre leg aligns, 4 it swings the chain and the other leg around
   itself; the radius leg (2) rides until it lands. */
static void legmeca_ridechk2(sprite_status *y,sprite_status *p){
    short stack=y->xspeed.w;y->xspeed.w=0;y->sprvsize=43;
    short r=tp_ridechk(y,p);
    y->xspeed.w=stack;y->sprvsize=41;
    if(r)tp_ridechk(y,p);
}
static void legmeca_draw(sprite_status *m,sprite_status *x){if(x==m)tp_draw(x);else mm_draw_other(x);}
static void legmeca_center(sprite_status *m,sprite_status *x){
    sprite_status *p=&actwk[0];
    switch(x->r_no0){
    case 0:tp_ridechk(x,p);legmeca_draw(m,x);break;
    /* c_roll: retail R82A $20E32E has no rts and runs straight into c_roll1
       (the PC splits them; retail MM2A row 4268 swings the chain at once). */
    case 2:x->r_no0+=2;x->xposi.w.l=-32768;x->yposi.w.l=-32768;/* fall through */
    case 4:{
        mm_ws(m,24,mm_w(m,24)+512);
        int l5=x->xposi.l,l4=x->yposi.l;
        short s,c;sinset(m->actfree[3],&s,&c);
        int l1=(int)((uint32_t)(uint16_t)c<<16)>>5,l0=(int)((uint32_t)(uint16_t)s<<16)>>5;
        for(unsigned b=6;b<=18;b+=2){
            sprite_status *k=&actwk[(uint16_t)tp_w(m,b)&127];
            l5+=l1;l4+=l0;k->xposi.l=l5;k->yposi.l=l4;
        }
        sprite_status *leg=&actwk[(uint16_t)mm_w(m,33)&127];
        if(x->userflag.b.h)leg=&actwk[(uint16_t)mm_w(m,25)&127];
        int l3=leg->xposi.l;
        l5+=l1;l4+=l0;leg->xposi.l=l5;leg->yposi.l=l4;
        l5-=l3;l5>>=8;leg->xspeed.w=(short)l5;
        tp_ridechk(x,p);legmeca_draw(m,x);
        break;
    }
    }
}
static void legmeca_radius(sprite_status *m,sprite_status *y){
    sprite_status *p=&actwk[0];
    sprite_status *l0=&actwk[(uint16_t)mm_w(m,25)&127],*l1=&actwk[(uint16_t)mm_w(m,33)&127];
    if(!y->r_no0){
        if(tp_ridechk(y,p) && m->actfree[1]){--m->actfree[1];l0->r_no0+=2;l1->r_no0+=2;}
        legmeca_draw(m,y);return;
    }
    legmeca_ridechk2(y,p);legmeca_draw(m,y);
    short d0=(short)(mm_w(m,24)+16384);
    if(d0>=0){
        short d1=emycol_d(y);
        if(d1<0){
            y->yposi.w.h+=d1+2;m->actfree[0]+=2;mm_ws(m,24,mm_w(m,24)+32768);
            l0->r_no0=l1->r_no0=0;l0->xspeed.w=l1->xspeed.w=0;l0->yspeed.w=l1->yspeed.w=0;
        }
    }
}
static void legmeca_move(sprite_status *m,int phase1){
    sprite_status *leg2=&actwk[(uint16_t)mm_w(m,33)&127];
    if(!phase1){legmeca_center(m,leg2);legmeca_radius(m,m);}
    else{legmeca_center(m,m);legmeca_radius(m,leg2);}
    for(unsigned n=26;n<=32;n++)mm_draw_other(&actwk[(uint16_t)mm_w(m,n)&127]);
    tp_frameout_s(m);
}
static void legmeca_act(sprite_status *o){
    if(o->userflag.b.h){
        if(actwk[(uint16_t)mm_w(o,25)&127].actno!=SCD_OBJ_R8_LEGMECA)tp_frameout(o);
        return;
    }
    switch(o->actfree[0]){
    case 0:{
        short d4=o->xposi.w.h;sprite_status *n=o;
        for(unsigned i=0,b=4;i<=8;i++,b+=2){
            if(i){
                if(tp_actwkchk(&n)){tp_frameout(o);return;}
                n->userflag.b.h=1;tp_setactno(n,o->actno);n->sprpri=3;n->patno=1;n->sprhs=n->sprhsize=n->sprvsize=4;
                n->yposi.w.h=o->yposi.w.h;d4+=8;n->xposi.w.h=d4;
            }
            tp_wset(o,b,(uint16_t)mm_index(n));mm_ws(n,25,(uint16_t)mm_index(o));n->actflg|=4;n->sproffset=792;
        }
        n->patno=0;n->sprpri=4;n->sprhs=n->sprhsize=24;n->sprvsize=41;
        o->patno=0;o->sprpri=4;o->sprhs=o->sprhsize=24;o->sprvsize=41;
        o->actfree[0]+=2;o->actfree[1]=12;mm_ws(o,24,-32768);
        legmeca_move(o,0);
        break;
    }
    case 2:legmeca_move(o,0);break;
    case 4:o->actfree[0]=6;legmeca_move(o,1);break;
    case 6:legmeca_move(o,1);break;
    case 8:o->actfree[0]=2;legmeca_move(o,0);break;
    }
}
