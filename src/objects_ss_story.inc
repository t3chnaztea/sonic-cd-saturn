/* Stardust Speedway (R7) story actors: R7/MOVIE7.C (Metal Sonic projector),
   FRIEND7.C (Flicky / Ricky) and ET7.C (robot generator). Each is R7's own
   definition, vetted against the compiled R7 source in
   tools/test-ss-actors.sh; the R4/R5 routines of the same names differ:
   - MOVIE7 counts its explosion clock in the high byte of word 23
     (+= 256) and m_die marks the screens with actfree[21]=255. m_init does
     not run m_wait in its first update. divdevset(4/5) is an empty stub in
     the PC source (SCR71A.C). On the 68k it is LoadPLC: .deps/scddisasm has
     no R7 level, but the Wacky Workbench projector (Level/Wacky Workbench/
     Objects/Projector/Main.asm) calls LoadPLC 5 in init and LoadPLC 4 when
     it starts exploding and when it despawns (CheckObjDespawn). These only
     queue VRAM art; no actor state changes. Saturn art is resident, so the
     port omits them. If the renderer shares VRAM between the projector and
     another art set, it must swap art at those three points.
     The 68k Robot Generator (_Objects/Robot Generator) calls no LoadPLC.
   - FRIEND7's Ricky hops twice before it turns: p_move's landing only adds
     2 to r_no0, so r_no0 4 runs p_move again and r_no0 6 (p_rev) turns it.
     Its landing test is emycol_d <= 0 (FRIEND5: < 0). Flicky's pchg00 waits
     3 frames and does not set sproffset bit 15.
   - ET7 is ET4.C's script with R7's pattern offset 942 and RIDECHK solids.
   The PC keeps a char* event cursor in ((char**)o)[12] (actfree bytes 2-5
   on the 32-bit PC); the port keeps the table offset in pool[].phase and
   leaves those bytes zero, as the fixture does (ss_cur12). */

/* MOVIE7.C / ET7.C explosion: actwkchk + actno 24, r_no1 1, soundset(158)
   only when an actor is free. */
static void ss_blast(int x,int y){tt_blast(x,y);}

/* ---- MOVIE7.C: the Metal Sonic projector and its screens ---------------- */
static const uint8_t movie7_pchg00[]={0,2,1,3,1,255};
static const uint8_t movie7_pchg01[]={0,4,4,1,4,4,1,4,4,1,4,4,1,4,4,1,1,4,4,1,1,4,4,1,1,4,4,1,1,5,
    5,1,5,5,1,5,5,1,5,5,1,5,5,1,1,5,5,1,1,5,5,1,1,5,5,1,1,255};
