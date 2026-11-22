/* Quartz Quadrant platforms: R5/BURANKO5.C, HASIRA5.C, HASHI5.C and
   BELTSW5.C. Line-for-line ports on the PC scratch layout
   (objects_qq_common.inc); ridechk/hitchk/ride_on_set/ride_on_clr are the
   tp_* RIDECHK port. Children reuse the parent type. */

/* ---- BURANKO5.C: swinging platform on a chain ---------------------------- */
static void buranko5_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.l){
        sprite_status *m=&actwk[o->actfree[0]&127];
        if(!(o->userflag.b.l&128)){
            /* middle: a chain link. */
            if(o->r_no0){if(m->actno==SCD_OBJ_R5_BURANKO5)tp_draw(o);else tp_frameout(o);return;}
            o->r_no0+=2;o->patno=1;o->sprhs=o->sprhsize=o->sprvsize=8;o->sprpri=3;o->sproffset=856;return;
        }
        /* radius: the platform at the chain's end. */
        if(!o->r_no0){o->r_no0+=2;o->patno=2;o->sprhs=o->sprhsize=32;o->sprvsize=8;o->sprpri=2;o->sproffset=17180;}
        short sp=o->xspeed.w;o->xspeed.w=0;o->sprvsize=10;
        int ride=tp_ridechk(o,p)!=0;
        o->xspeed.w=sp;o->sprvsize=8;
        if(ride && tp_ridechk(o,p))p->xposi.w.h+=colrevflag?-2:2;
        if(m->actno==SCD_OBJ_R5_BURANKO5)tp_draw(o);else tp_frameout(o);
        return;
    }
    if(!o->r_no0){
        static const short tbl0[6]={5,0,5,-32768,7,16384};
        sprite_status *c=0;
        o->r_no0+=2;o->actflg|=4;o->sprhs=o->sprhsize=o->sprvsize=8;o->sprpri=3;o->sproffset=856;
        qq_ws(o,29,tbl0[o->userflag.b.h&254]);qq_ws(o,25,tbl0[(o->userflag.b.h&254)+1]);qq_ws(o,27,256);
        if(o->userflag.b.h&1){tp_lset(o,4,-tp_l(o,4));tp_lset(o,8,-tp_l(o,8));}
        for(short n=qq_w(o,29),i=0;n>=0;--n,++i){
            if(tp_actwkchk2(o,&c)){tp_frameout(o);return;}
            o->actfree[i+14]=(unsigned char)qq_index(c);c->userflag.b.l=1;qq_ws(c,23,qq_index(o));
            tp_setactno(c,o->actno);c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;c->actflg=o->actflg;
        }
        if(c)c->userflag.b.l=-1;
        return;
    }
    int l6=tp_l(o,0)+tp_l(o,8),l5=tp_l(o,4);
    if(l5){
        int l1=l6,l0=l5;
        if(l5<0){l1=-l1;l0=-l0;}
        if(l1<0){l6=0;tp_lset(o,8,-tp_l(o,8));}
        else if(l1>l0){l6=l5;tp_lset(o,8,-tp_l(o,8));}
    }
    tp_lset(o,0,l6);
    short n=qq_w(o,29)-1;int l4=o->yposi.l,l3;l5=o->xposi.l;
    short sn,cs;sinset(o->actfree[1],&sn,&cs);
    int l1=(int)((uint32_t)(uint16_t)cs<<16)/16,l0=(int)((uint32_t)(uint16_t)sn<<16)/16;
    unsigned i=0;
    for(;n>=0;--n){
        sprite_status *m=&actwk[o->actfree[i++ +14]&127];
        m->xposi.l=l5+=l1;m->yposi.l=l4+=l0;
    }
    sprite_status *m=&actwk[o->actfree[i+14]&127];
    l3=l5+l1;m->xposi.l=l5+l1;m->yposi.l=l4+l0;
    m->xspeed.w=(short)(l5-l3)>>8;
    tp_draw(o);tp_frameout_s(o);
}

