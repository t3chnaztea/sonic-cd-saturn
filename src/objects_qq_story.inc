/* Quartz Quadrant round-specific story actors: R5/SHOOT5.C, MOVIE5.C,
   FRIEND5.C, ET5.C and KOWASI5.C. Each is its own R5 definition (vetted in
   tools/test-qq-actors.sh against the compiled R5 source), not the PPZ/R3/R4
   routine of the same name:
   - SHOOT5 routes through R5's own shooterpositbl and only runs when the
     belt direction (colrevflag) matches subtype bit 0 for subtypes >= 128.
   - MOVIE5 counts explosions with a byte counter and its screens/animals
     sit at R5 offsets; FRIEND5's Flicky orbits and its Ricky hops.
   - ET5 is ET4.C except the pattern offset (1234 for 1104): it reuses
     et4_step (objects_tt_friends.inc) and swaps the offset after init.
   - KOWASI5 breaks into three pieces thrown by the player's direction. */

/* ---- SHOOT5.C: pipe route (shooter) -------------------------------------- */
static const short shoot5_0[]={40,9808,208,9808,240,9888,272,9760,304,9888,336,9760,368,9888,400,9760,432,9904,488,9904,520};
static const short shoot5_1[]={36,10320,496,10320,528,10416,560,10288,592,10416,624,10288,656,10416,688,10288,720,10416,752};
static const short shoot5_2[]={28,2944,672,2944,728,2976,752,2848,784,2976,816,2848,848,2976,880};
static const short shoot5_3[]={60,9840,264,9840,288,9920,320,9792,352,9920,384,9792,416,9920,448,9792,480,9920,512,9792,544,9920,576,9792,608,9920,640,9792,672,9920,752};
static const short shoot5_4[]={48,10288,296,10432,368,10304,400,10432,432,10304,464,10432,496,10304,528,10432,560,10304,592,10432,624,10304,656,10432,752};
static const short shoot5_5[]={36,6480,488,6480,528,6576,560,6448,592,6576,624,6448,656,6576,688,6448,720,6576,752};
static const short shoot5_6[]={36,6512,488,6512,528,6592,560,6464,592,6592,624,6464,656,6592,688,6464,720,6592,752};
static const short shoot5_7[]={8,1424,200,1424,376};
static const short shoot5_8[]={8,1424,200,1424,376};
static const short shoot5_9[]={8,1424,376,1424,200};
static const short shoot5_0a[]={8,5744,296,5744,400};
static const short shoot5_0b[]={8,5744,400,5744,296};
static const short shoot5_0c[]={8,7088,520,7088,600};
static const short shoot5_0d[]={8,7088,600,7088,520};
static const short shoot5_0e[]={8,7120,520,7120,600};
static const short shoot5_0f[]={8,7120,600,7120,520};
static const short shoot5_10[]={84,6912,112,6768,112,6752,128,6736,160,6752,192,6768,208,6800,208,6816,224,6832,256,6832,296,
    6856,344,6832,392,6856,440,6832,488,6856,536,6832,584,6856,632,6832,680,6856,728,6832,776,6832,856};
static const short shoot5_11[]={84,6832,856,6832,776,6856,728,6832,680,6856,632,6832,584,6856,536,6832,488,6856,440,6832,392,
    6856,344,6832,296,6832,256,6816,224,6800,208,6768,208,6752,192,6736,160,6752,128,6768,112,6912,112};
static const short shoot5_12[]={28,5008,672,5008,736,5024,752,4896,784,5024,816,4896,848,5024,880};
static const short shoot5_13[]={80,6832,856,6832,760,6856,712,6832,664,6856,616,6832,568,6832,504,6856,456,6832,408,6856,360,
    6832,312,6832,256,6816,224,6800,208,6768,208,6752,192,6736,160,6752,128,6768,112,6912,112};
static const short shoot5_14[]={80,6912,112,6768,112,6752,128,6736,160,6752,192,6768,208,6800,208,6816,224,6832,256,6832,312,
    6856,360,6832,408,6856,456,6832,504,6832,568,6856,616,6832,664,6856,712,6832,760,6832,856};
static const short shoot5_15[]={36,6480,488,6480,528,6576,544,6448,576,6576,608,6448,640,6576,672,6448,704,6576,736};
static const short *const shoot5_tbl[22]={shoot5_0,shoot5_1,shoot5_2,shoot5_3,shoot5_4,shoot5_5,shoot5_6,shoot5_7,shoot5_8,shoot5_9,
    shoot5_0a,shoot5_0b,shoot5_0c,shoot5_0d,shoot5_0e,shoot5_0f,shoot5_10,shoot5_11,shoot5_12,shoot5_13,shoot5_14,shoot5_15};
/* The route after its length word; the original keeps this pointer in
   ((short**)o)[16], i.e. it only depends on the subtype. */