static const uint8_t *const movie7_pchg[]={movie7_pchg00,movie7_pchg01};
/* actwk[((short*)o)[33]]: the projector a screen or animal belongs to. */
static int ss_movie_gone(const sprite_status *o){
    const sprite_status *m=&actwk[(uint16_t)ss_w(o,33)&127];
    return m->actno!=SCD_OBJ_R7_MOVIE7 || m->actfree[21];
}
static void movie7_act(sprite_status *o){
    static const int8_t tbl0[37]={1,0,0,5,-18,-10,10,-10,10,15,0,-18,20,-10,18,22,8,23,25,13,-10,28,-3,-25,
        30,10,20,32,-10,2,35,13,-10,40,-10,10,-1};
    sprite_status *p=&actwk[0];unsigned i=tp_slot(o);
    if(o->userflag.b.h){
        /* sub: a screen (userflag -1) or the projector's lens (1). */
        if(ss_movie_gone(o)){tp_frameout(o);return;}
        if(!o->r_no0){
            o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sproffset=1199;
            if((int8_t)o->userflag.b.h<0){o->sprhs=o->sprhsize=8;o->sprvsize=4;o->mstno.b.h=0;}
            else{o->sprhs=o->sprhsize=20;o->sprvsize=24;o->mstno.b.h=1;}
        }
        tp_patchg(o,movie7_pchg);tp_draw(o);return;
    }
    switch(o->r_no0){
    case 0:{
        if(projector_destroyed){tp_frameout(o);return;}
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=o->sprvsize=12;o->colino=251;o->sproffset=1199;pool[i].phase=0;
        static const struct{int8_t dx,dy,sub;uint8_t friend;}kids[4]={{-21,-7,-1,0},{-88,-4,1,0},{-88,-24,-128,1},{-98,0,-127,1}};
        for(unsigned k=0;k<4;k++){
            sprite_status *c;
            if(tp_actwkchk(&c)){tp_frameout(o);return;}
            c->xposi.w.h=o->xposi.w.h+kids[k].dx;c->yposi.w.h=o->yposi.w.h+kids[k].dy;c->userflag.b.h=kids[k].sub;
            ss_ws(c,33,(uint8_t)ss_index(o));tp_setactno(c,kids[k].friend?SCD_OBJ_R7_FRIEND7:SCD_OBJ_R7_MOVIE7);
        }
        break;
    }
    case 2:
        if(o->colicnt){o->colino=0;o->colicnt=0;o->r_no0+=2;}
        tp_hitchk(o,p);break;
    case 4:
        o->r_no0+=2;o->patno=1;o->actfree[21]=255;
        if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        break;
    case 6:{
        unsigned c=pool[i].phase;int t=tbl0[c];
        if(t>=0){
            if(++o->actfree[1]==(uint8_t)t){pool[i].phase=c+3;ss_blast(o->xposi.w.h+tbl0[c+1],o->yposi.w.h+tbl0[c+2]);}
        }else{o->r_no0+=2;ss_ws(o,23,60);}
        break;
    }
    case 8:
        if(!ss_ws(o,23,ss_w(o,23)-1)){projector_destroyed=1;projector_flag=255;tp_frameout(o);return;}
        break;
    }
    tp_draw(o);
    if(o->r_no0<=2)tp_frameout_s(o);
}

/* ---- FRIEND7.C: Flicky (orbiting) and Ricky (hopping) -------------------- */
static void friend7_sproffset(sprite_status *o){
    static const unsigned short tbl[11]={918,918,918,0,918,918,918,0,0,0,918};
    unsigned n=(objects_act*4+qq_time_flag())&255;
    o->sproffset=n<11?tbl[n]:0;
}
static void friend7_rev(sprite_status *o){o->actflg^=1;o->cddat^=1;}
static void friend7_roll(sprite_status *o,int cs_shift,int sn_shift){
    short sn,cs;sinset(o->actfree[4],&sn,&cs);
    o->xposi.w.h=(short)((cs>>cs_shift)+ss_w(o,23));o->yposi.w.h=(short)((sn>>sn_shift)+ss_w(o,24));
}
static void friend7_act(sprite_status *o){
    static const uint8_t p0_00[]={3,0,1,255},p0_01[]={0,0,0,2,0,0,2,1,1,2,2,1,1,2,2,0,0,2,0,0,2,1,1,2,2,1,1,2,2,255};
    static const uint8_t p1_00[]={0,3,3,2,3,3,2,3,3,2,3,3,2,3,3,2,2,3,3,2,2,3,3,2,2,3,3,2,2,4,
        4,2,4,4,2,4,4,2,4,4,2,4,4,2,2,4,4,2,2,4,4,2,2,4,4,2,2,255};
    static const uint8_t *const pchg0[]={p0_00,p0_01},*const pchg1[]={p1_00};
    if(qq_friend_suicide(o))return;
    if(!(o->userflag.b.h&127)){
        /* Flicky */
        switch(o->r_no0){
        case 0:
            o->r_no0+=2;o->actflg=4;o->sprvsize=8;o->sprhs=8;o->sprpri=4;o->sprhsize=8;
            ss_ws(o,23,o->xposi.w.h);ss_ws(o,24,o->yposi.w.h);friend7_rev(o);friend7_sproffset(o);
            if((int8_t)o->userflag.b.h>=0){o->actfree[4]=1;o->actfree[5]=1;}
            else{o->r_no0+=2;o->mstno.b.h=1;o->sprpri=3;}
            return;
        case 2:{
            friend7_roll(o,1,1);
            unsigned char t=(unsigned char)(o->actfree[4]+o->actfree[5]);
            if((unsigned char)(t-1)>=127){t=o->actfree[4];o->actfree[5]=(unsigned char)-o->actfree[5];friend7_rev(o);}
            o->actfree[4]=t;
            tp_patchg(o,pchg0);tp_draw(o);tp_frameout_s00(o,ss_w(o,23));return;
        }
        case 4:
            if(ss_movie_gone(o)){tp_frameout(o);return;}
            friend7_roll(o,3,4);o->actfree[4]+=4;
            if(!(o->actfree[4]&127))friend7_rev(o);
            else{tp_patchg(o,pchg0);tp_draw(o);}
            return;
        }
        return;
    }
    /* Ricky */
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg=4;o->sprvsize=12;o->sprhs=8;o->sprpri=4;o->sprhsize=8;friend7_sproffset(o);
        if((int8_t)o->userflag.b.h>=0){ss_ls(o,12,65536);ss_ls(o,13,-0x40000);}
        else{o->r_no0=8;friend7_rev(o);}
        return;
    case 2:case 4:{
        o->xposi.l+=ss_l(o,12);o->yposi.l+=ss_l(o,13);
        o->patno=ss_ls(o,13,(int)((uint32_t)ss_l(o,13)+8192))<0?0:1;
        short c=emycol_d(o);
        if(c<=0){o->r_no0+=2;o->yposi.w.h+=c;ss_ls(o,13,-0x40000);}
        tp_draw(o);tp_frameout_s(o);return;
    }
    case 6:
        o->r_no0=2;ss_ls(o,12,(int)(0u-(uint32_t)ss_l(o,12)));friend7_rev(o);
        tp_draw(o);tp_frameout_s(o);return;
    case 8:
        if(ss_movie_gone(o)){tp_frameout(o);return;}
        tp_patchg(o,pchg1);tp_draw(o);return;
    }
}

