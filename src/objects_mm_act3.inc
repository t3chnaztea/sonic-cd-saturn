/* Metallic Madness (R8) shrink machine and Act 3 hazards: R8/BEAM.C (the
   beam that shrinks or restores the player: chibi_flag), PLAYSP8.C
   chibi_coli (the solid block a small player fits past), JETTOGE8.C (the
   sliding spike jet) and KONBEA83.C (Act 3's folding conveyor block;
   Acts 1-2 use KONBEA.C, the global SCD_OBJ_KONBEA).
   Line-for-line ports on the PC scratch layout (objects_mm_common.inc).
   Quirks kept:
   - BEAM keeps its splash child as a PC pointer in ((sprite_status**)o)[12]
     (actfree bytes 2-5); the port keeps the child's actor number in
     pool[].phase and leaves those bytes zero.
   - A beam that finds no actor for its splash sets actfree[21] and never
     tells the splash to go (there is none).
   - chibi_flag toggles on every beam contact; the player's small form
     itself (sprvsize 10 / sprhs 5 and PLAYER6.C's small animations) is
     player code: native hook for player.c.
   - JETTOGE's spikes hurt only on the lower layer (prio_flag clear).
   - KONBEA83 indexes its script table by the secondary byte: every Act 3
     placement uses 0 (no children); a nonzero byte would make the block
     look for a parent at actwk[word 23] and frame out. */
extern unsigned char chibi_flag;

/* ---- BEAM.C: the shrink beam ------------------------------------------- */
static const uint8_t beam_c0[]={2,5,13,255},beam_c1[]={2,14,6,255},beam_c2[]={2,7,15,255},beam_c3[]={2,16,8,255},
    beam_c4[]={2,9,17,255},beam_c5[]={2,18,10,255},beam_c6[]={2,11,19,255},beam_c7[]={2,20,12,255},beam_c8[]={2,3,4,255};
static const uint8_t *const beamchg[9]={beam_c0,beam_c1,beam_c2,beam_c3,beam_c4,beam_c5,beam_c6,beam_c7,beam_c8};
static void beam_coli(sprite_status *o){
    static const int8_t tbl[8]={-12,-28,-44,-60,-76,-92,-108,-124};
    sprite_status *p=&actwk[0];
    if(editmode.b.h)return;
    short cs=(int8_t)p->sprhs+4,cp=o->xposi.w.h-p->xposi.w.h+cs;
    if(cp<0 || cp>=cs*2)return;
    /* BEAM.C reads sprvsize here, but retail (R82A $20B644) does move.w $16(a6),d1;
       ext.w d1: the low byte, $17, the X radius (port sprhs: 9, rolling 7, small 5).
       The X check above reads $17 as a byte (move.b $17(a6),d1), sprhs too. */
    cs=(int8_t)p->sprhs;cp=p->yposi.w.h+cs;
    short ct=tbl[o->mstno.b.h&7]+o->yposi.w.h;
    if(ct>=cp)return;
    cp=p->yposi.w.h-cs;ct=o->yposi.w.h+4;
    if(cp>=ct)return;
    p->r_no0=4;p->cddat|=2;p->yspeed.w=-1024;p->xspeed.w=-512;
    if(p->xposi.w.h>=o->xposi.w.h)p->xspeed.w=-p->xspeed.w;
    p->mspeed.w=0;p->mstno.b.h=56;p->sprvsize=10;p->sprhs=5;
    chibi_flag^=1;
    if(!chibi_flag){p->sprvsize=19;p->sprhs=9;}
}
static void beam_coli0(sprite_status *o){
    if(actwk[0].mstno.b.h==43)return;
    if(!o->userflag.b.h){if(!chibi_flag)beam_coli(o);}
    else if(chibi_flag)beam_coli(o);
}
static void beam_act(sprite_status *o){
    unsigned i=tp_slot(o);
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->patno=o->userflag.b.h?2:1;o->actfree[0]=1;
        /* fall through: beam_init calls beam_mast */
    case 2:{
        if(--o->actfree[0])break;
        sprite_status *n;
        if(tp_actwkchk2(o,&n) && tp_actwkchk(&n))break;
        n->r_no0=4;n->actflg|=4;n->sprpri=2;n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h&65520;
        n->userflag.b.h=o->userflag.b.h;n->sprvsize=4;tp_setactno(n,SCD_OBJ_R8_BEAM);
        o->actfree[0]=30;
        if(o->actflg&128)soundset(o->userflag.b.h?188:197);
        break;
    }
    case 4:{
        o->yposi.w.h+=4;
        if(!(o->yposi.w.h&15) && ++o->mstno.b.h>=7)o->mstno.b.h=7;
        tp_patchg(o,beamchg);
        if(emycol_d(o)<0){
            o->r_no0+=2;
            sprite_status *n;
            if(tp_actwkchk2(o,&n))o->actfree[21]=255;
            else{
                n->actflg|=4;n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;n->r_no0=8;n->mstno.b.h=8;
                tp_setactno(n,SCD_OBJ_R8_BEAM);pool[i].phase=mm_index(n);
            }
        }
        beam_coli0(o);
        break;
    }
    case 6:{
        short cy=o->yposi.w.h+4;
        if(!(cy&15)){
            cy-=16;
            if((int8_t)o->mstno.b.h-1<0){
                if(!o->actfree[21])actwk[pool[i].phase&127].actfree[0]=1;
                tp_frameout(o);return;
            }
            --o->mstno.b.h;
        }
        o->yposi.w.h=cy;tp_patchg(o,beamchg);beam_coli0(o);
        break;
    }
    case 8:
        if(o->actfree[0]){tp_frameout(o);return;}
        tp_patchg(o,beamchg);
        break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- PLAYSP8.C chibi_coli: solid block --------------------------------- */
static void chibi_coli_act(sprite_status *o){
    if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprhs=o->sprhsize=o->sprvsize=16;}
    tp_hitchk(o,&actwk[0]);
    tp_draw(o);tp_frameout_s(o);
}