static const short *shoot5_route(const sprite_status *o){unsigned n=o->userflag.b.h&127;return (n<22?shoot5_tbl[n]:shoot5_0)+1;}
static short shoot5_div(int n,short d){return d?(short)(n/d):0;}
static void shoot5_spdset(sprite_status *o){
    sprite_status *p=&actwk[0];
    short d2,d3;d2=d3=p->mspeed.w?p->mspeed.w:2560;
    short tx=qq_w(o,29),ty=qq_w(o,30),ax,ay;
    if(tx<p->xposi.w.h){ax=-(short)(tx-p->xposi.w.h);d2=-d2;}else ax=tx-p->xposi.w.h;
    if(ty<p->yposi.w.h){ay=-(short)(ty-p->yposi.w.h);d3=-d3;}else ay=ty-p->yposi.w.h;
    if((unsigned short)ay>=(unsigned short)ax){
        short dy=ty-p->yposi.w.h,q=shoot5_div((int)((uint32_t)(uint16_t)dy<<16),d3);
        short dx=tx-p->xposi.w.h,r=dx;
        if(dx)r=shoot5_div((int)((uint32_t)(uint16_t)dx<<16),q);
        p->xspeed.w=r;p->yspeed.w=d3;
        if(q<0)q=-q;
        qq_ws(o,25,q);
    }else{
        short dx=tx-p->xposi.w.h,q=shoot5_div((int)((uint32_t)(uint16_t)dx<<16),d2);
        short dy=ty-p->yposi.w.h,r=dy;
        if(dy)r=shoot5_div((int)((uint32_t)(uint16_t)dy<<16),q);
        p->yspeed.w=r;p->xspeed.w=d2;
        if(q<0)q=-q;
        qq_ws(o,25,q);
    }
}
static void shoot5_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    /* time_flag bit 7 (time travel in progress) never reaches native
       actors, so the flagwork clearing ahead of it has nothing to do. */
    int run=!(o->userflag.b.h&128) || (colrevflag?(o->userflag.b.h&1):!(o->userflag.b.h&1));
    if(run){
        if(p->mstno.b.h==43 || p->r_no0>=6)return;
        switch(o->r_no0){
        case 0:{
            const short *a=shoot5_route(o);
            o->actflg=4;o->sprpri=1;o->sprhsize=16;o->r_no0+=2;
            qq_ws(o,31,a[-1]);qq_ws(o,29,a[0]);qq_ws(o,30,a[1]);
        }   /* fall through: shooterinit calls shootermove */
        case 2:
            if((unsigned short)(p->xposi.w.h-o->xposi.w.h+16)>=32 || (unsigned short)(p->yposi.w.h-o->yposi.w.h+16)>=32 || p->actfree[2])break;
            if(p->r_no0==4){p->r_no0-=2;qq_ws(p,26,120);}
            o->r_no0+=2;p->actfree[2]=129;p->mstno.b.h=2;p->mspeed.w=2560;p->xspeed.w=0;p->yspeed.w=0;
            o->cddat&=223;p->cddat&=223;p->cddat|=2;p->xposi.w.h=o->xposi.w.h;p->yposi.w.h=o->yposi.w.h;
            o->actfree[8]=0;soundset(145);
            break;
        case 4:shoot5_spdset(o);o->r_no0+=2;soundset(145);break;
        case 6:
            if((int8_t)--o->actfree[5]<0){
                p->xposi.w.h=qq_w(o,29);p->yposi.w.h=qq_w(o,30);
                unsigned char d1=o->actfree[17]+4;
                if(d1>=o->actfree[16]){p->yposi.w.h&=2047;o->r_no0=0;p->actfree[2]=0;o->r_no1=2;break;}
                o->actfree[17]=d1;
                const short *a=shoot5_route(o)+d1/2;
                qq_ws(o,29,a[0]);qq_ws(o,30,a[1]);shoot5_spdset(o);
                break;
            }
            p->xposi.l+=(int)p->xspeed.w*256;p->yposi.l+=(int)p->yspeed.w*256;
            break;
        }
        if(o->r_no0>=4)return;
    }
    tp_frameout_s(o);
}

