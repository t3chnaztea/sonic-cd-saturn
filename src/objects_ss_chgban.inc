/* Stardust Speedway R7/CHGBAN.C: chgban (the layer switch board), spring_r
   (the rotating spring and its two side guards) and gun7 (the launcher and
   its spark, hibana). Line-for-line ports on the PC scratch layout
   (objects_ss_common.inc). spring_r keeps the actor numbers of its parts in
   PC longs (*(int*)&actfree[0], [4], [12], [16]); children reuse the parent
   type as the original reuses its actor number (30, 8, 9 -> spring_r, gun7,
   hibana). prio_flag is the PC's player layer (EQU.C). */

/* ---- chgban ------------------------------------------------------------ */
static const unsigned char chgban_chg0[]={4,0,1,2,3,4,3,2,1,0,252};
static const unsigned char *const chgban_chg[]={chgban_chg0};
static void chgban_move0(sprite_status *o){
    if(o->actfree[0]){--o->actfree[0];return;}
    short xsz=(short)(char)o->sprhs+(short)(char)actwk[0].sprhs,xdst=o->xposi.w.h-actwk[0].xposi.w.h;
    short ysz=(short)(char)o->sprvsize+(short)(char)actwk[0].sprvsize,ydst=o->yposi.w.h-actwk[0].yposi.w.h;
    if((xdst+=xsz)<0 || xdst>=xsz*2 || (ydst+=ysz)<0 || ydst>=ysz*2){
        if(((o->sproffset&32768) && prio_flag) || (!(o->sproffset&32768) && !prio_flag)){o->actfree[0]=60;o->r_no0+=2;}
    }else{o->actfree[0]=60;o->r_no0+=2;prio_flag^=1;}
}
static void chgban_act(sprite_status *o){
    switch(o->r_no0/2){
    case 0:
        if(o->userflag.b.h)o->actflg|=2;
        o->r_no0+=2;o->actflg|=4;o->sproffset=845;
        if(!prio_flag)o->sproffset|=32768;
        o->sprhs=o->sprhsize=o->sprvsize=24;
        chgban_move0(o);
        break;
    case 1:chgban_move0(o);break;
    case 2:tp_patchg(o,chgban_chg);break;
    default:
        if(!prio_flag){o->sproffset|=32768;o->sprpri=4;}
        else{o->sproffset&=32767;o->sprpri=0;}
        o->patcnt=0;o->r_no0-=4;
        break;
    }
    tp_draw(o);
    tp_frameout_s(o);
}

/* ---- spring_r ---------------------------------------------------------- */
static const char sr_revtbl0[9]={0,0,0,0,1,1,1,0,0},sr_revtbl1[9]={2,0,0,0,1,1,3,2,2},sr_revtbl2[9]={1,1,3,2,2,0,0,0,1};
static const short sr_positbl0[18]={8,-8,8,0,8,-8,0,-8,-8,-8,-8,0,-8,-8,0,-8,8,-8};
static const short sr_positbl1[18]={8,8,8,0,8,-8,0,-8,-8,-8,-8,0,-8,8,0,8,8,8};
static const short sr_positbl2[18]={-8,-8,-8,0,-8,8,0,8,8,8,8,0,8,-8,0,-8,-8,-8};
static const char sr_ppositbl0[9]={1,0,1,2,3,4,3,2,1};
static const unsigned char sr_ppositblg_0[9]={1,0,1,2,3,4,5,6,7},sr_ppositblg_1[9]={3,4,5,6,7,0,1,2,3};
static const short sr_ppositbl[16]={24,0,24,-24,0,-24,-24,-24,-24,0,-24,24,0,24,24,24};
static const unsigned char sr_gpattbl[9]={4,2,4,3,4,2,4,3,4};
static const unsigned char sr_grevtbl0_0[9]={0,0,0,0,2,2,2,0,0},sr_grevtbl0_1[9]={3,2,3,1,1,0,1,1,3};
static const unsigned char sr_grevtbl1_0[9]={1,0,0,0,2,2,3,1,1},sr_grevtbl1_1[9]={2,2,3,1,1,0,0,0,2};
static const unsigned char sr_gpositbl0_0[9]={1,0,1,2,3,4,3,2,1},sr_gpositbl0_1[9]={9,8,9,10,11,12,11,10,9};
static const unsigned char sr_gpositbl1_0[9]={7,0,1,2,3,4,5,6,7},sr_gpositbl1_1[9]={3,4,5,6,7,0,1,2,3};
static const unsigned char sr_gpositbl2_0[9]={11,12,13,14,15,8,9,10,11},sr_gpositbl2_1[9]={15,8,9,10,11,12,13,14,15};
static const short sr_gpositbl[32]={24,-16,4,-28,-16,-24,-28,-4,-24,16,-4,28,16,24,28,4,24,16,28,-4,16,-24,-4,-28,-24,-16,-28,4,-16,24,4,28};
static const short sr_gspdtbl0[18]={-1,-1,-1,0,-1,1,0,1,1,1,1,0,1,-1,0,-1,-1,-1};
static const short sr_gspdtbl1[18]={1,1,1,0,1,-1,0,-1,-1,-1,-1,0,-1,1,0,1,1,1};
static const unsigned char sr_rchg0[]={5,1,1,1,1,1,1,1,1,255};
static const unsigned char *const sr_rchg[]={sr_rchg0};
/* SPRING.C springchg. */
static const unsigned char sr_springchg0[]={0,0,1,1,2,2,2,2,2,2,1,252};
static const unsigned char *const sr_springchg[]={sr_springchg0};
static unsigned char sr_prio_sav;
/* The spring's pattern table: 0 spring90pat2, 1 springpat2, 2 spring45pat2
   (patbase in the original; the view picks the art from the sprite offset). */