/* ---- JETTOGE8.C: the sliding spike jet --------------------------------- */
static void jettoge_act(sprite_status *o){
    static const uint8_t p00[]={1,0,1,255};
    static const uint8_t *const pchg[]={p00};
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sproffset=33856;mm_ws(o,26,o->xposi.w.h);o->actfree[9]=177;mm_ls(o,12,20480);
        o->sprvsize=76;o->sprpri=1;o->sprhsize=16;
    }
    o->xposi.l+=mm_l(o,12);
    o->colino=prio_flag?0:o->actfree[9];
    short t=mm_w(o,23);mm_ws(o,23,t-1);
    if(t<=0){mm_ws(o,23,409);mm_ls(o,12,(int)(0u-(uint32_t)mm_l(o,12)));o->actflg^=1;o->cddat^=1;}
    tp_patchg(o,pchg);tp_draw(o);tp_frameout_s00(o,mm_w(o,26));
}

/* ---- KONBEA83.C: Act 3's folding block --------------------------------- */
static void konbea83_init_sub(const sprite_status *m,sprite_status *a){
    a->r_no0=2;a->actflg|=4;a->sprpri=3;a->sprhs=a->sprhsize=16;a->sprvsize=5;a->sproffset=844;
    mm_ws(a,25,m->xposi.w.h);mm_ws(a,26,m->yposi.w.h);
}
static void konbea83_act(sprite_status *o){
    static const short tbl00[2]={60,0},tbl01[5]={60,1,60,32,0};
    static const uint8_t pchg_00[]={1,1,2,3,4,5,6,1,2,3,4,5,0,255};
    static const uint8_t *const pchg[]={pchg_00};
    sprite_status *p=&actwk[0];
    if(o->userflag.b.l){
        const sprite_status *m=&actwk[(uint16_t)mm_w(o,23)&127];
        if(m->actno!=SCD_OBJ_R8_KONBEA83 || mm_w(o,25)!=mm_w(m,25) || mm_w(o,26)!=mm_w(m,26)){tp_frameout(o);return;}
    }
    switch(o->r_no0){
    case 0:{
        const short *t=o->userflag.b.l==1?tbl01:tbl00;
        mm_ws(o,24,*t++);konbea83_init_sub(o,o);
        for(short n=*t++-1;n>=0;--n){
            sprite_status *a;
            if(tp_actwkchk(&a)){tp_frameout(o);return;}
            mm_ws(a,23,(uint16_t)mm_index(o));a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=-1;tp_setactno(a,o->actno);
            mm_ws(a,24,*t++);a->xposi.w.h=o->xposi.w.h+*t++;a->yposi.w.h=o->yposi.w.h+*t++;
            konbea83_init_sub(o,a);
        }
        break;
    }
    case 2:
        o->sprvsize=5;mm_ws(o,24,120);o->r_no0+=2;
        /* fall through: a_stop calls a_stop1 */
    case 4:
        o->actfree[20]=tp_ridechk(o,p)?255:0;
        if(!mm_ws(o,24,mm_w(o,24)-1)){
            o->sprvsize=16;o->mstno.w=255;o->r_no0+=2;
            if(o->actfree[20])tp_ride_on_clr(o,p);
        }
        break;
    case 6:
        tp_patchg(o,pchg);
        if(!o->patno)o->r_no0=2;
        break;
    }
    tp_draw(o);
    if(!(o->userflag.b.l&128))tp_frameout_s00(o,mm_w(o,25));
}