/* ---- ET7.C: robot generator ---------------------------------------------- */
static void et7_act(sprite_status *o){
    static const uint8_t p_a[]={3,3,4,5,6,255};
    static const uint8_t *const pchg[]={p_a};
    static const int8_t tbl0[64]={1,0,0,2,-40,-20,3,28,10,4,18,-18,5,-18,-10,6,8,-8,8,-18,14,10,-10,10,
        12,30,-10,15,0,-18,18,20,-10,20,-10,18,22,8,23,25,13,-10,26,23,-22,28,-3,-25,30,10,20,32,-10,2,34,30,-8,35,13,-10,40,-10,10,-1};
    sprite_status *p=&actwk[0];unsigned i=tp_slot(o),tf=qq_time_flag();
    switch(o->r_no0){
    case 0:{
        static const uint16_t sproffsets[3][4]={{942,942,0,0},{942,942,0,0},{0,0,0,0}};
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=34;o->sprvsize=32;
        o->sproffset=sproffsets[objects_act<3?objects_act:2][tf];pool[i].phase=0;
        ss_ws(o,26,o->yposi.w.h);ss_ws(o,23,4);ss_ws(o,27,1);
        o->patno=(good_future?0:2)+(tf==0);
        if(!good_future && tf==0){o->colino=250;o->yposi.w.h-=16;}
    }   /* fall through: m_init calls m_wait */
    case 2:
        if(good_future || tf!=0)break;
        /* a_hover */
        ss_ws(o,23,ss_w(o,23)+1);
        if(!(ss_w(o,23)&7))o->yposi.w.h+=ss_w(o,27);
        if(!(ss_w(o,23)&31))ss_ws(o,27,-ss_w(o,27));
        if(o->colicnt){
            o->colino=o->colicnt=0;ss_ws(o,23,0);o->patno=7;o->r_no0+=2;
            good_future=pending_generator=1;tp_scoreup(150);
            if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        }else{tp_hitchk(o,p);tp_patchg(o,pchg);}
        break;
    case 4:{
        unsigned c=pool[i].phase;int t=tbl0[c];
        if(t<0){o->r_no0+=2;o->actfree[0]=8;break;}
        if(++o->actfree[0]==(uint8_t)t){pool[i].phase=c+3;ss_blast(o->xposi.w.h+tbl0[c+1],o->yposi.w.h+tbl0[c+2]);}
        break;
    }
    case 6:
        if(!--o->actfree[0]){o->r_no0-=6;o->yposi.w.h=ss_w(o,26);soundset(217);}
        break;
    }
    tp_draw(o);
    if(o->r_no0<=2)tp_frameout_s(o);
}