static sprite_status *sr_link(const sprite_status *o,unsigned b){return &actwk[tp_l(o,b)];}
static void sr_set(sprite_status *o){
    const char *rev;const short *pos;
    switch(o->userflag.b.h){
    case 0:rev=sr_revtbl0;pos=sr_positbl0;break;
    case 1:rev=sr_revtbl1;pos=sr_positbl1;break;
    default:rev=sr_revtbl2;pos=sr_positbl2;break;
    }
    o->sproffset=1312;
    sprite_status *m=sr_link(o,0);
    short c=m->patcnt;
    if(!(c&1))o->sproffset=1266;
    o->actflg&=252;o->actflg|=rev[c];
    o->xposi.w.h=m->xposi.w.h+pos[c*2];o->yposi.w.h=m->yposi.w.h+pos[c*2+1];
}
static unsigned sr_coli0(sprite_status *o,sprite_status *p,short xo,short yo){
    if(p->r_no0==4){p->r_no0-=2;scd_word_set(p,26,120);}
    if(p->mstno.b.h==43 || p->r_no0>=6)return 0;
    short s=(short)(char)p->sprhs+xo,d=o->xposi.w.h-p->xposi.w.h;
    if((d+=s)<0 || d>=s*2)return 0;
    s=(short)(char)p->sprvsize+yo;d=o->yposi.w.h-p->yposi.w.h;
    if((d+=s)<0 || d>=s*2)return 0;
    return 1;
}
static short sr_pposiset(sprite_status *o,sprite_status *m,sprite_status *p,const char *tbl){
    short c=m->patcnt,pw=(short)(tbl[c]*2);
    p->xposi.w.h=o->xposi.w.h+sr_ppositbl[pw];p->yposi.w.h=o->yposi.w.h+sr_ppositbl[pw+1];
    return c;
}
static void sr_plspdset(sprite_status *o,sprite_status *p,short c){
    if(!(c&1)){
        int_union s,k;s.l=k.l=0;
        sinset(224,&s.w.l,&k.w.l);
        s.l<<=12;k.l<<=12;s.l=(int)((unsigned int)s.l>>8);k.l=(int)((unsigned int)k.l>>8);
        p->yspeed.w=s.w.l;p->xspeed.w=k.w.l;
        if(o->actflg&2)p->yspeed.w=-p->yspeed.w;
        p->cddat&=254;
        if(o->actflg&1){p->cddat|=1;p->xspeed.w=-p->xspeed.w;}
    }else if(!(c&2)){
        p->yspeed.w=0;p->xspeed.w=4096;if(o->actflg&1)p->xspeed.w=-p->xspeed.w;
    }else{
        p->xspeed.w=0;p->yspeed.w=-4096;if(o->actflg&2)p->yspeed.w=-p->yspeed.w;
    }
    p->cddat|=2;p->cddat&=247;
}
static void sr_playset(sprite_status *o,sprite_status *p){
    p->actfree[18]=0;p->actfree[2]|=1;p->cddat|=4;p->sprvsize=14;p->sprhs=7;p->mstno.b.h=2;
    sr_prio_sav=(unsigned char)((p->sproffset&32768)>>8);p->sproffset&=32767;
    tp_lset(o,4,(int)ss_index(p));o->actfree[8]=60;o->r_no0+=2;
    short c=sr_pposiset(o,sr_link(o,0),p,sr_ppositbl0);
    sr_plspdset(o,p,c);
}
static void sr_move4(sprite_status *o);
static void sr_move5(sprite_status *o);
static void sr_gspdset(sprite_status *m,sprite_status *g){
    const short *t=sr_gspdtbl0;
    unsigned char r=g->r_no1;
    if((unsigned char)(r-10))t=sr_gspdtbl1;
    unsigned char c=(unsigned char)(m->patcnt*2);
    g->xspeed.w=t[c];g->yspeed.w=t[c+1];g->actfree[8]=26;
}
static void sr_playset_g(sprite_status *o,sprite_status *mst,sprite_status *p,const unsigned char *ptbl){
    p->actfree[18]=0;p->actfree[2]|=1;p->cddat|=4;p->sprvsize=14;p->sprhs=7;p->mstno.b.h=2;
    sprite_status *m=sr_link(sr_link(o,0),0);
    m->r_no0+=2;m->userflag.b.l=1;tp_lset(m,4,(int)ss_index(p));
    sr_pposiset(m,mst,p,(const char*)ptbl);
    m=sr_link(o,0);
    sprite_status *g=o->r_no0==10?sr_link(m,16):sr_link(m,12);
    g->r_no1=g->r_no0;
    sprite_status *sv=mst;
    mst=sr_link(sr_link(o,0),0);
    if(g->r_no0==10){mst->userflag.b.h=2;sr_move4(g);}
    else{mst->userflag.b.h=1;sr_move5(g);}
    g->r_no0=14;g->userflag.b.l=1;
    sr_gspdset(sv,g);
}
static void sr_g_move0(sprite_status *o,const unsigned char *pat,const unsigned char *rev,const unsigned char *gpos,const unsigned char *ppos){
    sprite_status *m=sr_link(o,0);
    unsigned char c=m->patcnt;
    o->patno=pat[c];o->actflg&=252;o->actflg|=rev[c];
    c=(unsigned char)(gpos[c]*2);
    o->xposi.w.h=m->xposi.w.h+sr_gpositbl[c];o->yposi.w.h=m->yposi.w.h+sr_gpositbl[c+1];
    if(o->userflag.b.h){
        sprite_status *m2=sr_link(sr_link(o,0),0);
        if(m2->userflag.b.l){
            if(m2->userflag.b.l==2 && !o->userflag.b.l)sr_pposiset(m2,m,sr_link(m2,4),(const char*)ppos);
        }else if(!editmode.b.h){
            if(sr_coli0(o,&actwk[0],24,24))sr_playset_g(o,m,&actwk[0],ppos);
            else o->userflag.b.l=0;
        }
    }
}
static void sr_move4(sprite_status *o){
    const unsigned char *rev,*pos;
    if(!o->userflag.b.h){rev=sr_grevtbl0_0;pos=sr_gpositbl0_0;}
    else{rev=sr_grevtbl1_0;pos=!o->userflag.b.l?sr_gpositbl1_0:sr_gpositbl2_0;}
    sr_g_move0(o,sr_gpattbl,rev,pos,sr_ppositblg_0);
}
static void sr_move5(sprite_status *o){
    const unsigned char *rev,*pos;
    if(!o->userflag.b.h){rev=sr_grevtbl0_1;pos=sr_gpositbl0_1;}
    else{rev=sr_grevtbl1_1;pos=!o->userflag.b.l?sr_gpositbl1_1:sr_gpositbl2_1;}
    sr_g_move0(o,sr_gpattbl,rev,pos,sr_ppositblg_1);
}
/* actwkchk2 without a claim: the first free pool slot after o's. */
static sprite_status *sr_free_after(sprite_status *o){
    for(unsigned i=tp_slot(o)+1;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type)return &actwk[i+1];
    return 0;
}
static void sr_init(sprite_status *o){
    o->r_no0+=2;ss_ws(o,28,o->xposi.w.h);o->actflg|=4;o->sproffset=768;o->sprhs=8;o->sprvsize=8;o->patno=1;
    if(o->userflag.b.h>=2){o->userflag.b.l=o->patcnt=o->userflag.b.h-1;o->userflag.b.h=0;}
    sprite_status *n=o;
    for(int i=0;i<3;i++){
        sprite_status *t=sr_free_after(n);
        if(!t){tp_frameout(o);return;}
        n=t;
    }
    unsigned char r=4;
    for(int i=2;i>=0;i--){
        /* The first child synchronizes dead/borrowed slots. Between these
           allocations only our preceding child becomes live, so later children
           keep that mapping without another full pool synchronization. Always
           search from the parent: the first sync may release a lower slot. */
        if(i==2){if(tp_actwkchk2(o,&n)){tp_frameout(o);return;}}
        else{
            if(tp_claim(tp_slot(o)+1,&n)){tp_frameout(o);return;}
            scd_boss_slot_after_next((unsigned)(n-actwk),(unsigned)(o-actwk));
        }
        tp_setactno(n,SCD_OBJ_R7_SPRING_R);
        n->actflg|=4;n->xposi.w.h=o->xposi.w.h;ss_ws(n,28,o->xposi.w.h);n->yposi.w.h=o->yposi.w.h;
        if(i==2){n->sproffset=1312;n->sprpri=5;tp_lset(o,0,(int)ss_index(n));}
        else{
            n->sproffset=768;n->sprhs=32;n->sprvsize=32;
            tp_lset(o,i==1?12:16,(int)ss_index(n));
        }
        n->userflag.b.h=o->userflag.b.h;tp_lset(n,0,(int)ss_index(o));n->r_no0=r;
        if(i==2)r+=4;
        r+=2;
    }
    if(!o->userflag.b.l){
        sprite_status *m=sr_link(o,0);
        if(m->r_no0<6 || m->userflag.b.l==2)tp_patchg(o,sr_rchg);
    }
}
static void sr_step(sprite_status *o){
    switch(o->r_no0/2){
    case 0:sr_init(o);break;
    case 1:
        if(!o->userflag.b.l){
            sprite_status *m=sr_link(o,0);
            if(m->r_no0<6 || m->userflag.b.l==2)tp_patchg(o,sr_rchg);
        }
        break;
    case 2:
        if(!o->userflag.b.h){sr_set(o);if(!editmode.b.h && sr_coli0(o,&actwk[0],32,32))sr_playset(o,&actwk[0]);}
        break;
    case 3:{
        sprite_status *p=sr_link(o,4);
        if(o->userflag.b.h){
            if(o->userflag.b.l==4){tp_patchg(o,sr_springchg);sr_set(o);}
            else if(o->userflag.b.l!=2 || !(swdata.b.l&112))sr_set(o);
            else{
                o->userflag.b.l=4;
                sr_plspdset(o,p,sr_link(o,0)->patcnt);
                actwk[0].actfree[2]&=254;soundset(206);tp_patchg(o,sr_springchg);sr_set(o);
            }
        }else{
            if(!o->actfree[8]){tp_patchg(o,sr_springchg);sr_set(o);}
            else if(--o->actfree[8])sr_set(o);
            else{actwk[0].actfree[2]&=254;soundset(206);tp_patchg(o,sr_springchg);sr_set(o);}
        }
        break;
    }
    case 4:
        o->r_no0-=4;o->patcnt=0;o->patno=0;o->userflag.b.l=0;
        if(o->userflag.b.h){
            sprite_status *m=sr_link(o,0);
            sr_link(m,12)->userflag.b.l=0;sr_link(m,16)->userflag.b.l=0;o->userflag.b.l=0;
        }
        break;
    case 5:sr_move4(o);break;
    case 6:sr_move5(o);break;
    default:
        if(!--o->actfree[8]){
            sprite_status *m=sr_link(sr_link(o,0),0);
            m->userflag.b.l=2;o->r_no0=o->r_no1;soundset(192);
            actwk[0].sproffset|=sr_prio_sav<<8;sr_prio_sav=0;
        }
        o->xposi.w.h+=o->xspeed.w;o->yposi.w.h+=o->yspeed.w;
        break;
    }
}
static void spring_r_act(sprite_status *o){
    if(o->r_no0>=4 && o->actfree[20]){tp_frameout(o);return;}
    if(!o->r_no0 || actwk[0].r_no0<6){
        sr_step(o);
        if(!o->actno)return;
        if(o->r_no0!=4 || !o->userflag.b.h)tp_draw(o);
    }else tp_draw(o);
    if(o->r_no0!=2)return;
    int m=tp_l(o,0),g0=tp_l(o,12),g1=tp_l(o,16);
    if(tp_frameout_s00(o,ss_w(o,28))){actwk[m].actfree[20]=1;actwk[g0].actfree[20]=1;actwk[g1].actfree[20]=1;}
}