/* ---- HASIRA5.C: pillar that shatters when rolled into -------------------- */
static void hasira5_act(sprite_status *o){
    static const uint8_t tbl0patno[8]={2,5,3,5,4,5,7,5};
    static const short tbl0dposi[16]={-8,-24,16,0, 0,16,16,16, 0,32,16,32, 0,48,16,48};
    static const int tbl0speed[16]={-77101,-131072,77101,-131072,-163840,-98304,163840,-98304,
                                    -327680,32768,327680,32768,-163840,65536,163840,65536};
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=16;o->sprvsize=48;o->colino=238;o->sproffset=17515;
        /* fall through: m_init calls m_wait */
    case 2:{
        if(!o->colicnt){tp_hitchk(o,p);break;}
        o->colicnt=0;p->xspeed.w>>=1;p->mspeed.w>>=1;
        if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        soundset(176);o->r_no0+=2;o->colino=0;
        sprite_status *a=o;
        for(unsigned n=0;n<8;n++){
            if(n){
                if(tp_actwkchk(&a))break;
                tp_setactno(a,o->actno);a->r_no0=o->r_no0;a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h;
                a->actflg=o->actflg;a->sprpri=o->sprpri;a->sproffset=o->sproffset;
            }
            a->sprhs=a->sprhsize=16;a->sprvsize=12;
            a->xposi.w.h+=tbl0dposi[n*2];a->yposi.w.h+=tbl0dposi[n*2+1];
            tp_lset(a,0,tbl0speed[n*2]);tp_lset(a,4,tbl0speed[n*2+1]);a->patno=tbl0patno[n];
        }
    }   /* fall through: m_wait calls m_down */
    case 4:
        tp_lset(o,4,tp_l(o,4)+16384);o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);
        if((short)(p->yposi.w.h-o->yposi.w.h)<=-224){tp_frameout(o);return;}
        break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- HASHI5.C: bridge of eight planks sagging under the player ----------- */
static void hashi5_posiset(sprite_status *o){
    static const uint8_t hashitbl_8[8]={2,4,6,8,8,6,4,2}; /* hashitbl[128..135] */
    static const uint8_t hashitbl2[128]={
        255,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  181,255,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        126,219,255,0,0,0,0,0,0,0,0,0,0,0,0,0,  97,181,236,255,0,0,0,0,0,0,0,0,0,0,0,0,
        74,147,205,243,255,0,0,0,0,0,0,0,0,0,0,0,  62,126,176,219,246,255,0,0,0,0,0,0,0,0,0,0,
        56,109,157,197,228,248,255,0,0,0,0,0,0,0,0,0,  49,97,142,181,212,236,251,255,0,0,0,0,0,0,0,0};
    short n=o->actfree[19];
    short sn,cs;sinset(o->actfree[16],&sn,&cs);
    int s=(uint16_t)sn,b5=hashitbl_8[n&7];
    const uint8_t *a3=&hashitbl2[(n&15)*16],*a2=o->actfree;
    for(;n>=0;--n){
        sprite_status *c=&actwk[*a2++&127];
        int v=(*a3+++1)*b5*s;
        c->yposi.w.h=qq_w(c,27)+(short)(v>>16);
    }
    n=(unsigned char)(7-o->actfree[19]);
    if((int8_t)n<0)return;
    a3=&hashitbl2[n*16+n];
    if(--n<0)return;
    for(;n>=0;--n){
        sprite_status *c=&actwk[*a2++&127];
        int v=((unsigned short)*--a3+2)*b5*s;
        c->yposi.w.h=qq_w(c,27)+(short)(v>>16);
    }
}
static int hashi5_ridechk1p(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(p->r_no0!=6 && !editmode.b.h && p->yspeed.w>=0){
        short d0=72+(p->xposi.w.h-o->xposi.w.h);
        if(d0>=0 && d0<128){
            d0=o->yposi.w.h-8;short y=p->yposi.w.h,d1=y+(short)p->sprvsize+4;
            if((unsigned short)d0<=(unsigned short)d1){
                d0-=d1;
                if((unsigned short)d0>=65520 && p->r_no0<6){p->yposi.w.h=y+d0+3;tp_ride_on_set(o,p);return 1;}
            }
        }
    }
    if(p->actfree[19]==(unsigned char)qq_index(o)){p->actfree[14]=0;p->cddat&=247;}
    return 0;
}
static void hashi5_act(sprite_status *o){
    static const short xofsettbl[8]={48,32,16,0,-16,-32,-48,-64};
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17152;qq_ws(o,29,o->xposi.w.h);qq_ws(o,27,o->yposi.w.h);
        o->sprhsize=64;o->sprvsize=8;o->patno=1;
        for(unsigned i=0;i<8;i++){
            sprite_status *c;
            if(tp_actwkchk(&c))continue;
            o->actfree[i]=(unsigned char)qq_index(c);tp_setactno(c,SCD_OBJ_R5_HASHI5);c->r_no0=4;
            qq_ws(c,29,o->xposi.w.h);qq_ws(c,27,o->yposi.w.h);c->yposi.w.h=o->yposi.w.h;c->actflg|=4;c->sprpri=3;
            c->sproffset=17152;c->sprvsize=8;c->sprhsize=8;qq_ws(c,28,qq_index(o));c->actfree[21]=255;
            c->actfree[18]=7-i;c->xposi.w.h=xofsettbl[7-i]+o->xposi.w.h;
        }
        break;
    case 2:
        o->actfree[19]=0;
        if(hashi5_ridechk1p(o)){
            unsigned short d0=p->xposi.w.h-o->xposi.w.h+72;
            o->actfree[19]=!(p->cddat&2) && !(d0&32768) && d0<128?d0>>4:0;
        }
        if(o->actfree[19]){
            if(o->actfree[16]!=64)o->actfree[16]+=4;
            hashi5_posiset(o);
            if(o->actfree[19])p->yposi.w.h=actwk[o->actfree[o->actfree[19]]&127].yposi.w.h-8-(short)(unsigned short)p->sprvsize;
        }else if(o->actfree[16]){o->actfree[16]-=4;hashi5_posiset(o);}
        tp_frameout_s(o);
        if(!o->actno)return;
        break;
    case 4:{
        sprite_status *m=qq_link(o,28);
        if(m->actno!=SCD_OBJ_R5_HASHI5 || m->actfree[21]){tp_frameout(o);return;}
        break;
    }
    }
    tp_draw(o);
}