/* ---- MOVIE5.C: the Metal Sonic projector --------------------------------- */
static void movie5_act(sprite_status *o){
    static const int8_t tbl0[37]={1,0,0,5,-18,-10,10,-10,10,15,0,-18,20,-10,18,22,8,23,25,13,-10,28,-3,-25,
        30,10,20,32,-10,2,35,13,-10,40,-10,10,-1};
    static const uint8_t pchg00[]={0,2,1,3,1,255},pchg01[]={0,4,4,1,4,4,1,4,4,1,4,4,1,4,4,1,1,4,4,1,1,4,4,1,1,4,4,1,1,5,
        5,1,5,5,1,5,5,1,5,5,1,5,5,1,1,5,5,1,1,5,5,1,1,5,5,1,1,255};
    static const uint8_t *const pchg[]={pchg00,pchg01};
    sprite_status *p=&actwk[0];unsigned i=tp_slot(o);
    if(o->userflag.b.h){
        sprite_status *m=qq_link(o,33);
        if(m->actno!=SCD_OBJ_R5_MOVIE5 || m->actfree[21]){tp_frameout(o);return;}
        if(!o->r_no0){
            o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sproffset=950;
            if(o->userflag.b.h&128){o->sprhs=o->sprhsize=8;o->sprvsize=4;o->mstno.b.h=0;}
            else{o->sprhs=o->sprhsize=20;o->sprvsize=24;o->mstno.b.h=1;}
        }
        tp_patchg(o,pchg);tp_draw(o);return;
    }
    switch(o->r_no0){
    case 0:{
        if(projector_destroyed){tp_frameout(o);return;}
        o->r_no0+=2;o->actflg|=4;o->sprhs=o->sprhsize=o->sprvsize=12;o->colino=251;o->sproffset=950;pool[i].phase=0;
        static const struct{int8_t dx,dy,sub;uint8_t friend;}kids[4]={{-21,-7,-1,0},{-88,-4,1,0},{-88,-24,-128,1},{-100,4,-127,1}};
        for(unsigned k=0;k<4;k++){
            sprite_status *c;
            if(tp_actwkchk(&c)){tp_frameout(o);return;}
            c->xposi.w.h=o->xposi.w.h+kids[k].dx;c->yposi.w.h=o->yposi.w.h+kids[k].dy;c->userflag.b.h=kids[k].sub;
            qq_ws(c,33,qq_index(o));tp_setactno(c,kids[k].friend?SCD_OBJ_R5_FRIEND5:SCD_OBJ_R5_MOVIE5);
        }
    }   /* fall through: m_init calls m_wait */
    case 2:
        if(o->colicnt){o->colino=0;o->colicnt=0;o->r_no0+=2;}
        tp_hitchk(o,p);break;
    case 4:
        o->r_no0+=2;o->patno=1;o->actfree[21]=1;
        if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        /* fall through: m_die calls m_baku */
    case 6:{
        unsigned c=pool[i].phase;int t=tbl0[c];
        if(t>=0){
            if(++o->actfree[0]==(uint8_t)t){pool[i].phase=c+3;tt_blast(o->xposi.w.h+tbl0[c+1],o->yposi.w.h+tbl0[c+2]);}
        }else{o->r_no0+=2;qq_ws(o,23,60);}
        break;
    }
    case 8:
        if(!qq_ws(o,23,qq_w(o,23)-1)){projector_destroyed=1;projector_flag=1;tp_frameout(o);return;}
        break;
    }
    tp_draw(o);
    if(o->r_no0<3)tp_frameout_s(o);
}