/* ---- gun7 and hibana --------------------------------------------------- */
static const unsigned char hibana7_chg0[]={3,0,1,0,1,252};
static const unsigned char *const hibana7_chg[]={hibana7_chg0};
static void gun7_set(sprite_status *o){
    sprite_status *n=0,*g=0;
    actwk[0].actfree[2]=0;
    if(!tp_actwkchk(&n)){
        tp_setactno(n,SCD_OBJ_R7_GUN7);n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;n->userflag.b.h=1;
        g=n;
        if(!tp_actwkchk(&n)){tp_setactno(n,SCD_OBJ_R7_HIBANA7);n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h-6;}
        else n=0;
    }else n=0;
    soundset(206);
    o->r_no0+=2;ss_ws(o,24,o->xposi.w.h);o->actfree[0]=6;
    if(o->xposi.w.h<actwk[0].xposi.w.h){
        if(g)g->xspeed.w=512;
        if(n){n->cddat|=1;n->xposi.w.h+=16;}
        actwk[0].xspeed.w=-4096;actwk[0].mspeed.w=actwk[0].xspeed.w;actwk[0].cddat|=1;o->xspeed.w=2048;
    }else{
        if(g)g->xspeed.w=-512;
        if(n){n->cddat&=254;n->xposi.w.h-=16;}
        actwk[0].xspeed.w=4096;actwk[0].mspeed.w=actwk[0].xspeed.w;actwk[0].cddat&=254;o->xspeed.w=-2048;
    }
}
static void gun7_move0(sprite_status *o){
    if(!editmode.b.h && !(actwk[0].cddat&2) && sr_coli0(o,&actwk[0],32,16))gun7_set(o);
}
static void gun7_move2(sprite_status *o){
    o->yspeed.w+=64;speedset2(o);
    if((short)scd_act_view_y()+232<o->yposi.w.h)tp_frameout(o);
}
static void gun7_act(sprite_status *o){
    switch(o->r_no0/2){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sproffset=768;o->sprhsize=32;o->sprvsize=12;o->patno=2;
        if(!o->userflag.b.h)gun7_move0(o);
        else{o->patno=0;o->yspeed.w=-2048;o->r_no0=6;gun7_move2(o);}
        break;
    case 1:gun7_move0(o);break;
    case 2:
        if(o->actfree[0]){
            speedset2(o);
            if(--o->actfree[0])break;
            o->xspeed.w=-o->xspeed.w;
        }else{
            speedset2(o);
            if(o->xposi.w.h==ss_w(o,24))o->r_no0-=2;
        }
        break;
    default:gun7_move2(o);break;
    }
    /* frameout: gun7's actionsub/frameout_s then see a cleared actor. */
    if(!o->actno)return;
    tp_draw(o);
    tp_frameout_s(o);
}
static void hibana7_act(sprite_status *o){
    switch(o->r_no0/2){
    case 0:o->r_no0+=2;o->actflg|=4;o->sproffset=33592;break;
    case 1:tp_patchg(o,hibana7_chg);break;
    default:tp_frameout(o);return;
    }
    tp_draw(o);
}