/* ---- BELTSW5.C: switch reversing the conveyor belts (colrevflag) --------- */
static void beltsw5_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhsize=o->sprvsize=24;o->sproffset=18327;
        if(colrevflag&1)o->patno=2;
        o->actfree[18]=colrevflag;
        /* fall through: beltsw5_init calls beltsw5_move1 */
    case 2:{
        if(!editmode.b.h){
            short d0=p->yposi.w.h-o->yposi.w.h;if((unsigned short)p->yposi.w.h<(unsigned short)o->yposi.w.h)d0=-d0;
            if((unsigned short)d0<16){
                d0=p->xposi.w.h-o->xposi.w.h;if((unsigned short)p->xposi.w.h<(unsigned short)o->xposi.w.h)d0=-d0;
                if((unsigned short)d0<8){colrevflag^=1;scd_r5_set_colrev(colrevflag&1);o->r_no0+=2;if(o->actflg&128)soundset(191);break;}
            }
        }
        if(colrevflag!=o->actfree[18]){o->actfree[19]=255;o->r_no0+=2;}
        o->actfree[18]=colrevflag;
        break;
    }
    case 4:
        if(++o->actfree[16]==7)o->patno=1;
        else if(o->actfree[16]==14){
            o->actfree[16]=0;o->patno=colrevflag&1?2:0;o->r_no0+=2;o->actfree[19]=0;
        }
        break;
    case 6:{
        short d0=p->yposi.w.h-o->yposi.w.h;if((unsigned short)p->yposi.w.h<(unsigned short)o->yposi.w.h)d0=-d0;
        if((unsigned short)d0<32){
            d0=p->xposi.w.h-o->xposi.w.h;if((unsigned short)p->xposi.w.h<(unsigned short)o->xposi.w.h)d0=-d0;
            if((unsigned short)d0<16)break;
        }
        o->r_no0=2;o->actfree[18]=colrevflag;
        break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}