/* ---- FRIEND5.C: Flicky (orbiting) and Ricky (hopping) -------------------- */
static void friend5_sproffset(sprite_status *o){
    static const short tbl[11]={1210,1210,1210,0,1210,1210,1210,0,0,0,1210};
    unsigned n=qq_time_flag()+stageno.b.l*4;
    o->sproffset=n<11?tbl[n]:0;
}
static void friend5_roll(sprite_status *o,int xs,int ys){
    short sn,cs;sinset(o->actfree[4],&sn,&cs);
    cs>>=xs;sn>>=ys;
    o->xposi.w.h=cs+qq_w(o,23);o->yposi.w.h=sn+qq_w(o,24);
}
static int friend5_movie_gone(sprite_status *o){
    sprite_status *m=qq_link(o,33);
    if(m->actno!=SCD_OBJ_R5_MOVIE5 || m->actfree[21]){tp_frameout(o);return 1;}
    return 0;
}
static void friend5_act(sprite_status *o){
    static const uint8_t p0_00[]={19,0,1,255},p0_01[]={0,0,0,2,0,0,2,1,1,2,2,1,1,2,2,0,0,2,0,0,2,1,1,2,2,1,1,2,2,255};
    static const uint8_t p1_00[]={0,3,3,2,3,3,2,3,3,2,3,3,2,3,3,2,2,3,3,2,2,3,3,2,2,3,3,2,2,4,
        4,2,4,4,2,4,4,2,4,4,2,4,4,2,2,4,4,2,2,4,4,2,2,4,4,2,2,255};
    static const uint8_t *const pchg0[]={p0_00,p0_01},*const pchg1[]={p1_00};
    if(qq_friend_suicide(o))return;
    if(o->userflag.b.h&127){
        /* Ricky */
        switch(o->r_no0){
        case 0:
            o->r_no0+=2;o->actflg=4;o->sprvsize=8;o->sprhs=o->sprhsize=8;o->sprpri=4;qq_ws(o,23,o->xposi.w.h);friend5_sproffset(o);
            if(o->userflag.b.h&128){o->r_no0+=2;o->actflg^=1;o->cddat^=1;}
            else{qq_ls(o,12,65536);qq_ls(o,13,-0x40000);}
            return;
        case 2:{
            o->xposi.l+=qq_l(o,12);o->yposi.l+=qq_l(o,13);
            o->patno=qq_ls(o,13,qq_l(o,13)+8192)<0?0:1;
            short c=emycol_d(o);
            if(c<0){o->yposi.w.h+=c;qq_ls(o,13,-0x40000);qq_ls(o,12,-qq_l(o,12));o->actflg^=1;o->cddat^=1;}
            tp_draw(o);tp_frameout_s(o);return;
        }
        case 4:
            if(friend5_movie_gone(o))return;
            tp_patchg(o,pchg1);tp_draw(o);return;
        }
        return;
    }
    /* Flicky */
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg=4;o->sprvsize=8;o->sprhs=o->sprhsize=8;o->sprpri=4;
        qq_ws(o,23,o->xposi.w.h);qq_ws(o,24,o->yposi.w.h);o->actflg^=1;o->cddat^=1;friend5_sproffset(o);
        if(o->userflag.b.h&128){o->r_no0+=2;o->mstno.b.h=1;o->sprpri=3;}
        else{o->sproffset|=32768;o->actfree[4]=1;o->actfree[5]=1;}
        return;
    case 2:{
        friend5_roll(o,1,1);
        int8_t a=(int8_t)(o->actfree[4]+o->actfree[5]);
        if((unsigned char)(a-1)>=127){a=(int8_t)o->actfree[4];o->actfree[5]=-o->actfree[5];o->actflg^=1;o->cddat^=1;}
        o->actfree[4]=a;
        tp_patchg(o,pchg0);tp_draw(o);tp_frameout_s00(o,qq_w(o,23));return;
    }
    case 4:
        if(friend5_movie_gone(o))return;
        friend5_roll(o,3,4);o->actfree[4]+=4;
        if(!(o->actfree[4]&127)){o->actflg^=1;o->cddat^=1;}
        else{tp_patchg(o,pchg0);tp_draw(o);}
        return;
    }
}

/* ---- ET5.C: robot generator (ET4.C with R5's pattern offset) ------------- */
static void et5_act(sprite_status *o){
    int init=!o->r_no0;unsigned i=tp_slot(o);
    et4_step(i);
    if(!o->actno)return;
    if(init && o->sproffset==1104)o->sproffset=1234;
    pool[i].sink=1; /* et4_step drew it (cc_object_draw) */
}

/* ---- KOWASI5.C: breakable block ------------------------------------------ */
static void kowasi5_down(sprite_status *o){
    tp_lset(o,4,tp_l(o,4)+16384);o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);
    if(actwk[0].yposi.w.h-o->yposi.w.h<=-224)tp_frameout(o);else tp_draw(o);
}
static void kowasi5_act(sprite_status *o){
    static const short dposiy[3]={-16,0,16};
    static const unsigned char tbl0pat[6]={2,3,4,5,5,5};
    static const int tbl0speed[6]={-194180,-84144,-252434,0,-194180,84144};
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=8;o->sprvsize=8;o->colino=243;o->sproffset=17575;
        o->patno=o->userflag.b.h&1;
        if(o->userflag.b.h==2){o->actflg|=1;o->cddat|=1;}
        /* fall through: m_init calls m_wait */
    case 2:{
        if(!o->colicnt){tp_hitchk(o,p);tp_draw(o);tp_frameout_s(o);return;}
        o->colino=o->colicnt=0;o->r_no0+=2;qq_ws(o,23,p->xspeed.w);qq_ws(o,25,p->yspeed.w);
        if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        soundset(176);
        const unsigned char *pat=tbl0pat+(o->userflag.b.h&1?3:0);
        p->xspeed.w>>=1;
        sprite_status *c=o;
        for(unsigned n=0;n<3;n++){
            if(n){
                if(tp_actwkchk(&c))break;
                tp_setactno(c,o->actno);c->r_no0=o->r_no0;c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;
                c->actflg=o->actflg;c->sprpri=o->sprpri;c->sproffset=o->sproffset;
            }
            c->patno=pat[n];c->sprhs=c->sprhsize=c->sprvsize=8;c->yposi.w.h+=dposiy[n];
            int s=tbl0speed[n*2];tp_lset(c,4,tbl0speed[n*2+1]);
            if(p->xspeed.w<0)s=-s;
            tp_lset(c,0,s);
        }
        kowasi5_down(o);return;
    }
    case 4:kowasi5_down(o);return;
    }
}
